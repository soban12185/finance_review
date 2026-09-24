"""Canonical category catalog.

This is the single source of truth for the category list used by the rule
engine, the LLM classifier, the review UI and the financial engine. The
``categories`` table is kept in sync with this catalog (idempotent upsert
performed on startup and before ingestion).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.core.constants import AccountingTreatment, PnlType

# PnL line codes used across the application.
L_REVENUE = PnlType.REVENUE.value
L_COGS = PnlType.COGS.value
L_PAYROLL = PnlType.PAYROLL.value
L_OPEX = PnlType.OPERATING_EXPENSE.value
L_NON_PNL = PnlType.NON_PNL.value


@dataclass(frozen=True)
class CategoryDef:
    code: str
    name: str
    subcategory: str
    pnl_type: str
    accounting_treatment: str
    is_contra: bool = False
    sort_order: int = 0
    description: str = ""


CATALOG: list[CategoryDef] = [
    # ------------------------------------------------------------------ revenue
    CategoryDef("food_sales", "Food Sales", "Food Sales", L_REVENUE,
                AccountingTreatment.OPERATING_REVENUE.value, sort_order=10,
                description="POS batch deposits from on-premise food sales."),
    CategoryDef("beverage_sales", "Beverage Sales", "Beverage Sales", L_REVENUE,
                AccountingTreatment.OPERATING_REVENUE.value, sort_order=11,
                description="POS batch deposits from beverage sales."),
    CategoryDef("catering_revenue", "Catering Revenue", "Catering", L_REVENUE,
                AccountingTreatment.OPERATING_REVENUE.value, sort_order=12,
                description="Invoice payments from catering clients."),
    CategoryDef("delivery_revenue", "Third-Party Delivery", "Third-Party Delivery", L_REVENUE,
                AccountingTreatment.OPERATING_REVENUE.value, sort_order=13,
                description="Marketplace payouts from third-party delivery platforms."),
    CategoryDef("refunds_discounts", "Refunds & Discounts", "Contra-Revenue", L_REVENUE,
                AccountingTreatment.CONTRA_REVENUE.value, is_contra=True, sort_order=14,
                description="Customer refunds and discounts that reduce revenue."),
    CategoryDef("delivery_commissions", "Delivery Commissions", "Contra-Revenue", L_REVENUE,
                AccountingTreatment.CONTRA_REVENUE.value, is_contra=True, sort_order=15,
                description="Platform/marketplace commissions deducted from sales."),
    # ------------------------------------------------------------------ COGS
    CategoryDef("food_inventory", "Food Inventory", "Food Inventory", L_COGS,
                AccountingTreatment.COST_OF_GOODS_SOLD.value, sort_order=20,
                description="Purchases of food inventory from suppliers."),
    CategoryDef("beverage_inventory", "Beverage Inventory", "Beverage Inventory", L_COGS,
                AccountingTreatment.COST_OF_GOODS_SOLD.value, sort_order=21,
                description="Purchases of beverage/alcohol inventory from distributors."),
    CategoryDef("catering_food_purchases", "Catering Food Purchases", "Catering Food", L_COGS,
                AccountingTreatment.COST_OF_GOODS_SOLD.value, sort_order=22,
                description="Direct food purchases for one-off large catering events."),
    # ------------------------------------------------------------------ payroll
    CategoryDef("wages_salaries", "Wages & Salaries", "Payroll", L_PAYROLL,
                AccountingTreatment.PAYROLL_EXPENSE.value, sort_order=30,
                description="Hourly kitchen/FOH wages and manager salaries."),
    CategoryDef("payroll_taxes_benefits", "Payroll Taxes & Benefits", "Payroll", L_PAYROLL,
                AccountingTreatment.PAYROLL_EXPENSE.value, sort_order=31,
                description="Employer payroll taxes and benefits."),
    # ------------------------------------------------------------------ operating expenses
    CategoryDef("rent", "Rent & Occupancy", "Rent & Occupancy", L_OPEX,
                AccountingTreatment.OPERATING_EXPENSE.value, sort_order=40,
                description="Lease/rent payments for the location."),
    CategoryDef("software_subscriptions", "Software & Subscriptions", "Software", L_OPEX,
                AccountingTreatment.OPERATING_EXPENSE.value, sort_order=41,
                description="POS and software subscription fees."),
    CategoryDef("insurance", "Insurance", "Insurance", L_OPEX,
                AccountingTreatment.OPERATING_EXPENSE.value, sort_order=42,
                description="Business insurance premiums."),
    CategoryDef("professional_services", "Professional Services", "Professional Services", L_OPEX,
                AccountingTreatment.OPERATING_EXPENSE.value, sort_order=43,
                description="Accounting and bookkeeping services."),
    CategoryDef("utilities", "Utilities", "Utilities", L_OPEX,
                AccountingTreatment.OPERATING_EXPENSE.value, sort_order=44,
                description="Electricity, gas and water."),
    CategoryDef("communications", "Communications", "Communications", L_OPEX,
                AccountingTreatment.OPERATING_EXPENSE.value, sort_order=45,
                description="Internet and phone services."),
    CategoryDef("marketing", "Marketing & Advertising", "Marketing", L_OPEX,
                AccountingTreatment.OPERATING_EXPENSE.value, sort_order=46,
                description="Local advertising spend."),
    CategoryDef("repairs_maintenance", "Repairs & Maintenance", "Repairs", L_OPEX,
                AccountingTreatment.OPERATING_EXPENSE.value, sort_order=47,
                description="Equipment repairs and building maintenance."),
    CategoryDef("supplies_packaging", "Supplies & Packaging", "Supplies", L_OPEX,
                AccountingTreatment.OPERATING_EXPENSE.value, sort_order=48,
                description="To-go packaging, disposables and office/admin supplies."),
    CategoryDef("cleaning_linen", "Cleaning & Linen", "Cleaning", L_OPEX,
                AccountingTreatment.OPERATING_EXPENSE.value, sort_order=49,
                description="Cleaning services and linen service."),
    CategoryDef("licenses_permits", "Licenses & Permits", "Licenses", L_OPEX,
                AccountingTreatment.OPERATING_EXPENSE.value, sort_order=50,
                description="Business license and permit renewals."),
    # ------------------------------------------------------------------ non-P&L
    CategoryDef("capex_equipment", "Capital Expenditure", "Capital Expenditure", L_NON_PNL,
                AccountingTreatment.CAPITAL_EXPENDITURE.value, sort_order=60,
                description="Purchases capitalised on the balance sheet (fixed assets)."),
    CategoryDef("sales_tax_remittance", "Sales Tax Remittance", "Sales Tax", L_NON_PNL,
                AccountingTreatment.SALES_TAX_LIABILITY.value, sort_order=61,
                description="Remittance of collected sales tax (liability settlement)."),
    CategoryDef("gift_card_deposits", "Gift Card Deposits", "Gift Cards", L_NON_PNL,
                AccountingTreatment.DEFERRED_REVENUE.value, sort_order=62,
                description="Cash received for gift cards - deferred revenue liability."),
    CategoryDef("loan_principal", "Loan Principal Repayment", "Financing", L_NON_PNL,
                AccountingTreatment.LOAN_PRINCIPAL.value, sort_order=63,
                description="Repayment of loan principal (financing activity)."),
    CategoryDef("owner_distributions", "Owner Distributions", "Equity", L_NON_PNL,
                AccountingTreatment.OWNER_DISTRIBUTION.value, sort_order=64,
                description="Distributions of cash to owners (equity activity)."),
    CategoryDef("other_non_pnl", "Other Non-P&L", "Non-P&L", L_NON_PNL,
                "other_non_pnl", sort_order=65,
                description="Manual designation as non-P&L (balance-sheet / financing / equity activity)."),
    # ------------------------------------------------------------------ fallback
    CategoryDef("uncategorized", "Uncategorized", "Uncategorized", "unknown",
                "unclassified", sort_order=999,
                description="Fallback when neither rules nor the LLM can classify."),
]

BY_CODE: dict[str, CategoryDef] = {c.code: c for c in CATALOG}


def get_category(code: str) -> CategoryDef | None:
    return BY_CODE.get(code)


def pnl_line(category: CategoryDef) -> str:
    return category.pnl_type


def line_label(line: str) -> str:
    """Human label for a PnL line code used by the financial engine."""
    return {
        L_REVENUE: "Revenue",
        L_COGS: "COGS",
        "gross_profit": "Gross Profit",
        L_PAYROLL: "Payroll",
        L_OPEX: "Operating Expenses",
        "operating_profit": "Operating Profit",
    }[line]