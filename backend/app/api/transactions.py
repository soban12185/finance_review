from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.errors import NotFoundError, ValidationError
from app.repositories import transaction_repo as repo
from app.schemas.transaction import transaction_detail, transaction_summary

router = APIRouter()


@router.get("")
def list_transactions_endpoint(
    db: Session = Depends(get_db),
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    category: str | None = Query(default=None),
    pnl_type: str | None = Query(default=None),
    review_status: str | None = Query(default=None),
    requires_review: bool | None = Query(default=None),
    search: str | None = Query(default=None, max_length=200),
    method: str | None = Query(default=None),
    sort_by: str = Query(default="date"),
    sort_dir: str = Query(default="asc"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    try:
        rows, total = repo.list_transactions(
            db,
            month=month,
            category_code=category,
            pnl_type=pnl_type,
            review_status=review_status,
            requires_review=requires_review,
            search=search,
            method=method,
            sort_by=sort_by,
            sort_dir=sort_dir,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "transactions": [transaction_summary(t) for t in rows],
    }


@router.get("/{transaction_id}")
def get_transaction_endpoint(transaction_id: str, db: Session = Depends(get_db)):
    txn = repo.get_transaction_by_id(db, transaction_id)
    if txn is None:
        raise NotFoundError(f"Transaction {transaction_id} not found.")
    return transaction_detail(txn)


@router.get("/meta/filters")
def filters_meta(db: Session = Depends(get_db)):
    return {
        "months": repo.available_months(db),
        "categories": repo.categories_with_counts(db),
        "methods": repo.methods_in_use(db),
        "pnl_types": ["revenue", "cogs", "payroll", "operating_expense", "non_pnl"],
    }