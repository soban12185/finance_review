"""Hybrid classification: rules first, LLM fallback, review queue seeding."""
from app.classification.rules import apply_rules
from app.core.constants import ClassificationSource, PnlType, ReviewStatus
from app.models.classification import Classification
from app.models.review_item import ReviewItem
from app.services.classification import build_classification, persist_classification
from app.models.transaction import Transaction


def _txn(db, tid="TX1"):
    from datetime import date

    t = Transaction(transaction_id=tid, date=date(2026, 1, 1), description="x",
                    counterparty="y", amount_cents=1000, method="ACH")
    db.add(t)
    db.flush()
    return t


# ---------------------------------------------------------------------------
# Rule engine
# ---------------------------------------------------------------------------
def test_rule_revenue():
    r = apply_rules(description="POS batch deposit - food sales week 2", counterparty="Toast POS",
                    method="Bank deposit", amount_cents=10000)
    assert r.category.code == "food_sales"
    assert r.confidence >= 0.95
    assert not r.requires_review


def test_rule_contra_revenue():
    r = apply_rules(description="Refunds and discounts week 1", counterparty="Toast POS",
                    method="POS adjustment", amount_cents=-1000)
    assert r.category.code == "refunds_discounts"
    assert r.category.is_contra is True
    assert r.category.pnl_type == PnlType.REVENUE.value


def test_rule_cogs():
    r = apply_rules(description="Food inventory purchase - Sysco", counterparty="Sysco",
                    method="ACH/card", amount_cents=-4000)
    assert r.category.code == "food_inventory"
    assert r.category.pnl_type == PnlType.COGS.value


def test_rule_payroll():
    r = apply_rules(description="Payroll - hourly kitchen and FOH wages", counterparty="Gusto Payroll",
                    method="ACH", amount_cents=-5000)
    assert r.category.code == "wages_salaries"
    assert r.category.pnl_type == PnlType.PAYROLL.value


def test_rule_opex():
    r = apply_rules(description="Utilities - electric/gas/water", counterparty="City Utilities",
                    method="ACH", amount_cents=-2000)
    assert r.category.code == "utilities"
    assert r.category.pnl_type == PnlType.OPERATING_EXPENSE.value


def test_rule_non_pnl_forces_review():
    r = apply_rules(description="Equipment purchase - new oven", counterparty="Restaurant Equipment World",
                    method="ACH", amount_cents=-5000)
    assert r.category.code == "capex_equipment"
    assert r.category.pnl_type == PnlType.NON_PNL.value
    assert r.requires_review is True

    r2 = apply_rules(description="Gift card sales deposit", counterparty="Toast POS",
                     method="Bank deposit", amount_cents=1000)
    assert r2.category.code == "gift_card_deposits"
    assert r2.category.pnl_type == PnlType.NON_PNL.value
    assert r2.requires_review is True


def test_rule_no_match():
    r = apply_rules(description="Something totally unusual and unique", counterparty="X Corp",
                    method="Wire", amount_cents=100)
    assert r is None


# ---------------------------------------------------------------------------
# build_classification (hybrid, LLM disabled in tests)
# ---------------------------------------------------------------------------
def test_build_classification_high_confidence_no_llm():
    data = build_classification(description="Rent", counterparty="Landlord", method="ACH", amount_cents=-9000)
    assert data.category_code == "rent"
    assert data.source == ClassificationSource.RULE.value
    assert data.requires_review is False


def test_build_classification_uncategorized_fallback():
    data = build_classification(description="Mystery fee", counterparty="??", method="Wire", amount_cents=-10)
    assert data.category_code == "uncategorized"
    assert data.requires_review is True


# ---------------------------------------------------------------------------
# Persistence + review queue
# ---------------------------------------------------------------------------
def test_persist_classification_creates_review_item(db_session):
    txn = _txn(db_session)
    data = build_classification(description="Sales tax remittance", counterparty="Florida Dept. of Revenue",
                                method="ACH", amount_cents=-6000)
    persist_classification(db_session, txn, data, actor="system")
    cls = db_session.query(Classification).filter(Classification.transaction_id == txn.id).one()
    assert cls.requires_review is True
    item = db_session.query(ReviewItem).filter(ReviewItem.transaction_id == txn.id).one()
    assert item.status == ReviewStatus.PENDING.value
    assert item.submitted_category_code == "sales_tax_remittance"


def test_persist_classification_high_confidence_no_review(db_session):
    txn = _txn(db_session)
    data = build_classification(description="Rent", counterparty="Landlord", method="ACH", amount_cents=-9000)
    persist_classification(db_session, txn, data)
    cls = db_session.query(Classification).filter(Classification.transaction_id == txn.id).one()
    assert cls.requires_review is False
    assert cls.review_status == ReviewStatus.NONE.value
    assert db_session.query(ReviewItem).filter(ReviewItem.transaction_id == txn.id).count() == 0


def test_version_history_on_reclass(db_session):
    from datetime import date
    txn = _txn(db_session)
    data = build_classification(description="Repairs and maintenance", counterparty="Kitchen Repair Co.",
                                method="Card", amount_cents=-1000)
    persist_classification(db_session, txn, data)
    cls = db_session.query(Classification).filter(Classification.transaction_id == txn.id).one()
    assert cls.version == 1

    # manual re-classification bumps the version and records history
    from app.services.review import change_classification
    from app.models.review_item import ReviewItem
    item = ReviewItem(transaction_id=txn.id, status="pending",
                      submitted_category_code=cls.category_code, submitted_category_name=cls.category_name,
                      submitted_pnl_type=cls.pnl_type, submitted_accounting_treatment=cls.accounting_treatment,
                      submitted_confidence=cls.confidence, submitted_source=cls.source,
                      submitted_reasoning=cls.reasoning)
    db_session.add(item)
    db_session.commit()
    change_classification(db_session, item.id, "insurance", note="test", actor="analyst")
    from app.models.classification import ClassificationHistory
    assert cls.version == 2
    assert db_session.query(ClassificationHistory).filter(ClassificationHistory.transaction_id == txn.id).count() == 1
    assert cls.category_code == "insurance"
    assert cls.source == ClassificationSource.MANUAL.value