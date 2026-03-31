"""Database engine/session factory."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from macmarket_trader.config import settings
from macmarket_trader.domain.models import Base


def build_engine(database_url: str | None = None) -> Engine:
    """Create a SQLAlchemy engine for the configured database URL."""
    return create_engine(database_url or settings.database_url, future=True)


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a SQLAlchemy session factory for dependency injection in tests."""
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


engine = build_engine()
SessionLocal = build_session_factory(engine)


def init_db(target_engine: Engine | None = None) -> None:
    """Initialize schema for local runs/tests."""
    Base.metadata.create_all(bind=target_engine or engine)
