"""Add paper max order notional user setting.

Revision ID: 20260502_0009
Revises: 20260430_0008
Create Date: 2026-05-02
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260502_0009"
down_revision = "20260430_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("app_users")}
    if "paper_max_order_notional" not in columns:
        op.add_column("app_users", sa.Column("paper_max_order_notional", sa.Float(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("app_users")}
    if "paper_max_order_notional" in columns:
        op.drop_column("app_users", "paper_max_order_notional")
