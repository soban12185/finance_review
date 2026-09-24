"""AI Financial Analyst - tool-calling loop.

The analyst answers questions *only* from data returned by the controlled
backend tools. It has no database access of its own. The system prompt enforces
the financial-accuracy safety rules required by the product.

Flow for e.g. "Why did operating profit change between February and March?":
    get_monthly_pnl -> compare_months -> get_variance_drivers -> get_transactions
    -> grounded explanation with transaction-id evidence
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.ai.client import LLMClient, get_llm
from app.ai.tools import TOOL_FUNCTIONS, TOOL_SCHEMAS
from app.core.config import get_settings
from app.core.errors import LLMUnavailable, ValidationError
from app.repositories import transaction_repo as repo

_settings = get_settings()

SAFETY_SYSTEM_PROMPT = """You are the AI Financial Analyst embedded in the FINZ AI-native financial-review platform. You answer questions about a restaurant company's finances using backend tools. The platform is a hybrid AI system: the backend (PostgreSQL + a Python engine) is the sole source of truth, and you are here to retrieve and explain, never to compute or invent.

GROUNDING RULES (non-negotiable):
1. NEVER invent transactions, totals, categories, percentages, variances, transaction ids or any number. Every figure you state must have been returned by a backend tool in this same conversation.
2. NEVER compute authoritative financial totals yourself (no adding or subtracting line items, no multiplying rates by hand). The tool outputs ARE the authoritative numbers; reproduce their exact values without rounding or reformatting.
3. ALWAYS call a tool before quoting a number. If you have not retrieved a figure, do not state it.
4. When you cite a transaction, use its exact transaction id (e.g. "TX1051") exactly as a tool returned it. Never guess an id.
5. PRESERVE exact values from tool output. Never round, average or approximate authoritative figures. Where you offer an interpretation of relative size ("most of the movement"), say explicitly that this is an interpretation.
6. Clearly separate FACTS (tool output, with ids) from INTERPRETATION (your analysis). Use phrases like "the data shows" vs "this suggests".
7. If the tools give insufficient evidence to answer, say so explicitly ("I don't have enough data to answer this") and say what additional data would help - never guess or extrapolate.
8. Do not expose hidden reasoning or chain-of-thought; give concise, direct reasoning alongside the supporting numbers.
9. Read-only analyst: never modify records.
10. State accounting treatment (e.g. gift-card deposits are deferred revenue, loan principal is financing, equipment is capex) only when supported by the tool data.
11. Keep answers tight and professional, written as a financial analyst's note, matching the numbering style of the tool output.

ANSWER FORMAT:
- Start with a concise direct answer.
- Support the answer with the retrieved numbers and transaction ids.
- List the transaction ids that back the claim when useful.
- Be honest when information is missing.

Available months in this dataset: {months}. If the user references a month outside this list, tell them it is not available in the data."""

# Tool pipeline metadata (name -> (stage, human label)). "retrieval" = pulling
# rows from PostgreSQL via SQL; "deterministic" = the tool returned results
# computed by the integer-cent financial engine. Exposed to the UI so every
# answer can show how it was produced (tool selection -> retrieval/calculation
# -> evidence -> explanation), never a black-box LLM->answer.
TOOL_STAGES: dict[str, tuple[str, str]] = {
    "get_monthly_pnl": ("deterministic", "Monthly P&L (deterministic)"),
    "compare_months": ("deterministic", "Month-over-month compare (deterministic)"),
    "get_variance": ("deterministic", "Materiality variance (deterministic)"),
    "get_variance_drivers": ("deterministic", "Variance drivers (deterministic)"),
    "get_category_total": ("deterministic", "Category total (deterministic)"),
    "get_transactions": ("retrieval", "Transaction retrieval"),
    "get_transaction": ("retrieval", "Transaction detail retrieval"),
    "get_review_items": ("retrieval", "Review queue retrieval"),
    "search_transactions": ("retrieval", "Free-text transaction search"),
}

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


@dataclass
class ToolCallRecord:
    id: str
    name: str
    arguments: dict
    result: dict | None = None
    error: str | None = None

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "arguments": self.arguments,
            "result": self.result,
            "error": self.error,
        }


@dataclass
class AnalystResponse:
    answer: str
    model: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    error: str | None = None
    stopped_prematurely: bool = False
    tools_used: list[str] = field(default_factory=list)
    evidence: dict = field(default_factory=dict)
    pipeline: list[str] = field(default_factory=list)


def _collect_evidence(records: list[ToolCallRecord]) -> tuple[list[str], dict, list[str]]:
    """Derive evidence metadata *only* from the tool calls actually executed.

    Months are gathered from the validated arguments and from the returned
    payloads; transaction ids are gathered only from what the tools actually
    returned (never inferred). ``pipeline`` is the ordered set of stages run
    (retrieval / deterministic), so the UI can show that an answer passed
    through tool selection -> data retrieval / calculation -> evidence.
    """
    months: set[str] = set()
    txids: list[str] = []
    txn_count = 0
    tools: list[str] = []
    pipeline: list[str] = []
    for rec in records:
        if rec.error or not isinstance(rec.result, dict):
            continue
        tools.append(rec.name)
        stage = TOOL_STAGES.get(rec.name, ("retrieval", "Retrieval"))[0]
        if stage not in pipeline:
            pipeline.append(stage)
        for key in ("month", "month_a", "month_b"):
            for source in (rec.arguments, rec.result):
                value = source.get(key)
                if isinstance(value, str) and _MONTH_RE.match(value):
                    months.add(value)
        for key in ("transactions", "items"):
            for row in rec.result.get(key) or ():
                if isinstance(row, dict):
                    tid = row.get("transaction_id")
                    if tid:
                        txids.append(str(tid))
                        txn_count += 1
        txn = rec.result.get("transaction")
        if isinstance(txn, dict):
            tid = txn.get("transaction_id")
            if tid:
                txids.append(str(tid))
                txn_count += 1
        for driver in rec.result.get("drivers") or ():
            if not isinstance(driver, dict):
                continue
            for tx in driver.get("transactions") or ():
                if isinstance(tx, dict):
                    tid = tx.get("transaction_id")
                    if tid:
                        txids.append(str(tid))
                        txn_count += 1
    seen: set[str] = set()
    unique_txids = [t for t in txids if not (t in seen or seen.add(t))]
    tools_used = list(dict.fromkeys(tools))
    evidence = {
        "months": sorted(months),
        "transaction_ids": sorted(unique_txids),
        "transactions_returned": txn_count,
    }
    return tools_used, evidence, pipeline


def _available_months(db: Session) -> str:
    months = repo.available_months(db)
    if not months:
        return "no data loaded yet"
    return ", ".join(months)


def run_analyst(
    db: Session,
    question: str,
    *,
    history: list[dict] | None = None,
    max_iterations: int | None = None,
) -> AnalystResponse:
    question = (question or "").strip()
    if len(question) < 3 or len(question) > 2000:
        raise ValidationError("Please ask a question between 3 and 2000 characters.")

    llm: LLMClient = None
    system = SAFETY_SYSTEM_PROMPT.format(months=_available_months(db))

    messages: list[dict] = [{"role": "system", "content": system}]
    for m in (history or []):
        role = m.get("role")
        content = (m.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content[:4000]})
    messages.append({"role": "user", "content": question})

    iterations = max_iterations or _settings.groq_max_tool_iterations
    records: list[ToolCallRecord] = []

    try:
        llm = get_llm()
        for _ in range(iterations):
            payload = llm.chat_completion(
                messages=messages,
                tools=TOOL_SCHEMAS,
                temperature=0.1,
                max_tokens=2048,
            )
            message = payload["choices"][0]["message"]
            tool_calls = message.get("tool_calls")

            if not tool_calls:
                answer = (message.get("content") or "").strip()
                tools_used, evidence, pipeline = _collect_evidence(records)
                return AnalystResponse(
                    answer=answer,
                    model=payload.get("model", _settings.groq_model),
                    tool_calls=records,
                    tools_used=tools_used,
                    evidence=evidence,
                    pipeline=pipeline,
                )

            assistant_msg: dict = {"role": "assistant", "content": message.get("content") or "", "tool_calls": []}
            tool_results: list[tuple[str, str, str]] = []
            for tc in tool_calls:
                fn = tc.get("function", {})
                name = fn.get("name", "")
                raw_args = fn.get("arguments") or "{}"
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args or {})
                except json.JSONDecodeError:
                    args = {}
                if not isinstance(args, dict):
                    args = {}

                call_id = tc.get("id") or f"{name}_{len(records)}"
                assistant_msg["tool_calls"].append({
                    "id": call_id,
                    "type": "function",
                    "function": {"name": name, "arguments": _json_dumps(args)},
                })

                record = ToolCallRecord(id=call_id, name=name, arguments=args)
                try:
                    handler = TOOL_FUNCTIONS.get(name)
                    if handler is None:
                        raise ValueError(f"Unknown tool '{name}'")
                    result = handler(db, **args)
                    record.result = result
                    content = _json_dumps(result)
                except Exception as exc:  # noqa: BLE001 - tool errors are returned to the model for recovery
                    record.error = str(exc)
                    content = json.dumps({"error": str(exc), "tool": name})

                tool_results.append((call_id, name, content))
                records.append(record)

            messages.append(assistant_msg)
            for call_id, name, content in tool_results:
                messages.append({"role": "tool", "tool_call_id": call_id, "name": name, "content": content})
    except LLMUnavailable as exc:
        return AnalystResponse(answer="", model=_settings.groq_model, error=exc.message)

    last = next((m for m in reversed(messages) if m.get("role") == "assistant"), None)
    answer = (last.get("content") or "").strip() if last else "I ran out of steps before producing a final answer."
    tools_used, evidence, pipeline = _collect_evidence(records)
    return AnalystResponse(
        answer=answer,
        model=_settings.groq_model,
        tool_calls=records,
        stopped_prematurely=True,
        tools_used=tools_used,
        evidence=evidence,
        pipeline=pipeline,
    )


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, default=str, separators=(",", ":"))