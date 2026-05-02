"""Deterministic HACO chart payload builder."""

from __future__ import annotations

from datetime import UTC, datetime

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
    @staticmethod
    def _canonical_bars(bars: list[Bar]) -> list[Bar]:
        return sorted(
            bars,
            key=lambda bar: bar.timestamp or datetime.combine(bar.date, datetime.min.time(), tzinfo=UTC),
        )

    @staticmethod
    def _is_intraday_timeframe(timeframe: str) -> bool:
        return timeframe.upper() != "1D"

    @classmethod
    def _chart_time(cls, bar: Bar, timeframe: str) -> str | int:
        if cls._is_intraday_timeframe(timeframe) and bar.timestamp is not None:
            return int(bar.timestamp.astimezone(UTC).timestamp())
        return bar.date.isoformat()

    @classmethod
    def _dedupe_canonical_bars(cls, bars: list[Bar], timeframe: str) -> list[Bar]:
        if not cls._is_intraday_timeframe(timeframe):
            return bars
        by_time: dict[str | int, Bar] = {}
        for bar in bars:
            by_time[cls._chart_time(bar, timeframe)] = bar
        return list(by_time.values())

    def build_payload(
        self,
        symbol: str,
        timeframe: str,
        bars: list[Bar],
        include_heikin_ashi: bool = True,
        data_source: str = "request_bars",
        fallback_mode: bool = False,
        metadata: dict[str, object] | None = None,
    ) -> HacoChartPayload:
        canonical_bars = self._dedupe_canonical_bars(self._canonical_bars(bars), timeframe)
        metadata = metadata or {}
        chart_times = [self._chart_time(bar, timeframe) for bar in canonical_bars]
        opens = [bar.open for bar in canonical_bars]
        highs = [bar.high for bar in canonical_bars]
        lows = [bar.low for bar in canonical_bars]
        closes = [bar.close for bar in canonical_bars]

        ha_open, ha_high, ha_low, ha_close, haco_states = compute_haco_from_ha(opens, highs, lows, closes)
        hacolt_states = compute_hacolt_direction(closes)

        markers: list[HacoMarker] = []
        latest_flip = "none"
        latest_flip_bars_ago: int | None = None
        for idx, (bar, point) in enumerate(zip(canonical_bars, haco_states, strict=True)):
            if point.flip:
                latest_flip = point.flip
                latest_flip_bars_ago = len(canonical_bars) - idx - 1
                markers.append(
                    HacoMarker(
                        index=idx,
                        time=chart_times[idx],
                        marker_type="arrow_up" if point.flip == "buy" else "arrow_down",
                        direction=point.flip,
                        price=bar.low if point.flip == "buy" else bar.high,
                        text=point.flip.upper(),
                    )
                )

        haco_strip = [
            HacoStatePoint(index=idx, time=chart_times[idx], value=point.state_value, state=point.state)
            for idx, (bar, point) in enumerate(zip(canonical_bars, haco_states, strict=True))
        ]
        hacolt_strip = [
            HacoltStatePoint(index=idx, time=chart_times[idx], value=point.strip_value, direction=point.direction)
            for idx, (bar, point) in enumerate(zip(canonical_bars, hacolt_states, strict=True))
        ]

        current_haco_state = haco_states[-1].state if haco_states else "neutral"
        current_hacolt_direction = hacolt_states[-1].direction if hacolt_states else "flat"
        first_bar = canonical_bars[0] if canonical_bars else None
        last_bar = canonical_bars[-1] if canonical_bars else None

        return HacoChartPayload(
            symbol=symbol,
            timeframe=timeframe,
            candles=[
                ChartCandle(
                    index=idx,
                    time=chart_times[idx],
                    open=bar.open,
                    high=bar.high,
                    low=bar.low,
                    close=bar.close,
                    volume=bar.volume,
                )
                for idx, bar in enumerate(canonical_bars)
            ],
            heikin_ashi_candles=[
                ChartCandle(
                    index=idx,
                    time=chart_times[idx],
                    open=o,
                    high=h,
                    low=l,
                    close=c,
                    volume=bar.volume,
                )
                for idx, (bar, o, h, l, c) in enumerate(zip(canonical_bars, ha_open, ha_high, ha_low, ha_close, strict=True))
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
            session_policy=metadata.get("session_policy") or (first_bar.session_policy if first_bar else None),
            source_session_policy=metadata.get("source_session_policy") or (first_bar.source_session_policy if first_bar else None),
            source_timeframe=metadata.get("source_timeframe") or (first_bar.source_timeframe if first_bar else None),
            output_timeframe=metadata.get("output_timeframe") or timeframe.upper(),
            filtered_extended_hours_count=metadata.get("filtered_extended_hours_count"),  # type: ignore[arg-type]
            rth_bucket_count=metadata.get("rth_bucket_count") if metadata.get("rth_bucket_count") is not None else len(canonical_bars),
            first_bar_timestamp=(
                str(metadata.get("first_bar_timestamp"))
                if metadata.get("first_bar_timestamp") is not None
                else (first_bar.timestamp.isoformat() if first_bar and first_bar.timestamp else None)
            ),
            last_bar_timestamp=(
                str(metadata.get("last_bar_timestamp"))
                if metadata.get("last_bar_timestamp") is not None
                else (last_bar.timestamp.isoformat() if last_bar and last_bar.timestamp else None)
            ),
        )
