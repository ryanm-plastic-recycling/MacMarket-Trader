"""HACO short-term deterministic state model."""

from __future__ import annotations

from pydantic import BaseModel

from macmarket_trader.indicators.common import ema


class HacoPoint(BaseModel):
    state: str
    state_value: int
    momentum: float
    flip: str | None = None


def compute_haco_states(closes: list[float]) -> list[HacoPoint]:
    if not closes:
        return []

    fast = ema(closes, period=3)
    slow = ema(closes, period=8)
    momentum = [f - s for f, s in zip(fast, slow, strict=True)]

    out: list[HacoPoint] = []
    previous_state: str | None = None
    for value in momentum:
        state = "green" if value >= 0 else "red"
        state_value = 100 if state == "green" else 0
        flip: str | None = None
        if previous_state and previous_state != state:
            flip = "buy" if state == "green" else "sell"
        out.append(HacoPoint(state=state, state_value=state_value, momentum=value, flip=flip))
        previous_state = state
    return out
