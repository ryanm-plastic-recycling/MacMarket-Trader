"""Backfill paper lifecycle columns and add missing lineage indexes.

Revision ID: 20260508_0011
Revises: 20260503_0010
Create Date: 2026-05-08

Background
----------
The original ``20260415_0005_replay_stageable_and_paper_portfolio_scaffold``
migration created ``paper_positions`` and ``paper_trades`` from an earlier
ORM shape.  Subsequent additions on
``src/macmarket_trader/domain/models.py`` (``opened_qty``,
``remaining_qty``, the ``replay_run_id`` lineage column on
``paper_positions``, and the ``position_id`` / ``replay_run_id`` lineage
columns on ``paper_trades``) were patched into the live schema at startup
by ``apply_schema_updates()`` in ``src/macmarket_trader/storage/db.py``
rather than through a formal Alembic revision, and the corresponding
``index=True`` indexes that the ORM declares were never produced by
Alembic on databases that started from migration 0005.

What this migration does
------------------------
* Backfills the three columns explicitly called out by the
  2026-05-07 roadmap reality audit if they are still missing
  (``paper_positions.opened_qty``, ``paper_positions.remaining_qty``,
  ``paper_trades.realized_pnl``).  ``paper_trades.realized_pnl`` was in
  fact created by 0005, but it remains in the idempotent "if missing"
  list so that databases bootstrapped via ``init_db()`` /
  ``apply_schema_updates()`` reach the same end state.
* Defensively backfills the three lineage columns that the next step
  needs to index (``paper_positions.replay_run_id``,
  ``paper_trades.replay_run_id``, ``paper_trades.position_id``) so the
  index creation never fires against a missing column.
* Adds the three explicit lineage indexes if missing:
  ``ix_paper_positions_replay_run_id``,
  ``ix_paper_trades_replay_run_id``, ``ix_paper_trades_position_id``.

Safety
------
Every step is guarded by an SQLAlchemy inspector check, so the migration
is a no-op on databases where ``apply_schema_updates()`` has already
added the columns, or where ``Base.metadata.create_all()`` already
produced the lineage indexes from the ORM ``index=True`` declarations.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260508_0011"
down_revision = "20260503_0010"
branch_labels = None
depends_on = None


def _column_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {index["name"] for index in inspector.get_indexes(table_name)}


# Columns this migration is responsible for, in upgrade order.
# Each entry is (table_name, column_name, sqlalchemy_column_factory).
# Factories are zero-argument callables so that each call returns a
# fresh ``sa.Column`` (Alembic mutates the column on add_column).
_BACKFILL_COLUMNS: tuple[tuple[str, str, "callable[[], sa.Column]"], ...] = (
    ("paper_positions", "opened_qty",
        lambda: sa.Column("opened_qty", sa.Float(), nullable=True)),
    ("paper_positions", "remaining_qty",
        lambda: sa.Column("remaining_qty", sa.Float(), nullable=True)),
    ("paper_positions", "replay_run_id",
        lambda: sa.Column("replay_run_id", sa.Integer(), nullable=True)),
    ("paper_trades", "realized_pnl",
        lambda: sa.Column("realized_pnl", sa.Float(), nullable=False, server_default="0")),
    ("paper_trades", "position_id",
        lambda: sa.Column("position_id", sa.Integer(), nullable=True)),
    ("paper_trades", "replay_run_id",
        lambda: sa.Column("replay_run_id", sa.Integer(), nullable=True)),
)


# Indexes this migration is responsible for.
# (index_name, table_name, column_name)
_LINEAGE_INDEXES: tuple[tuple[str, str, str], ...] = (
    ("ix_paper_positions_replay_run_id", "paper_positions", "replay_run_id"),
    ("ix_paper_trades_replay_run_id", "paper_trades", "replay_run_id"),
    ("ix_paper_trades_position_id", "paper_trades", "position_id"),
)


def upgrade() -> None:
    # Pass 1 — backfill any missing columns.  Each table is inspected once
    # per column to keep the conditional logic obvious; the underlying
    # ``inspect`` call is cheap enough at private-alpha scale.
    for table_name, column_name, factory in _BACKFILL_COLUMNS:
        if column_name not in _column_names(table_name):
            op.add_column(table_name, factory())

    # Pass 2 — add lineage indexes if both column and index are in the
    # expected state.  Skip silently when the column is missing for any
    # unexpected reason; this keeps the migration idempotent on partially
    # patched databases.
    for index_name, table_name, column_name in _LINEAGE_INDEXES:
        if column_name not in _column_names(table_name):
            continue
        if index_name not in _index_names(table_name):
            op.create_index(index_name, table_name, [column_name], unique=False)


def downgrade() -> None:
    # Drop indexes first so the columns underneath are not in use.
    for index_name, table_name, _ in _LINEAGE_INDEXES:
        if index_name in _index_names(table_name):
            op.drop_index(index_name, table_name=table_name)

    # Drop columns in reverse order.  ``realized_pnl`` is intentionally
    # NOT dropped on downgrade because it pre-existed this migration in
    # the 0005 ledger, and a downgrade should not erase data that earlier
    # migrations created.
    preserve = {("paper_trades", "realized_pnl")}
    for table_name, column_name, _ in reversed(_BACKFILL_COLUMNS):
        if (table_name, column_name) in preserve:
            continue
        if column_name in _column_names(table_name):
            op.drop_column(table_name, column_name)
