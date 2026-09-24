from app.financial.money import cents_to_amount
from app.schemas.common import ORMModel


def classification_out(cls) -> dict:
    if cls is None:
        return {}
    return {
        "category_code": cls.category_code,
        "category_name": cls.category_name,
        "subcategory": cls.subcategory,
        "pnl_type": cls.pnl_type,
        "accounting_treatment": cls.accounting_treatment,
        "is_contra": cls.is_contra,
        "confidence": float(cls.confidence),
        "requires_review": bool(cls.requires_review),
        "review_status": cls.review_status,
        "source": cls.source,
        "reasoning": cls.reasoning,
        "version": cls.version,
    }


def transaction_summary(txn) -> dict:
    cls = txn.classification
    return {
        "id": txn.id,
        "transaction_id": txn.transaction_id,
        "date": txn.date.isoformat(),
        "description": txn.description,
        "counterparty": txn.counterparty,
        "amount_cents": txn.amount_cents,
        "amount": cents_to_amount(txn.amount_cents),
        "method": txn.method,
        "raw_amount": txn.raw_amount,
        "status": txn.status,
        "classification": classification_out(cls),
    }


def transaction_detail(txn) -> dict:
    d = transaction_summary(txn)
    d["review_items"] = [
        {
            "id": it.id,
            "status": it.status,
            "note": it.note or "",
            "reviewed_at": it.reviewed_at.isoformat() if it.reviewed_at else None,
            "reviewed_by": it.reviewed_by,
            "decided_category_name": it.decided_category_name,
            "decided_pnl_type": it.decided_pnl_type,
        }
        for it in txn.review_items
    ]
    return d