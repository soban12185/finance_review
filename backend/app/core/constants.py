"""Shared domain constants and enums."""
from __future__ import annotations

from enum import Enum


class PnlType(str, Enum):
    REVENUE = "revenue"
    COGS = "cogs"
    PAYROLL = "payroll"
    OPERATING_EXPENSE = "operating_expense"
    NON_PNL = "non_pnl"

    @property
    def label(self) -> str:  # pragma: no cover - trivial
        return self.value.replace("_", " ").title()


class AccountingTreatment(str, Enum):
    OPERATING_REVENUE = "operating_revenue"
    CONTRA_REVENUE = "contra_revenue"
    COST_OF_GOODS_SOLD = "cost_of_goods_sold"
    PAYROLL_EXPENSE = "payroll_expense"
    OPERATING_EXPENSE = "operating_expense"
    CAPITAL_EXPENDITURE = "capital_expenditure"
    SALES_TAX_LIABILITY = "sales_tax_liability"
    DEFERRED_REVENUE = "deferred_revenue"
    LOAN_PRINCIPAL = "loan_principal"
    OWNER_DISTRIBUTION = "owner_distribution"

    @property
    def label(self) -> str:  # pragma: no cover - trivial
        return self.value.replace("_", " ").title()


class ClassificationSource(str, Enum):
    RULE = "rule"
    LLM = "llm"
    MANUAL = "manual"


class ReviewStatus(str, Enum):
    NONE = "none"
    PENDING = "pending"
    APPROVED = "approved"
    CORRECTED = "corrected"
    MARKED_NON_PNL = "marked_non_pnl"

    @property
    def label(self) -> str:  # pragma: no cover - trivial
        return self.value.replace("_", " ").title()


class ReviewSource(str, Enum):
    """Why a transaction was surfaced in the review queue.

    A single transaction may be flagged by several sources at once; every
    reason is preserved on the review item (``review_sources`` /
    ``review_reasons``) so the queue is fully explainable.
    """
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    ACCOUNTING_JUDGMENT = "ACCOUNTING_JUDGMENT"
    UNUSUAL_TRANSACTION = "UNUSUAL_TRANSACTION"
    DATA_INCONSISTENCY = "DATA_INCONSISTENCY"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class TransactionStatus(str, Enum):
    NORMAL = "normal"
    EXCLUDED = "excluded"


PNL_LINES = ("revenue", "cogs", "gross_profit", "payroll", "operating_expenses", "operating_profit")