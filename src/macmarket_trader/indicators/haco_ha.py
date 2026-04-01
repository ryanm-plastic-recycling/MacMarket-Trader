"""HACO with Heikin-Ashi transformed candles."""

from __future__ import annotations

from macmarket_trader.indicators.common import heikin_ashi_candles
from macmarket_trader.indicators.haco import HacoPoint, compute_haco_states


def compute_haco_from_ha(
    opens: list[float], highs: list[float], lows: list[float], closes: list[float]
) -> tuple[list[float], list[float], list[float], list[float], list[HacoPoint]]:
    ha_open, ha_high, ha_low, ha_close = heikin_ashi_candles(opens, highs, lows, closes)
    states = compute_haco_states(ha_close)
    return ha_open, ha_high, ha_low, ha_close, states
