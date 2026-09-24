"""API request/response schemas (Pydantic v2)."""
from pydantic import BaseModel, ConfigDict, Field

from app.financial.money import cents_to_amount


def money_dict(cents: int) -> dict:
    return {"cents": int(cents), "amount": cents_to_amount(int(cents))}


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Money(BaseModel):
    cents: int
    amount: float

    @classmethod
    def from_cents(cls, cents: int) -> "Money":
        return cls(cents=int(cents), amount=cents_to_amount(int(cents)))