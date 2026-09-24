from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.constants import ReviewStatus
from app.core.errors import ValidationError
from app.db.session import get_db
from app.repositories import transaction_repo as repo
from app.schemas.review import ReviewAction
from app.services import review as review_service

router = APIRouter()


def _review_item_out(item) -> dict:
    txn = item.transaction
    cls = txn.classification
    return {
        "id": item.id,
        "transaction_id": txn.transaction_id,
        "date": txn.date.isoformat(),
        "description": txn.description,
        "counterparty": txn.counterparty,
        "amount_cents": txn.amount_cents,
        "amount": round(txn.amount_cents / 100.0, 2),
        "method": txn.method,
        "status": item.status,
        "current_classification": {
            "category_code": cls.category_code if cls else None,
            "category_name": cls.category_name if cls else None,
            "pnl_type": cls.pnl_type if cls else None,
            "accounting_treatment": cls.accounting_treatment if cls else None,
            "confidence": float(cls.confidence) if cls else None,
            "source": cls.source if cls else None,
            "reasoning": cls.reasoning if cls else None,
        },
        "submitted": {
            "category_code": item.submitted_category_code,
            "category_name": item.submitted_category_name,
            "pnl_type": item.submitted_pnl_type,
            "accounting_treatment": item.submitted_accounting_treatment,
            "confidence": float(item.submitted_confidence),
            "source": item.submitted_source,
            "reasoning": item.submitted_reasoning,
        },
        "review_sources": (item.review_sources or []),
        "review_reasons": (item.review_reasons or []),
        "suggested_action": item.suggested_action,
        "decided": {
            "category_code": item.decided_category_code,
            "category_name": item.decided_category_name,
            "pnl_type": item.decided_pnl_type,
            "accounting_treatment": item.decided_accounting_treatment,
            "confidence": float(item.decided_confidence) if item.decided_confidence is not None else None,
        } if item.status != ReviewStatus.PENDING.value else None,
        "note": item.note or "",
        "reviewed_by": item.reviewed_by,
        "reviewer_decision": item.reviewer_decision,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "reviewed_at": item.reviewed_at.isoformat() if item.reviewed_at else None,
        "resolved_at": item.resolved_at.isoformat() if item.resolved_at else None,
    }


@router.get("")
def list_review_items(
    db: Session = Depends(get_db),
    status: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
):
    rows, total = repo.list_review_items(db, status=status, limit=limit)
    return {"total": total, "items": [_review_item_out(it) for it in rows]}


@router.get("/meta/counts")
def review_counts(db: Session = Depends(get_db)):
    rows = repo.list_review_items(db, status=None, limit=100000)[0]
    counts = {s.value: 0 for s in ReviewStatus}
    for it in rows:
        counts[it.status] = counts.get(it.status, 0) + 1
    return counts


@router.post("/{item_id}/resolve")
def resolve_review(item_id: int, body: ReviewAction, db: Session = Depends(get_db)):
    if body.action == "approve":
        item = review_service.approve_review(db, item_id, note=body.note, actor=body.actor)
    elif body.action == "change_classification":
        if not body.category_code:
            raise ValidationError("category_code is required to change the classification.")
        item = review_service.change_classification(db, item_id, body.category_code, note=body.note, actor=body.actor)
    elif body.action == "mark_non_pnl":
        if not body.category_code:
            raise ValidationError("category_code (a non-P&L category) is required.")
        item = review_service.mark_non_pnl(db, item_id, body.category_code, note=body.note, actor=body.actor)
    else:  # pragma: no cover - guarded by schema pattern
        raise ValidationError(f"Unknown action: {body.action}")
    return _review_item_out(item)


@router.get("/audit/events")
def audit_events(db: Session = Depends(get_db), limit: int = Query(default=100, ge=1, le=500)):
    from app.models.audit_event import AuditEvent
    from sqlalchemy import desc

    rows = db.query(AuditEvent).order_by(desc(AuditEvent.created_at)).limit(limit).all()
    return {
        "total": len(rows),
        "events": [
            {
                "id": e.id,
                "entity_type": e.entity_type,
                "entity_id": e.entity_id,
                "action": e.action,
                "summary": e.summary,
                "actor": e.actor,
                "created_at": e.created_at.isoformat() if e.created_at else None,
                "old_value": e.old_value,
                "new_value": e.new_value,
            }
            for e in rows
        ],
    }