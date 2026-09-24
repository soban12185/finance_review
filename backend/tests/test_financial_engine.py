"""P&L engine: deterministic totals from underlying transactions."""
import datetime

from app.financial import engine
from app.financial.money import value_to_cents
from app.repositories import transaction_repo as repo
from tests.conftest import seed_sample_dataset


def _insert_txn(db, tid, day, desc, cp, amount, method):
    from app.services.classification import build_classification, persist_classification
    from app.models.transaction import Transaction

    t = Transaction(transaction_id=tid, date=datetime.date(2026, 1, day), description=desc,
                    counterparty=cp, amount_cents=value_to_cents(amount), method=method)
    db.add(t)
    db.flush()
    data = build_classification(description=desc, counterparty=cp, method=method, amount_cents=t.amount_cents)
    persist_classification(db, t, data, actor="system")


def _seed_known(db):
    _insert_txn(db, "R1", 1, "POS batch deposit - food sales week 1", "Toast POS", 1000.00, "Bank deposit")
    _insert_txn(db, "R2", 2, "POS batch deposit - beverage sales week 1", "Toast POS", 400.00, "Bank deposit")
    _insert_txn(db, "R3", 3, "Refunds and discounts week 1", "Toast POS", -100.00, "POS adjustment")
    _insert_txn(db, "C1", 4, "Food inventory purchase - Sysco", "Sysco", -300.00, "ACH/card")
    _insert_txn(db, "C2", 5, "Beverage inventory purchase - Craft Beer Distributor", "Craft Beer Distributor", -50.00, "ACH/card")
    _insert_txn(db, "P1", 6, "Payroll - hourly kitchen and FOH wages", "Gusto Payroll", -200.00, "ACH")
    _insert_txn(db, "P2", 7, "Payroll taxes and benefits", "Gusto Payroll", -25.00, "ACH")
    _insert_txn(db, "O1", 8, "Rent", "Landlord", -100.00, "ACH")
    _insert_txn(db, "N1", 9, "Equipment purchase - new oven", "Restaurant Equipment World", -1000.00, "ACH")


def test_arithmetic_primitives():
    gp = engine.calculate_gross_profit(value_to_cents("1000.00"), value_to_cents("-400.00"))
    assert engine.calculate_operating_profit(gp, value_to_cents("-200.00"), value_to_cents("-100.00")) == value_to_cents("300.00")
    # Gross Profit = Revenue - |COGS|
    assert engine.calculate_gross_profit(value_to_cents("1000.00"), value_to_cents("-400.00")) == value_to_cents("600.00")


def test_monthly_pnl_full(db_session):
    _seed_known(db_session)
    pnl = engine.calculate_monthly_pnl(db_session, "2026-01")
    lines = pnl.lines

    # Revenue net of contra-revenue: 1000 + 400 - 100 = 1300
    assert lines["revenue"].amount_cents == value_to_cents("1300.00")
    assert lines["revenue"].transaction_count == 3

    # COGS: -(300 + 50)
    assert lines["cogs"].amount_cents == value_to_cents("-350.00")

    # Gross profit = 1300 - 350
    assert lines["gross_profit"].amount_cents == value_to_cents("950.00")

    # Payroll = -(200 + 25)
    assert lines["payroll"].amount_cents == value_to_cents("-225.00")

    # Opex = -100
    assert lines["operating_expenses"].amount_cents == value_to_cents("-100.00")

    # Operating profit = 950 - 225 - 100
    assert lines["operating_profit"].amount_cents == value_to_cents("625.00")

    # Non-P&L equipment purchase is excluded from every line
    assert lines["operating_expenses"].transaction_count == 1
    assert pnl.transaction_count >= 8
    assert pnl.net_cash_cents == value_to_cents("1000.00") + value_to_cents("400.00") - value_to_cents("100.00") \
        - value_to_cents("350.00") - value_to_cents("225.00") - value_to_cents("100.00") - value_to_cents("1000.00")


def test_individual_calculators(db_session):
    _seed_known(db_session)
    assert engine.calculate_revenue(db_session, "2026-01") == value_to_cents("1300.00")
    assert engine.calculate_cogs(db_session, "2026-01") == value_to_cents("-350.00")
    assert engine.calculate_payroll(db_session, "2026-01") == value_to_cents("-225.00")
    assert engine.calculate_operating_expenses(db_session, "2026-01") == value_to_cents("-100.00")


def test_pnl_category_breakdown(db_session):
    _seed_known(db_session)
    pnl = engine.calculate_monthly_pnl(db_session, "2026-01")
    revenue_cats = {c.category_code: c.amount_cents for c in pnl.lines["revenue"].categories}
    assert revenue_cats["food_sales"] == value_to_cents("1000.00")
    assert revenue_cats["beverage_sales"] == value_to_cents("400.00")
    assert revenue_cats["refunds_discounts"] == value_to_cents("-100.00")


def test_drilldown(db_session):
    _seed_known(db_session)
    rows = engine.line_transactions_for_drilldown(db_session, "2026-01", "revenue")
    assert len(rows) == 3
    assert {r.transaction_id for r in rows} == {"R1", "R2", "R3"}


def test_reclass_affects_pnl(db_session):
    """Correcting a transaction in the review queue must change the P&L."""
    _seed_known(db_session)
    pnl_before = engine.calculate_monthly_pnl(db_session, "2026-01")

    # move "Refunds and discounts" to be treated as opex (a wrong-ish but valid correction)
    from app.models.transaction import Transaction
    from app.models.review_item import ReviewItem
    txn = db_session.query(Transaction).filter(Transaction.transaction_id == "R3").one()
    cls = txn.classification
    item = ReviewItem(transaction_id=txn.id, status="pending",
                      submitted_category_code=cls.category_code, submitted_category_name=cls.category_name,
                      submitted_pnl_type=cls.pnl_type, submitted_accounting_treatment=cls.accounting_treatment,
                      submitted_confidence=cls.confidence, submitted_source=cls.source, submitted_reasoning="x")
    db_session.add(item)
    db_session.commit()

    from app.services.review import change_classification
    change_classification(db_session, item.id, "supplies_packaging", note="reclass as supplies", actor="tester")

    pnl_after = engine.calculate_monthly_pnl(db_session, "2026-01")
    assert pnl_after.lines["revenue"].amount_cents == pnl_before.lines["revenue"].amount_cents + value_to_cents("100.00")
    assert pnl_after.lines["operating_expenses"].amount_cents == pnl_before.lines["operating_expenses"].amount_cents - value_to_cents("100.00")


def test_seed_sample_dataset_utility(db_session):
    from tests.conftest import SAMPLE_ROWS

    inserted = seed_sample_dataset(db_session)
    assert inserted == len(SAMPLE_ROWS)