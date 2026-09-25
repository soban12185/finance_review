from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.constants import PnlType
from app.db.session import get_db
from app.financial import engine
from app.financial.money import cents_to_amount
from app.repositories import transaction_repo as repo

router = APIRouter()

_LINE_BY_PNL_TYPE = {
    PnlType.REVENUE.value: "revenue",
    PnlType.COGS.value: "cogs",
    PnlType.PAYROLL.value: "payroll",
    PnlType.OPERATING_EXPENSE.value: "operating_expenses",
}

_EXPENSE_BUCKETS = (
    (PnlType.OPERATING_EXPENSE.value, "Operating Expenses"),
    (PnlType.PAYROLL.value, "Payroll"),
)


def _month_lines(totals: dict[str, tuple[int, int]]) -> dict[str, tuple[int, int]]:
    """Build the six P&L lines (cents, count) for a month from per-type totals.

    Uses the same arithmetic primitives as ``engine.calculate_monthly_pnl`` so
    every figure is identical to the per-row calculation.
    """
    revenue, rev_count = totals.get("revenue", (0, 0))
    cogs, cogs_count = totals.get("cogs", (0, 0))
    payroll, payroll_count = totals.get("payroll", (0, 0))
    opex, opex_count = totals.get("operating_expenses", (0, 0))

    gp = engine.calculate_gross_profit(revenue, cogs)
    op = engine.calculate_operating_profit(gp, payroll, opex)

    return {
        "revenue": (revenue, rev_count),
        "cogs": (cogs, cogs_count),
        "gross_profit": (gp, rev_count + cogs_count),
        "payroll": (payroll, payroll_count),
        "operating_expenses": (opex, opex_count),
        "operating_profit": (op, rev_count + cogs_count + payroll_count + opex_count),
    }


@router.get("")
def dashboard(
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    db: Session = Depends(get_db),
):
    aggregate = repo.available_months_agg(db)
    agg_by_month = {e["month"]: e for e in aggregate}
    months = [e["month"] for e in aggregate]
    selected = month or (months[0] if months else None)

    lines_by_month: dict[str, dict[str, tuple[int, int]]] = {}
    categories_by_month: dict[str, dict[str, dict[tuple[str, str], tuple[int, int]]]] = {}
    for d, pnl_type, cat_code, cat_name, cents, cnt in repo.monthly_classified_totals(db):
        if d is None:
            continue
        m = d.strftime("%Y-%m")
        line = _LINE_BY_PNL_TYPE.get(pnl_type)
        if line is None:
            continue
        month_lines = lines_by_month.setdefault(m, {})
        cur_cents, cur_cnt = month_lines.get(line, (0, 0))
        month_lines[line] = (cur_cents + cents, cur_cnt + cnt)
        bucket = categories_by_month.setdefault(m, {}).setdefault(pnl_type, {})
        key = (cat_code, cat_name)
        cat_cents, cat_cnt = bucket.get(key, (0, 0))
        bucket[key] = (cat_cents + cents, cat_cnt + cnt)

    overview = {}
    if selected:
        agg = agg_by_month[selected]
        month_lines = _month_lines(lines_by_month.get(selected, {}))
        overview = {
            "month": selected,
            "lines": {line: v[0] for line, v in month_lines.items()},
            "amounts": {line: cents_to_amount(v[0]) for line, v in month_lines.items()},
            "transaction_count": sum(v[1] for v in month_lines.values()),
            "net_cash_cents": agg["net_cash_cents"],
            "net_cash": cents_to_amount(agg["net_cash_cents"]),
            "pending_review_count": repo.pending_review_for_month(db, selected),
        }

    trend = []
    for m in months:
        ml = _month_lines(lines_by_month.get(m, {}))
        trend.append({
            "month": m,
            "revenue_cents": ml["revenue"][0],
            "cogs_cents": ml["cogs"][0],
            "gross_profit_cents": ml["gross_profit"][0],
            "operating_profit_cents": ml["operating_profit"][0],
            "payroll_cents": ml["payroll"][0],
            "operating_expenses_cents": ml["operating_expenses"][0],
        })

    expense_mix = []
    if selected:
        for pnl_type, label in _EXPENSE_BUCKETS:
            bucket = categories_by_month.get(selected, {}).get(pnl_type, {})
            for (cat_code, cat_name), (cat_cents, _count) in bucket.items():
                expense_mix.append({
                    "category_code": cat_code,
                    "category_name": cat_name,
                    "amount_cents": cat_cents,
                    "amount": cents_to_amount(cat_cents),
                    "bucket": label,
                })
        expense_mix.sort(key=lambda x: -abs(x["amount_cents"]))

    return {
        "selected_month": selected,
        "months": aggregate,
        "overview": overview,
        "trend": trend,
        "expense_mix": expense_mix,
        "stats": {
            "total_transactions": sum(e["transaction_count"] for e in aggregate),
            "pending_review": repo.pending_review_count(db),
            "categories_in_use": len(repo.categories_with_counts(db)),
        },
    }