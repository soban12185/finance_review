from app.schemas.common import BaseModel


class CategoryTotalOut(BaseModel):
    category_code: str
    category_name: str
    amount_cents: int
    amount: float
    transaction_count: int


class LineTotalOut(BaseModel):
    line: str
    label: str
    amount_cents: int
    amount: float
    transaction_count: int
    is_computed: bool
    categories: list[CategoryTotalOut] = []


class MonthlyPnLOut(BaseModel):
    month: str
    transaction_count: int
    net_cash_cents: int
    net_cash: float
    pending_review_count: int
    lines: dict[str, LineTotalOut]


class DrilldownOut(BaseModel):
    month: str
    line: str
    label: str
    amount_cents: int
    transactions: list[dict]