"""Deterministic review-queue triggers.

Every transaction is evaluated against five explainable rules when it is
classified. Anything that triggers is surfaced in the review queue with the
individual reasons preserved (a transaction may be flagged by several sources):

A. LOW_CONFIDENCE           effective confidence below the configured threshold
B. ACCOUNTING_JUDGMENT      treatment needs human confirmation (non-P&L, capex,
                            deferred revenue, tax liability, financing, equity)
C. UNUSUAL_TRANSACTION      robust outlier vs. other transactions in the same
                            category (median + z * 1.4826 * MAD), configurable
D. DATA_INCONSISTENCY       description/rule or counterparty conflicts with the
                            assigned classification
E. HUMAN_REVIEW             financially significant amounts, or an explicit
                            requires_review flag from the classifier itself

The rules are deterministic, statistical where appropriate, and every reason is
a human-readable sentence. ``requires_review`` on the classification is derived
from these sources; nothing here ever computes a P&L figure.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median

from sqlalchemy.orm import Session

from sqlalchemy import func

from app.classification.rules import apply_rules
from app.core.config import get_settings
from app.core.constants import AccountingTreatment, PnlType, ReviewSource, ReviewStatus
from app.financial.money import cents_to_amount
from app.models.classification import Classification
from app.models.review_item import ReviewItem
from app.models.transaction import Transaction

_settings = get_settings()

# Accounting treatments that require explicit human confirmation before the
# transaction is treated as a normal P&L item.
_JUDGMENT_TREATMENTS = {
    AccountingTreatment.CAPITAL_EXPENDITURE.value,
    AccountingTreatment.SALES_TAX_LIABILITY.value,
    AccountingTreatment.DEFERRED_REVENUE.value,
    AccountingTreatment.LOAN_PRINCIPAL.value,
    AccountingTreatment.OWNER_DISTRIBUTION.value,
}

_TREATMENT_LABELS = {
    AccountingTreatment.CAPITAL_EXPENDITURE.value: "capital expenditure",
    AccountingTreatment.SALES_TAX_LIABILITY.value: "sales tax liability",
    AccountingTreatment.DEFERRED_REVENUE.value: "deferred revenue",
    AccountingTreatment.LOAN_PRINCIPAL.value: "loan principal",
    AccountingTreatment.OWNER_DISTRIBUTION.value: "owner distribution",
}


@dataclass
class DetectionResult:
    sources: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    requires_review: bool = False
    suggested_action: str = "approve"

    def has(self, source: str) -> bool:
        return source in self.sources


def _add(result: DetectionResult, source: str, reason: str) -> None:
    if source not in result.sources:
        result.sources.append(source)
    if reason not in result.reasons:
        result.reasons.append(reason)


def _low_confidence(data) -> None:
    threshold = float(_settings.review_confidence_threshold)
    if float(data.confidence) < threshold:
        pct = round(float(data.confidence) * 100)
        return (
            ReviewSource.LOW_CONFIDENCE.value,
            f"Classification confidence is {pct}%, below the {round(threshold * 100)}% review threshold.",
        )
    return None


def _accounting_judgment(data) -> tuple[str, str] | None:
    if data.pnl_type == PnlType.NON_PNL.value:
        label = _TREATMENT_LABELS.get(data.accounting_treatment, data.accounting_treatment.replace("_", " "))
        return (
            ReviewSource.ACCOUNTING_JUDGMENT.value,
            f"Accounting treatment requires human confirmation ({label}).",
        )
    if data.accounting_treatment in _JUDGMENT_TREATMENTS:
        label = _TREATMENT_LABELS.get(data.accounting_treatment, data.accounting_treatment.replace("_", " "))
        return (
            ReviewSource.ACCOUNTING_JUDGMENT.value,
            f"Accounting treatment requires human confirmation ({label}).",
        )
    return None


def _unusual_transaction(db: Session, txn: Transaction, data) -> tuple[str, str] | None:
    abs_amount = abs(txn.amount_cents)

    # Small transactions are never considered unusual: the guard avoids noise in
    # categories whose amounts are tiny.
    if abs_amount < int(_settings.unusual_amount_min_abs_cents):
        return None

    # Require a minimum sample of comparable transactions in the category before
    # statistical outlier detection is meaningful (avoid single-item categories).
    amounts = db.query(
        func.abs(Transaction.amount_cents),
    ).join(Classification, Classification.transaction_id == Transaction.id).filter(
        Classification.transaction_id != txn.id,
        Classification.category_code == data.category_code,
    ).all()
    values = [int(a) for (a,) in amounts if a is not None]
    if len(values) < int(_settings.unusual_amount_min_count):
        return None

    # Robust outlier test: median + multiplier * 1.4826 * MAD. Deterministic and
    # explainable - we state the median it is compared against.
    med = float(median(values))
    mad = median([abs(v - med) for v in values])
    threshold = med + float(_settings.unusual_amount_multiplier) * (max(mad, 1.0) * 1.4826)

    if abs_amount > threshold:
        return (
            ReviewSource.UNUSUAL_TRANSACTION.value,
            f"Transaction amount is unusually high compared with other transactions in this category "
            f"({cents_to_amount(abs_amount):,.2f} vs a {cents_to_amount(int(round(med))):,.2f} typical amount).",
        )
    return None


def _description_conflict_from_txn(db: Session, txn: Transaction, data) -> tuple[str, str] | None:
    rule = apply_rules(
        description=txn.description,
        counterparty=txn.counterparty,
        method=txn.method,
        amount_cents=txn.amount_cents,
    )
    if rule is not None and rule.category.code != data.category_code:
        return (
            ReviewSource.DATA_INCONSISTENCY.value,
            f"Transaction description conflicts with the assigned category: the description suggests "
            f"'{rule.category.name}' but the classification is '{data.category_name}'.",
        )
    return None


def _counterparty_conflict(db: Session, txn: Transaction, data) -> tuple[str, str] | None:
    # Only evaluate P&L classifications: judgment items are already surfaced and
    # a counterparty that legitimately spans several revenue lines (e.g. a POS
    # aggregator) is normal. A counterparty is only treated as a "norm" when it
    # is used for >= 3 transactions AND one category clearly dominates (>= 80%)
    # - e.g. a supplier that only ever invoices inventory.
    if data.pnl_type == PnlType.NON_PNL.value or data.pnl_type == "unknown":
        return None
    cp = (txn.counterparty or "").strip().lower()
    if len(cp) < 2:
        return None

    rows = db.query(Classification.category_code, Classification.category_name).join(
        Transaction, Transaction.id == Classification.transaction_id
    ).filter(
        Transaction.id != txn.id,
        Transaction.counterparty.ilike(cp),
    ).all()
    total = len(rows)
    if total < 3:
        return None

    counts: dict[str, tuple[str, int]] = {}
    for code, name in rows:
        code = code or ""
        existing = counts.get(code, (name, 0))
        counts[code] = (existing[0], existing[1] + 1)

    norm_code, (norm_name, norm_count) = max(counts.items(), key=lambda kv: kv[1][1])
    dominance = norm_count / total
    if norm_code != data.category_code and norm_count >= 3 and dominance >= 0.80:
        return (
            ReviewSource.DATA_INCONSISTENCY.value,
            f"Counterparty '{txn.counterparty}' is normally classified as '{norm_name}' "
            f"({round(dominance * 100)}% of its transactions), but this transaction was "
            f"classified as '{data.category_name}'.",
        )
    return None


def _significance(txn: Transaction) -> tuple[str, str] | None:
    abs_amount = abs(txn.amount_cents)
    if abs_amount >= int(_settings.review_significance_min_cents):
        return (
            ReviewSource.HUMAN_REVIEW.value,
            f"Transaction amount ({cents_to_amount(abs_amount):,.2f}) is financially significant and "
            "warrants human confirmation.",
        )
    return None


def detect_review_triggers(
    db: Session, txn: Transaction, data, *, honor_explicit_flag: bool = True
) -> DetectionResult:
    """Evaluate all triggers for a transaction + its classification data.

    ``data`` exposes ``category_code``, ``category_name``, ``pnl_type``,
    ``accounting_treatment``, ``confidence`` and ``requires_review``.

    ``honor_explicit_flag`` only affects the E trigger: fresh classifications pass
    True so a classifier's explicit ``requires_review`` request surfaces; the
    startup reconciliation passes False so that stale ``requires_review`` flags
    left by older logic cannot mass-surface confident rows - each trigger is
    re-evaluated independently instead.
    """
    result = DetectionResult()

    low = _low_confidence(data)
    if low:
        _add(result, low[0], low[1])

    judgment = _accounting_judgment(data)
    if judgment:
        _add(result, judgment[0], judgment[1])

    unusual = _unusual_transaction(db, txn, data)
    if unusual:
        _add(result, unusual[0], unusual[1])

    conflict = _description_conflict_from_txn(db, txn, data)
    if conflict:
        _add(result, conflict[0], conflict[1])

    cp_conflict = _counterparty_conflict(db, txn, data)
    if cp_conflict:
        _add(result, cp_conflict[0], cp_conflict[1])

    significant = _significance(txn)
    if significant:
        _add(result, significant[0], significant[1])

    # E. The classifier explicitly asked for human review even though no rule
    # above fired (e.g. the LLM requested review, or a rule marked the item).
    if honor_explicit_flag and data.requires_review and not result.sources:
        note = str(getattr(data, "review_note", "")).strip()
        if note:
            _add(result, ReviewSource.HUMAN_REVIEW.value, note)
        else:
            _add(
                result,
                ReviewSource.HUMAN_REVIEW.value,
                "The classification system explicitly flagged this transaction for human review.",
            )

    # Sources and reasons stay paired in insertion order (deterministic per the
    # evaluation order above); sorting could de-align them.
    result.reasons = list(dict.fromkeys(result.reasons))
    result.requires_review = bool(result.sources)
    if data.pnl_type == PnlType.NON_PNL.value:
        result.suggested_action = "mark_non_pnl"
    else:
        result.suggested_action = "approve"
    return result


def reconcile_pending_reviews(db: Session) -> int:
    """Re-run detection over existing classifications and sync the queue.

    * Items still pending get their reasons refreshed (no duplicates created).
    * Newly detected issues create a fresh pending review item.
    * Transactions that no longer require review lose their *pending* item.
    * Resolved items (approved / corrected / marked non-P&L) are never touched,
      preserving the audit trail of every human decision.

    Returns the number of review items that were created or updated.
    """
    from app.core.constants import ReviewStatus

    resolved = {
        ReviewStatus.APPROVED.value,
        ReviewStatus.CORRECTED.value,
        ReviewStatus.MARKED_NON_PNL.value,
    }

    changed = 0
    classifications = db.query(Classification).all()
    for cls in classifications:
        if cls.review_status in resolved:
            # Resolved decisions stay exactly as the reviewer left them.
            continue

        txn = db.get(Transaction, cls.transaction_id)
        if txn is None:
            continue

        result = detect_review_triggers(db, txn, cls, honor_explicit_flag=False)
        existing = (
            db.query(ReviewItem)
            .filter(
                ReviewItem.transaction_id == txn.id,
                ReviewItem.status == ReviewStatus.PENDING.value,
            )
            .first()
        )

        if not result.requires_review:
            cls.requires_review = False
            cls.review_status = ReviewStatus.NONE.value
            if existing is not None:
                db.delete(existing)
                changed += 1
            db.commit()
            continue

        cls.requires_review = True
        cls.review_status = ReviewStatus.PENDING.value
        if existing is None:
            db.add(ReviewItem(
                transaction_id=txn.id,
                status=ReviewStatus.PENDING.value,
                submitted_category_code=cls.category_code,
                submitted_category_name=cls.category_name,
                submitted_pnl_type=cls.pnl_type,
                submitted_accounting_treatment=cls.accounting_treatment,
                submitted_confidence=float(cls.confidence),
                submitted_source=cls.source,
                submitted_reasoning=cls.reasoning,
                review_sources=result.sources,
                review_reasons=result.reasons,
                suggested_action=result.suggested_action,
            ))
            changed += 1
        else:
            existing.review_sources = result.sources
            existing.review_reasons = result.reasons
            existing.suggested_action = result.suggested_action
            existing.submitted_category_code = cls.category_code
            existing.submitted_category_name = cls.category_name
            existing.submitted_pnl_type = cls.pnl_type
            existing.submitted_accounting_treatment = cls.accounting_treatment
            existing.submitted_confidence = float(cls.confidence)
            existing.submitted_source = cls.source
            existing.submitted_reasoning = cls.reasoning
            changed += 1
        db.commit()
    return changed


__all__ = [
    "DetectionResult",
    "detect_review_triggers",
    "reconcile_pending_reviews",
]