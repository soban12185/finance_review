"""Review queue service.

Manual review decisions are the authoritative override: the AI (rules + LLM) is
never allowed to overwrite a manual correction. Every decision is versioned in
``classification_history`` and recorded in ``audit_events``.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.classification.catalog import get_category
from app.core.constants import ClassificationSource, PnlType, ReviewStatus
from app.core.errors import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.audit_event import AuditEvent
from app.models.classification import Classification, ClassificationHistory
from app.models.review_item import ReviewItem
from app.models.transaction import Transaction

logger = get_logger(__name__)

NON_PNL_TYPES = {PnlType.NON_PNL.value}


def _snapshot_classification(cls: Classification) -> dict:
    return {
        "category_code": cls.category_code,
        "category_name": cls.category_name,
        "subcategory": cls.subcategory,
        "pnl_type": cls.pnl_type,
        "accounting_treatment": cls.accounting_treatment,
        "is_contra": cls.is_contra,
        "confidence": float(cls.confidence),
        "requires_review": cls.requires_review,
        "source": cls.source,
        "reasoning": cls.reasoning,
        "version": cls.version,
    }


def get_review_item(db: Session, item_id: int) -> ReviewItem:
    item = db.get(ReviewItem, item_id)
    if item is None:
        raise NotFoundError(f"Review item {item_id} not found.")
    return item


def _apply_correction(
    db: Session,
    item_id: int,
    category_code: str,
    note: str,
    actor: str,
    status_after: str,
    *,
    only_pnl_types: set[str] | None = None,
) -> ReviewItem:
    item = get_review_item(db, item_id)
    cat = get_category(category_code)
    if cat is None:
        raise ValidationError(f"Unknown category code: {category_code}")
    if only_pnl_types is not None and cat.pnl_type not in only_pnl_types:
        raise ValidationError(
            f"Category '{cat.name}' is not valid for this action (expected one of {sorted(only_pnl_types)})."
        )

    txn = db.get(Transaction, item.transaction_id)
    cls = db.query(Classification).filter(Classification.transaction_id == txn.id).first()
    if cls is None:
        raise NotFoundError(f"Classification for transaction {txn.transaction_id} not found.")

    # Version history for the outgoing classification.
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

    old = _snapshot_classification(cls)

    cls.category_code = cat.code
    cls.category_name = cat.name
    cls.subcategory = cat.subcategory
    cls.pnl_type = cat.pnl_type
    cls.accounting_treatment = cat.accounting_treatment
    cls.is_contra = cat.is_contra
    cls.confidence = 1.0
    cls.requires_review = False
    cls.review_status = status_after
    cls.source = ClassificationSource.MANUAL.value
    cls.reasoning = f"Manual review decision by {actor}. {note}".strip()
    cls.version = cls.version + 1
    # do not overwrite ManualCorrections timestamp fields beyond updated_at
    cls.updated_at = datetime.now(timezone.utc)

    new = _snapshot_classification(cls)

    item.status = status_after
    item.decided_category_code = cat.code
    item.decided_category_name = cat.name
    item.decided_pnl_type = cat.pnl_type
    item.decided_accounting_treatment = cat.accounting_treatment
    item.decided_confidence = 1.0
    item.note = note
    item.reviewed_by = actor
    item.reviewed_at = datetime.now(timezone.utc)
    item.resolved_at = item.reviewed_at
    item.reviewer_decision = status_after

    db.add(AuditEvent(
        entity_type="review_item",
        entity_id=str(item.id),
        action=f"review_{status_after}",
        summary=f"{actor} {status_after.replace('_', ' ')} {txn.transaction_id}: "
                f"{old['category_name']} -> {cat.name} (version {cls.version})",
        old_value=old,
        new_value=new,
        actor=actor,
    ))
    db.commit()
    return item


def approve_review(db: Session, item_id: int, note: str = "", actor: str = "user") -> ReviewItem:
    """Approve the auto-suggested classification (no category change)."""
    item = get_review_item(db, item_id)
    if item.status != ReviewStatus.PENDING.value:
        raise ValidationError(f"Review item {item_id} is not pending (status={item.status}).")

    txn = db.get(Transaction, item.transaction_id)
    cls = db.query(Classification).filter(Classification.transaction_id == txn.id).first()
    if cls is None:
        raise NotFoundError(f"Classification for transaction {txn.transaction_id} not found.")

    old = _snapshot_classification(cls)
    cls.review_status = ReviewStatus.APPROVED.value
    cls.requires_review = False
    cls.updated_at = datetime.now(timezone.utc)
    new = _snapshot_classification(cls)

    item.status = ReviewStatus.APPROVED.value
    item.decided_category_code = cls.category_code
    item.decided_category_name = cls.category_name
    item.decided_pnl_type = cls.pnl_type
    item.decided_accounting_treatment = cls.accounting_treatment
    item.decided_confidence = float(cls.confidence)
    item.note = note
    item.reviewed_by = actor
    item.reviewed_at = datetime.now(timezone.utc)
    item.resolved_at = item.reviewed_at
    item.reviewer_decision = "approved"

    db.add(AuditEvent(
        entity_type="review_item",
        entity_id=str(item.id),
        action="review_approved",
        summary=f"{actor} approved auto-classification of {txn.transaction_id} ({cls.category_name}).",
        old_value=old,
        new_value=new,
        actor=actor,
    ))
    db.commit()
    return item


def change_classification(
    db: Session, item_id: int, category_code: str, note: str = "", actor: str = "user"
) -> ReviewItem:
    """Reclassify the transaction into a chosen catalog category."""
    return _apply_correction(
        db, item_id=item_id, category_code=category_code, note=note, actor=actor,
        status_after=ReviewStatus.CORRECTED.value,
    )


def mark_non_pnl(db: Session, item_id: int, category_code: str, note: str = "", actor: str = "user") -> ReviewItem:
    """Explicitly designate a transaction as non-P&L (only non-P&L categories)."""
    return _apply_correction(
        db, item_id=item_id, category_code=category_code, note=note, actor=actor,
        status_after=ReviewStatus.MARKED_NON_PNL.value,
        only_pnl_types=NON_PNL_TYPES,
    )