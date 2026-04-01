"""Shared pytest fixtures for deterministic database isolation."""

from __future__ import annotations

import pytest

from macmarket_trader.domain.models import Base
from macmarket_trader.storage.db import engine


@pytest.fixture(autouse=True)
def reset_sqlite_schema() -> None:
    """Reset schema per test to prevent cross-test sqlite state leakage."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
