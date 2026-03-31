"""Deterministic regime classification engine."""

from statistics import mean

from macmarket_trader.domain.enums import RegimeType
from macmarket_trader.domain.schemas import Bar, RegimeState


class RegimeEngine:
    """Classifies risk regime from daily bars."""

    version = "regime-v1"

    def classify(self, bars: list[Bar]) -> RegimeState:
        if len(bars) < 5:
            msg = "Need at least 5 bars for regime classification"
            raise ValueError(msg)

        closes = [bar.close for bar in bars[-5:]]
        ranges = [bar.high - bar.low for bar in bars[-5:]]
        vols = [bar.volume for bar in bars[-5:]]

        trend_score = (closes[-1] - closes[0]) / max(closes[0], 0.01)
        volatility_score = mean(ranges) / max(closes[-1], 0.01)
        participation_score = vols[-1] / max(mean(vols), 1.0)

        if trend_score > 0.02 and participation_score >= 1.0:
            regime = RegimeType.RISK_ON_TREND
        elif trend_score < -0.02:
            regime = RegimeType.RISK_OFF
        else:
            regime = RegimeType.RANGE_BALANCED

        return RegimeState(
            regime=regime,
            trend_score=trend_score,
            volatility_score=volatility_score,
            participation_score=participation_score,
            version=self.version,
        )
