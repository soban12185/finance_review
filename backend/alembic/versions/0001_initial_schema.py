"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-01-01

Creates every table used by the application and seeds the category catalog.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Keep in sync with app/classification/catalog.py (the app reconciles on startup).
_SEED_CATEGORIES: list[dict] = [
    {"code": "food_sales", "name": "Food Sales", "subcategory": "Food Sales", "pnl_type": "revenue", "accounting_treatment": "operating_revenue", "is_contra": False, "sort_order": 10, "description": "POS batch deposits from on-premise food sales."},
    {"code": "beverage_sales", "name": "Beverage Sales", "subcategory": "Beverage Sales", "pnl_type": "revenue", "accounting_treatment": "operating_revenue", "is_contra": False, "sort_order": 11, "description": "POS batch deposits from beverage sales."},
    {"code": "catering_revenue", "name": "Catering Revenue", "subcategory": "Catering", "pnl_type": "revenue", "accounting_treatment": "operating_revenue", "is_contra": False, "sort_order": 12, "description": "Invoice payments from catering clients."},
    {"code": "delivery_revenue", "name": "Third-Party Delivery", "subcategory": "Third-Party Delivery", "pnl_type": "revenue", "accounting_treatment": "operating_revenue", "is_contra": False, "sort_order": 13, "description": "Marketplace payouts from third-party delivery platforms."},
    {"code": "refunds_discounts", "name": "Refunds & Discounts", "subcategory": "Contra-Revenue", "pnl_type": "revenue", "accounting_treatment": "contra_revenue", "is_contra": True, "sort_order": 14, "description": "Customer refunds and discounts that reduce revenue."},
    {"code": "delivery_commissions", "name": "Delivery Commissions", "subcategory": "Contra-Revenue", "pnl_type": "revenue", "accounting_treatment": "contra_revenue", "is_contra": True, "sort_order": 15, "description": "Platform/marketplace commissions deducted from sales."},
    {"code": "food_inventory", "name": "Food Inventory", "subcategory": "Food Inventory", "pnl_type": "cogs", "accounting_treatment": "cost_of_goods_sold", "is_contra": False, "sort_order": 20, "description": "Purchases of food inventory from suppliers."},
    {"code": "beverage_inventory", "name": "Beverage Inventory", "subcategory": "Beverage Inventory", "pnl_type": "cogs", "accounting_treatment": "cost_of_goods_sold", "is_contra": False, "sort_order": 21, "description": "Purchases of beverage/alcohol inventory from distributors."},
    {"code": "catering_food_purchases", "name": "Catering Food Purchases", "subcategory": "Catering Food", "pnl_type": "cogs", "accounting_treatment": "cost_of_goods_sold", "is_contra": False, "sort_order": 22, "description": "Direct food purchases for one-off large catering events."},
    {"code": "wages_salaries", "name": "Wages & Salaries", "subcategory": "Payroll", "pnl_type": "payroll", "accounting_treatment": "payroll_expense", "is_contra": False, "sort_order": 30, "description": "Hourly kitchen/FOH wages and manager salaries."},
    {"code": "payroll_taxes_benefits", "name": "Payroll Taxes & Benefits", "subcategory": "Payroll", "pnl_type": "payroll", "accounting_treatment": "payroll_expense", "is_contra": False, "sort_order": 31, "description": "Employer payroll taxes and benefits."},
    {"code": "rent", "name": "Rent & Occupancy", "subcategory": "Rent & Occupancy", "pnl_type": "operating_expense", "accounting_treatment": "operating_expense", "is_contra": False, "sort_order": 40, "description": "Lease/rent payments for the location."},
    {"code": "software_subscriptions", "name": "Software & Subscriptions", "subcategory": "Software", "pnl_type": "operating_expense", "accounting_treatment": "operating_expense", "is_contra": False, "sort_order": 41, "description": "POS and software subscription fees."},
    {"code": "insurance", "name": "Insurance", "subcategory": "Insurance", "pnl_type": "operating_expense", "accounting_treatment": "operating_expense", "is_contra": False, "sort_order": 42, "description": "Business insurance premiums."},
    {"code": "professional_services", "name": "Professional Services", "subcategory": "Professional Services", "pnl_type": "operating_expense", "accounting_treatment": "operating_expense", "is_contra": False, "sort_order": 43, "description": "Accounting and bookkeeping services."},
    {"code": "utilities", "name": "Utilities", "subcategory": "Utilities", "pnl_type": "operating_expense", "accounting_treatment": "operating_expense", "is_contra": False, "sort_order": 44, "description": "Electricity, gas and water."},
    {"code": "communications", "name": "Communications", "subcategory": "Communications", "pnl_type": "operating_expense", "accounting_treatment": "operating_expense", "is_contra": False, "sort_order": 45, "description": "Internet and phone services."},
    {"code": "marketing", "name": "Marketing & Advertising", "subcategory": "Marketing", "pnl_type": "operating_expense", "accounting_treatment": "operating_expense", "is_contra": False, "sort_order": 46, "description": "Local advertising spend."},
    {"code": "repairs_maintenance", "name": "Repairs & Maintenance", "subcategory": "Repairs", "pnl_type": "operating_expense", "accounting_treatment": "operating_expense", "is_contra": False, "sort_order": 47, "description": "Equipment repairs and building maintenance."},
    {"code": "supplies_packaging", "name": "Supplies & Packaging", "subcategory": "Supplies", "pnl_type": "operating_expense", "accounting_treatment": "operating_expense", "is_contra": False, "sort_order": 48, "description": "To-go packaging, disposables and office/admin supplies."},
    {"code": "cleaning_linen", "name": "Cleaning & Linen", "subcategory": "Cleaning", "pnl_type": "operating_expense", "accounting_treatment": "operating_expense", "is_contra": False, "sort_order": 49, "description": "Cleaning services and linen service."},
    {"code": "licenses_permits", "name": "Licenses & Permits", "subcategory": "Licenses", "pnl_type": "operating_expense", "accounting_treatment": "operating_expense", "is_contra": False, "sort_order": 50, "description": "Business license and permit renewals."},
    {"code": "capex_equipment", "name": "Capital Expenditure", "subcategory": "Capital Expenditure", "pnl_type": "non_pnl", "accounting_treatment": "capital_expenditure", "is_contra": False, "sort_order": 60, "description": "Purchases capitalised on the balance sheet (fixed assets)."},
    {"code": "sales_tax_remittance", "name": "Sales Tax Remittance", "subcategory": "Sales Tax", "pnl_type": "non_pnl", "accounting_treatment": "sales_tax_liability", "is_contra": False, "sort_order": 61, "description": "Remittance of collected sales tax (liability settlement)."},
    {"code": "gift_card_deposits", "name": "Gift Card Deposits", "subcategory": "Gift Cards", "pnl_type": "non_pnl", "accounting_treatment": "deferred_revenue", "is_contra": False, "sort_order": 62, "description": "Cash received for gift cards - deferred revenue liability."},
    {"code": "loan_principal", "name": "Loan Principal Repayment", "subcategory": "Financing", "pnl_type": "non_pnl", "accounting_treatment": "loan_principal", "is_contra": False, "sort_order": 63, "description": "Repayment of loan principal (financing activity)."},
    {"code": "owner_distributions", "name": "Owner Distributions", "subcategory": "Equity", "pnl_type": "non_pnl", "accounting_treatment": "owner_distribution", "is_contra": False, "sort_order": 64, "description": "Distributions of cash to owners (equity activity)."},
    {"code": "other_non_pnl", "name": "Other Non-P&L", "subcategory": "Non-P&L", "pnl_type": "non_pnl", "accounting_treatment": "other_non_pnl", "is_contra": False, "sort_order": 65, "description": "Manual designation as non-P&L (balance-sheet / financing / equity activity)."},
    {"code": "uncategorized", "name": "Uncategorized", "subcategory": "Uncategorized", "pnl_type": "unknown", "accounting_treatment": "unclassified", "is_contra": False, "sort_order": 999, "description": "Fallback when neither rules nor the LLM can classify."},
]


def upgrade() -> None:
    categories = op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("subcategory", sa.String(length=80), nullable=False),
        sa.Column("pnl_type", sa.String(length=32), nullable=False),
        sa.Column("accounting_treatment", sa.String(length=48), nullable=False),
        sa.Column("is_contra", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index("ix_categories_code", "categories", ["code"], unique=True)

    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("transaction_id", sa.String(length=32), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("counterparty", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("method", sa.String(length=50), nullable=False, server_default=""),
        sa.Column("raw_amount", sa.String(length=40), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="normal"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_transactions_transaction_id", "transactions", ["transaction_id"], unique=True)
    op.create_index("ix_transactions_date", "transactions", ["date"])
    op.create_index("ix_transactions_status", "transactions", ["status"])

    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="completed"),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("inserted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicates_skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("potential_duplicates", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("message", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index("ix_ingestion_runs_source_hash", "ingestion_runs", ["source_hash"])

    op.create_table(
        "ingestion_errors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("ingestion_runs.id"), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.String(length=32), nullable=True),
        sa.Column("error_type", sa.String(length=40), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("row_data", sa.Text(), nullable=True),
    )
    op.create_index("ix_ingestion_errors_run_id", "ingestion_errors", ["run_id"])

    op.create_table(
        "classifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("transactions.id"), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id"), nullable=True),
        sa.Column("category_code", sa.String(length=64), nullable=False),
        sa.Column("category_name", sa.String(length=120), nullable=False),
        sa.Column("subcategory", sa.String(length=80), nullable=False),
        sa.Column("pnl_type", sa.String(length=32), nullable=False),
        sa.Column("accounting_treatment", sa.String(length=48), nullable=False),
        sa.Column("is_contra", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False, server_default="0"),
        sa.Column("requires_review", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("review_status", sa.String(length=32), nullable=False, server_default="none"),
        sa.Column("source", sa.String(length=24), nullable=False, server_default="rule"),
        sa.Column("reasoning", sa.Text(), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("auto_classified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("transaction_id", name="uq_classifications_transaction"),
    )
    op.create_index("ix_classifications_transaction_id", "classifications", ["transaction_id"], unique=True)
    op.create_index("ix_classifications_category_code", "classifications", ["category_code"])
    op.create_index("ix_classifications_requires_review", "classifications", ["requires_review"])

    op.create_table(
        "classification_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("transactions.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("category_code", sa.String(length=64), nullable=False),
        sa.Column("category_name", sa.String(length=120), nullable=False),
        sa.Column("subcategory", sa.String(length=80), nullable=False),
        sa.Column("pnl_type", sa.String(length=32), nullable=False),
        sa.Column("accounting_treatment", sa.String(length=48), nullable=False),
        sa.Column("is_contra", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False, server_default="0"),
        sa.Column("source", sa.String(length=24), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_classification_history_transaction_id", "classification_history", ["transaction_id"])

    op.create_table(
        "review_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("transactions.id"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("submitted_category_code", sa.String(length=64), nullable=False),
        sa.Column("submitted_category_name", sa.String(length=120), nullable=False),
        sa.Column("submitted_pnl_type", sa.String(length=32), nullable=False),
        sa.Column("submitted_accounting_treatment", sa.String(length=48), nullable=False),
        sa.Column("submitted_confidence", sa.Numeric(5, 4), nullable=False, server_default="0"),
        sa.Column("submitted_source", sa.String(length=24), nullable=False, server_default="rule"),
        sa.Column("submitted_reasoning", sa.Text(), nullable=False, server_default=""),
        sa.Column("decided_category_code", sa.String(length=64), nullable=True),
        sa.Column("decided_category_name", sa.String(length=120), nullable=True),
        sa.Column("decided_pnl_type", sa.String(length=32), nullable=True),
        sa.Column("decided_accounting_treatment", sa.String(length=48), nullable=True),
        sa.Column("decided_confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("reviewed_by", sa.String(length=64), nullable=False, server_default="user"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_review_items_transaction_id", "review_items", ["transaction_id"])
    op.create_index("ix_review_items_status", "review_items", ["status"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_type", sa.String(length=40), nullable=False),
        sa.Column("entity_id", sa.String(length=40), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("old_value", sa.JSON(), nullable=True),
        sa.Column("new_value", sa.JSON(), nullable=True),
        sa.Column("actor", sa.String(length=64), nullable=False, server_default="system"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_events_entity_type", "audit_events", ["entity_type"])
    op.create_index("ix_audit_events_entity_id", "audit_events", ["entity_id"])
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])

    op.bulk_insert(categories, _SEED_CATEGORIES)


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("review_items")
    op.drop_table("classification_history")
    op.drop_table("classifications")
    op.drop_table("ingestion_errors")
    op.drop_table("ingestion_runs")
    op.drop_table("transactions")
    op.drop_table("categories")