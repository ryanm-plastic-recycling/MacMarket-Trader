from datetime import date, timedelta

from sqlalchemy import select

from macmarket_trader.domain.enums import Direction
from macmarket_trader.domain.models import OrderModel, RecommendationModel
from macmarket_trader.domain.schemas import Bar, OrderRecord, PortfolioSnapshot
from macmarket_trader.service import RecommendationService
from macmarket_trader.storage.db import build_engine, build_session_factory, init_db
from macmarket_trader.storage.repositories import OrderRepository, RecommendationRepository


def _bars() -> list[Bar]:
    base = date(2026, 1, 1)
    return [
        Bar(
            date=base + timedelta(days=i),
            open=100 + i,
            high=101 + i,
            low=99 + i,
            close=100.5 + i,
            volume=1_000_000 + i * 10_000,
            rel_volume=1.1,
        )
        for i in range(25)
    ]


def test_database_initialization(tmp_path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'test.db'}")
    init_db(engine)
    with engine.connect() as conn:
        assert conn.dialect.has_table(conn, "recommendations")
        assert conn.dialect.has_table(conn, "orders")


def test_recommendation_persistence(tmp_path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'test.db'}")
    init_db(engine)
    session_factory = build_session_factory(engine)
    service = RecommendationService(
        persist_audit=True,
        recommendation_repository=RecommendationRepository(session_factory),
        order_repository=OrderRepository(session_factory),
    )

    rec = service.generate(
        symbol="AAPL",
        bars=_bars(),
        event_text="earnings beat",
        event=None,
        portfolio=PortfolioSnapshot(),
    )

    with session_factory() as session:
        rows = session.execute(select(RecommendationModel)).scalars().all()
        assert len(rows) == 1
        assert rows[0].symbol == rec.symbol


def test_order_persistence(tmp_path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'test.db'}")
    init_db(engine)
    session_factory = build_session_factory(engine)
    service = RecommendationService(
        persist_audit=True,
        recommendation_repository=RecommendationRepository(session_factory),
        order_repository=OrderRepository(session_factory),
    )

    order = OrderRecord(
        recommendation_id="rec_1",
        symbol="AAPL",
        side=Direction.LONG,
        shares=10,
        limit_price=100,
    )
    service.persist_order(order, notes="unit-test")

    with session_factory() as session:
        rows = session.execute(select(OrderModel)).scalars().all()
        assert len(rows) == 1
        assert rows[0].notes == "unit-test"
