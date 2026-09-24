from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.errors import ValidationError
from app.db.session import get_db
from app.financial import engine
from app.financial.variance import calculate_month_variance, find_variance_drivers

router = APIRouter()


def _validate_month_pair(month_a: str, month_b: str) -> None:
    import re
    pattern = r"^\d{4}-(0[1-9]|1[0-2])$"
    if not re.match(pattern, month_a) or not re.match(pattern, month_b):
        raise ValidationError("Month arguments must be YYYY-MM.")


@router.get("")
def variance_report(
    month_a: str = Query(...),
    month_b: str = Query(...),
    materiality_percent: float | None = Query(default=None, ge=0, le=1000),
    materiality_abs_cents: int | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
):
    _validate_month_pair(month_a, month_b)
    pa = engine.calculate_monthly_pnl(db, month_a)
    pb = engine.calculate_monthly_pnl(db, month_b)
    variances = calculate_month_variance(
        pa,
        pb,
        materiality_percent=materiality_percent,
        materiality_abs_cents=materiality_abs_cents,
    )
    return {
        "month_a": month_a,
        "month_b": month_b,
        "materiality": {
            "percent": materiality_percent,
            "abs_cents": materiality_abs_cents,
        },
        "lines": [v.as_dict() for v in variances],
    }


@router.get("/drivers")
def variance_drivers(
    month_a: str = Query(...),
    month_b: str = Query(...),
    line: str = Query(...),
    db: Session = Depends(get_db),
):
    _validate_month_pair(month_a, month_b)
    try:
        drivers = find_variance_drivers(db, month_a, month_b, line)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    pa = engine.calculate_monthly_pnl(db, month_a)
    pb = engine.calculate_monthly_pnl(db, month_b)
    line_variance = pb.lines[line].amount_cents - pa.lines[line].amount_cents
    return {
        "month_a": month_a,
        "month_b": month_b,
        "line": line,
        "label": pb.lines[line].label,
        "line_variance_cents": line_variance,
        "drivers": [d.as_dict() for d in drivers],
    }