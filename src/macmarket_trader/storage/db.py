"""Database engine/session factory."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from macmarket_trader.config import settings
from macmarket_trader.domain.models import Base

engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


def init_db() -> None:
    """Initialize schema for local runs/tests."""
    Base.metadata.create_all(bind=engine)
