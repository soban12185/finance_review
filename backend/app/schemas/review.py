from datetime import date

from pydantic import Field

from app.schemas.common import ORMModel, BaseModel

PENDING = "pending"


class ReviewItemOut(ORMModel):
    id: int
    transaction_id: int
    status: str
    submitted_category_code: str
    submitted_category_name: str
    submitted_pnl_type: str
    submitted_accounting_treatment: str
    submitted_confidence: float
    submitted_source: str
    submitted_reasoning: str
    review_sources: list[str] = []
    review_reasons: list[str] = []
    suggested_action: str = "approve"
    decided_category_code: str | None = None
    decided_category_name: str | None = None
    decided_pnl_type: str | None = None
    decided_accounting_treatment: str | None = None
    decided_confidence: float | None = None
    note: str = ""
    reviewed_by: str = "user"
    reviewer_decision: str = ""
    created_at: str | None = None
    reviewed_at: str | None = None
    resolved_at: str | None = None


class ReviewAction(BaseModel):
    action: str = Field(pattern="^(approve|change_classification|mark_non_pnl)$")
    category_code: str | None = Field(default=None, max_length=64)
    note: str = Field(default="", max_length=2000)
    actor: str = Field(default="user", max_length=64)


class ReviewDetail(BaseModel):
    transaction_id: str
    date: date
    description: str
    counterparty: str
    amount_cents: int
    amount: float
    method: str
    current_classification: dict