from datetime import date, timedelta

from sqlalchemy import select

from macmarket_trader.domain.enums import Direction
from macmarket_trader.domain.models import (
    AuditLogModel,
    FillModel,
    OrderModel,
    RecommendationEvidenceModel,
    RecommendationModel,
    ReplayRunModel,
)
from macmarket_trader.domain.schemas import Bar, FillRecord, OrderRecord, PortfolioSnapshot, ReplayRunRequest
from macmarket_trader.replay.engine import ReplayEngine
from macmarket_trader.service import RecommendationService
from macmarket_trader.storage.db import build_engine, build_session_factory, init_db
from macmarket_trader.storage.repositories import FillRepository, OrderRepository, RecommendationRepository, ReplayRepository


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
        assert conn.dialect.has_table(conn, "fills")
        assert conn.dialect.has_table(conn, "app_users")


def test_recommendation_persistence(tmp_path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'test.db'}")
    init_db(engine)
    session_factory = build_session_factory(engine)
    service = RecommendationService(
        persist_audit=True,
        recommendation_repository=RecommendationRepository(session_factory),
        order_repository=OrderRepository(session_factory),
        fill_repository=FillRepository(session_factory),
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
        assert session.execute(select(RecommendationEvidenceModel)).scalar_one() is not None
        assert session.execute(select(AuditLogModel)).scalar_one() is not None


def test_order_fill_replay_persistence(tmp_path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'test.db'}")
    init_db(engine)
    session_factory = build_session_factory(engine)
    service = RecommendationService(
        persist_audit=True,
        recommendation_repository=RecommendationRepository(session_factory),
        order_repository=OrderRepository(session_factory),
        fill_repository=FillRepository(session_factory),
    )

    order = OrderRecord(
        recommendation_id="rec_1",
        symbol="AAPL",
        side=Direction.LONG,
        shares=10,
        limit_price=100,
    )
    service.persist_order(order, notes="unit-test")
    service.persist_fill(FillRecord(order_id=order.order_id, fill_price=100.0, filled_shares=10))

    replay = ReplayEngine(service=service, replay_repository=ReplayRepository(session_factory))
    replay.run(ReplayRunRequest(symbol="AAPL", event_texts=["a", "b"], bars=_bars(), portfolio=PortfolioSnapshot()))

    with session_factory() as session:
        assert len(session.execute(select(OrderModel)).scalars().all()) >= 1
        assert len(session.execute(select(FillModel)).scalars().all()) >= 1
        assert len(session.execute(select(ReplayRunModel)).scalars().all()) >= 1
