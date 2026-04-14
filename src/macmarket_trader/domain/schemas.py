"""Pydantic domain schemas for recommendation and execution flows."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from macmarket_trader.domain.enums import AppRole, ApprovalStatus, Direction, EventSourceType, InstrumentType, MarketMode, OrderStatus, RegimeType, SetupType, TradingSessionModel
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


class IndicatorContext(BaseModel):
    haco_state: str
    haco_flip_recency_bars: int | None = None
    hacolt_direction: str
    agrees_with_recommendation: bool


class ChartCandle(BaseModel):
    index: int
    time: date
    open: float
    high: float
    low: float
    close: float
    volume: int


class HacoMarker(BaseModel):
    index: int
    time: date
    marker_type: str
    direction: str
    price: float
    text: str


class HacoStatePoint(BaseModel):
    index: int
    time: date
    value: int
    state: str


class HacoltStatePoint(BaseModel):
    index: int
    time: date
    value: int
    direction: str


class HacoChartRequest(BaseModel):
    symbol: str
    timeframe: str = "1D"
    include_heikin_ashi: bool = True
    bars: list[Bar] = Field(default_factory=list)


class HacoChartExplanation(BaseModel):
    current_haco_state: str
    latest_flip: str
    latest_flip_bars_ago: int | None = None
    current_hacolt_direction: str


class HacoChartPayload(BaseModel):
    symbol: str
    timeframe: str
    candles: list[ChartCandle]
    heikin_ashi_candles: list[ChartCandle] = Field(default_factory=list)
    markers: list[HacoMarker]
    haco_strip: list[HacoStatePoint]
    hacolt_strip: list[HacoltStatePoint]
    explanation: HacoChartExplanation
    data_source: str = "request_bars"
    fallback_mode: bool = False


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
    market_mode: MarketMode = MarketMode.EQUITIES
    recommendation_id: str = Field(default_factory=lambda: f"rec_{uuid4().hex[:12]}")
    symbol: str
    side: Direction
    thesis: str
    event: NewsEvent | MacroEvent | CorporateEvent
    catalyst: CatalystMetadata
    regime_context: RegimeContext
    technical_context: TechnicalContext
    indicator_context: IndicatorContext | None = None
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


class InstrumentIdentity(BaseModel):
    market_mode: MarketMode = MarketMode.EQUITIES
    instrument_type: InstrumentType = InstrumentType.EQUITY
    symbol: str
    underlying_symbol: str | None = None
    quote_currency: str = "USD"
    trading_session_model: TradingSessionModel = TradingSessionModel.US_EQUITIES_REGULAR_HOURS


class OptionContractContext(BaseModel):
    expiration: date
    strike: float
    option_right: Literal["call", "put"]
    multiplier: int = 100
    days_to_expiration: int
    implied_volatility: float | None = None
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
    open_interest: int | None = None
    bid: float | None = None
    ask: float | None = None


class OptionStructureLeg(BaseModel):
    action: Literal["buy", "sell"]
    option_right: Literal["call", "put"]
    strike: float
    quantity: int = 1


class OptionStructureContext(BaseModel):
    strategy_id: str
    strategy_legs: list[OptionStructureLeg] = Field(default_factory=list)
    net_debit_credit: float
    max_profit: float
    max_loss: float
    breakeven_low: float | None = None
    breakeven_high: float | None = None


class ExpectedRange(BaseModel):
    method: Literal["iv_1sigma", "atm_straddle_mid", "equity_realized_vol_1sigma", "equity_atr_projection", "crypto_realized_vol_1sigma"] | None = None
    horizon_value: int | None = None
    horizon_unit: Literal["calendar_days", "trading_days", "hours"] | None = None
    reference_price_type: str | None = None
    absolute_move: float | None = None
    percent_move: float | None = None
    lower_bound: float | None = None
    upper_bound: float | None = None
    snapshot_timestamp: datetime | None = None
    provenance_notes: str | None = None
    status: Literal["computed", "blocked", "omitted"] = "omitted"
    reason: str | None = None


class CryptoMarketContext(BaseModel):
    venue: str
    quote_currency: str = "USD"
    mark_price: float | None = None
    index_price: float | None = None
    funding_rate: float | None = None
    basis: float | None = None
    open_interest: float | None = None
    liquidation_buffer_pct: float | None = None


class RecommendationGenerateRequest(BaseModel):
    symbol: str
    market_mode: MarketMode = MarketMode.EQUITIES
    strategy_id: str | None = None
    event_text: str | None = None
    event: NewsEvent | MacroEvent | CorporateEvent | None = None
    bars: list[Bar]
    portfolio: PortfolioSnapshot | None = None


class ReplayRunRequest(BaseModel):
    symbol: str
    market_mode: MarketMode = MarketMode.EQUITIES
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


class InviteCreateRequest(BaseModel):
    email: str
    display_name: str | None = None

class ReplayRunResponse(BaseModel):
    market_mode: MarketMode = MarketMode.EQUITIES
    recommendations: list[TradeRecommendation]
    orders: list[OrderRecord]
    fills: list[FillRecord]
    final_portfolio: PortfolioSnapshot
    summary_metrics: ReplaySummaryMetrics
