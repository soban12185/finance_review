"""Deterministic monthly P&L engine.

This module is the authoritative financial source of truth. Every number is
computed from the signed amounts of classified transactions stored in the
database - the LLM never calculates a P&L figure.

Formulas (implemented in code):
    Gross Profit      = Revenue + COGS            (COGS is a signed negative total)
    Operating Profit  = Gross Profit + Payroll + Operating Expenses
                      = Gross Profit - |Payroll| - |Operating Expenses|

All amounts are integer cents; ``amount`` (dollars) is derived for display only.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.constants import PnlType
from app.financial.money import cents_to_amount
from app.repositories import transaction_repo as repo

CENTS_0 = 0

LINE_LABELS = {
    "revenue": "Revenue",
    "cogs": "COGS",
    "gross_profit": "Gross Profit",
    "payroll": "Payroll",
    "operating_expenses": "Operating Expenses",
    "operating_profit": "Operating Profit",
}

LINE_PNL_TYPES = {
    "revenue": [PnlType.REVENUE.value],
    "cogs": [PnlType.COGS.value],
    "payroll": [PnlType.PAYROLL.value],
    "operating_expenses": [PnlType.OPERATING_EXPENSE.value],
}

COMPUTED_LINES = ("gross_profit", "operating_profit")


@dataclass
class CategoryTotal:
    category_code: str
    category_name: str
    amount_cents: int
    amount: float
    transaction_count: int


@dataclass
class LineTotal:
    line: str
    label: str
    amount_cents: int
    amount: float
    transaction_count: int
    categories: list[CategoryTotal] = field(default_factory=list)

    @property
    def is_computed(self) -> bool:
        return self.line in COMPUTED_LINES


@dataclass
class MonthlyPnL:
    month: str
    lines: dict[str, LineTotal]
    transaction_count: int
    net_cash_cents: int
    pending_review_count: int

    @property
    def net_cash(self) -> float:
        return cents_to_amount(self.net_cash_cents)


# ---------------------------------------------------------------------------
# Arithmetic primitives (unit-testable without a database)
# ---------------------------------------------------------------------------
def calculate_revenue_cents(amounts_cents: list[int]) -> int:
    return sum(amounts_cents)


def calculate_gross_profit(revenue_cents: int, cogs_cents: int) -> int:
    """Gross Profit = Revenue - |COGS| == Revenue + COGS (COGS negative)."""
    return revenue_cents + cogs_cents


def calculate_operating_profit(gross_profit_cents: int, payroll_cents: int, opex_cents: int) -> int:
    """Operating Profit = Gross Profit - |Payroll| - |OpEx|."""
    return gross_profit_cents + payroll_cents + opex_cents


# ---------------------------------------------------------------------------
# Month-level calculations against the database
# ---------------------------------------------------------------------------
def calculate_revenue(db: Session, month: str) -> int:
    total, _ = repo.signed_total_by_pnl_type(db, month, PnlType.REVENUE.value)
    return total


def calculate_cogs(db: Session, month: str) -> int:
    total, _ = repo.signed_total_by_pnl_type(db, month, PnlType.COGS.value)
    return total


def calculate_payroll(db: Session, month: str) -> int:
    total, _ = repo.signed_total_by_pnl_type(db, month, PnlType.PAYROLL.value)
    return total


def calculate_operating_expenses(db: Session, month: str) -> int:
    total, _ = repo.signed_total_by_pnl_type(db, month, PnlType.OPERATING_EXPENSE.value)
    return total


def _line_total(db: Session, month: str, line: str, pnl_type: str) -> LineTotal:
    total_cents, count = repo.signed_total_by_pnl_type(db, month, pnl_type)
    cats = []
    for code, name, amt, cnt in repo.category_totals_for_month(db, month, pnl_type):
        cats.append(CategoryTotal(
            category_code=code,
            category_name=name,
            amount_cents=amt,
            amount=cents_to_amount(amt),
            transaction_count=cnt,
        ))
    cats.sort(key=lambda c: -abs(c.amount_cents))
    return LineTotal(
        line=line,
        label=LINE_LABELS[line],
        amount_cents=total_cents,
        amount=cents_to_amount(total_cents),
        transaction_count=count,
        categories=cats,
    )


def calculate_monthly_pnl(db: Session, month: str) -> MonthlyPnL:
    """Full monthly P&L built from underlying transaction data."""
    revenue = _line_total(db, month, "revenue", PnlType.REVENUE.value)
    cogs = _line_total(db, month, "cogs", PnlType.COGS.value)
    payroll = _line_total(db, month, "payroll", PnlType.PAYROLL.value)
    opex = _line_total(db, month, "operating_expenses", PnlType.OPERATING_EXPENSE.value)

    gp_cents = calculate_gross_profit(revenue.amount_cents, cogs.amount_cents)
    op_cents = calculate_operating_profit(gp_cents, payroll.amount_cents, opex.amount_cents)

    lines = {
        "revenue": revenue,
        "cogs": cogs,
        "gross_profit": LineTotal("gross_profit", LINE_LABELS["gross_profit"], gp_cents,
                                  cents_to_amount(gp_cents), revenue.transaction_count + cogs.transaction_count),
        "payroll": payroll,
        "operating_expenses": opex,
        "operating_profit": LineTotal("operating_profit", LINE_LABELS["operating_profit"], op_cents,
                                      cents_to_amount(op_cents),
                                      revenue.transaction_count + cogs.transaction_count + payroll.transaction_count + opex.transaction_count),
    }

    pnl_txn_count = sum(t.transaction_count for t in lines.values())
    return MonthlyPnL(
        month=month,
        lines=lines,
        transaction_count=pnl_txn_count,
        net_cash_cents=repo.net_cash_for_month(db, month),
        pending_review_count=repo.pending_review_for_month(db, month),
    )


def line_transactions_for_drilldown(db: Session, month: str, line: str) -> list:
    """Transactions feeding a P&L line (used for drill-down)."""
    pnl_types = LINE_PNL_TYPES.get(line)
    if pnl_types is None:
        raise ValueError(f"Line '{line}' has no direct transactions.")
    return repo.transactions_for_month(db, month, pnl_types)