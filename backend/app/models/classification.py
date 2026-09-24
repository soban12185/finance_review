"""Current + historical classification models.

* ``classifications``          - the single effective classification of each
                                 transaction right now.
* ``classification_history``   - every past version so corrections are fully
                                 auditable.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import ClassificationSource, PnlType, ReviewStatus
from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Classification(Base):
    __tablename__ = "classifications"
    __table_args__ = (UniqueConstraint("transaction_id", name="uq_classifications_transaction"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id"), nullable=False, unique=True, index=True
    )
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=True, index=True)
    category_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    category_name: Mapped[str] = mapped_column(String(120), nullable=False)
    subcategory: Mapped[str] = mapped_column(String(80), nullable=False)
    pnl_type: Mapped[str] = mapped_column(String(32), nullable=False)
    accounting_treatment: Mapped[str] = mapped_column(String(48), nullable=False)
    is_contra: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confidence: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0.0)
    requires_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default=ReviewStatus.NONE.value)
    source: Mapped[str] = mapped_column(String(24), nullable=False, default=ClassificationSource.RULE.value)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False, default="")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    auto_classified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    transaction = relationship("Transaction", back_populates="classification")
    category = relationship("Category", back_populates="classifications")


class ClassificationHistory(Base):
    __tablename__ = "classification_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    category_code: Mapped[str] = mapped_column(String(64), nullable=False)
    category_name: Mapped[str] = mapped_column(String(120), nullable=False)
    subcategory: Mapped[str] = mapped_column(String(80), nullable=False)
    pnl_type: Mapped[str] = mapped_column(String(32), nullable=False)
    accounting_treatment: Mapped[str] = mapped_column(String(48), nullable=False)
    is_contra: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confidence: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0.0)
    source: Mapped[str] = mapped_column(String(24), nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    transaction = relationship("Transaction", back_populates="classification_history")