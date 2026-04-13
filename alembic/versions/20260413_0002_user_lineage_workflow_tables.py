"""add app_user_id lineage to workflow persistence tables"""

from alembic import op
import sqlalchemy as sa

revision = "20260413_0002"
down_revision = "20260331_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("recommendations", sa.Column("app_user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_recommendations_app_user_id",
        "recommendations",
        "app_users",
        ["app_user_id"],
        ["id"],
    )
    op.create_index("ix_recommendations_app_user_id", "recommendations", ["app_user_id"])

    op.add_column("replay_runs", sa.Column("app_user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_replay_runs_app_user_id",
        "replay_runs",
        "app_users",
        ["app_user_id"],
        ["id"],
    )
    op.create_index("ix_replay_runs_app_user_id", "replay_runs", ["app_user_id"])

    op.add_column("orders", sa.Column("app_user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_orders_app_user_id",
        "orders",
        "app_users",
        ["app_user_id"],
        ["id"],
    )
    op.create_index("ix_orders_app_user_id", "orders", ["app_user_id"])


def downgrade() -> None:
    op.drop_index("ix_orders_app_user_id", table_name="orders")
    op.drop_constraint("fk_orders_app_user_id", "orders", type_="foreignkey")
    op.drop_column("orders", "app_user_id")

    op.drop_index("ix_replay_runs_app_user_id", table_name="replay_runs")
    op.drop_constraint("fk_replay_runs_app_user_id", "replay_runs", type_="foreignkey")
    op.drop_column("replay_runs", "app_user_id")

    op.drop_index("ix_recommendations_app_user_id", table_name="recommendations")
    op.drop_constraint("fk_recommendations_app_user_id", "recommendations", type_="foreignkey")
    op.drop_column("recommendations", "app_user_id")
