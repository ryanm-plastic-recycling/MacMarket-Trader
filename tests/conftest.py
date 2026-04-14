"""Shared pytest fixtures for deterministic database isolation.

Uses a StaticPool in-memory SQLite engine so every session shares a single
connection — no file locks, no WAL files, no cross-run stale state that can
cause intermittent "database is locked" or "no such table" errors when the
full suite runs.

The override of storage.db.engine and storage.db.SessionLocal must happen
BEFORE any macmarket_trader route module is imported, because those modules
capture the SessionLocal reference at import time.  conftest.py is imported
by pytest before any test-file imports, which satisfies that ordering
constraint.
"""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Force test environment defaults before any macmarket_trader imports.
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("AUTH_PROVIDER", "mock")
os.environ.setdefault("EMAIL_PROVIDER", "console")
# Disable live market-data providers so _workflow_bars uses the deterministic
# fallback without triggering the provider-unavailable 503 guard.
os.environ.setdefault("POLYGON_ENABLED", "false")
os.environ.setdefault("MARKET_DATA_ENABLED", "false")
# Point DATABASE_URL at in-memory SQLite so storage.db builds its initial
# singleton against the correct URL (we override it right below).
os.environ["DATABASE_URL"] = "sqlite://"

# ── Build the shared in-memory test engine ──────────────────────────────────
# StaticPool reuses a single SQLite connection across all pool checkouts.
# This means drop_all / create_all and every session in a test all share one
# connection, eliminating SQLite file-level lock contention entirely.
_test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_test_session_factory = sessionmaker(
    bind=_test_engine,
    autoflush=False,
    autocommit=False,
    class_=Session,
)

# ── Patch storage.db singletons before route modules import SessionLocal ─────
# Route modules (admin.py, recommendations.py, …) do
#   from macmarket_trader.storage.db import SessionLocal
#   user_repo = UserRepository(SessionLocal)
# at module level.  Replacing engine and SessionLocal here means those
# module-level captures get our in-memory factory instead of a file-backed one.
import macmarket_trader.storage.db as _db_module  # noqa: E402

_db_module.engine = _test_engine
_db_module.SessionLocal = _test_session_factory

from macmarket_trader.domain.models import Base  # noqa: E402


@pytest.fixture(autouse=True)
def reset_sqlite_schema() -> Generator[None, None, None]:
    """Drop and recreate the schema before each test; dispose after.

    Because StaticPool holds a single connection, drop_all and create_all
    operate on the same connection that all sessions use — no lock races.
    engine.dispose() after the test closes and discards the StaticPool
    connection so the next test starts with a completely empty in-memory
    database (SQLite creates a new in-memory DB on the next connection).
    """
    Base.metadata.drop_all(bind=_test_engine)
    Base.metadata.create_all(bind=_test_engine)
    yield
    _test_engine.dispose()
