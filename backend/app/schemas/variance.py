from app.schemas.common import BaseModel


class VarianceLineOut(BaseModel):
    line: str
    label: str
    previous_cents: int
    current_cents: int
    previous: float
    current: float
    absolute_cents: int
    absolute: float
    percent: float | None
    material: bool


class VarianceReport(BaseModel):
    month_a: str
    month_b: str
    materiality: dict
    lines: list[VarianceLineOut]


class VarianceDriverOut(BaseModel):
    category_code: str
    category_name: str
    previous_cents: int
    current_cents: int
    previous: float
    current: float
    absolute_cents: int
    absolute: float
    percent: float | None
    material: bool
    contribution_percent: float
    transaction_count: int
    transactions: list[dict]


class VarianceDriverReport(BaseModel):
    month_a: str
    month_b: str
    line: str
    label: str
    line_variance_cents: int
    drivers: list[VarianceDriverOut]