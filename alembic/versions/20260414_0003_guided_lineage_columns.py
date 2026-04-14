"""add replay/order lineage columns

Revision ID: 20260414_0003
Revises: 20260413_0002
Create Date: 2026-04-14
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260414_0003"
down_revision = "20260413_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("replay_runs", sa.Column("recommendation_id", sa.String(length=64), nullable=True))
    op.add_column("orders", sa.Column("replay_run_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "replay_run_id")
    op.drop_column("replay_runs", "recommendation_id")
