from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.financial import engine
from app.financial.money import cents_to_amount
from app.models.transaction import Transaction
from app.repositories import transaction_repo as repo

router = APIRouter()


@router.get("")
def dashboard(
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    db: Session = Depends(get_db),
):
    months = repo.available_months(db)
    aggregate = repo.available_months_agg(db)
    selected = month or (months[0] if months else None)

    overview = {}
    if selected:
        pnl = engine.calculate_monthly_pnl(db, selected)
        overview = {
            "month": selected,
            "lines": {line: lt.amount_cents for line, lt in pnl.lines.items()},
            "amounts": {line: cents_to_amount(lt.amount_cents) for line, lt in pnl.lines.items()},
            "transaction_count": pnl.transaction_count,
            "net_cash_cents": pnl.net_cash_cents,
            "net_cash": pnl.net_cash,
            "pending_review_count": pnl.pending_review_count,
        }

    # Revenue / operating profit trend per month
    trend = []
    for m in months:
        p = engine.calculate_monthly_pnl(db, m)
        trend.append({
            "month": m,
            "revenue_cents": p.lines["revenue"].amount_cents,
            "cogs_cents": p.lines["cogs"].amount_cents,
            "gross_profit_cents": p.lines["gross_profit"].amount_cents,
            "operating_profit_cents": p.lines["operating_profit"].amount_cents,
            "payroll_cents": p.lines["payroll"].amount_cents,
            "operating_expenses_cents": p.lines["operating_expenses"].amount_cents,
        })

    # Expense mix by category for the selected month
    expense_mix = []
    if selected:
        ops = engine._line_total(db, selected, "operating_expenses", "operating_expense")
        payroll_lt = engine._line_total(db, selected, "payroll", "payroll")
        for c in ops.categories:
            expense_mix.append({
                "category_code": c.category_code,
                "category_name": c.category_name,
                "amount_cents": c.amount_cents,
                "amount": c.amount,
                "bucket": "Operating Expenses",
            })
        for c in payroll_lt.categories:
            expense_mix.append({
                "category_code": c.category_code,
                "category_name": c.category_name,
                "amount_cents": c.amount_cents,
                "amount": c.amount,
                "bucket": "Payroll",
            })
        expense_mix.sort(key=lambda x: -abs(x["amount_cents"]))

    total_txns = db.query(Transaction).count()
    pending = repo.pending_review_count(db)
    return {
        "selected_month": selected,
        "months": aggregate,
        "overview": overview,
        "trend": trend,
        "expense_mix": expense_mix,
        "stats": {
            "total_transactions": total_txns,
            "pending_review": pending,
            "categories_in_use": len(repo.categories_with_counts(db)),
        },
    }