"""AI tool layer: controlled functions the analyst is allowed to call."""
import datetime

import pytest

from app.ai import tools as ai_tools
from app.financial.money import value_to_cents
from app.models.transaction import Transaction


def _add_txn(db, tid, year, month, day, desc, cp, amount, method):
    from app.services.classification import build_classification, persist_classification

    t = Transaction(transaction_id=tid, date=datetime.date(year, month, day), description=desc,
                    counterparty=cp, amount_cents=value_to_cents(amount), method=method)
    db.add(t)
    db.flush()
    data = build_classification(description=desc, counterparty=cp, method=method, amount_cents=t.amount_cents)
    persist_classification(db, t, data, actor="system")


def _seed(db):
    _add_txn(db, "T0001", 2026, 3, 10, "POS batch deposit - food sales week 1", "Toast POS", 2000.00, "Bank deposit")
    _add_txn(db, "T0002", 2026, 3, 11, "Food inventory purchase - Sysco", "Sysco", -600.00, "ACH/card")
    _add_txn(db, "T0003", 2026, 3, 12, "Payroll - hourly kitchen and FOH wages", "Gusto Payroll", -300.00, "ACH")
    _add_txn(db, "T0004", 2026, 3, 13, "Sales tax remittance", "Florida Dept. of Revenue", -100.00, "ACH")


def test_get_monthly_pnl(db_session):
    _seed(db_session)
    res = ai_tools.get_monthly_pnl(db_session, "2026-03")
    assert res["lines"]["revenue"]["amount_cents"] == value_to_cents("2000.00")
    assert res["lines"]["cogs"]["amount_cents"] == value_to_cents("-600.00")
    # gross profit = 2000 - 600; operating profit = 1400 - 300 = 1100
    assert res["lines"]["gross_profit"]["amount_cents"] == value_to_cents("1400.00")
    assert res["lines"]["operating_profit"]["amount_cents"] == value_to_cents("1100.00")
    assert res["transaction_count"] >= 4


def test_get_monthly_pnl_invalid_month(db_session):
    _seed(db_session)
    with pytest.raises(ValueError):
        ai_tools.get_monthly_pnl(db_session, "march")


def test_compare_months(db_session):
    _seed(db_session)
    _add_txn(db_session, "T0101", 2026, 2, 10, "POS batch deposit - food sales week 1", "Toast POS", 1500.00, "Bank deposit")
    res = ai_tools.compare_months(db_session, "2026-02", "2026-03")
    lines = {l["line"]: l for l in res["lines"]}
    assert lines["revenue"]["absolute_cents"] == value_to_cents("500.00")
    assert lines["revenue"]["percent"] == pytest.approx(33.3333)


def test_get_variance_drivers(db_session):
    _seed(db_session)
    _add_txn(db_session, "T0101", 2026, 2, 10, "POS batch deposit - food sales week 1", "Toast POS", 1500.00, "Bank deposit")
    res = ai_tools.get_variance_drivers(db_session, "2026-02", "2026-03", "revenue")
    food = [d for d in res["drivers"] if d["category_code"] == "food_sales"][0]
    assert food["absolute_cents"] == value_to_cents("500.00")
    assert food["transactions"][0]["transaction_id"] == "T0001"
    with pytest.raises(ValueError):
        ai_tools.get_variance_drivers(db_session, "2026-02", "2026-03", "gross_profit")


def test_get_category_total(db_session):
    _seed(db_session)
    res = ai_tools.get_category_total(db_session, "food_sales", "2026-03")
    assert res["amount_cents"] == value_to_cents("2000.00")
    assert res["transaction_count"] == 1


def test_get_transaction_found_and_not(db_session):
    _seed(db_session)
    res = ai_tools.get_transaction(db_session, "T0001")
    assert res["found"] is True
    assert res["transaction"]["category_code"] == "food_sales"
    missing = ai_tools.get_transaction(db_session, "ZZZZ")
    assert missing["found"] is False


def test_get_transactions_filters(db_session):
    _seed(db_session)
    res = ai_tools.get_transactions(db_session, month="2026-03", category="food_inventory")
    assert res["total_matching"] == 1
    assert res["transactions"][0]["transaction_id"] == "T0002"

    res2 = ai_tools.get_transactions(db_session, search="gusto")
    assert res2["total_matching"] == 1
    assert res2["transactions"][0]["transaction_id"] == "T0003"


def test_get_review_items(db_session):
    _seed(db_session)
    res = ai_tools.get_review_items(db_session, status="pending")
    ids = {it["transaction_id"] for it in res["items"]}
    assert "T0004" in ids  # sales tax remittance -> review
    assert "T0001" not in ids


def test_search_transactions(db_session):
    _seed(db_session)
    res = ai_tools.search_transactions(db_session, "sysco")
    assert res["total_matching"] == 1
    assert res["transactions"][0]["transaction_id"] == "T0002"


def test_all_tools_registered():
    assert set(ai_tools.TOOL_FUNCTIONS) == {s["function"]["name"] for s in ai_tools.TOOL_SCHEMAS}
    assert len(ai_tools.TOOL_FUNCTIONS) >= 9