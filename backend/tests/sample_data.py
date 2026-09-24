"""Shared multi-month sample data for variance tests."""
import datetime

from app.financial.money import value_to_cents
from app.models.transaction import Transaction


def _c(db, tid, year, month, day, desc, cp, amount, method="ACH"):
    from app.services.classification import build_classification, persist_classification

    t = Transaction(transaction_id=tid, date=datetime.date(year, month, day), description=desc,
                    counterparty=cp, amount_cents=value_to_cents(amount), method=method)
    db.add(t)
    db.flush()
    data = build_classification(description=desc, counterparty=cp, method=method, amount_cents=t.amount_cents)
    persist_classification(db, t, data, actor="system")


def seed_two_months(db) -> None:
    # ---- January
    _c(db, "T1001", 2026, 1, 8, "POS batch deposit - food sales week 1", "Toast POS", 1000.00, "Bank deposit")
    _c(db, "T1002", 2026, 1, 8, "POS batch deposit - beverage sales week 1", "Toast POS", 400.00, "Bank deposit")
    _c(db, "T1003", 2026, 1, 9, "Refunds and discounts week 1", "Toast POS", -50.00, "POS adjustment")
    _c(db, "T1004", 2026, 1, 10, "Food inventory purchase - Sysco", "Sysco", -300.00, "ACH/card")
    _c(db, "T1005", 2026, 1, 12, "Payroll - hourly kitchen and FOH wages", "Gusto Payroll", -200.00, "ACH")
    _c(db, "T1006", 2026, 1, 13, "Rent", "Landlord", -100.00, "ACH")

    # ---- February (food sales up a lot, beverage same)
    _c(db, "T2001", 2026, 2, 8, "POS batch deposit - food sales week 1", "Toast POS", 1650.00, "Bank deposit")
    _c(db, "T2002", 2026, 2, 8, "POS batch deposit - beverage sales week 1", "Toast POS", 400.00, "Bank deposit")
    _c(db, "T2003", 2026, 2, 10, "Food inventory purchase - Sysco", "Sysco", -450.00, "ACH/card")
    _c(db, "T2005", 2026, 2, 12, "Payroll - hourly kitchen and FOH wages", "Gusto Payroll", -210.00, "ACH")
    _c(db, "T2006", 2026, 2, 13, "Rent", "Landlord", -100.00, "ACH")