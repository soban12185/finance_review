"""Review queue: approve / change / mark non-P&L + audit trail."""
import pytest

from app.core.constants import ReviewStatus
from app.core.errors import ValidationError
from app.models.audit_event import AuditEvent
from app.models.classification import Classification, ClassificationHistory
from app.models.review_item import ReviewItem
from app.models.transaction import Transaction
from app.services import review as review_service
from app.services.classification import build_classification, persist_classification


@pytest.fixture()
def pending_item(db_session):
    t = Transaction(transaction_id="RV1", date=__import__("datetime").date(2026, 1, 15),
                    description="Sales tax remittance", counterparty="Florida Dept. of Revenue",
                    amount_cents=-6000, method="ACH")
    db_session.add(t)
    db_session.flush()
    data = build_classification(description=t.description, counterparty=t.counterparty,
                                method=t.method, amount_cents=t.amount_cents)
    persist_classification(db_session, t, data, actor="system")
    item = db_session.query(ReviewItem).filter(ReviewItem.transaction_id == t.id).one()
    return item


def test_approve_review(pending_item, db_session):
    item = review_service.approve_review(db_session, pending_item.id, note="looks right", actor="analyst")
    db_session.refresh(item)
    assert item.status == ReviewStatus.APPROVED.value
    txn = db_session.get(Transaction, item.transaction_id)
    assert txn.classification.review_status == ReviewStatus.APPROVED.value
    assert txn.classification.requires_review is False
    evt = db_session.query(AuditEvent).filter(AuditEvent.entity_id == str(item.id)).one()
    assert evt.action == "review_approved"


def test_change_classification(pending_item, db_session):
    before = db_session.get(Transaction, pending_item.transaction_id).classification
    item = review_service.change_classification(db_session, pending_item.id, "insurance",
                                                note="manual override", actor="analyst")
    db_session.refresh(before)
    assert before.category_code == "insurance"
    assert before.source == "manual"
    assert before.version == 2
    item = db_session.get(ReviewItem, item.id)
    assert item.status == ReviewStatus.CORRECTED.value
    assert item.decided_category_name == "Insurance"
    # history recorded
    assert db_session.query(ClassificationHistory).filter(
        ClassificationHistory.transaction_id == before.transaction_id).count() == 1
    # audit trail with old/new
    evt = db_session.query(AuditEvent).filter(AuditEvent.entity_id == str(item.id)).one()
    assert evt.action == "review_corrected"
    assert evt.old_value["category_code"] == "sales_tax_remittance"
    assert evt.new_value["category_code"] == "insurance"


def test_mark_non_pnl(pending_item, db_session):
    item = review_service.mark_non_pnl(db_session, pending_item.id, "other_non_pnl",
                                       note="confirm balance sheet", actor="analyst")
    txn = db_session.get(Transaction, item.transaction_id)
    assert txn.classification.pnl_type == "non_pnl"
    assert txn.classification.review_status == ReviewStatus.MARKED_NON_PNL.value


def test_mark_non_pnl_rejects_pnl_category(pending_item, db_session):
    with pytest.raises(ValidationError):
        review_service.mark_non_pnl(db_session, pending_item.id, "food_sales")


def test_change_unknown_category(pending_item, db_session):
    with pytest.raises(ValidationError):
        review_service.change_classification(db_session, pending_item.id, "no_such_cat")


def test_resolve_twice_rejected(pending_item, db_session):
    review_service.approve_review(db_session, pending_item.id, actor="a")
    with pytest.raises(ValidationError):
        review_service.approve_review(db_session, pending_item.id, actor="b")


def test_already_reviewed_keeps_manual_value(pending_item, db_session):
    """The AI must never overwrite a manual correction."""
    review_service.change_classification(db_session, pending_item.id, "insurance", note="correct", actor="analyst")
    txn = db_session.get(Transaction, pending_item.transaction_id)

    # simulate an auto-classifier attempting to overwrite:
    data = build_classification(description=txn.description, counterparty=txn.counterparty,
                                method=txn.method, amount_cents=txn.amount_cents)
    data = __import__("dataclasses").replace(data, category_code="food_inventory", category_name="Food Inventory",
                                             subcategory="Food Inventory", pnl_type="cogs")
    persist_classification(db_session, txn, data, actor="system")

    db_session.refresh(txn)
    assert txn.classification.category_code == "insurance"
    assert txn.classification.source == "manual"