"""Mock deterministic provider for local research/testing."""

from statistics import mean

from macmarket_trader.data.providers.base import MarketDataProvider
from macmarket_trader.domain.schemas import Bar, TechnicalContext


class MockMarketDataProvider(MarketDataProvider):
    """Builds technical context from daily bars with simple ATR approximation."""

    def build_technical_context(self, bars: list[Bar]) -> TechnicalContext:
        if len(bars) < 2:
            msg = "At least two bars are required to build technical context"
            raise ValueError(msg)

        prior = bars[-2]
        window = bars[-20:]
        tr_values = [bar.high - bar.low for bar in bars[-14:]] or [bars[-1].high - bars[-1].low]
        atr14 = mean(tr_values)
        event_day = bars[-1]
        return TechnicalContext(
            prior_day_high=prior.high,
            prior_day_low=prior.low,
            recent_20d_high=max(bar.high for bar in window),
            recent_20d_low=min(bar.low for bar in window),
            atr14=max(atr14, 0.01),
            event_day_range=event_day.high - event_day.low,
            rel_volume=event_day.rel_volume,
        )
