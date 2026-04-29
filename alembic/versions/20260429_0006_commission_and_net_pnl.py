"""add commission settings and gross/net paper trade pnl

Revision ID: 20260429_0006
Revises: 20260415_0005
Create Date: 2026-04-29
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260429_0006"
down_revision = "20260415_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("app_users", sa.Column("commission_per_trade", sa.Float(), nullable=True))
    op.add_column("app_users", sa.Column("commission_per_contract", sa.Float(), nullable=True))

    op.add_column("paper_trades", sa.Column("gross_pnl", sa.Float(), nullable=False, server_default="0"))
    op.add_column("paper_trades", sa.Column("net_pnl", sa.Float(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("paper_trades", "net_pnl")
    op.drop_column("paper_trades", "gross_pnl")

    op.drop_column("app_users", "commission_per_contract")
    op.drop_column("app_users", "commission_per_trade")
