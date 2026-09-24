"""LLM classification helper.

Step 2 of the hybrid classifier. Used ONLY when the deterministic rule engine
cannot classify with sufficient confidence. The model returns strict JSON
referencing category codes from the application catalog - its output is validated
against the catalog before it is allowed to influence financial records.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from app.ai.client import get_llm, LLMClient
from app.classification.catalog import BY_CODE, CATALOG
from app.core.config import get_settings
from app.core.errors import LLMUnavailable

_settings = get_settings()

_CATEGORY_CODES = ", ".join(c.code for c in CATALOG)

_SYSTEM_PROMPT = (
    "You are a classification assistant for a restaurant company. "
    "Classify a single bank transaction into exactly one category from the "
    "provided list. Consider whether the transaction belongs on the P&L "
    "(revenue, COGS, payroll, operating expense) or requires a non-P&L "
    "accounting treatment (capital expenditure, sales tax liability, deferred "
    "revenue/gift cards, loan principal, owner distribution).\n"
    f"Valid category codes: {_CATEGORY_CODES}.\n"
    'Reply with strict JSON in the exact shape: {"category_code": string, '
    '"confidence": number between 0 and 1, "reasoning": string. Optionally also '
    'include "requires_review": boolean (true only when a human should confirm '
    'the classification) and "review_reasons": [a concise list of human-readable '
    'reasons why]. Do not output anything else.'
)


@dataclass(frozen=True)
class LLMClassification:
    category_code: str
    confidence: float
    reasoning: str
    requires_review: bool = False
    review_reasons: list[str] = field(default_factory=list)


def _extract_json(text: str) -> dict | None:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except (json.JSONDecodeError, TypeError):
        return None


def classify_with_llm(description: str, counterparty: str = "", amount_cents: int = 0) -> LLMClassification | None:
    """Ask the LLM for a structured classification.

    Returns None on any failure so the caller can fall back to deterministic
    behaviour (the transaction is then simply flagged for review).
    """
    try:
        llm: LLMClient = get_llm()
    except LLMUnavailable:
        return None

    user = (
        f"Transaction description: {description}\n"
        f"Counterparty: {counterparty or 'N/A'}\n"
        f"Signed amount (dollars): {amount_cents / 100.0:.2f}\n"
        "Output the classification JSON."
    )
    try:
        payload = llm.chat_completion(
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
    except LLMUnavailable:
        return None

    content = payload.get("choices", [{}])[0].get("message", {}).get("content") or ""
    data = _extract_json(content)
    if not data:
        return None

    code = str(data.get("category_code", "")).strip()
    if code not in BY_CODE:
        return None

    try:
        confidence = float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    reasoning = str(data.get("reasoning", "")).strip() or "LLM classification."

    requires_review = bool(data.get("requires_review", False))

    raw_reasons = data.get("review_reasons", [])
    if isinstance(raw_reasons, str):
        raw_reasons = [raw_reasons]
    review_reasons = [str(r).strip() for r in raw_reasons if str(r).strip()]
    review_reasons = review_reasons[:5]

    return LLMClassification(
        category_code=code,
        confidence=confidence,
        reasoning=reasoning,
        requires_review=requires_review,
        review_reasons=review_reasons,
    )