from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.classification.catalog import CATALOG
from app.db.session import get_db

router = APIRouter()


@router.get("")
def list_categories(db: Session = Depends(get_db)):
    return [
        {
            "code": c.code,
            "name": c.name,
            "subcategory": c.subcategory,
            "pnl_type": c.pnl_type,
            "accounting_treatment": c.accounting_treatment,
            "is_contra": c.is_contra,
            "description": c.description,
        }
        for c in sorted(CATALOG, key=lambda c: c.sort_order)
    ]


@router.get("/non-pnl")
def non_pnl_categories():
    from app.core.constants import PnlType
    return [
        {"code": c.code, "name": c.name, "accounting_treatment": c.accounting_treatment}
        for c in CATALOG if c.pnl_type == PnlType.NON_PNL.value
    ]