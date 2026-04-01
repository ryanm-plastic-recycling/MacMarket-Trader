"""HACOLT long-term trend strip."""

from __future__ import annotations

from pydantic import BaseModel

from macmarket_trader.indicators.common import ema


class HacoltPoint(BaseModel):
    direction: str
    strip_value: int
    spread: float


def compute_hacolt_direction(closes: list[float]) -> list[HacoltPoint]:
    if not closes:
        return []
    mid = ema(closes, period=21)
    long = ema(closes, period=55)
    out: list[HacoltPoint] = []
    for m, l in zip(mid, long, strict=True):
        bull = m >= l
        out.append(
            HacoltPoint(
                direction="up" if bull else "down",
                strip_value=100 if bull else 0,
                spread=m - l,
            )
        )
    return out
