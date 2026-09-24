"""Deterministic rule-based classification.

Step 1 of the hybrid classifier. Rules parse the structured bank descriptions
produced by POS/merchant systems. Because the rule engine is pure Python it is
deterministic, fast and independent of any external service.

Rules that represent accounting *judgement* (non-P&L treatment, capitalisation,
deferred revenue, financing, equity and unusual one-off purchases) deliberately
return a low confidence and ``requires_review=True`` so a human always confirms
them. The LLM is only consulted for transactions the rules cannot classify with
sufficient confidence (see :mod:`app.ai.classifier`).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.classification.catalog import CategoryDef, BY_CODE
from app.core.config import get_settings

_settings = get_settings()


@dataclass(frozen=True)
class RuleResult:
    category: CategoryDef
    confidence: float
    reason: str
    requires_review: bool = False


def _has(text: str, *words: str) -> bool:
    lowered = text.lower()
    return all(w in lowered for w in words)


@dataclass(frozen=True)
class _Rule:
    category_code: str
    keywords: tuple[str, ...]
    confidence: float = 0.97
    counterparties: tuple[str, ...] = ()
    methods: tuple[str, ...] = ()
    expected_sign: str | None = None  # "positive" | "negative"
    always_review: bool = False
    reason: str = ""

    def match(self, description: str, counterparty: str, method: str, amount_cents: int) -> bool:
        if not _has(description, *self.keywords):
            return False
        if self.counterparties and not _has(counterparty, *self.counterparties):
            return False
        if self.methods and method.lower() not in {m.lower() for m in self.methods}:
            return False
        if self.expected_sign:
            positive = amount_cents >= 0
            if self.expected_sign == "positive" and not positive:
                return False
            if self.expected_sign == "negative" and positive:
                return False
        return True


# Order matters: the first rule that matches wins.
RULES: tuple[_Rule, ...] = (
    # ------------------------------- revenue
    _Rule("food_sales", ("pos batch deposit", "food sales"), 0.97, expected_sign="positive"),
    _Rule("beverage_sales", ("pos batch deposit", "beverage sales"), 0.97, expected_sign="positive"),
    _Rule("catering_revenue", ("catering invoice payment",), 0.97, expected_sign="positive"),
    _Rule("delivery_revenue", ("delivery marketplace payout",), 0.96, expected_sign="positive"),
    _Rule("gift_card_deposits", ("gift card sales deposit",), 0.72, expected_sign="positive",
          always_review=True, reason="Gift card cash is deferred revenue (a liability) until redeemed; confirm treatment."),
    # ------------------------------- contra revenue
    _Rule("refunds_discounts", ("refunds and discounts",), 0.94, expected_sign="negative",
          reason="Negative POS adjustment - contra-revenue line."),
    _Rule("delivery_commissions", ("delivery platform commission",), 0.93, methods=("Marketplace deduction",),
          expected_sign="negative", reason="Platform commission deducted from delivery batches - contra-revenue."),
    # ------------------------------- COGS
    _Rule("catering_food_purchases", ("large catering event food purchase",), 0.70, always_review=True,
          reason="One-off catering event purchase - confirm it is COGS and not a contracted-out catering expense."),
    _Rule("food_inventory", ("food inventory purchase",), 0.97, reason="Food inventory purchase from supplier - COGS."),
    _Rule("beverage_inventory", ("beverage inventory purchase",), 0.97, reason="Beverage inventory purchase from distributor - COGS."),
    # ------------------------------- payroll
    _Rule("wages_salaries", ("payroll - hourly",), 0.97, reason="Hourly payroll run - wages."),
    _Rule("wages_salaries", ("manager salary payroll",), 0.97, reason="Manager salary payroll run."),
    _Rule("payroll_taxes_benefits", ("payroll taxes",), 0.97, reason="Employer payroll taxes and benefits."),
    # ------------------------------- operating expenses
    _Rule("rent", ("rent",), 0.97, counterparties=("landlord",), reason="Fixed rent payment."),
    _Rule("software_subscriptions", ("pos/software subscription",), 0.97, reason="POS / software subscription."),
    _Rule("insurance", ("insurance premium",), 0.97, reason="Insurance premium."),
    _Rule("professional_services", ("accounting/bookkeeping",), 0.97, reason="Bookkeeping / accounting services."),
    _Rule("communications", ("internet and phone",), 0.97, reason="Internet and phone service."),
    _Rule("utilities", ("utilities",), 0.97, reason="Electric/gas/water utilities."),
    _Rule("cleaning_linen", ("cleaning and linen",), 0.97, reason="Cleaning and linen service."),
    _Rule("marketing", ("marketing - local ads",), 0.97, reason="Local advertising spend."),
    _Rule("repairs_maintenance", ("repairs and maintenance",), 0.97, reason="Repairs and maintenance."),
    _Rule("supplies_packaging", ("to-go packaging",), 0.96, reason="To-go packaging disposables."),
    _Rule("supplies_packaging", ("office/admin supplies",), 0.96, reason="Office/admin supplies."),
    _Rule("licenses_permits", ("annual license renewal",), 0.96, reason="Annual business license renewal."),
    # ------------------------------- non-P&L (always reviewed)
    _Rule("capex_equipment", ("equipment purchase",), 0.70, always_review=True,
          reason="Capital expenditure - purchases over threshold are capitalised rather than expensed."),
    _Rule("sales_tax_remittance", ("sales tax remittance",), 0.75, always_review=True,
          reason="Remittance of collected sales tax settles a liability; it is not an operating expense."),
    _Rule("loan_principal", ("loan principal repayment",), 0.75, always_review=True,
          reason="Principal repayment is a financing/balance-sheet transaction, not an expense."),
    _Rule("owner_distributions", ("owner distribution",), 0.78, always_review=True,
          reason="Cash distribution to owners is an equity activity, not an expense."),
)


def apply_rules(*, description: str, counterparty: str = "", method: str = "", amount_cents: int = 0) -> RuleResult | None:
    for rule in RULES:
        if rule.match(description, counterparty, method, amount_cents):
            category = BY_CODE[rule.category_code]
            reason = rule.reason or f"Matched deterministic rule for {category.name}."
            return RuleResult(
                category=category,
                confidence=rule.confidence,
                reason=reason,
                requires_review=rule.always_review,
            )
    return None