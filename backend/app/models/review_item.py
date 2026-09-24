"""Review item model.

``review_items`` captures every transaction the workflow asks a human to verify.
When ``classifications`` is corrected the review item records the submitted
(auto) classification, every reason it was flagged (``review_sources`` /
``review_reasons``), the resolution chosen by the reviewer, and any note.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import ReviewStatus
from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ReviewItem(Base):
    __tablename__ = "review_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=ReviewStatus.PENDING.value, index=True)

    # Snapshot of the *submitted* (auto) classification that triggered the review.
    submitted_category_code: Mapped[str] = mapped_column(String(64), nullable=False)
    submitted_category_name: Mapped[str] = mapped_column(String(120), nullable=False)
    submitted_pnl_type: Mapped[str] = mapped_column(String(32), nullable=False)
    submitted_accounting_treatment: Mapped[str] = mapped_column(String(48), nullable=False)
    submitted_confidence: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0.0)
    submitted_source: Mapped[str] = mapped_column(String(24), nullable=False, default="rule")
    submitted_reasoning: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Why the item ended up in the queue (every trigger that fired).
    review_sources: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    review_reasons: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # What the system suggests the reviewer confirm (approve / mark_non_pnl).
    suggested_action: Mapped[str] = mapped_column(String(48), nullable=False, default="approve")

    # Resolution chosen by the reviewer (null until decided).
    decided_category_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decided_category_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    decided_pnl_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    decided_accounting_treatment: Mapped[str | None] = mapped_column(String(48), nullable=True)
    decided_confidence: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)

    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    reviewed_by: Mapped[str] = mapped_column(String(64), nullable=False, default="user")
    # Machine-opinion tag of the decision actually applied (approved / changed /
    # marked_non_pnl) - independent of the status string, useful for reporting.
    reviewer_decision: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    transaction = relationship("Transaction", back_populates="review_items")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<ReviewItem #{self.id} {self.status}>"