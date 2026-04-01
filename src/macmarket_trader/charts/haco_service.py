"""Deterministic HACO chart payload builder."""

from __future__ import annotations

from macmarket_trader.domain.schemas import (
    Bar,
    ChartCandle,
    HacoChartExplanation,
    HacoChartPayload,
    HacoMarker,
    HacoStatePoint,
    HacoltStatePoint,
)
from macmarket_trader.indicators.haco_ha import compute_haco_from_ha
from macmarket_trader.indicators.hacolt import compute_hacolt_direction


class HacoChartService:
    def build_payload(
        self,
        symbol: str,
        timeframe: str,
        bars: list[Bar],
        include_heikin_ashi: bool = True,
        data_source: str = "request_bars",
        fallback_mode: bool = False,
    ) -> HacoChartPayload:
        opens = [bar.open for bar in bars]
        highs = [bar.high for bar in bars]
        lows = [bar.low for bar in bars]
        closes = [bar.close for bar in bars]

        ha_open, ha_high, ha_low, ha_close, haco_states = compute_haco_from_ha(opens, highs, lows, closes)
        hacolt_states = compute_hacolt_direction(closes)

        markers: list[HacoMarker] = []
        latest_flip = "none"
        latest_flip_bars_ago: int | None = None
        for idx, (bar, point) in enumerate(zip(bars, haco_states, strict=True)):
            if point.flip:
                latest_flip = point.flip
                latest_flip_bars_ago = len(bars) - idx - 1
                markers.append(
                    HacoMarker(
                        time=bar.date,
                        marker_type="arrow_up" if point.flip == "buy" else "arrow_down",
                        direction=point.flip,
                        price=bar.low if point.flip == "buy" else bar.high,
                        text=point.flip.upper(),
                    )
                )

        haco_strip = [
            HacoStatePoint(time=bar.date, value=point.state_value, state=point.state)
            for bar, point in zip(bars, haco_states, strict=True)
        ]
        hacolt_strip = [
            HacoltStatePoint(time=bar.date, value=point.strip_value, direction=point.direction)
            for bar, point in zip(bars, hacolt_states, strict=True)
        ]

        current_haco_state = haco_states[-1].state if haco_states else "neutral"
        current_hacolt_direction = hacolt_states[-1].direction if hacolt_states else "flat"

        return HacoChartPayload(
            symbol=symbol,
            timeframe=timeframe,
            candles=[
                ChartCandle(
                    time=bar.date,
                    open=bar.open,
                    high=bar.high,
                    low=bar.low,
                    close=bar.close,
                    volume=bar.volume,
                )
                for bar in bars
            ],
            heikin_ashi_candles=[
                ChartCandle(
                    time=bar.date,
                    open=o,
                    high=h,
                    low=l,
                    close=c,
                    volume=bar.volume,
                )
                for bar, o, h, l, c in zip(bars, ha_open, ha_high, ha_low, ha_close, strict=True)
            ]
            if include_heikin_ashi
            else [],
            markers=markers,
            haco_strip=haco_strip,
            hacolt_strip=hacolt_strip,
            explanation=HacoChartExplanation(
                current_haco_state=current_haco_state,
                latest_flip=latest_flip,
                latest_flip_bars_ago=latest_flip_bars_ago,
                current_hacolt_direction=current_hacolt_direction,
            ),
            data_source=data_source,
            fallback_mode=fallback_mode,
        )
