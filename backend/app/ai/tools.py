"""Controlled backend tools exposed to the AI Financial Analyst.

The model cannot touch the database directly - everything goes through these
validated functions. All financial figures are computed by the backend P&L /
variance engines. ``amount`` values are display-ready dollars; ``*_cents`` are
the authoritative integers.
"""
from __future__ import annotations

import re
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.financial.engine import calculate_monthly_pnl, line_transactions_for_drilldown
from app.financial.money import cents_to_amount
from app.financial.variance import (
    LINE_PNL_TYPE,
    calculate_month_variance,
    find_variance_drivers,
)
from app.repositories import transaction_repo as repo

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


def _coerce_int(value: Any, fallback: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _coerce_float(value: Any, fallback: float | None = None) -> float | None:
    if value is None:
        return fallback
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _validate_month(month: Any) -> str:
    m = str(month or "").strip()
    if not _MONTH_RE.match(m):
        raise ValueError(f"Invalid month '{m}'. Expected YYYY-MM.")
    return m


def _validate_id(value: Any) -> str:
    v = str(value or "").strip()
    if not _ID_RE.match(v):
        raise ValueError(f"Invalid identifier '{v}'.")
    return v


# ---------------------------------------------------------------------------
# Tool implementations  (each: fn(db, **kwargs) -> dict)
# ---------------------------------------------------------------------------
def get_monthly_pnl(db: Session, month: Any) -> dict:
    m = _validate_month(month)
    pnl = calculate_monthly_pnl(db, m)
    lines = {}
    for line, lt in pnl.lines.items():
        lines[line] = {
            "label": lt.label,
            "amount_cents": lt.amount_cents,
            "amount": lt.amount,
            "transaction_count": lt.transaction_count,
        }
    return {
        "month": m,
        "transaction_count": pnl.transaction_count,
        "net_cash_cents": pnl.net_cash_cents,
        "net_cash": pnl.net_cash,
        "pending_review_count": pnl.pending_review_count,
        "lines": lines,
    }


def compare_months(db: Session, month_a: Any, month_b: Any) -> dict:
    ma, mb = _validate_month(month_a), _validate_month(month_b)
    pa = calculate_monthly_pnl(db, ma)
    pb = calculate_monthly_pnl(db, mb)
    variances = calculate_month_variance(pa, pb)
    return {
        "month_a": ma,
        "month_b": mb,
        "lines": [v.as_dict() for v in variances],
    }


def get_variance(
    db: Session,
    month_a: Any,
    month_b: Any,
    materiality_percent: Any = None,
    materiality_abs_cents: Any = None,
) -> dict:
    ma, mb = _validate_month(month_a), _validate_month(month_b)
    pa = calculate_monthly_pnl(db, ma)
    pb = calculate_monthly_pnl(db, mb)
    variances = calculate_month_variance(
        pa,
        pb,
        materiality_percent=_coerce_float(materiality_percent),
        materiality_abs_cents=_coerce_int(materiality_abs_cents) if materiality_abs_cents is not None else None,
    )
    return {
        "month_a": ma,
        "month_b": mb,
        "materiality": {
            "percent": materiality_percent,
            "abs_cents": materiality_abs_cents,
        },
        "lines": [v.as_dict() for v in variances],
    }


def get_variance_drivers(db: Session, month_a: Any, month_b: Any, line: Any) -> dict:
    ma, mb = _validate_month(month_a), _validate_month(month_b)
    line_name = str(line or "").strip()
    if line_name not in LINE_PNL_TYPE:
        raise ValueError(
            f"line must be one of {sorted(LINE_PNL_TYPE)} (driver analysis is not available for computed lines)."
        )
    drivers = find_variance_drivers(db, ma, mb, line_name)
    return {
        "month_a": ma,
        "month_b": mb,
        "line": line_name,
        "drivers": [d.as_dict() for d in drivers],
    }


def get_category_total(db: Session, category: Any, month: Any) -> dict:
    code = str(category or "").strip()
    m = _validate_month(month)
    cats = repo.category_totals_for_month(db, m, _pnl_type_for_category(db, code))
    matched = [c for c in cats if c[0] == code]
    if not matched:
        return {"month": m, "category_code": code, "category_name": code, "amount_cents": 0, "amount": 0.0, "transaction_count": 0}
    _, name, amt, cnt = matched[0]
    return {
        "month": m,
        "category_code": code,
        "category_name": name,
        "amount_cents": int(amt),
        "amount": cents_to_amount(int(amt)),
        "transaction_count": cnt,
    }


def _pnl_type_for_category(db: Session, code: str) -> str:
    from app.models.classification import Classification
    row = db.query(Classification.pnl_type).filter(Classification.category_code == code).limit(1).first()
    if row is None:
        raise ValueError(f"Unknown category '{code}'.")
    return row[0]


def get_transactions(
    db: Session,
    month: Any = None,
    category: Any = None,
    search: Any = None,
    review_status: Any = None,
    requires_review: Any = None,
    limit: Any = 25,
) -> dict:
    if month is not None:
        month = _validate_month(month)
    limit_n = min(max(_coerce_int(limit, 25), 1), 100)
    requires = None if requires_review is None else requires_review in (True, "true", "True", 1, "1", "yes")
    rows, total = repo.list_transactions(
        db,
        month=month,
        category_code=str(category or "").strip() or None,
        review_status=str(review_status or "").strip() or None,
        requires_review=requires,
        search=str(search or "").strip() or None,
        limit=limit_n,
        sort_by="date",
        sort_dir="asc",
    )
    return {
        "total_matching": total,
        "returned": len(rows),
        "transactions": [_txn_summary(t) for t in rows],
    }


def get_transaction(db: Session, transaction_id: Any) -> dict:
    tid = _validate_id(transaction_id)
    txn = repo.get_transaction_by_id(db, tid)
    if txn is None:
        return {"found": False, "transaction_id": tid}
    return {"found": True, "transaction": _txn_detail(txn)}


def get_review_items(db: Session, status: Any = None, limit: Any = 50) -> dict:
    status = str(status or "").strip() or None
    rows, total = repo.list_review_items(db, status=status, limit=min(_coerce_int(limit, 50), 200))
    return {
        "total_matching": total,
        "items": [
            {
                "id": it.id,
                "transaction_id": it.transaction.transaction_id,
                "status": it.status,
                "submitted_category_name": it.submitted_category_name,
                "submitted_category_code": it.submitted_category_code,
                "submitted_pnl_type": it.submitted_pnl_type,
                "submitted_confidence": float(it.submitted_confidence),
                "submitted_reasoning": it.submitted_reasoning,
                "note": it.note or "",
                "amount_cents": it.transaction.amount_cents,
                "amount": cents_to_amount(it.transaction.amount_cents),
                "date": it.transaction.date.isoformat(),
            }
            for it in rows
        ],
    }


def search_transactions(db: Session, query: Any, limit: Any = 20) -> dict:
    q = str(query or "").strip()
    if not q:
        return {"query": "", "total_matching": 0, "transactions": []}
    rows, total = repo.list_transactions(db, search=q, limit=min(_coerce_int(limit, 20), 50))
    return {
        "query": q,
        "total_matching": total,
        "transactions": [_txn_summary(t) for t in rows],
    }


def _txn_summary(txn) -> dict:
    cls = txn.classification
    return {
        "transaction_id": txn.transaction_id,
        "date": txn.date.isoformat(),
        "description": txn.description,
        "counterparty": txn.counterparty,
        "amount_cents": txn.amount_cents,
        "amount": cents_to_amount(txn.amount_cents),
        "method": txn.method,
        "category": cls.category_name if cls else None,
        "category_code": cls.category_code if cls else None,
        "pnl_type": cls.pnl_type if cls else None,
        "requires_review": bool(cls.requires_review) if cls else None,
        "review_status": cls.review_status if cls else None,
    }


def _txn_detail(txn) -> dict:
    d = _txn_summary(txn)
    cls = txn.classification
    d.update({
        "accounting_treatment": cls.accounting_treatment if cls else None,
        "confidence": float(cls.confidence) if cls else None,
        "classification_source": cls.source if cls else None,
        "reasoning": cls.reasoning if cls else None,
        "status": txn.status,
    })
    return d


# ---------------------------------------------------------------------------
# Tool registry (name -> schema, implementation)
# ---------------------------------------------------------------------------
TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "get_monthly_pnl",
            "description": "Return the monthly P&L (Revenue, COGS, Gross Profit, Payroll, Operating Expenses, Operating Profit) for a YYYY-MM month. Use this before answering any question about monthly profitability.",
            "parameters": {
                "type": "object",
                "properties": {
                    "month": {"type": "string", "pattern": "^\\d{4}-\\d{2}$", "description": "Month as YYYY-MM, e.g. 2026-03."}
                },
                "required": ["month"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_months",
            "description": "Compare two months of P&L and return per-line variance (absolute and percentage). Use when asked to compare months or explain changes between months.",
            "parameters": {
                "type": "object",
                "properties": {
                    "month_a": {"type": "string", "pattern": "^\\d{4}-\\d{2}$"},
                    "month_b": {"type": "string", "pattern": "^\\d{4}-\\d{2}$"},
                },
                "required": ["month_a", "month_b"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_variance",
            "description": "Return materiality-flagged month-over-month variance for all P&L lines.",
            "parameters": {
                "type": "object",
                "properties": {
                    "month_a": {"type": "string", "pattern": "^\\d{4}-\\d{2}$"},
                    "month_b": {"type": "string", "pattern": "^\\d{4}-\\d{2}$"},
                    "materiality_percent": {"type": "number", "description": "Optional percentage threshold.", "minimum": 0},
                    "materiality_abs_cents": {"type": "integer", "description": "Optional absolute threshold in cents.", "minimum": 0},
                },
                "required": ["month_a", "month_b"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_variance_drivers",
            "description": "Return category-level drivers of a line's variance between two months, including the transactions behind each driver.",
            "parameters": {
                "type": "object",
                "properties": {
                    "month_a": {"type": "string", "pattern": "^\\d{4}-\\d{2}$"},
                    "month_b": {"type": "string", "pattern": "^\\d{4}-\\d{2}$"},
                    "line": {"type": "string", "enum": ["revenue", "cogs", "payroll", "operating_expenses"], "description": "Which P&L line to analyze."},
                },
                "required": ["month_a", "month_b", "line"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_category_total",
            "description": "Return the total for a single category code in a month. Category codes include food_sales, beverage_sales, catering_revenue, delivery_revenue, refunds_discounts, delivery_commissions, food_inventory, beverage_inventory, catering_food_purchases, wages_salaries, payroll_taxes_benefits, rent, software_subscriptions, insurance, professional_services, utilities, communications, marketing, repairs_maintenance, supplies_packaging, cleaning_linen, licenses_permits.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "month": {"type": "string", "pattern": "^\\d{4}-\\d{2}$"},
                },
                "required": ["category", "month"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_transactions",
            "description": "List transactions with optional filters for month, category, text search, or review status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "month": {"type": "string", "pattern": "^\\d{4}-\\d{2}$"},
                    "category": {"type": "string"},
                    "search": {"type": "string"},
                    "review_status": {"type": "string", "enum": ["none", "pending", "approved", "corrected", "marked_non_pnl"]},
                    "requires_review": {"type": "boolean"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_transaction",
            "description": "Return full detail for a single transaction id (e.g. TX1234) including classification and accounting treatment.",
            "parameters": {
                "type": "object",
                "properties": {"transaction_id": {"type": "string"}},
                "required": ["transaction_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_review_items",
            "description": "Return transactions currently in the review queue (status pending), or by a specific status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["pending", "approved", "corrected", "marked_non_pnl"]},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_transactions",
            "description": "Free-text search across transaction ids, descriptions and counterparties.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                },
                "required": ["query"],
            },
        },
    },
]

TOOL_FUNCTIONS: dict[str, Callable] = {
    "get_monthly_pnl": get_monthly_pnl,
    "compare_months": compare_months,
    "get_variance": get_variance,
    "get_variance_drivers": get_variance_drivers,
    "get_category_total": get_category_total,
    "get_transactions": get_transactions,
    "get_transaction": get_transaction,
    "get_review_items": get_review_items,
    "search_transactions": search_transactions,
}


__all__ = [
    "TOOL_SCHEMAS",
    "TOOL_FUNCTIONS",
    "get_monthly_pnl",
    "compare_months",
    "get_variance",
    "get_variance_drivers",
    "get_category_total",
    "get_transactions",
    "get_transaction",
    "get_review_items",
    "search_transactions",
    "line_transactions_for_drilldown",
]