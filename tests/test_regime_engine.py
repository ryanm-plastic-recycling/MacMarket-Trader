from datetime import date, timedelta

from macmarket_trader.domain.enums import RegimeType
from macmarket_trader.domain.schemas import Bar
from macmarket_trader.regime.engine import RegimeEngine


def test_regime_engine_risk_on_classification() -> None:
    base = date(2026, 1, 1)
    bars = [
        Bar(
            date=base + timedelta(days=i),
            open=100 + i,
            high=101 + i,
            low=99 + i,
            close=100 + i,
            volume=1_000_000 + (i * 100_000),
        )
        for i in range(6)
    ]
    regime = RegimeEngine().classify(bars)
    assert regime.regime == RegimeType.RISK_ON_TREND
