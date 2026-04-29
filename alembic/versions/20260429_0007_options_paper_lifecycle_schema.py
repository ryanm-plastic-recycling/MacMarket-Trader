"""add dedicated options paper lifecycle schema foundation

Revision ID: 20260429_0007
Revises: 20260429_0006
Create Date: 2026-04-29
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260429_0007"
down_revision = "20260429_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "paper_option_orders",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("app_user_id", sa.Integer(), sa.ForeignKey("app_users.id"), nullable=False),
        sa.Column("underlying_symbol", sa.String(length=16), nullable=False),
        sa.Column("structure_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="created"),
        sa.Column("expiration", sa.Date(), nullable=True),
        sa.Column("net_debit", sa.Float(), nullable=True),
        sa.Column("net_credit", sa.Float(), nullable=True),
        sa.Column("max_profit", sa.Float(), nullable=True),
        sa.Column("max_loss", sa.Float(), nullable=True),
        sa.Column("breakevens", sa.JSON(), nullable=True),
        sa.Column("execution_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_paper_option_orders_app_user_id", "paper_option_orders", ["app_user_id"])
    op.create_index(
        "ix_paper_option_orders_underlying_symbol", "paper_option_orders", ["underlying_symbol"]
    )
    op.create_index("ix_paper_option_orders_structure_type", "paper_option_orders", ["structure_type"])
    op.create_index("ix_paper_option_orders_status", "paper_option_orders", ["status"])
    op.create_index("ix_paper_option_orders_expiration", "paper_option_orders", ["expiration"])
    op.create_index("ix_paper_option_orders_created_at", "paper_option_orders", ["created_at"])

    op.create_table(
        "paper_option_order_legs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("option_order_id", sa.Integer(), sa.ForeignKey("paper_option_orders.id"), nullable=False),
        sa.Column("action", sa.String(length=8), nullable=False),
        sa.Column("right", sa.String(length=8), nullable=False),
        sa.Column("strike", sa.Float(), nullable=False),
        sa.Column("expiration", sa.Date(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("multiplier", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("premium", sa.Float(), nullable=False),
        sa.Column("leg_status", sa.String(length=24), nullable=False, server_default="created"),
        sa.Column("label", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_paper_option_order_legs_option_order_id", "paper_option_order_legs", ["option_order_id"]
    )
    op.create_index("ix_paper_option_order_legs_expiration", "paper_option_order_legs", ["expiration"])
    op.create_index("ix_paper_option_order_legs_leg_status", "paper_option_order_legs", ["leg_status"])

    op.create_table(
        "paper_option_positions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("app_user_id", sa.Integer(), sa.ForeignKey("app_users.id"), nullable=False),
        sa.Column("underlying_symbol", sa.String(length=16), nullable=False),
        sa.Column("structure_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="open"),
        sa.Column("expiration", sa.Date(), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("opening_net_debit", sa.Float(), nullable=True),
        sa.Column("opening_net_credit", sa.Float(), nullable=True),
        sa.Column("max_profit", sa.Float(), nullable=True),
        sa.Column("max_loss", sa.Float(), nullable=True),
        sa.Column("breakevens", sa.JSON(), nullable=True),
        sa.Column(
            "source_order_id", sa.Integer(), sa.ForeignKey("paper_option_orders.id"), nullable=True
        ),
    )
    op.create_index("ix_paper_option_positions_app_user_id", "paper_option_positions", ["app_user_id"])
    op.create_index(
        "ix_paper_option_positions_underlying_symbol", "paper_option_positions", ["underlying_symbol"]
    )
    op.create_index(
        "ix_paper_option_positions_structure_type", "paper_option_positions", ["structure_type"]
    )
    op.create_index("ix_paper_option_positions_status", "paper_option_positions", ["status"])
    op.create_index("ix_paper_option_positions_expiration", "paper_option_positions", ["expiration"])
    op.create_index("ix_paper_option_positions_opened_at", "paper_option_positions", ["opened_at"])
    op.create_index("ix_paper_option_positions_closed_at", "paper_option_positions", ["closed_at"])
    op.create_index(
        "ix_paper_option_positions_source_order_id", "paper_option_positions", ["source_order_id"]
    )

    op.create_table(
        "paper_option_position_legs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("position_id", sa.Integer(), sa.ForeignKey("paper_option_positions.id"), nullable=False),
        sa.Column("action", sa.String(length=8), nullable=False),
        sa.Column("right", sa.String(length=8), nullable=False),
        sa.Column("strike", sa.Float(), nullable=False),
        sa.Column("expiration", sa.Date(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("multiplier", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("entry_premium", sa.Float(), nullable=False),
        sa.Column("exit_premium", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="open"),
        sa.Column("label", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_paper_option_position_legs_position_id", "paper_option_position_legs", ["position_id"]
    )
    op.create_index(
        "ix_paper_option_position_legs_expiration", "paper_option_position_legs", ["expiration"]
    )
    op.create_index("ix_paper_option_position_legs_status", "paper_option_position_legs", ["status"])

    op.create_table(
        "paper_option_trades",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("app_user_id", sa.Integer(), sa.ForeignKey("app_users.id"), nullable=False),
        sa.Column(
            "position_id", sa.Integer(), sa.ForeignKey("paper_option_positions.id"), nullable=True
        ),
        sa.Column("structure_type", sa.String(length=32), nullable=False),
        sa.Column("underlying_symbol", sa.String(length=16), nullable=False),
        sa.Column("expiration", sa.Date(), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("gross_pnl", sa.Float(), nullable=True),
        sa.Column("total_commissions", sa.Float(), nullable=True),
        sa.Column("net_pnl", sa.Float(), nullable=True),
        sa.Column("settlement_mode", sa.String(length=24), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index("ix_paper_option_trades_app_user_id", "paper_option_trades", ["app_user_id"])
    op.create_index("ix_paper_option_trades_position_id", "paper_option_trades", ["position_id"])
    op.create_index(
        "ix_paper_option_trades_structure_type", "paper_option_trades", ["structure_type"]
    )
    op.create_index(
        "ix_paper_option_trades_underlying_symbol", "paper_option_trades", ["underlying_symbol"]
    )
    op.create_index("ix_paper_option_trades_expiration", "paper_option_trades", ["expiration"])
    op.create_index("ix_paper_option_trades_opened_at", "paper_option_trades", ["opened_at"])
    op.create_index("ix_paper_option_trades_closed_at", "paper_option_trades", ["closed_at"])
    op.create_index(
        "ix_paper_option_trades_settlement_mode", "paper_option_trades", ["settlement_mode"]
    )

    op.create_table(
        "paper_option_trade_legs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("trade_id", sa.Integer(), sa.ForeignKey("paper_option_trades.id"), nullable=False),
        sa.Column("action", sa.String(length=8), nullable=False),
        sa.Column("right", sa.String(length=8), nullable=False),
        sa.Column("strike", sa.Float(), nullable=False),
        sa.Column("expiration", sa.Date(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("multiplier", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("entry_premium", sa.Float(), nullable=True),
        sa.Column("exit_premium", sa.Float(), nullable=True),
        sa.Column("leg_gross_pnl", sa.Float(), nullable=True),
        sa.Column("leg_commission", sa.Float(), nullable=True),
        sa.Column("leg_net_pnl", sa.Float(), nullable=True),
        sa.Column("label", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_paper_option_trade_legs_trade_id", "paper_option_trade_legs", ["trade_id"])
    op.create_index("ix_paper_option_trade_legs_expiration", "paper_option_trade_legs", ["expiration"])


def downgrade() -> None:
    op.drop_index("ix_paper_option_trade_legs_expiration", table_name="paper_option_trade_legs")
    op.drop_index("ix_paper_option_trade_legs_trade_id", table_name="paper_option_trade_legs")
    op.drop_table("paper_option_trade_legs")

    op.drop_index("ix_paper_option_trades_settlement_mode", table_name="paper_option_trades")
    op.drop_index("ix_paper_option_trades_closed_at", table_name="paper_option_trades")
    op.drop_index("ix_paper_option_trades_opened_at", table_name="paper_option_trades")
    op.drop_index("ix_paper_option_trades_expiration", table_name="paper_option_trades")
    op.drop_index("ix_paper_option_trades_underlying_symbol", table_name="paper_option_trades")
    op.drop_index("ix_paper_option_trades_structure_type", table_name="paper_option_trades")
    op.drop_index("ix_paper_option_trades_position_id", table_name="paper_option_trades")
    op.drop_index("ix_paper_option_trades_app_user_id", table_name="paper_option_trades")
    op.drop_table("paper_option_trades")

    op.drop_index("ix_paper_option_position_legs_status", table_name="paper_option_position_legs")
    op.drop_index("ix_paper_option_position_legs_expiration", table_name="paper_option_position_legs")
    op.drop_index("ix_paper_option_position_legs_position_id", table_name="paper_option_position_legs")
    op.drop_table("paper_option_position_legs")

    op.drop_index(
        "ix_paper_option_positions_source_order_id", table_name="paper_option_positions"
    )
    op.drop_index("ix_paper_option_positions_closed_at", table_name="paper_option_positions")
    op.drop_index("ix_paper_option_positions_opened_at", table_name="paper_option_positions")
    op.drop_index("ix_paper_option_positions_expiration", table_name="paper_option_positions")
    op.drop_index("ix_paper_option_positions_status", table_name="paper_option_positions")
    op.drop_index(
        "ix_paper_option_positions_structure_type", table_name="paper_option_positions"
    )
    op.drop_index(
        "ix_paper_option_positions_underlying_symbol", table_name="paper_option_positions"
    )
    op.drop_index("ix_paper_option_positions_app_user_id", table_name="paper_option_positions")
    op.drop_table("paper_option_positions")

    op.drop_index("ix_paper_option_order_legs_leg_status", table_name="paper_option_order_legs")
    op.drop_index("ix_paper_option_order_legs_expiration", table_name="paper_option_order_legs")
    op.drop_index(
        "ix_paper_option_order_legs_option_order_id", table_name="paper_option_order_legs"
    )
    op.drop_table("paper_option_order_legs")

    op.drop_index("ix_paper_option_orders_created_at", table_name="paper_option_orders")
    op.drop_index("ix_paper_option_orders_expiration", table_name="paper_option_orders")
    op.drop_index("ix_paper_option_orders_status", table_name="paper_option_orders")
    op.drop_index("ix_paper_option_orders_structure_type", table_name="paper_option_orders")
    op.drop_index(
        "ix_paper_option_orders_underlying_symbol", table_name="paper_option_orders"
    )
    op.drop_index("ix_paper_option_orders_app_user_id", table_name="paper_option_orders")
    op.drop_table("paper_option_orders")
