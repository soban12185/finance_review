"""Orchestrates the hybrid classification workflow.

1. Deterministic rules classify confident transactions.
2. The LLM (Groq) is consulted only when rules are insufficient/ambiguous.
3. Low-confidence and judgement items land in the review queue.

Financial records are only ever mutated through this service, which renders the
LLM output inert without validation against the catalog.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.ai.classifier import classify_with_llm
from app.classification.catalog import BY_CODE, CategoryDef, CATALOG, get_category
from app.classification.rules import RuleResult, apply_rules
from app.core.config import get_settings
from app.core.constants import ClassificationSource, ReviewStatus
from app.core.logging import get_logger
from app.models.audit_event import AuditEvent
from app.models.category import Category
from app.models.classification import Classification, ClassificationHistory
from app.models.review_item import ReviewItem
from app.models.transaction import Transaction
from app.services.review_detection import DetectionResult, detect_review_triggers

logger = get_logger(__name__)
_settings = get_settings()


@dataclass(frozen=True)
class ClassificationData:
    category_code: str
    category_name: str
    subcategory: str
    pnl_type: str
    accounting_treatment: str
    is_contra: bool
    confidence: float
    requires_review: bool
    source: str
    reasoning: str
    version: int = 1
    review_note: str = ""


# ---------------------------------------------------------------------------
# Catalog sync
# ---------------------------------------------------------------------------
def ensure_categories(db: Session) -> None:
    """Idempotently upsert the category catalog into the database."""
    for cat in CATALOG:
        row = db.query(Category).filter(Category.code == cat.code).first()
        if row is None:
            db.add(Category(
                code=cat.code,
                name=cat.name,
                subcategory=cat.subcategory,
                pnl_type=cat.pnl_type,
                accounting_treatment=cat.accounting_treatment,
                is_contra=cat.is_contra,
                sort_order=cat.sort_order,
                description=cat.description,
            ))
        else:
            row.name = cat.name
            row.subcategory = cat.subcategory
            row.pnl_type = cat.pnl_type
            row.accounting_treatment = cat.accounting_treatment
            row.is_contra = cat.is_contra
            row.sort_order = cat.sort_order
            row.description = cat.description
    db.commit()


# ---------------------------------------------------------------------------
# Build classification data
# ---------------------------------------------------------------------------
def _from_rule(rule: RuleResult) -> ClassificationData:
    cat = rule.category
    return ClassificationData(
        category_code=cat.code,
        category_name=cat.name,
        subcategory=cat.subcategory,
        pnl_type=cat.pnl_type,
        accounting_treatment=cat.accounting_treatment,
        is_contra=cat.is_contra,
        confidence=rule.confidence,
        requires_review=rule.requires_review,
        source=ClassificationSource.RULE.value,
        reasoning=rule.reason,
    )


def _from_llm(llm, rule: RuleResult | None) -> ClassificationData:
    cat = BY_CODE[llm.category_code]
    confidence = max(rule.confidence if rule else 0.0, llm.confidence)
    requires_review = (
        llm.confidence < _settings.review_threshold
        or (rule is not None and rule.requires_review)
        or getattr(llm, "requires_review", False)
    )
    reasoning = f"LLM: {llm.reasoning}"
    if rule is not None:
        reasoning += f" Rule baseline: {rule.reason}"
    review_note = ""
    if getattr(llm, "requires_review", False):
        reasons = getattr(llm, "review_reasons", []) or []
        if reasons:
            review_note = "LLM review requested: " + "; ".join(reasons)
        else:
            review_note = "LLM review requested: " + llm.reasoning
    return ClassificationData(
        category_code=cat.code,
        category_name=cat.name,
        subcategory=cat.subcategory,
        pnl_type=cat.pnl_type,
        accounting_treatment=cat.accounting_treatment,
        is_contra=cat.is_contra,
        confidence=confidence,
        requires_review=requires_review,
        source=ClassificationSource.LLM.value,
        reasoning=reasoning,
        review_note=review_note,
    )


def _uncategorized(reason: str) -> ClassificationData:
    cat = BY_CODE["uncategorized"]
    return ClassificationData(
        category_code=cat.code,
        category_name=cat.name,
        subcategory=cat.subcategory,
        pnl_type=cat.pnl_type,
        accounting_treatment=cat.accounting_treatment,
        is_contra=cat.is_contra,
        confidence=0.0,
        requires_review=True,
        source=ClassificationSource.RULE.value,
        reasoning=reason,
    )


def build_classification(*, description: str, counterparty: str = "", method: str = "", amount_cents: int = 0) -> ClassificationData:
    rule = apply_rules(description=description, counterparty=counterparty, method=method, amount_cents=amount_cents)

    # Rules are confident enough: use them without calling the LLM.
    if rule is not None and rule.confidence >= _settings.llm_threshold:
        return _from_rule(rule)

    # Ambiguous / no rule -> LLM second opinion (graceful when unavailable).
    llm = None
    if _settings.enable_llm_classification:
        llm = classify_with_llm(description, counterparty, amount_cents)

    if llm is not None:
        return _from_llm(llm, rule)

    if rule is not None:
        reason = rule.reason + " LLM unavailable; confirm confidence."
        return ClassificationData(
            category_code=rule.category.code,
            category_name=rule.category.name,
            subcategory=rule.category.subcategory,
            pnl_type=rule.category.pnl_type,
            accounting_treatment=rule.category.accounting_treatment,
            is_contra=rule.category.is_contra,
            confidence=rule.confidence,
            requires_review=True,
            source=ClassificationSource.RULE.value,
            reasoning=reason,
        )

    return _uncategorized("No rule matched and LLM unavailable - requires manual classification.")


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------
def persist_classification(
    db: Session,
    txn: Transaction,
    data: ClassificationData,
    *,
    actor: str = "system",
    force: bool = False,
) -> None:
    """Create/update the effective classification for a transaction.

    Also appends a classification history entry when the version changes and
    creates/keeps a review item when the classification requires review.

    Manual corrections are authoritative: unless ``force`` is set, an automated
    classification never overwrites a classification whose source is ``manual``.
    """
    cls = db.query(Classification).filter(Classification.transaction_id == txn.id).first()

    if cls is not None and cls.source == ClassificationSource.MANUAL.value and not force:
        logger.info("Skipping auto-classification of %s: manual correction is authoritative.", txn.transaction_id)
        return

    if cls is not None and (
        cls.category_code != data.category_code
        or abs(float(cls.confidence) - data.confidence) > 0.0001
        or cls.requires_review != data.requires_review
    ):
        db.add(ClassificationHistory(
            transaction_id=txn.id,
            version=cls.version,
            category_code=cls.category_code,
            category_name=cls.category_name,
            subcategory=cls.subcategory,
            pnl_type=cls.pnl_type,
            accounting_treatment=cls.accounting_treatment,
            is_contra=cls.is_contra,
            confidence=float(cls.confidence),
            source=cls.source,
            reasoning=cls.reasoning,
        ))
        data = ClassificationData(**{**data.__dict__, "version": cls.version + 1})

    if cls is None:
        cls = Classification(transaction_id=txn.id)
        db.add(cls)

    cls.category_code = data.category_code
    cls.category_name = data.category_name
    cls.subcategory = data.subcategory
    cls.pnl_type = data.pnl_type
    cls.accounting_treatment = data.accounting_treatment
    cls.is_contra = data.is_contra
    cls.confidence = data.confidence
    cls.requires_review = data.requires_review
    cls.source = data.source
    cls.reasoning = data.reasoning
    cls.version = data.version

    # Surface the transaction in the review queue based on all explainable
    # triggers (low confidence, judgment, unusual amount, inconsistency...).
    detection = detect_review_triggers(db, txn, data)
    if detection.requires_review:
        cls.requires_review = True
        if cls.review_status not in (
            ReviewStatus.APPROVED.value,
            ReviewStatus.CORRECTED.value,
            ReviewStatus.MARKED_NON_PNL.value,
        ):
            cls.review_status = ReviewStatus.PENDING.value
            _append_reason_to_classification(cls, txn, detection)

    db.commit()

    _sync_review_item(db, txn, data, detection)

    if actor != "system":
        db.add(AuditEvent(
            entity_type="transaction",
            entity_id=txn.transaction_id,
            action="classification_updated",
            summary=f"As {actor}: {txn.transaction_id} -> {data.category_name} ({data.pnl_type})",
            new_value={
                "category_code": data.category_code,
                "category_name": data.category_name,
                "pnl_type": data.pnl_type,
                "accounting_treatment": data.accounting_treatment,
                "confidence": data.confidence,
                "requires_review": cls.requires_review,
                "source": data.source,
                "version": data.version,
            },
            actor=actor,
        ))
        db.commit()


def _append_reason_to_classification(cls: Classification, txn: Transaction, detection: DetectionResult) -> None:
    """Attach compact human-readable reasons to the classification row so the
    "why is this in review" is visible even without joining the review item."""
    if not detection.reasons:
        return
    extra = " | ".join(f"[{s}] {r}" for s, r in zip(detection.sources, detection.reasons))
    cls.reasoning = (cls.reasoning + "\nReview: " + extra).strip()


def _sync_review_item(db: Session, txn: Transaction, data: ClassificationData, detection: DetectionResult) -> None:
    """Ensure a pending review item exists for reviews and closes open ones when
    a classification no longer requires review. When a review item is already
    open, its reasons and suggested action are refreshed (never duplicated)."""
    existing = (
        db.query(ReviewItem)
        .filter(ReviewItem.transaction_id == txn.id, ReviewItem.status == ReviewStatus.PENDING.value)
        .first()
    )
    if data.requires_review or detection.requires_review:
        if existing is None:
            db.add(ReviewItem(
                transaction_id=txn.id,
                status=ReviewStatus.PENDING.value,
                submitted_category_code=data.category_code,
                submitted_category_name=data.category_name,
                submitted_pnl_type=data.pnl_type,
                submitted_accounting_treatment=data.accounting_treatment,
                submitted_confidence=data.confidence,
                submitted_source=data.source,
                submitted_reasoning=data.reasoning,
                review_sources=detection.sources,
                review_reasons=detection.reasons,
                suggested_action=detection.suggested_action,
            ))
            db.commit()
        else:
            existing.submitted_category_code = data.category_code
            existing.submitted_category_name = data.category_name
            existing.submitted_pnl_type = data.pnl_type
            existing.submitted_accounting_treatment = data.accounting_treatment
            existing.submitted_confidence = data.confidence
            existing.submitted_source = data.source
            existing.submitted_reasoning = data.reasoning
            existing.review_sources = detection.sources
            existing.review_reasons = detection.reasons
            existing.suggested_action = detection.suggested_action
            db.commit()
    elif existing is not None:
        db.delete(existing)
        db.commit()


def category_def_from_code(code: str) -> CategoryDef | None:
    return get_category(code)