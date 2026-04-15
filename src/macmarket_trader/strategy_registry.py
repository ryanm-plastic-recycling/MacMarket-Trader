"""Market-mode aware strategy registry for operator workflows."""

from __future__ import annotations

from pydantic import BaseModel, Field

from macmarket_trader.domain.enums import MarketMode


class StrategyRegistryEntry(BaseModel):
    strategy_id: str
    display_name: str
    market_mode: MarketMode
    status: str
    summary: str
    directional_profile: str
    execution_readiness: str
    required_data_inputs: list[str] = Field(default_factory=list)
    operator_notes: list[str] = Field(default_factory=list)
    description: str | None = None
    regime_fit: str | None = None


REGISTRY: list[StrategyRegistryEntry] = [
    StrategyRegistryEntry(
        strategy_id="event_continuation",
        display_name="Event Continuation",
        market_mode=MarketMode.EQUITIES,
        status="live",
        summary="Post-catalyst continuation setup for U.S. large-cap equities and ETFs.",
        directional_profile="bullish",
        execution_readiness="live",
        required_data_inputs=["daily_bars", "relative_volume", "regime_state"],
        operator_notes=["Use deterministic trigger + invalidation before promotion to Recommendations."],
        description="Trades in the direction of a catalyst after initial price discovery — earnings, guidance, or macro events with clear directional bias.",
        regime_fit="trending / catalyst-driven",
    ),
    StrategyRegistryEntry(
        strategy_id="breakout_prior_day_high",
        display_name="Breakout / Prior-Day High",
        market_mode=MarketMode.EQUITIES,
        status="live",
        summary="Breakout continuation above prior-day structure when liquidity and RVOL confirm.",
        directional_profile="bullish",
        execution_readiness="live",
        required_data_inputs=["daily_bars", "prior_day_levels", "relative_volume"],
        operator_notes=["Validate trigger quality around prior-day highs before staging."],
        description="Enters on confirmed range expansion above resistance or below support with volume confirmation.",
        regime_fit="trending / expanding volatility",
    ),
    StrategyRegistryEntry(
        strategy_id="pullback_trend_continuation",
        display_name="Pullback / Trend Continuation",
        market_mode=MarketMode.EQUITIES,
        status="live",
        summary="Trend pullback continuation using deterministic support and momentum recovery.",
        directional_profile="bullish",
        execution_readiness="live",
        required_data_inputs=["daily_bars", "trend_context", "atr"],
        description="Buys dips or sells rips within an established trend using structure levels as entry zones.",
        regime_fit="trending / orderly",
    ),
    StrategyRegistryEntry(
        strategy_id="gap_follow_through",
        display_name="Gap Follow-Through",
        market_mode=MarketMode.EQUITIES,
        status="live",
        summary="Gap continuation with opening acceptance and liquidity confirmation.",
        directional_profile="volatility",
        execution_readiness="live",
        required_data_inputs=["daily_bars", "gap_stats", "relative_volume"],
        description="Trades continuation after an overnight gap holds and establishes a new intraday trend direction.",
        regime_fit="volatile open / trending intraday",
    ),
    StrategyRegistryEntry(
        strategy_id="mean_reversion",
        display_name="Mean Reversion",
        market_mode=MarketMode.EQUITIES,
        status="live",
        summary="Counter-trend fade around deterministic support/resistance and volatility envelopes.",
        directional_profile="neutral",
        execution_readiness="live",
        required_data_inputs=["daily_bars", "volatility_context", "structure_levels"],
        description="Fades extended moves back toward equilibrium when price is stretched beyond normal expected range.",
        regime_fit="range-bound / low momentum",
    ),
    StrategyRegistryEntry(
        strategy_id="haco_context",
        display_name="HACO Context",
        market_mode=MarketMode.EQUITIES,
        status="live",
        summary="HACO/HACOLT context alignment as supporting technical confirmation.",
        directional_profile="neutral",
        execution_readiness="live",
        required_data_inputs=["daily_bars", "haco", "hacolt"],
        description="Uses HACO signal transitions and regime state as the primary entry trigger alongside price structure.",
        regime_fit="any — signal-driven",
    ),
    StrategyRegistryEntry(
        strategy_id="iron_condor",
        display_name="Iron Condor",
        market_mode=MarketMode.OPTIONS,
        status="research",
        summary="Defined-risk neutral short-vol structure: short put spread + short call spread same expiry.",
        directional_profile="neutral",
        execution_readiness="research_paper_only",
        required_data_inputs=["options_chain", "implied_volatility", "greeks", "open_interest", "event_calendar"],
        operator_notes=[
            "Paper research only; no live options routing.",
            "Prefer non-binary windows and require explicit event blocker review.",
        ],
    ),
    StrategyRegistryEntry(
        strategy_id="bull_call_debit_spread",
        display_name="Bull Call Debit Spread",
        market_mode=MarketMode.OPTIONS,
        status="research",
        summary="Defined-risk bullish debit spread for directional continuation with limited downside.",
        directional_profile="bullish",
        execution_readiness="research_paper_only",
        required_data_inputs=["options_chain", "implied_volatility", "greeks", "liquidity"],
    ),
    StrategyRegistryEntry(
        strategy_id="bear_put_debit_spread",
        display_name="Bear Put Debit Spread",
        market_mode=MarketMode.OPTIONS,
        status="research",
        summary="Defined-risk bearish debit spread for downside continuation with bounded loss.",
        directional_profile="bearish",
        execution_readiness="research_paper_only",
        required_data_inputs=["options_chain", "implied_volatility", "greeks", "liquidity"],
    ),
    StrategyRegistryEntry(
        strategy_id="covered_call",
        display_name="Covered Call Preview",
        market_mode=MarketMode.OPTIONS,
        status="research",
        summary="Yield-oriented overlay requiring stock inventory + assignment-aware risk modeling.",
        directional_profile="carry",
        execution_readiness="later_requires_inventory_modeling",
        required_data_inputs=["position_inventory", "options_chain", "assignment_risk"],
        operator_notes=["Requires inventory/assignment modeling — later than defined-risk spreads."],
    ),
    StrategyRegistryEntry(
        strategy_id="crypto_spot_breakout",
        display_name="Crypto Spot Breakout",
        market_mode=MarketMode.CRYPTO,
        status="research",
        summary="Spot breakout continuation with 24/7 session awareness and liquidity checks.",
        directional_profile="bullish",
        execution_readiness="research_paper_only",
        required_data_inputs=["spot_bars", "session_24_7", "volume_profile"],
    ),
    StrategyRegistryEntry(
        strategy_id="crypto_pullback_trend",
        display_name="Crypto Pullback Trend",
        market_mode=MarketMode.CRYPTO,
        status="research",
        summary="Spot trend pullback using regime + volatility context across continuous trading session.",
        directional_profile="bullish",
        execution_readiness="research_paper_only",
        required_data_inputs=["spot_bars", "atr", "trend_context"],
    ),
    StrategyRegistryEntry(
        strategy_id="crypto_basis_carry",
        display_name="Crypto Basis Carry",
        market_mode=MarketMode.CRYPTO,
        status="research",
        summary="Research carry setup using basis dislocation, OI, and funding context.",
        directional_profile="carry",
        execution_readiness="research_paper_only",
        required_data_inputs=["basis", "open_interest", "funding_rate", "venue_context"],
    ),
    StrategyRegistryEntry(
        strategy_id="crypto_funding_extreme_reversion",
        display_name="Funding Extreme Reversion",
        market_mode=MarketMode.CRYPTO,
        status="research",
        summary="Mean reversion research setup around extreme funding + crowded positioning signals.",
        directional_profile="volatility",
        execution_readiness="research_paper_only",
        required_data_inputs=["funding_rate", "open_interest", "liquidation_maps"],
    ),
]


def list_strategies(market_mode: MarketMode | None = None) -> list[StrategyRegistryEntry]:
    if market_mode is None:
        return REGISTRY
    return [entry for entry in REGISTRY if entry.market_mode == market_mode]


def get_strategy_by_display_name(display_name: str, *, market_mode: MarketMode | None = None) -> StrategyRegistryEntry | None:
    for entry in list_strategies(market_mode):
        if entry.display_name == display_name:
            return entry
    return None
