"""add source lineage columns for replay runs"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260414_0004"
down_revision = "20260414_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("replay_runs", sa.Column("source_recommendation_id", sa.String(length=64), nullable=True))
    op.add_column("replay_runs", sa.Column("source_strategy", sa.String(length=64), nullable=True))
    op.add_column("replay_runs", sa.Column("source_market_mode", sa.String(length=32), nullable=True))
    op.add_column("replay_runs", sa.Column("source_market_data_source", sa.String(length=64), nullable=True))
    op.add_column("replay_runs", sa.Column("source_fallback_mode", sa.Boolean(), nullable=True))
    op.create_index("ix_replay_runs_source_recommendation_id", "replay_runs", ["source_recommendation_id"])


def downgrade() -> None:
    op.drop_index("ix_replay_runs_source_recommendation_id", table_name="replay_runs")
    op.drop_column("replay_runs", "source_fallback_mode")
    op.drop_column("replay_runs", "source_market_data_source")
    op.drop_column("replay_runs", "source_market_mode")
    op.drop_column("replay_runs", "source_strategy")
    op.drop_column("replay_runs", "source_recommendation_id")
