"""SQLAlchemy repositories for recommendation and order audit writes."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

from macmarket_trader.domain.models import OrderModel, RecommendationModel
from macmarket_trader.domain.schemas import OrderRecord, TradeRecommendation

SessionFactory = Callable[[], Session]


class RecommendationRepository:
    """Persistence helper for recommendation payloads."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self.session_factory = session_factory

    def create(self, recommendation: TradeRecommendation) -> RecommendationModel:
        payload = recommendation.model_dump(mode="json")
        row = RecommendationModel(symbol=recommendation.symbol, payload=payload)
        with self.session_factory() as session:
            session.add(row)
            session.commit()
            session.refresh(row)
        return row


class OrderRepository:
    """Persistence helper for order records."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self.session_factory = session_factory

    def create(self, order: OrderRecord, notes: str = "") -> OrderModel:
        row = OrderModel(
            recommendation_id=order.recommendation_id,
            symbol=order.symbol,
            status=order.status.value,
            side=order.side.value,
            shares=order.shares,
            limit_price=order.limit_price,
            notes=notes,
        )
        with self.session_factory() as session:
            session.add(row)
            session.commit()
            session.refresh(row)
        return row
