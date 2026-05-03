"""Add listed option contract selection metadata.

Revision ID: 20260503_0010
Revises: 20260502_0009
Create Date: 2026-05-03
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260503_0010"
down_revision = "20260502_0009"
branch_labels = None
depends_on = None


LEG_TABLES = (
    "paper_option_order_legs",
    "paper_option_position_legs",
    "paper_option_trade_legs",
)


def _columns(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def _indexes(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    for table_name in LEG_TABLES:
        columns = _columns(table_name)
        if "option_symbol" not in columns:
            op.add_column(table_name, sa.Column("option_symbol", sa.String(length=64), nullable=True))
        if "target_strike" not in columns:
            op.add_column(table_name, sa.Column("target_strike", sa.Float(), nullable=True))
        if "contract_selection" not in columns:
            op.add_column(table_name, sa.Column("contract_selection", sa.JSON(), nullable=True))

        index_name = f"ix_{table_name}_option_symbol"
        if index_name not in _indexes(table_name):
            op.create_index(index_name, table_name, ["option_symbol"], unique=False)


def downgrade() -> None:
    for table_name in reversed(LEG_TABLES):
        indexes = _indexes(table_name)
        index_name = f"ix_{table_name}_option_symbol"
        if index_name in indexes:
            op.drop_index(index_name, table_name=table_name)
        columns = _columns(table_name)
        for column_name in ("contract_selection", "target_strike", "option_symbol"):
            if column_name in columns:
                op.drop_column(table_name, column_name)
