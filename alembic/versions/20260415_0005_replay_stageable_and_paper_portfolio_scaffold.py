"""add replay stageable outcome + paper portfolio scaffolding

Revision ID: 20260415_0005
Revises: 20260414_0004
Create Date: 2026-04-15
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260415_0005"
down_revision = "20260414_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("replay_runs", sa.Column("has_stageable_candidate", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("replay_runs", sa.Column("stageable_recommendation_id", sa.String(length=64), nullable=True))
    op.add_column("replay_runs", sa.Column("stageable_reason", sa.Text(), nullable=True))
    op.create_index("ix_replay_runs_stageable_recommendation_id", "replay_runs", ["stageable_recommendation_id"])

    op.create_table(
        "paper_positions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("app_user_id", sa.Integer(), sa.ForeignKey("app_users.id"), nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("average_price", sa.Float(), nullable=False),
        sa.Column("open_notional", sa.Float(), nullable=False, server_default="0"),
        sa.Column("unrealized_pnl", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_paper_positions_app_user_id", "paper_positions", ["app_user_id"])
    op.create_index("ix_paper_positions_symbol", "paper_positions", ["symbol"])
    op.create_index("ix_paper_positions_status", "paper_positions", ["status"])

    op.create_table(
        "paper_trades",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("app_user_id", sa.Integer(), sa.ForeignKey("app_users.id"), nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("exit_price", sa.Float(), nullable=True),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("realized_pnl", sa.Float(), nullable=False, server_default="0"),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_paper_trades_app_user_id", "paper_trades", ["app_user_id"])
    op.create_index("ix_paper_trades_symbol", "paper_trades", ["symbol"])


def downgrade() -> None:
    op.drop_index("ix_paper_trades_symbol", table_name="paper_trades")
    op.drop_index("ix_paper_trades_app_user_id", table_name="paper_trades")
    op.drop_table("paper_trades")

    op.drop_index("ix_paper_positions_status", table_name="paper_positions")
    op.drop_index("ix_paper_positions_symbol", table_name="paper_positions")
    op.drop_index("ix_paper_positions_app_user_id", table_name="paper_positions")
    op.drop_table("paper_positions")

    op.drop_index("ix_replay_runs_stageable_recommendation_id", table_name="replay_runs")
    op.drop_column("replay_runs", "stageable_reason")
    op.drop_column("replay_runs", "stageable_recommendation_id")
    op.drop_column("replay_runs", "has_stageable_candidate")
