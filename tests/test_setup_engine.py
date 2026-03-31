from datetime import datetime, timezone

from macmarket_trader.domain.enums import EventSourceType, RegimeType, SetupType
from macmarket_trader.domain.schemas import NewsEvent, RegimeState, TechnicalContext
from macmarket_trader.setups.engine import SetupEngine


def test_setup_engine_is_deterministic() -> None:
    event = NewsEvent(
        symbol="AAPL",
        source_type=EventSourceType.NEWS,
        source_timestamp=datetime.now(timezone.utc),
        headline="positive",
        summary="positive",
        sentiment_score=0.5,
    )
    regime = RegimeState(
        regime=RegimeType.RISK_ON_TREND,
        trend_score=0.1,
        volatility_score=0.01,
        participation_score=1.2,
    )
    tc = TechnicalContext(
        prior_day_high=102,
        prior_day_low=98,
        recent_20d_high=110,
        recent_20d_low=90,
        atr14=2,
        event_day_range=3,
        rel_volume=1.4,
    )
    engine = SetupEngine()
    setup_1 = engine.generate(event, regime, tc)
    setup_2 = engine.generate(event, regime, tc)
    assert setup_1 == setup_2
    assert setup_1.setup_type == SetupType.EVENT_CONTINUATION
