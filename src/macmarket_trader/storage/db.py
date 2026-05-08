"""Database engine/session factory."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from macmarket_trader.config import settings
from macmarket_trader.domain.models import Base


def build_engine(database_url: str | None = None) -> Engine:
    """Create a SQLAlchemy engine for the configured database URL."""
    target = database_url or settings.database_url
    connect_args = {"check_same_thread": False} if target.startswith("sqlite") else {}
    return create_engine(target, future=True, pool_pre_ping=True, connect_args=connect_args)


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a SQLAlchemy session factory for dependency injection in tests."""
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


engine = build_engine()
SessionLocal = build_session_factory(engine)


def init_db(target_engine: Engine | None = None) -> None:
    """Initialize schema for local runs/tests."""
    Base.metadata.create_all(bind=target_engine or engine)


def apply_schema_updates(target_engine: Engine | None = None) -> list[str]:
    """Add any columns that exist in the ORM models but are missing from the DB.

    Source of truth.  Alembic (``alembic/versions/*``) is the canonical
    schema source of truth for MacMarket-Trader: new tables, non-nullable
    columns, indexes, foreign keys, and structural changes must land in a
    formal migration.  This function is a *compatibility shim* only — it
    closes the gap between an ORM model that has already been updated and
    a live database that has not yet had the corresponding Alembic
    revision applied.  It exists so local dev, tests, and the deployed
    SQLite mirror keep working when an ORM addition is committed before
    its migration is.

    Anything added here should be backfilled by a follow-up Alembic
    migration so the migration ledger faithfully describes the runtime
    schema.  See ``alembic/versions/20260508_0011_paper_lifecycle_columns_and_indexes.py``
    for an example of that backfill pattern (idempotent column / index
    creation guarded by inspector checks).

    Safe to call on both fresh and existing databases — it is a no-op
    when the schema is already current.  Returns a list of
    ``'<table>.<column>'`` strings for every column that was added.
    """
    from sqlalchemy import inspect, text  # local to avoid circular import at module level

    e = target_engine or engine
    inspector = inspect(e)
    applied: list[str] = []

    # Ensure tables that don't exist yet are created first.
    Base.metadata.create_all(bind=e)

    with e.connect() as conn:
        for table_name, table in Base.metadata.tables.items():
            if not inspector.has_table(table_name):
                continue
            existing_col_names = {col["name"] for col in inspector.get_columns(table_name)}
            for col in table.columns:
                if col.name in existing_col_names:
                    continue
                # Compile the column type for the target dialect.
                col_type_str = col.type.compile(e.dialect)
                null_clause = "NULL" if col.nullable else "NOT NULL"
                default_clause = ""
                if col.default is not None and col.default.is_scalar:
                    raw = col.default.arg
                    if isinstance(raw, str):
                        default_clause = f" DEFAULT '{raw}'"
                    elif isinstance(raw, bool):
                        default_clause = f" DEFAULT {int(raw)}"
                    elif isinstance(raw, (int, float)):
                        default_clause = f" DEFAULT {raw}"
                ddl = (
                    f"ALTER TABLE {table_name} ADD COLUMN "
                    f"{col.name} {col_type_str} {null_clause}{default_clause}"
                )
                conn.execute(text(ddl))
                applied.append(f"{table_name}.{col.name}")
        if applied:
            conn.commit()

    return applied
