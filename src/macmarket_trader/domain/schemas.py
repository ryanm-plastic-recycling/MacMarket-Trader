"""Pydantic domain schemas for recommendation and execution flows."""

from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

from pydantic import BaseModel, Field

from macmarket_trader.domain.enums import Direction, EventSourceType, OrderStatus, RegimeType, SetupType


class Bar(BaseModel):
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int
    rel_volume: float | None = None


class BaseEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: f"evt_{uuid4().hex[:12]}")
    symbol: str
    source_type: EventSourceType
    source_timestamp: datetime
    headline: str
    summary: str
    sentiment_score: float = Field(ge=-1.0, le=1.0)
    tags: list[str] = Field(default_factory=list)


class NewsEvent(BaseEvent):
    source_type: EventSourceType = EventSourceType.NEWS


class MacroEvent(BaseEvent):
    source_type: EventSourceType = EventSourceType.MACRO


class CorporateEvent(BaseEvent):
    source_type: EventSourceType = EventSourceType.CORPORATE


class RegimeState(BaseModel):
    regime: RegimeType
    trend_score: float
    volatility_score: float
    participation_score: float
    version: str = "regime-v1"


class TechnicalContext(BaseModel):
    prior_day_high: float
    prior_day_low: float
    recent_20d_high: float
    recent_20d_low: float
    atr14: float
    event_day_range: float
    rel_volume: float | None = None


class TradeSetup(BaseModel):
    setup_type: SetupType
    direction: Direction
    entry_zone_low: float
    entry_zone_high: float
    trigger_text: str
    invalidation_price: float
    invalidation_reason: str
    target_1: float
    target_2: float
    trailing_rule_text: str
    time_stop_days: int = Field(ge=1, le=5)
    setup_engine_version: str = "setup-v1"


class EvidenceBundle(BaseModel):
    event_id: str
    source_type: EventSourceType
    source_timestamp: datetime
    regime_version: str
    setup_engine_version: str
    risk_engine_version: str
    explanatory_notes: list[str]


class TradeRecommendation(BaseModel):
    recommendation_id: str = Field(default_factory=lambda: f"rec_{uuid4().hex[:12]}")
    symbol: str
    event: NewsEvent | MacroEvent | CorporateEvent
    regime: RegimeState
    technical_context: TechnicalContext
    setup: TradeSetup
    stop_distance: float
    risk_dollars: float
    shares: int
    approved: bool
    rejection_reason: str | None = None
    evidence: EvidenceBundle


class OrderIntent(BaseModel):
    order_id: str = Field(default_factory=lambda: f"ord_{uuid4().hex[:12]}")
    recommendation_id: str
    symbol: str
    side: Direction
    shares: int
    limit_price: float


class OrderRecord(OrderIntent):
    status: OrderStatus = OrderStatus.CREATED
    created_at: datetime = Field(default_factory=datetime.utcnow)


class FillRecord(BaseModel):
    order_id: str
    fill_price: float
    filled_shares: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PortfolioSnapshot(BaseModel):
    equity: float = 100_000.0
    current_heat: float = 0.0
    open_positions_notional: float = 0.0


class AuditRecord(BaseModel):
    recommendation_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    payload: dict[str, object]


class RecommendationGenerateRequest(BaseModel):
    symbol: str
    event_text: str | None = None
    event: NewsEvent | MacroEvent | CorporateEvent | None = None
    bars: list[Bar]
    portfolio: PortfolioSnapshot | None = None


class ReplayRunRequest(BaseModel):
    symbol: str
    event_texts: list[str]
    bars: list[Bar]
    portfolio: PortfolioSnapshot | None = None


class ReplayRunResponse(BaseModel):
    recommendations: list[TradeRecommendation]
    orders: list[OrderRecord]
    fills: list[FillRecord]
    summary_metrics: dict[str, float]
