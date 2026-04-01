"""Pydantic domain schemas for recommendation and execution flows."""

from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

from pydantic import BaseModel, Field

from macmarket_trader.domain.enums import AppRole, ApprovalStatus, Direction, EventSourceType, OrderStatus, RegimeType, SetupType
from macmarket_trader.domain.time import utc_now


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


class RegimeContext(BaseModel):
    market_regime: RegimeType
    volatility_regime: str
    breadth_state: str


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


class CatalystMetadata(BaseModel):
    type: str
    novelty: str
    source_quality: str
    event_timestamp: datetime


class EntryMetadata(BaseModel):
    setup_type: SetupType
    zone_low: float
    zone_high: float
    trigger_text: str


class InvalidationMetadata(BaseModel):
    price: float
    reason: str


class TargetsMetadata(BaseModel):
    target_1: float
    target_2: float
    trailing_rule: str


class TimeStopMetadata(BaseModel):
    max_holding_days: int = Field(ge=1, le=5)
    reason: str


class SizingMetadata(BaseModel):
    risk_dollars: float
    stop_distance: float
    shares: int


class QualityMetadata(BaseModel):
    expected_rr: float
    confidence: float = Field(ge=0.0, le=1.0)
    risk_score: float = Field(ge=0.0, le=1.0)


class EvidenceBundle(BaseModel):
    event_id: str
    source_type: EventSourceType
    source_timestamp: datetime
    regime_version: str
    setup_engine_version: str
    risk_engine_version: str
    explanatory_notes: list[str]
    headlines: list[str] = Field(default_factory=list)
    filings: list[str] = Field(default_factory=list)
    technical_context_refs: list[str] = Field(default_factory=list)
    historical_analog_refs: list[str] = Field(default_factory=list)


class ConstraintCheck(BaseModel):
    name: str
    passed: bool
    details: str


class ConstraintReport(BaseModel):
    checks: list[ConstraintCheck]
    risk_based_share_cap: int
    notional_share_cap: int
    explicit_share_cap: int | None = None
    final_share_count: int


class TradeRecommendation(BaseModel):
    outcome: str = "approved"
    recommendation_id: str = Field(default_factory=lambda: f"rec_{uuid4().hex[:12]}")
    symbol: str
    side: Direction
    thesis: str
    event: NewsEvent | MacroEvent | CorporateEvent
    catalyst: CatalystMetadata
    regime_context: RegimeContext
    technical_context: TechnicalContext
    entry: EntryMetadata
    invalidation: InvalidationMetadata
    targets: TargetsMetadata
    time_stop: TimeStopMetadata
    sizing: SizingMetadata
    quality: QualityMetadata
    approved: bool
    rejection_reason: str | None = None
    constraints: ConstraintReport
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
    filled_shares: int = 0
    created_at: datetime = Field(default_factory=utc_now)


class FillRecord(BaseModel):
    order_id: str
    fill_price: float
    filled_shares: int
    timestamp: datetime = Field(default_factory=utc_now)


class PortfolioSnapshot(BaseModel):
    equity: float = 100_000.0
    current_heat: float = 0.0
    open_positions_notional: float = 0.0


class AuditRecord(BaseModel):
    recommendation_id: str
    timestamp: datetime = Field(default_factory=utc_now)
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




class ReplaySummaryMetrics(BaseModel):
    recommendation_count: float
    approved_count: float
    fill_count: float
    ending_heat: float
    ending_open_notional: float


class AppUser(BaseModel):
    external_auth_user_id: str
    email: str
    display_name: str
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    app_role: AppRole = AppRole.USER
    mfa_enabled: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    approved_at: datetime | None = None
    approved_by: str | None = None


class ApprovalActionRequest(BaseModel):
    user_id: int
    note: str = ""

class ReplayRunResponse(BaseModel):
    recommendations: list[TradeRecommendation]
    orders: list[OrderRecord]
    fills: list[FillRecord]
    final_portfolio: PortfolioSnapshot
    summary_metrics: ReplaySummaryMetrics
