"""Data-access layer.

All SQL lives here so that services, the financial engine and AI tools never
build ad-hoc queries. Query parameters are validated by API schemas before they
reach this layer.
"""
from __future__ import annotations

from datetime import date
from typing import Sequence

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, joinedload

from app.core.constants import PnlType, ReviewStatus
from app.models.classification import Classification
from app.models.review_item import ReviewItem
from app.models.transaction import Transaction


def month_range(month: str) -> tuple[date, date]:
    """Return (first_day, first_day_of_next_month) for a 'YYYY-MM' string."""
    y, m = (int(p) for p in month.split("-"))
    start = date(y, m, 1)
    if m == 12:
        end = date(y + 1, 1, 1)
    else:
        end = date(y, m + 1, 1)
    return start, end


def get_transaction_by_id(db: Session, transaction_id: str) -> Transaction | None:
    return (
        db.query(Transaction)
        .options(joinedload(Transaction.classification), joinedload(Transaction.review_items))
        .filter(Transaction.transaction_id == transaction_id)
        .first()
    )


def list_transactions(
    db: Session,
    *,
    month: str | None = None,
    category_code: str | None = None,
    pnl_type: str | None = None,
    review_status: str | None = None,
    requires_review: bool | None = None,
    search: str | None = None,
    method: str | None = None,
    sort_by: str = "date",
    sort_dir: str = "asc",
    limit: int = 200,
    offset: int = 0,
) -> tuple[Sequence[Transaction], int]:
    q = db.query(Transaction).options(joinedload(Transaction.classification))

    if month:
        start, end = month_range(month)
        q = q.filter(Transaction.date >= start, Transaction.date < end)
    if category_code:
        q = q.join(Classification, Classification.transaction_id == Transaction.id).filter(
            Classification.category_code == category_code
        )
    if pnl_type:
        q = q.join(Classification, Classification.transaction_id == Transaction.id).filter(
            Classification.pnl_type == pnl_type
        )
    if requires_review is not None:
        q = q.join(Classification, Classification.transaction_id == Transaction.id).filter(
            Classification.requires_review == requires_review
        )
    if review_status:
        valid = {s.value for s in ReviewStatus}
        if review_status not in valid:
            raise ValueError(f"Invalid review_status: {review_status}")
        q = q.join(Classification, Classification.transaction_id == Transaction.id).filter(
            Classification.review_status == review_status
        )
    if method:
        q = q.filter(Transaction.method == method)
    if search:
        like = f"%{search.strip()}%"
        q = q.filter(or_(
            Transaction.transaction_id.ilike(like),
            Transaction.description.ilike(like),
            Transaction.counterparty.ilike(like),
        ))

    total = q.count()

    column = {
        "date": Transaction.date,
        "amount": Transaction.amount_cents,
        "transaction_id": Transaction.transaction_id,
        "description": Transaction.description,
        "counterparty": Transaction.counterparty,
        "method": Transaction.method,
    }.get(sort_by, Transaction.date)
    order = column.asc() if sort_dir == "asc" else column.desc()

    rows = (
        q.order_by(order, Transaction.id)
        .limit(min(limit, 1000))
        .offset(offset)
        .all()
    )
    return rows, total


def transactions_for_month(
    db: Session, month: str, pnl_types: list[str] | None = None
) -> list[Transaction]:
    start, end = month_range(month)
    q = db.query(Transaction).join(Classification, Classification.transaction_id == Transaction.id).filter(
        Transaction.date >= start,
        Transaction.date < end,
    )
    if pnl_types is not None:
        q = q.filter(Classification.pnl_type.in_(pnl_types))
    return q.options(joinedload(Transaction.classification)).all()


def category_totals_for_month(db: Session, month: str, pnl_type: str) -> list[tuple[str, str, int, int]]:
    """Return (category_code, category_name, amount_cents, count) grouped by category."""
    start, end = month_range(month)
    rows = (
        db.query(
            Classification.category_code,
            Classification.category_name,
            func.sum(Transaction.amount_cents),
            func.count(Transaction.id),
        )
        .join(Transaction, Transaction.id == Classification.transaction_id)
        .filter(
            Transaction.date >= start,
            Transaction.date < end,
            Classification.pnl_type == pnl_type,
        )
        .group_by(Classification.category_code, Classification.category_name)
        .all()
    )
    return [(code, name, int(total or 0), cnt) for code, name, total, cnt in rows]


def signed_total_by_pnl_type(db: Session, month: str, pnl_type: str) -> tuple[int, int]:
    """Return (signed total cents, transaction count) for a P&L line type."""
    start, end = month_range(month)
    total_cents, count = (
        db.query(
            func.coalesce(func.sum(Transaction.amount_cents), 0),
            func.count(Transaction.id),
        )
        .join(Classification, Classification.transaction_id == Transaction.id)
        .filter(
            Transaction.date >= start,
            Transaction.date < end,
            Classification.pnl_type == pnl_type,
        )
        .first()
    )
    return int(total_cents or 0), int(count or 0)


def pending_review_count(db: Session) -> int:
    return (
        db.query(func.count(Classification.id))
        .filter(Classification.requires_review.is_(True), Classification.review_status == ReviewStatus.PENDING.value)
        .scalar()
        or 0
    )


def pending_review_for_month(db: Session, month: str) -> int:
    start, end = month_range(month)
    return (
        db.query(func.count(Classification.id))
        .join(Transaction, Transaction.id == Classification.transaction_id)
        .filter(
            Transaction.date >= start,
            Transaction.date < end,
            Classification.requires_review.is_(True),
            Classification.review_status == ReviewStatus.PENDING.value,
        )
        .scalar()
        or 0
    )


def list_review_items(db: Session, status: str | None = None, limit: int = 200) -> tuple[list[ReviewItem], int]:
    q = db.query(ReviewItem).options(joinedload(ReviewItem.transaction)).order_by(ReviewItem.created_at.asc())
    if status:
        q = q.filter(ReviewItem.status == status)
    rows = q.limit(limit).all()
    return list(rows), len(rows)


def categories_with_counts(db: Session) -> list[dict]:
    rows = (
        db.query(Classification.category_code, Classification.category_name, func.count(Transaction.id))
        .join(Transaction, Transaction.id == Classification.transaction_id)
        .group_by(Classification.category_code, Classification.category_name)
        .order_by(Classification.category_name.asc())
        .all()
    )
    return [{"category_code": c, "category_name": n, "transaction_count": cnt} for c, n, cnt in rows]


def methods_in_use(db: Session) -> list[str]:
    rows = db.query(Transaction.method).distinct().order_by(Transaction.method).all()
    return [r[0] for r in rows]


def available_months(db: Session) -> list[str]:
    """Distinct months present in the data (dialect-independent)."""
    dates = db.query(Transaction.date).all()
    months = sorted({d[0].strftime("%Y-%m") for d in dates if d[0] is not None})
    return months


def available_months_agg(db: Session) -> list[dict]:
    """Month list with aggregate metadata for the dashboard month selector."""
    rows = db.query(Transaction.date, Transaction.amount_cents).all()
    agg: dict[str, dict] = {}
    for d, amt in rows:
        if d is None:
            continue
        key = d.strftime("%Y-%m")
        entry = agg.setdefault(key, {"month": key, "transaction_count": 0, "net_cash_cents": 0})
        entry["transaction_count"] += 1
        entry["net_cash_cents"] += int(amt)
    return [agg[k] for k in sorted(agg)]


def net_cash_for_month(db: Session, month: str) -> int:
    start, end = month_range(month)
    total = db.query(func.coalesce(func.sum(Transaction.amount_cents), 0)).filter(
        Transaction.date >= start, Transaction.date < end
    ).scalar()
    return int(total or 0)