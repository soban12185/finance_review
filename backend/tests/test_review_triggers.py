"""Review-queue triggers: explainable reasons, the full resolution workflow,
and P&L integration.

Covers the required scenarios:
* low-confidence items surface with the confidence threshold in the reason
* accounting-judgment (non-P&L / correctional treatments) items surface
* unusual amounts are detected against the same-category peer set
* description/rule-conflicts surface as data inconsistency
* normal high-confidence transactions are NOT surfaced (no over-flagging)
* approve / reclassify / mark-non-P&L resolve the item, keep reasons, and
  change the P&L deterministically
* multiple triggers preserve every reason
* the classifier's explicit "requires review" flag is honoured
* the actual dataset items (equipment / oven, sales tax, gift cards) appear
"""
import datetime
from dataclasses import replace

import pytest

from app.core.constants import ReviewSource, ReviewStatus
from app.financial import engine
from app.models.audit_event import AuditEvent
from app.models.classification import Classification
from app.models.review_item import ReviewItem
from app.models.transaction import Transaction
from app.services import review as review_service
from app.services.classification import build_classification, persist_classification


def _insert(db, tid="T1", day=1, desc="x", cp="y", amount=100.00, method="ACH"):
    t = Transaction(transaction_id=tid, date=datetime.date(2026, 1, day), description=desc,
                    counterparty=cp, amount_cents=int(round(amount * 100)), method=method)
    db.add(t)
    db.flush()
    return t


def _classify(db, txn, data=None, actor="system"):
    data = data or build_classification(description=txn.description, counterparty=txn.counterparty,
                                        method=txn.method, amount_cents=txn.amount_cents)
    persist_classification(db, txn, data, actor=actor)
    return data


def _pending_item(db, txn):
    return db.query(ReviewItem).filter(ReviewItem.transaction_id == txn.id, ReviewItem.status == ReviewStatus.PENDING.value).one()


# ---------------------------------------------------------------------------
# Triggers
# ---------------------------------------------------------------------------
def test_low_confidence_surfaces_with_threshold(db_session):
    txn = _insert(db_session, "L1", desc="Rent", cp="Landlord", amount=-900)
    data = build_classification(description=txn.description, counterparty=txn.counterparty,
                                method=txn.method, amount_cents=txn.amount_cents)
    # same category, but re-persisted with a below-threshold confidence
    data = replace(data, confidence=0.50, requires_review=False)
    _classify(db_session, txn, data)

    item = _pending_item(db_session, txn)
    assert ReviewSource.LOW_CONFIDENCE.value in item.review_sources
    reason = [r for s, r in zip(item.review_sources, item.review_reasons)
              if s == ReviewSource.LOW_CONFIDENCE.value][0]
    assert "50%" in reason and "review threshold" in reason


def test_accounting_judgment_surfaces_non_pnl(db_session):
    txn = _insert(db_session, "J1", desc="Equipment purchase - new oven", cp="Restaurant Equipment World", amount=-5000)
    data = _classify(db_session, txn)

    # explicit non-P&L / judgement treatment -> must be confirmed by a human
    data = replace(data, pnl_type="non_pnl", accounting_treatment="capital_expenditure")
    _classify(db_session, txn, data)

    item = _pending_item(db_session, txn)
    assert ReviewSource.ACCOUNTING_JUDGMENT.value in item.review_sources
    reason = [r for s, r in zip(item.review_sources, item.review_reasons)
              if s == ReviewSource.ACCOUNTING_JUDGMENT.value][0]
    assert "Accounting treatment requires human confirmation" in reason


def test_unusual_amount_detected_against_peer_set(db_session):
    peers = []
    for i, amount in enumerate([400.00, 300.00, 350.00, 320.00], start=1):
        t = _insert(db_session, f"U{i}", day=i, desc="Food inventory purchase - Sysco", cp="Sysco", amount=-amount)
        _classify(db_session, t)
        peers.append(t)

    # a single outlier should surface - peers do not
    outlier = _insert(db_session, "U5", day=5, desc="Food inventory purchase - Sysco", cp="Sysco", amount=-9000)
    data = _classify(db_session, outlier)
    assert data.category_code == "food_inventory"

    item = _pending_item(db_session, outlier)
    assert ReviewSource.UNUSUAL_TRANSACTION.value in item.review_sources
    reason = [r for s, r in zip(item.review_sources, item.review_reasons)
              if s == ReviewSource.UNUSUAL_TRANSACTION.value][0]
    assert "unusually high" in reason

    # the four normal-priced peers never got flagged while peers were missing
    assert all(
        db_session.query(ReviewItem).filter(ReviewItem.transaction_id == p.id).count() == 0
        for p in peers
    )


def test_data_inconsistency_rule_conflict(db_session):
    # description/rule strongly suggests food_inventory, but the assigned
    # classification is marketing -> contradiction surfaced
    txn = _insert(db_session, "D1", desc="Food inventory purchase - Sysco", cp="Sysco", amount=-400)
    data = build_classification(description=txn.description, counterparty=txn.counterparty,
                                method=txn.method, amount_cents=txn.amount_cents)
    data = replace(data, category_code="marketing", category_name="Marketing & Advertising",
                   subcategory="Marketing", pnl_type="operating_expense",
                   accounting_treatment="operating_expense")
    _classify(db_session, txn, data)

    item = _pending_item(db_session, txn)
    assert ReviewSource.DATA_INCONSISTENCY.value in item.review_sources
    reason = [r for s, r in zip(item.review_sources, item.review_reasons)
              if s == ReviewSource.DATA_INCONSISTENCY.value][0]
    assert "Food Inventory" in reason and "Marketing" in reason


def test_normal_high_confidence_not_flagged(db_session):
    # routine items (POS deposit, rent, payroll) must not be surfaced
    _insert(db_session, "N1", day=1, desc="Rent", cp="Landlord", amount=-1000)
    _insert(db_session, "N2", day=2, desc="POS batch deposit - food sales week 1", cp="Toast POS", amount=1200)
    _insert(db_session, "N3", day=3, desc="Payroll - hourly kitchen and FOH wages", cp="Gusto Payroll", amount=-500)
    for txn in db_session.query(Transaction).all():
        _classify(db_session, txn)
    assert db_session.query(ReviewItem).count() == 0
    assert all(c.requires_review is False for c in db_session.query(Classification).all())


def test_llm_explicit_review_flag(db_session):
    txn = _insert(db_session, "H1", desc="Utilities - electric/gas/water", cp="City Utilities", amount=-200)
    data = build_classification(description=txn.description, counterparty=txn.counterparty,
                                method=txn.method, amount_cents=txn.amount_cents)
    # confident rule outcome, but the classifier explicitly asked for review
    data = replace(data, requires_review=True, review_note="LLM review requested: unusual counterparty")
    _classify(db_session, txn, data)

    item = _pending_item(db_session, txn)
    assert ReviewSource.HUMAN_REVIEW.value in item.review_sources
    reason = [r for s, r in zip(item.review_sources, item.review_reasons)
              if s == ReviewSource.HUMAN_REVIEW.value][0]
    assert "LLM review requested" in reason


def test_multiple_triggers_all_reasons_preserved(db_session):
    # low confidence AND a description/rule conflict fire together
    txn = _insert(db_session, "M1", desc="Food inventory purchase - Sysco", cp="Sysco", amount=-900)
    data = build_classification(description=txn.description, counterparty=txn.counterparty,
                                method=txn.method, amount_cents=txn.amount_cents)
    data = replace(data, category_code="food_sales", category_name="Food Sales",
                   subcategory="Food Sales", pnl_type="revenue",
                   accounting_treatment="operating_revenue", confidence=0.50)
    _classify(db_session, txn, data)

    item = _pending_item(db_session, txn)
    sources = set(item.review_sources)
    assert ReviewSource.LOW_CONFIDENCE.value in sources
    assert ReviewSource.DATA_INCONSISTENCY.value in sources
    assert len(item.review_reasons) == len(item.review_sources)
    assert len(sources) >= 2


def test_real_dataset_items_surface_with_reasons(db_session):
    # the actual dataset items required by the assignment
    txn = _insert(db_session, "T5007", day=7, desc="Equipment purchase - new oven",
                  cp="Restaurant Equipment World", amount=-7800)
    data = _classify(db_session, txn)
    assert data.category_code == "capex_equipment"

    txn2 = _insert(db_session, "T5009", day=9, desc="Sales tax remittance",
                   cp="Florida Dept. of Revenue", amount=-6150)
    data2 = _classify(db_session, txn2)
    assert data2.category_code == "sales_tax_remittance"

    txn3 = _insert(db_session, "T5010", day=10, desc="Gift card sales deposit",
                   cp="Toast POS", amount=2400)
    data3 = _classify(db_session, txn3)
    assert data3.category_code == "gift_card_deposits"

    for t in (txn, txn2, txn3):
        item = _pending_item(db_session, t)
        assert ReviewSource.ACCOUNTING_JUDGMENT.value in item.review_sources
        assert item.review_sources and item.review_reasons


# ---------------------------------------------------------------------------
# Resolution workflow + P&L integration
# ---------------------------------------------------------------------------
def _seed_queue(db):
    sample = [
        ("R1", 1, "POS batch deposit - food sales week 1", "Toast POS", 1000.00),
        ("R2", 2, "POS batch deposit - beverage sales week 1", "Toast POS", 400.00),
        ("R3", 3, "Refunds and discounts week 1", "Toast POS", -100.00),
        ("R4", 4, "Food inventory purchase - Sysco", "Sysco", -300.00),
        ("R5", 5, "Beverage inventory purchase - Craft Beer Distributor", "Craft Beer Distributor", -50.00),
        ("R6", 6, "Payroll - hourly kitchen and FOH wages", "Gusto Payroll", -200.00),
        ("R7", 7, "Payroll taxes and benefits", "Gusto Payroll", -25.00),
        ("R8", 8, "Rent", "Landlord", -100.00),
        ("R9", 9, "Marketing - local ads", "Print Shop", -80.00),
        ("R10", 10, "Equipment purchase - new oven", "Restaurant Equipment World", -1000.00),
        ("R11", 11, "Sales tax remittance", "Florida Dept. of Revenue", -60.00),
    ]
    for tid, day, desc, cp, amount in sample:
        t = _insert(db, tid, day, desc, cp, amount)
        _classify(db, t)
    return db.query(Transaction).all()


def test_approve_records_decision_and_clears_review(db_session):
    _seed_queue(db_session)
    item = db_session.query(ReviewItem).first()

    result = review_service.approve_review(db_session, item.id, note="looks right", actor="analyst")

    db_session.refresh(result)
    assert result.status == ReviewStatus.APPROVED.value
    assert result.reviewer_decision == "approved"
    assert result.resolved_at is not None
    assert result.reviewed_at is not None
    assert result.review_sources and result.review_reasons  # reasons kept for audit


def test_reclassify_reflects_in_pnl(db_session):
    _seed_queue(db_session)
    ovens = db_session.query(Transaction).filter(Transaction.transaction_id == "R10").one()
    item = _pending_item(db_session, ovens)

    before = engine.calculate_monthly_pnl(db_session, "2026-01")

    review_service.change_classification(db_session, item.id, "repairs_maintenance",
                                         note="equipment repair under warranty?", actor="analyst")

    db_session.refresh(ovens)
    assert ovens.classification.category_code == "repairs_maintenance"
    assert ovens.classification.source == "manual"
    assert ovens.classification.review_status == ReviewStatus.CORRECTED.value

    after = engine.calculate_monthly_pnl(db_session, "2026-01")
    # the $1000 equipment purchase was non-P&L; as repairs it now hits opex
    assert after.lines["operating_expenses"].amount_cents == \
        before.lines["operating_expenses"].amount_cents - 100_000
    # resolved item still records why it was flagged
    item = db_session.get(ReviewItem, item.id)
    assert item.status == ReviewStatus.CORRECTED.value
    assert (item.review_sources or []), "resolved item keeps its triggers"


def test_mark_non_pnl_excludes_from_pnl(db_session):
    _seed_queue(db_session)
    marketing = db_session.query(Transaction).filter(Transaction.transaction_id == "R9").one()

    # marketing auto-classified cleanly; reviewer decides it is balance-sheet spend
    cls = marketing.classification
    item = ReviewItem(transaction_id=marketing.id, status="pending",
                      submitted_category_code=cls.category_code, submitted_category_name=cls.category_name,
                      submitted_pnl_type=cls.pnl_type, submitted_accounting_treatment=cls.accounting_treatment,
                      submitted_confidence=cls.confidence, submitted_source=cls.source,
                      submitted_reasoning=cls.reasoning, review_sources=["DATA_INCONSISTENCY"],
                      review_reasons=["Reviewer flagged a misposting."])
    db_session.add(item)
    db_session.commit()

    before = engine.calculate_monthly_pnl(db_session, "2026-01")
    assert before.lines["operating_expenses"].amount_cents <= -8_000  # marketing -$80 is in opex

    review_service.mark_non_pnl(db_session, item.id, "other_non_pnl", note="capital campaign", actor="analyst")

    after = engine.calculate_monthly_pnl(db_session, "2026-01")
    assert after.lines["operating_expenses"].amount_cents == before.lines["operating_expenses"].amount_cents + 8_000
    db_session.refresh(item)
    assert item.status == ReviewStatus.MARKED_NON_PNL.value
    assert item.reviewer_decision == "marked_non_pnl"
    assert item.resolved_at is not None


def test_audit_events_record_every_decision(db_session):
    _seed_queue(db_session)
    item = db_session.query(ReviewItem).first()
    review_service.approve_review(db_session, item.id, actor="reviewer")
    events = db_session.query(AuditEvent).filter(AuditEvent.entity_id == str(item.id)).all()
    assert len(events) == 1
    assert events[0].action == "review_approved"
    assert events[0].actor == "reviewer"


def test_suggested_action_marks_non_pnl(db_session):
    txn = _insert(db_session, "S1", desc="Gift card sales deposit", cp="Toast POS", amount=2400)
    data = _classify(db_session, txn)
    assert data.category_code == "gift_card_deposits"
    item = _pending_item(db_session, txn)
    assert item.suggested_action == "mark_non_pnl"