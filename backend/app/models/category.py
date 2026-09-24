"""Category catalog model.

Rows describe the canonical set of categories/subcategories the classification
layer may assign. ``pnl_type`` determines which P&L line (if any) a transaction in
this category feeds, and ``is_contra`` marks contra-revenue items whose signed
amounts reduce the line total.
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import AccountingTreatment, PnlType
from app.db.base import Base


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    subcategory: Mapped[str] = mapped_column(String(80), nullable=False)
    pnl_type: Mapped[str] = mapped_column(String(32), nullable=False, default=PnlType.NON_PNL.value)
    accounting_treatment: Mapped[str] = mapped_column(
        String(48), nullable=False, default=AccountingTreatment.OPERATING_REVENUE.value
    )
    is_contra: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    classifications = relationship("Classification", back_populates="category")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Category {self.code} ({self.name})>"