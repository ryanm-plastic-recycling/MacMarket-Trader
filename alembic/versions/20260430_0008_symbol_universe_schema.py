"""add symbol universe schema foundation

Revision ID: 20260430_0008
Revises: 20260429_0007
Create Date: 2026-04-30
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260430_0008"
down_revision = "20260429_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_symbol_universe",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("app_user_id", sa.Integer(), sa.ForeignKey("app_users.id"), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("normalized_symbol", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("asset_type", sa.String(length=32), nullable=True),
        sa.Column("exchange", sa.String(length=64), nullable=True),
        sa.Column("provider_source", sa.String(length=64), nullable=True),
        sa.Column("provider_symbol", sa.String(length=64), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "app_user_id",
            "normalized_symbol",
            name="uq_user_symbol_universe_user_symbol",
        ),
    )
    op.create_index("ix_user_symbol_universe_app_user_id", "user_symbol_universe", ["app_user_id"])
    op.create_index("ix_user_symbol_universe_symbol", "user_symbol_universe", ["symbol"])
    op.create_index(
        "ix_user_symbol_universe_normalized_symbol",
        "user_symbol_universe",
        ["normalized_symbol"],
    )
    op.create_index("ix_user_symbol_universe_asset_type", "user_symbol_universe", ["asset_type"])
    op.create_index("ix_user_symbol_universe_active", "user_symbol_universe", ["active"])
    op.create_index("ix_user_symbol_universe_created_at", "user_symbol_universe", ["created_at"])
    op.create_index("ix_user_symbol_universe_updated_at", "user_symbol_universe", ["updated_at"])
    op.create_index(
        "ix_user_symbol_universe_user_active",
        "user_symbol_universe",
        ["app_user_id", "active"],
    )
    op.create_index(
        "ix_user_symbol_universe_user_asset_type",
        "user_symbol_universe",
        ["app_user_id", "asset_type"],
    )

    op.create_table(
        "watchlist_symbols",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("watchlist_id", sa.Integer(), sa.ForeignKey("watchlists.id"), nullable=False),
        sa.Column("app_user_id", sa.Integer(), sa.ForeignKey("app_users.id"), nullable=False),
        sa.Column(
            "user_symbol_id",
            sa.Integer(),
            sa.ForeignKey("user_symbol_universe.id"),
            nullable=True,
        ),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("normalized_symbol", sa.String(length=32), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("sort_order", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "watchlist_id",
            "normalized_symbol",
            name="uq_watchlist_symbols_watchlist_symbol",
        ),
    )
    op.create_index("ix_watchlist_symbols_watchlist_id", "watchlist_symbols", ["watchlist_id"])
    op.create_index("ix_watchlist_symbols_app_user_id", "watchlist_symbols", ["app_user_id"])
    op.create_index("ix_watchlist_symbols_user_symbol_id", "watchlist_symbols", ["user_symbol_id"])
    op.create_index("ix_watchlist_symbols_symbol", "watchlist_symbols", ["symbol"])
    op.create_index(
        "ix_watchlist_symbols_normalized_symbol",
        "watchlist_symbols",
        ["normalized_symbol"],
    )
    op.create_index("ix_watchlist_symbols_active", "watchlist_symbols", ["active"])
    op.create_index("ix_watchlist_symbols_added_at", "watchlist_symbols", ["added_at"])
    op.create_index("ix_watchlist_symbols_created_at", "watchlist_symbols", ["created_at"])
    op.create_index("ix_watchlist_symbols_updated_at", "watchlist_symbols", ["updated_at"])
    op.create_index(
        "ix_watchlist_symbols_watchlist_active_sort",
        "watchlist_symbols",
        ["watchlist_id", "active", "sort_order"],
    )


def downgrade() -> None:
    op.drop_index("ix_watchlist_symbols_watchlist_active_sort", table_name="watchlist_symbols")
    op.drop_index("ix_watchlist_symbols_updated_at", table_name="watchlist_symbols")
    op.drop_index("ix_watchlist_symbols_created_at", table_name="watchlist_symbols")
    op.drop_index("ix_watchlist_symbols_added_at", table_name="watchlist_symbols")
    op.drop_index("ix_watchlist_symbols_active", table_name="watchlist_symbols")
    op.drop_index("ix_watchlist_symbols_normalized_symbol", table_name="watchlist_symbols")
    op.drop_index("ix_watchlist_symbols_symbol", table_name="watchlist_symbols")
    op.drop_index("ix_watchlist_symbols_user_symbol_id", table_name="watchlist_symbols")
    op.drop_index("ix_watchlist_symbols_app_user_id", table_name="watchlist_symbols")
    op.drop_index("ix_watchlist_symbols_watchlist_id", table_name="watchlist_symbols")
    op.drop_table("watchlist_symbols")

    op.drop_index("ix_user_symbol_universe_user_asset_type", table_name="user_symbol_universe")
    op.drop_index("ix_user_symbol_universe_user_active", table_name="user_symbol_universe")
    op.drop_index("ix_user_symbol_universe_updated_at", table_name="user_symbol_universe")
    op.drop_index("ix_user_symbol_universe_created_at", table_name="user_symbol_universe")
    op.drop_index("ix_user_symbol_universe_active", table_name="user_symbol_universe")
    op.drop_index("ix_user_symbol_universe_asset_type", table_name="user_symbol_universe")
    op.drop_index("ix_user_symbol_universe_normalized_symbol", table_name="user_symbol_universe")
    op.drop_index("ix_user_symbol_universe_symbol", table_name="user_symbol_universe")
    op.drop_index("ix_user_symbol_universe_app_user_id", table_name="user_symbol_universe")
    op.drop_table("user_symbol_universe")
