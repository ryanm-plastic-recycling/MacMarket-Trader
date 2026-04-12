"""Shared pytest fixtures for deterministic database isolation."""

from __future__ import annotations

import os

import pytest

# Ensure pytest always runs against deterministic local/mock auth defaults,
# regardless of developer-specific .env configuration.
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("AUTH_PROVIDER", "mock")
os.environ.setdefault("EMAIL_PROVIDER", "console")
# Redirect to an isolated test database before any app module is imported.
# settings = Settings() and engine = build_engine() are module-level singletons
# in config.py and storage/db.py — they read DATABASE_URL exactly once at import
# time. Setting this env var here (before the imports below) ensures the entire
# test run uses macmarket_trader_test.db regardless of what directory pytest
# runs from, including deploy-time runs from C:\Dashboard\MacMarket-Trader.
# The production macmarket_trader.db file is never opened or modified by pytest.
os.environ["DATABASE_URL"] = "sqlite:///./macmarket_trader_test.db"

from macmarket_trader.domain.models import Base
from macmarket_trader.storage.db import engine


@pytest.fixture(autouse=True)
def reset_sqlite_schema() -> None:
    """Reset schema per test to prevent cross-test sqlite state leakage."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
