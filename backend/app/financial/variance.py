"""Month-over-month variance analysis.

Pure, deterministic math: every figure derives from the underlying monthly P&L
category totals. The LLM may only *explain* the numbers produced here, never
compute them.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.financial.engine import LINE_LABELS, MonthlyPnL, calculate_monthly_pnl
from app.financial.money import cents_to_amount, pct_change
from app.models.classification import Classification
from app.models.transaction import Transaction
from app.repositories import transaction_repo as repo

LINE_ORDER = ("revenue", "cogs", "gross_profit", "payroll", "operating_expenses", "operating_profit")

# line code -> classification pnl_type for the lines that have direct transactions
LINE_PNL_TYPE = {
    "revenue": "revenue",
    "cogs": "cogs",
    "payroll": "payroll",
    "operating_expenses": "operating_expense",
}

_settings = get_settings()


@dataclass
class VarianceResult:
    line: str
    label: str
    previous_cents: int
    current_cents: int
    previous: float
    current: float
    absolute_cents: int
    absolute: float
    percent: float | None
    material: bool

    def as_dict(self) -> dict:
        return {
            "line": self.line,
            "label": self.label,
            "previous_cents": self.previous_cents,
            "current_cents": self.current_cents,
            "previous": self.previous,
            "current": self.current,
            "absolute_cents": self.absolute_cents,
            "absolute": self.absolute,
            "percent": self.percent,
            "material": self.material,
        }


@dataclass
class DriverResult:
    category_code: str
    category_name: str
    previous_cents: int
    current_cents: int
    previous: float
    current: float
    absolute_cents: int
    absolute: float
    percent: float | None
    material: bool
    contribution_percent: float
    transaction_count: int
    transactions: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "category_code": self.category_code,
            "category_name": self.category_name,
            "previous_cents": self.previous_cents,
            "current_cents": self.current_cents,
            "previous": self.previous,
            "current": self.current,
            "absolute_cents": self.absolute_cents,
            "absolute": self.absolute,
            "percent": self.percent,
            "material": self.material,
            "contribution_percent": self.contribution_percent,
            "transaction_count": self.transaction_count,
            "transactions": self.transactions,
        }


def is_material(
    prev_cents: int,
    curr_cents: int,
    *,
    materiality_percent: float | None = None,
    materiality_abs_cents: int | None = None,
) -> bool:
    """Materiality rule.

    A move is material when its absolute size is at least
    ``materiality_abs_cents`` AND either the percentage move meets
    ``materiality_percent`` or there is no prior basis but the size itself is
    large enough.
    """
    pct = materiality_percent if materiality_percent is not None else _settings.variance_materiality_percent
    abs_min = materiality_abs_cents if materiality_abs_cents is not None else _settings.variance_materiality_abs_cents
    delta = int(curr_cents) - int(prev_cents)
    if abs(delta) < abs_min:
        return False
    if int(prev_cents) == 0:
        return abs(int(curr_cents)) >= abs_min
    return abs(delta) / abs(int(prev_cents)) * 100.0 >= pct


def calculate_variance(
    prev_cents: int,
    curr_cents: int,
    *,
    line: str = "",
    materiality_percent: float | None = None,
    materiality_abs_cents: int | None = None,
) -> VarianceResult:
    return VarianceResult(
        line=line,
        label=LINE_LABELS.get(line, ""),
        previous_cents=int(prev_cents),
        current_cents=int(curr_cents),
        previous=cents_to_amount(int(prev_cents)),
        current=cents_to_amount(int(curr_cents)),
        absolute_cents=int(curr_cents) - int(prev_cents),
        absolute=cents_to_amount(int(curr_cents) - int(prev_cents)),
        percent=pct_change(int(prev_cents), int(curr_cents)),
        material=is_material(
            int(prev_cents),
            int(curr_cents),
            materiality_percent=materiality_percent,
            materiality_abs_cents=materiality_abs_cents,
        ),
    )


def calculate_month_variance(
    prev_pnl: MonthlyPnL,
    curr_pnl: MonthlyPnL,
    *,
    materiality_percent: float | None = None,
    materiality_abs_cents: int | None = None,
) -> list[VarianceResult]:
    out = []
    for line in LINE_ORDER:
        out.append(calculate_variance(
            prev_pnl.lines[line].amount_cents,
            curr_pnl.lines[line].amount_cents,
            line=line,
            materiality_percent=materiality_percent,
            materiality_abs_cents=materiality_abs_cents,
        ))
    return out


def _category_map(db: Session, month: str, pnl_type: str) -> dict[str, dict]:
    mapped: dict[str, dict] = {}
    for code, name, amt, cnt in repo.category_totals_for_month(db, month, pnl_type):
        mapped[code] = {"name": name, "amount_cents": int(amt), "count": cnt}
    return mapped


def _month_transactions(db: Session, month: str, category_code: str, limit: int, *, order_desc: bool = True) -> list:
    start, end = repo.month_range(month)
    q = (
        db.query(Transaction)
        .join(Classification, Classification.transaction_id == Transaction.id)
        .filter(
            Transaction.date >= start,
            Transaction.date < end,
            Classification.category_code == category_code,
        )
    )
    order = Transaction.date.desc() if order_desc else Transaction.date.asc()
    return q.order_by(order).limit(limit).all()


def _month_transaction_count(db: Session, month: str, category_code: str) -> int:
    start, end = repo.month_range(month)
    return (
        db.query(func.count(Transaction.id))
        .join(Classification, Classification.transaction_id == Transaction.id)
        .filter(
            Transaction.date >= start,
            Transaction.date < end,
            Classification.category_code == category_code,
        )
        .scalar()
        or 0
    )


def find_variance_drivers(
    db: Session,
    prev_month: str,
    curr_month: str,
    line: str,
    *,
    limit: int = 20,
    materiality_percent: float | None = None,
    materiality_abs_cents: int | None = None,
) -> list[DriverResult]:
    """Category-level drivers of a line's month-over-month variance.

    Each driver references the transactions behind it, so an explanation is
    always traceable.
    """
    pnl_type = LINE_PNL_TYPE.get(line)
    if pnl_type is None:
        raise ValueError(
            f"Cannot determine drivers for computed line '{line}'. Drivers are "
            "available for revenue, cogs, payroll and operating_expenses."
        )

    prev_pnl = calculate_monthly_pnl(db, prev_month)
    curr_pnl = calculate_monthly_pnl(db, curr_month)
    prev_map = _category_map(db, prev_month, pnl_type)
    curr_map = _category_map(db, curr_month, pnl_type)

    prev_line = prev_pnl.lines[line].amount_cents
    curr_line = curr_pnl.lines[line].amount_cents
    line_delta = curr_line - prev_line

    drivers: list[DriverResult] = []
    for code in sorted(set(prev_map) | set(curr_map)):
        prev_c = int(prev_map.get(code, {}).get("amount_cents", 0))
        curr_c = int(curr_map.get(code, {}).get("amount_cents", 0))
        name = curr_map.get(code, prev_map.get(code, {})).get("name", code)
        delta = curr_c - prev_c
        contribution = round(abs(delta) / abs(line_delta) * 100.0, 2) if line_delta != 0 else 0.0
        changed = delta != 0
        drivers.append(DriverResult(
            category_code=code,
            category_name=name,
            previous_cents=prev_c,
            current_cents=curr_c,
            previous=cents_to_amount(prev_c),
            current=cents_to_amount(curr_c),
            absolute_cents=delta,
            absolute=cents_to_amount(delta),
            percent=pct_change(prev_c, curr_c),
            material=is_material(
                prev_c, curr_c, materiality_percent=materiality_percent, materiality_abs_cents=materiality_abs_cents
            ),
            contribution_percent=contribution,
            transaction_count=_month_transaction_count(db, curr_month, code) if changed else 0,
            transactions=[
                {
                    "transaction_id": t.transaction_id,
                    "date": t.date.isoformat(),
                    "description": t.description,
                    "counterparty": t.counterparty,
                    "amount_cents": t.amount_cents,
                    "amount": cents_to_amount(t.amount_cents),
                }
                for t in (_month_transactions(db, curr_month, code, limit) if changed else [])
            ],
        ))

    drivers.sort(key=lambda d: -abs(d.absolute_cents))
    return drivers