"""Common deterministic indicator helpers."""

from __future__ import annotations

from typing import Iterable


def ema(values: Iterable[float], period: int) -> list[float]:
    """Return EMA series with deterministic seed using first value."""
    values_list = list(values)
    if not values_list:
        return []
    if period <= 0:
        raise ValueError("period must be > 0")

    k = 2.0 / (period + 1)
    out = [values_list[0]]
    for value in values_list[1:]:
        out.append((value * k) + (out[-1] * (1.0 - k)))
    return out


def heikin_ashi_candles(
    opens: list[float], highs: list[float], lows: list[float], closes: list[float]
) -> tuple[list[float], list[float], list[float], list[float]]:
    """Project OHLC into Heikin-Ashi OHLC."""
    if not (len(opens) == len(highs) == len(lows) == len(closes)):
        raise ValueError("OHLC arrays must be the same length")
    if not opens:
        return [], [], [], []

    ha_close = [(o + h + l + c) / 4.0 for o, h, l, c in zip(opens, highs, lows, closes, strict=True)]
    ha_open = [((opens[0] + closes[0]) / 2.0)]
    for i in range(1, len(opens)):
        ha_open.append((ha_open[i - 1] + ha_close[i - 1]) / 2.0)

    ha_high = [max(h, ho, hc) for h, ho, hc in zip(highs, ha_open, ha_close, strict=True)]
    ha_low = [min(l, ho, hc) for l, ho, hc in zip(lows, ha_open, ha_close, strict=True)]
    return ha_open, ha_high, ha_low, ha_close
