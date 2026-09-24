"""review queue explainability + resolution metadata

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-24

Adds the explainable-review fields to ``review_items``:

* ``review_sources``        - every trigger that surfaced the item (JSON list)
* ``review_reasons``        - a human-readable reason per source (JSON list)
* ``suggested_action``      - what the system suggests the reviewer confirm
* ``reviewer_decision``     - the decision actually applied (approved / changed /
                              marked_non_pnl), independent of the status string
* ``resolved_at``           - when the human resolved the item

Existing rows are backfilled with empty lists so the queue stays renderable.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_JSON_EMPTY_LIST = sa.text("'[]'::json")


def upgrade() -> None:
    op.add_column("review_items", sa.Column("review_sources", sa.JSON(), nullable=False, server_default=_JSON_EMPTY_LIST))
    op.add_column("review_items", sa.Column("review_reasons", sa.JSON(), nullable=False, server_default=_JSON_EMPTY_LIST))
    op.add_column("review_items", sa.Column("suggested_action", sa.String(length=48), nullable=False, server_default="approve"))
    op.add_column("review_items", sa.Column("reviewer_decision", sa.String(length=64), nullable=False, server_default=""))
    op.add_column("review_items", sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("review_items", "resolved_at")
    op.drop_column("review_items", "reviewer_decision")
    op.drop_column("review_items", "suggested_action")
    op.drop_column("review_items", "review_reasons")
    op.drop_column("review_items", "review_sources")