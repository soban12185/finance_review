from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.errors import ValidationError
from app.db.session import get_db
from app.financial import engine
from app.financial.money import cents_to_amount
from app.repositories import transaction_repo as repo

router = APIRouter()


def _line_out(lt: engine.LineTotal) -> dict:
    return {
        "line": lt.line,
        "label": lt.label,
        "amount_cents": lt.amount_cents,
        "amount": lt.amount,
        "transaction_count": lt.transaction_count,
        "is_computed": lt.is_computed,
        "categories": [
            {
                "category_code": c.category_code,
                "category_name": c.category_name,
                "amount_cents": c.amount_cents,
                "amount": c.amount,
                "transaction_count": c.transaction_count,
            }
            for c in lt.categories
        ],
    }


@router.get("/{month}")
def monthly_pnl(month: str = Path(pattern=r"^\d{4}-\d{2}$"), db: Session = Depends(get_db)):
    pnl = engine.calculate_monthly_pnl(db, month)
    return {
        "month": month,
        "transaction_count": pnl.transaction_count,
        "net_cash_cents": pnl.net_cash_cents,
        "net_cash": pnl.net_cash,
        "pending_review_count": pnl.pending_review_count,
        "lines": {line: _line_out(lt) for line, lt in pnl.lines.items()},
    }


@router.get("/{month}/drilldown/{line}")
def monthly_pnl_drilldown(
    month: str = Path(pattern=r"^\d{4}-\d{2}$"),
    line: str = Path(...),
    db: Session = Depends(get_db),
):
    pnl = engine.calculate_monthly_pnl(db, month)
    if line not in pnl.lines:
        raise ValidationError(f"Unknown P&L line '{line}'.")
    if line in engine.COMPUTED_LINES:
        lt = pnl.lines[line]
        return {
            "month": month,
            "line": line,
            "label": lt.label,
            "amount_cents": lt.amount_cents,
            "amount": cents_to_amount(lt.amount_cents),
            "computed": True,
            "components": [
                {"line": k, "label": v.label, "amount_cents": v.amount_cents, "amount": v.amount}
                for k, v in pnl.lines.items() if k in ("revenue", "cogs", "payroll", "operating_expenses")
            ],
            "transactions": [],
        }
    try:
        rows = engine.line_transactions_for_drilldown(db, month, line)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    return {
        "month": month,
        "line": line,
        "label": pnl.lines[line].label,
        "amount_cents": pnl.lines[line].amount_cents,
        "amount": pnl.lines[line].amount,
        "computed": False,
        "components": [],
        "transactions": [
            {
                "transaction_id": t.transaction_id,
                "date": t.date.isoformat(),
                "description": t.description,
                "counterparty": t.counterparty,
                "amount_cents": t.amount_cents,
                "amount": cents_to_amount(t.amount_cents),
                "method": t.method,
                "category": t.classification.category_name if t.classification else None,
                "category_code": t.classification.category_code if t.classification else None,
            }
            for t in rows
        ],
    }


@router.get("/months/available")
def months(db: Session = Depends(get_db)):
    return list(repo.available_months(db))