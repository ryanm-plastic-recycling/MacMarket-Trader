"""Deterministic setup generation engine."""

from macmarket_trader.domain.enums import Direction, RegimeType, SetupType
from macmarket_trader.domain.schemas import BaseEvent, RegimeState, TechnicalContext, TradeSetup


class SetupEngine:
    """Constructs non-generic entry/invalidation/target levels from daily structure."""

    version = "setup-v1"

    def generate(self, event: BaseEvent, regime: RegimeState, tc: TechnicalContext) -> TradeSetup:
        direction = Direction.LONG if event.sentiment_score >= 0 else Direction.SHORT

        if regime.regime == RegimeType.RISK_ON_TREND and direction == Direction.LONG:
            return self._event_continuation(tc)
        if regime.regime == RegimeType.RANGE_BALANCED:
            return self._pullback_continuation(direction, tc)
        return self._failed_event_fade(tc)

    def _event_continuation(self, tc: TechnicalContext) -> TradeSetup:
        entry_low = tc.prior_day_high
        entry_high = tc.prior_day_high + 0.2 * tc.atr14
        invalidation = tc.prior_day_low
        return TradeSetup(
            setup_type=SetupType.EVENT_CONTINUATION,
            direction=Direction.LONG,
            entry_zone_low=entry_low,
            entry_zone_high=entry_high,
            trigger_text="Break and hold above prior-day high on strong participation",
            invalidation_price=invalidation,
            invalidation_reason="Loss of prior-day low breaks continuation structure",
            target_1=min(tc.recent_20d_high, entry_high + tc.event_day_range),
            target_2=entry_high + 2.0 * tc.atr14,
            trailing_rule_text="Trail below 2-day swing low after target_1 is touched",
            time_stop_days=3,
            setup_engine_version=self.version,
        )

    def _pullback_continuation(self, direction: Direction, tc: TechnicalContext) -> TradeSetup:
        if direction == Direction.LONG:
            entry_low = tc.prior_day_low + 0.25 * tc.atr14
            entry_high = tc.prior_day_low + 0.6 * tc.atr14
            invalidation = tc.recent_20d_low
            target_1 = tc.prior_day_high
            target_2 = min(tc.recent_20d_high, entry_high + 1.8 * tc.atr14)
        else:
            entry_high = tc.prior_day_high - 0.25 * tc.atr14
            entry_low = tc.prior_day_high - 0.6 * tc.atr14
            invalidation = tc.recent_20d_high
            target_1 = tc.prior_day_low
            target_2 = max(tc.recent_20d_low, entry_low - 1.8 * tc.atr14)

        return TradeSetup(
            setup_type=SetupType.PULLBACK_CONTINUATION,
            direction=direction,
            entry_zone_low=entry_low,
            entry_zone_high=entry_high,
            trigger_text="Reject pullback zone and reclaim short-term trend alignment",
            invalidation_price=invalidation,
            invalidation_reason="Pullback exceeded recent structure boundary",
            target_1=target_1,
            target_2=target_2,
            trailing_rule_text="Move stop to breakeven after target_1; trail by 1 ATR thereafter",
            # TODO: Replace ATR-only trailing approximation with anchored VWAP when intraday bars are available.
            time_stop_days=4,
            setup_engine_version=self.version,
        )

    def _failed_event_fade(self, tc: TechnicalContext) -> TradeSetup:
        entry_high = tc.prior_day_high - 0.1 * tc.atr14
        entry_low = entry_high - 0.3 * tc.atr14
        invalidation = tc.recent_20d_high
        return TradeSetup(
            setup_type=SetupType.FAILED_EVENT_FADE,
            direction=Direction.SHORT,
            entry_zone_low=entry_low,
            entry_zone_high=entry_high,
            trigger_text="Event spike fails and closes back inside prior range",
            invalidation_price=invalidation,
            invalidation_reason="Reclaim of 20-day high invalidates fade thesis",
            target_1=tc.prior_day_low,
            target_2=max(tc.recent_20d_low, entry_low - tc.atr14),
            trailing_rule_text="Trail above 2-day swing high after first target",
            time_stop_days=2,
            setup_engine_version=self.version,
        )
