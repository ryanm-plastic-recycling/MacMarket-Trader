"""Pydantic domain schemas for recommendation and execution flows."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from macmarket_trader.domain.enums import AppRole, ApprovalStatus, Direction, EventSourceType, InstrumentType, MarketMode, OrderStatus, RegimeType, SetupType, TradingSessionModel
from macmarket_trader.domain.time import utc_now


class Bar(BaseModel):
    date: date
    timestamp: datetime | None = None
    open: float
    high: float
    low: float
    close: float
    volume: int
    rel_volume: float | None = None
    session_policy: str | None = None
    source_session_policy: str | None = None
    source_timeframe: str | None = None
    provider: str | None = None


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
    time: str | int
    open: float
    high: float
    low: float
    close: float
    volume: int


class HacoMarker(BaseModel):
    index: int
    time: str | int
    marker_type: str
    direction: str
    price: float
    text: str


class HacoStatePoint(BaseModel):
    index: int
    time: str | int
    value: int
    state: str


class HacoltStatePoint(BaseModel):
    index: int
    time: str | int
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
    session_policy: str | None = None
    source_session_policy: str | None = None
    source_timeframe: str | None = None
    output_timeframe: str | None = None
    filtered_extended_hours_count: int | None = None
    rth_bucket_count: int | None = None
    first_bar_timestamp: str | None = None
    last_bar_timestamp: str | None = None


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


class LLMEventFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: EventSourceType
    headline: str = Field(min_length=1, max_length=240)
    summary: str = Field(min_length=1, max_length=1200)
    sentiment_score: float = Field(ge=-1.0, le=1.0)
    tags: list[str] = Field(default_factory=list, max_length=12)


class LLMRecommendationExplanation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=1200)
    approval_explanation: str = Field(min_length=1, max_length=1200)
    counter_thesis: list[str] = Field(default_factory=list, max_length=8)
    deterministic_engine_owns: list[str] = Field(
        default_factory=lambda: ["entry", "stop", "target", "sizing", "approval", "order_routing"]
    )
    explanation_only: bool = True

    @model_validator(mode="after")
    def _guardrail_fields(self) -> "LLMRecommendationExplanation":
        required = {"entry", "stop", "target", "sizing", "approval", "order_routing"}
        if set(self.deterministic_engine_owns) != required:
            raise ValueError("deterministic_engine_owns must name only the deterministic decision fields")
        if self.explanation_only is not True:
            raise ValueError("LLM explanation must be labeled explanation_only")
        return self


class LLMProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    model: str | None = None
    prompt_version: str
    generated_at: datetime
    fallback_used: bool = False
    validation_errors: list[str] = Field(default_factory=list)


class OpportunityIntelligenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected_recommendation_ids: list[str] = Field(default_factory=list, max_length=12)
    watchlist_or_universe_name: str | None = Field(default=None, max_length=120)
    include_better_elsewhere: bool = False
    max_candidates: int = Field(default=5, ge=2, le=12)


RiskEventType = Literal[
    "cpi",
    "pce",
    "fomc_decision",
    "fomc_press_conference",
    "nonfarm_payrolls",
    "gdp",
    "retail_sales",
    "treasury_auction",
    "market_holiday",
    "market_half_day",
    "monthly_opex",
    "quarterly_opex",
    "quad_witching",
    "index_rebalance",
    "earnings",
    "earnings_call",
    "investor_day",
    "product_event",
    "regulatory_event",
    "unscheduled_news_shock",
    "provider_data_issue",
]
RiskEventScope = Literal["market", "sector", "symbol", "portfolio"]
RiskDecisionState = Literal[
    "normal",
    "caution",
    "restricted",
    "no_trade",
    "requires_event_evidence",
    "data_quality_block",
]
RiskLevel = Literal["normal", "elevated", "high", "extreme"]
RiskRecommendedAction = Literal[
    "trade_normally",
    "caution",
    "reduce_size",
    "wait",
    "sit_out",
    "event_trade_review",
]
RiskEventImpact = Literal["low", "medium", "high", "extreme"]


class MarketRiskEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(default_factory=lambda: f"risk_evt_{uuid4().hex[:12]}")
    event_type: RiskEventType
    scope: RiskEventScope = "market"
    title: str
    starts_at: datetime
    ends_at: datetime | None = None
    impact: RiskEventImpact = "medium"
    symbols: list[str] = Field(default_factory=list)
    sectors: list[str] = Field(default_factory=list)
    source: str = "static"
    is_confirmed: bool = True


class SymbolRiskEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(default_factory=lambda: f"risk_evt_{uuid4().hex[:12]}")
    event_type: RiskEventType
    scope: Literal["symbol"] = "symbol"
    symbol: str
    title: str
    starts_at: datetime
    ends_at: datetime | None = None
    impact: RiskEventImpact = "medium"
    source: str = "static"
    is_confirmed: bool = True


class EventEvidenceBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    as_of: datetime
    event_type: RiskEventType
    symbol: str | None = None
    summary: str
    metrics: dict[str, object] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
    provenance: dict[str, object] = Field(default_factory=dict)
    stale: bool = False


class RiskGateDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_state: RiskDecisionState = "normal"
    allow_new_entries: bool = True
    requires_confirmation: bool = False
    recommended_action: RiskRecommendedAction = "trade_normally"
    risk_level: RiskLevel = "normal"
    block_reason: str | None = None
    warning_summary: str = "No active market-risk calendar blocks."
    active_events: list[MarketRiskEvent | SymbolRiskEvent] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    override_allowed: bool = False
    override_reason_required: bool = False
    assessed_at: datetime = Field(default_factory=utc_now)
    paper_only: bool = True
    regular_hours_only: bool = True


class RiskCalendarAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str | None = None
    timeframe: str = "1D"
    decision: RiskGateDecision
    market_events: list[MarketRiskEvent] = Field(default_factory=list)
    symbol_events: list[SymbolRiskEvent] = Field(default_factory=list)
    evidence: list[EventEvidenceBundle] = Field(default_factory=list)
    volatility_flags: list[str] = Field(default_factory=list)
    data_quality_flags: list[str] = Field(default_factory=list)


class OpportunityCandidateSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation_id: str
    display_id: str | None = None
    symbol: str
    side: str
    timeframe: str = "1D"
    approved: bool
    status: str
    deterministic_score: float | None = None
    confidence: float | None = None
    risk_score: float | None = None
    expected_rr: float | None = None
    entry: dict[str, object] | None = None
    invalidation: dict[str, object] | None = None
    targets: dict[str, object] | None = None
    risk_dollars: float | None = None
    final_order_shares: int | None = None
    final_order_notional: float | None = None
    current_recommendation_rank: int | None = None
    reasons: list[str] = Field(default_factory=list, max_length=12)
    rejection_reason: str | None = None
    market_regime: dict[str, object] | None = None
    event_summary: str | None = None
    workflow_source: str | None = None
    session_policy: str | None = None
    data_quality: dict[str, object] | None = None
    risk_calendar: RiskCalendarAssessment | None = None


class BetterElsewhereCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation_id: str | None = None
    symbol: str
    rank: int | None = None
    deterministic_score: float | None = None
    expected_rr: float | None = None
    confidence: float | None = None
    reason: str
    source: Literal["deterministic_scan", "research_only_unverified"] = "deterministic_scan"
    verified_by_scan: bool = True


class OpportunityIntelligenceProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    model: str | None = None
    prompt_version: str
    generated_at: datetime
    fallback_used: bool = False
    validation_errors: list[str] = Field(default_factory=list)
    candidate_ids: list[str] = Field(default_factory=list)
    scanned_symbols: list[str] = Field(default_factory=list)
    better_elsewhere_source: Literal["deterministic_scan", "omitted"] = "omitted"


class OpportunityComparisonMemo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    best_deterministic_candidate_id: str | None = None
    best_deterministic_symbol: str | None = None
    market_desk_memo: str = Field(min_length=1, max_length=2400)
    comparison_rows: list[dict[str, object]] = Field(default_factory=list, max_length=12)
    counter_thesis_by_candidate: dict[str, list[str]] = Field(default_factory=dict)
    better_elsewhere: list[BetterElsewhereCandidate] = Field(default_factory=list, max_length=12)
    not_good_enough_warning: str | None = Field(default=None, max_length=600)
    missing_data: list[str] = Field(default_factory=list, max_length=12)
    deterministic_engine_owns: list[str] = Field(
        default_factory=lambda: [
            "approved",
            "side",
            "entry",
            "invalidation",
            "targets",
            "shares",
            "sizing",
            "order_status",
            "paper_position_status",
        ]
    )
    explanation_only: bool = True
    candidates: list[OpportunityCandidateSummary] = Field(default_factory=list, max_length=12)
    provenance: OpportunityIntelligenceProvenance | None = None

    @model_validator(mode="after")
    def _guardrail_fields(self) -> "OpportunityComparisonMemo":
        required = {
            "approved",
            "side",
            "entry",
            "invalidation",
            "targets",
            "shares",
            "sizing",
            "order_status",
            "paper_position_status",
        }
        if set(self.deterministic_engine_owns) != required:
            raise ValueError("deterministic_engine_owns must name only deterministic trade fields")
        if self.explanation_only is not True:
            raise ValueError("Opportunity Intelligence must be labeled explanation_only")
        return self


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
    ai_explanation: LLMRecommendationExplanation | None = None
    llm_provenance: LLMProvenance | None = None
    risk_calendar: RiskCalendarAssessment | None = None


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


class OptionReplayPreviewLegRequest(BaseModel):
    action: str | None = None
    right: str | None = None
    strike: object | None = None
    premium: object | None = None
    quantity: object | None = 1
    multiplier: object | None = 100
    label: str | None = None


class OptionReplayPreviewRequest(BaseModel):
    structure_type: str | None = None
    legs: list[OptionReplayPreviewLegRequest] = Field(default_factory=list)
    underlying_prices: list[object] | None = None
    underlying_symbol: str | None = None
    expiration: date | None = None
    notes: list[str] = Field(default_factory=list)
    source: str | None = None
    workflow_source: str | None = None


class OptionReplayPreviewLeg(BaseModel):
    action: str | None = None
    right: str | None = None
    strike: float | None = None
    premium: float | None = None
    quantity: int | None = None
    multiplier: int | None = None
    label: str | None = None


class OptionReplayPreviewLegPayoff(BaseModel):
    label: str
    payoff: float


class OptionReplayPreviewPoint(BaseModel):
    underlying_price: float
    total_payoff: float
    leg_payoffs: list[OptionReplayPreviewLegPayoff] = Field(default_factory=list)


class OptionReplayPreviewResponse(BaseModel):
    execution_enabled: bool = False
    persistence_enabled: bool = False
    market_mode: MarketMode = MarketMode.OPTIONS
    preview_type: Literal["expiration_payoff"] = "expiration_payoff"
    status: Literal["ready", "blocked", "unsupported"] = "ready"
    structure_type: str | None = None
    underlying_symbol: str | None = None
    expiration: date | None = None
    replay_run_id: int | None = None
    recommendation_id: str | None = None
    order_id: str | None = None
    is_defined_risk: bool = False
    net_debit: float | None = None
    net_credit: float | None = None
    max_profit: float | None = None
    max_loss: float | None = None
    breakevens: list[float] = Field(default_factory=list)
    payoff_points: list[OptionReplayPreviewPoint] = Field(default_factory=list)
    legs: list[OptionReplayPreviewLeg] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    blocked_reason: str | None = None
    operator_disclaimer: str = "Options research only. Paper-only preview. Not execution support."
    notes: list[str] = Field(default_factory=list)
    source: str | None = None
    workflow_source: str | None = None


class OptionPaperLegInput(BaseModel):
    action: Literal["buy", "sell"]
    right: Literal["call", "put"]
    strike: float
    expiration: date
    premium: float
    quantity: int = 1
    multiplier: int = 100
    label: str | None = None


class OptionPaperStructureInput(BaseModel):
    market_mode: MarketMode = MarketMode.OPTIONS
    structure_type: Literal["long_call", "long_put", "vertical_debit_spread", "iron_condor"]
    underlying_symbol: str
    expiration: date | None = None
    legs: list[OptionPaperLegInput] = Field(default_factory=list)
    net_debit: float | None = None
    net_credit: float | None = None
    max_profit: float | None = None
    max_loss: float | None = None
    breakevens: list[float] = Field(default_factory=list)
    notes: str | None = None


class OptionPaperOrderLegRecord(BaseModel):
    id: int
    option_order_id: int
    action: str
    right: str
    strike: float
    expiration: date
    quantity: int
    multiplier: int
    premium: float
    leg_status: str
    label: str | None = None


class OptionPaperOrderRecord(BaseModel):
    id: int
    app_user_id: int
    market_mode: MarketMode = MarketMode.OPTIONS
    underlying_symbol: str
    structure_type: str
    status: str
    expiration: date | None = None
    net_debit: float | None = None
    net_credit: float | None = None
    max_profit: float | None = None
    max_loss: float | None = None
    breakevens: list[float] = Field(default_factory=list)
    execution_enabled: bool = False
    notes: str = ""
    created_at: datetime
    legs: list[OptionPaperOrderLegRecord] = Field(default_factory=list)


class OptionPaperPositionLegRecord(BaseModel):
    id: int
    position_id: int
    action: str
    right: str
    strike: float
    expiration: date
    quantity: int
    multiplier: int
    entry_premium: float
    exit_premium: float | None = None
    status: str
    label: str | None = None


class OptionPaperPositionRecord(BaseModel):
    id: int
    app_user_id: int
    market_mode: MarketMode = MarketMode.OPTIONS
    underlying_symbol: str
    structure_type: str
    status: str
    expiration: date | None = None
    opened_at: datetime
    closed_at: datetime | None = None
    opening_net_debit: float | None = None
    opening_net_credit: float | None = None
    max_profit: float | None = None
    max_loss: float | None = None
    breakevens: list[float] = Field(default_factory=list)
    source_order_id: int | None = None
    legs: list[OptionPaperPositionLegRecord] = Field(default_factory=list)


class OptionPaperTradeLegRecord(BaseModel):
    id: int
    trade_id: int
    action: str
    right: str
    strike: float
    expiration: date
    quantity: int
    multiplier: int
    entry_premium: float | None = None
    exit_premium: float | None = None
    leg_gross_pnl: float | None = None
    leg_commission: float | None = None
    leg_net_pnl: float | None = None
    label: str | None = None


class OptionPaperTradeRecord(BaseModel):
    id: int
    app_user_id: int
    market_mode: MarketMode = MarketMode.OPTIONS
    position_id: int | None = None
    structure_type: str
    underlying_symbol: str
    expiration: date | None = None
    opened_at: datetime
    closed_at: datetime | None = None
    gross_pnl: float | None = None
    total_commissions: float | None = None
    net_pnl: float | None = None
    settlement_mode: str | None = None
    notes: str = ""
    legs: list[OptionPaperTradeLegRecord] = Field(default_factory=list)


class OptionPaperLifecycleLegSummary(BaseModel):
    action: str
    right: str
    strike: float
    expiration: date
    quantity: int
    multiplier: int
    entry_premium: float | None = None
    exit_premium: float | None = None
    status: str | None = None
    label: str | None = None
    leg_gross_pnl: float | None = None
    leg_commission: float | None = None
    leg_net_pnl: float | None = None


class OptionPaperLifecycleSummary(BaseModel):
    position_id: int
    trade_id: int | None = None
    market_mode: MarketMode = MarketMode.OPTIONS
    underlying_symbol: str
    structure_type: str
    status: str
    expiration: date | None = None
    opened_at: datetime
    closed_at: datetime | None = None
    source_order_id: int | None = None
    contract_count: int | None = None
    leg_count: int = 0
    opening_net_debit: float | None = None
    opening_net_credit: float | None = None
    max_profit: float | None = None
    max_loss: float | None = None
    breakevens: list[float] = Field(default_factory=list)
    settlement_mode: str | None = None
    gross_pnl: float | None = None
    opening_commissions: float | None = None
    closing_commissions: float | None = None
    total_commissions: float | None = None
    net_pnl: float | None = None
    execution_enabled: bool = False
    persistence_enabled: bool = True
    paper_only: bool = True
    operator_disclaimer: str = (
        "Persisted paper-only options lifecycle record. No broker order, live routing, or expiration settlement automation."
    )
    legs: list[OptionPaperLifecycleLegSummary] = Field(default_factory=list)


class OptionPaperLifecycleSummaryListResponse(BaseModel):
    market_mode: MarketMode = MarketMode.OPTIONS
    paper_only: bool = True
    operator_disclaimer: str = (
        "Paper-only options lifecycle listing. No broker execution, live routing, or replay persistence."
    )
    items: list[OptionPaperLifecycleSummary] = Field(default_factory=list)


class OptionPaperOpenStructureResponse(BaseModel):
    order_id: int
    position_id: int
    market_mode: MarketMode = MarketMode.OPTIONS
    structure_type: str
    underlying_symbol: str
    status: str
    order_status: str
    position_status: str
    opening_net_debit: float | None = None
    opening_net_credit: float | None = None
    commission_per_contract: float | None = None
    opening_commissions: float | None = None
    max_profit: float | None = None
    max_loss: float | None = None
    breakevens: list[float] = Field(default_factory=list)
    execution_enabled: bool = False
    persistence_enabled: bool = True
    paper_only: bool = True
    operator_disclaimer: str = (
        "Paper-only options structure open with paper fee modeling only. No replay runs, live routing, or broker execution."
    )
    legs: list[OptionPaperPositionLegRecord] = Field(default_factory=list)
    order_created_at: datetime
    position_opened_at: datetime


class OptionPaperCloseLegInput(BaseModel):
    position_leg_id: int
    exit_premium: float


class OptionPaperCloseStructureRequest(BaseModel):
    settlement_mode: str = "manual_close"
    legs: list[OptionPaperCloseLegInput] = Field(default_factory=list)
    underlying_settlement_price: float | None = None
    notes: str | None = None


class OptionPaperCloseStructureResponse(BaseModel):
    position_id: int
    trade_id: int
    market_mode: MarketMode = MarketMode.OPTIONS
    structure_type: str
    underlying_symbol: str
    status: str
    position_status: str
    settlement_mode: str
    commission_per_contract: float | None = None
    opening_commissions: float | None = None
    closing_commissions: float | None = None
    gross_pnl: float | None = None
    net_pnl: float | None = None
    total_commissions: float | None = None
    execution_enabled: bool = False
    persistence_enabled: bool = True
    paper_only: bool = True
    operator_disclaimer: str = (
        "Paper-only options structure close with paper contract commission modeling only. No live routing or broker execution."
    )
    legs: list[OptionPaperTradeLegRecord] = Field(default_factory=list)
    closed_at: datetime


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
