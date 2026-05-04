"""Deterministic index-risk signal extraction.

The signals in this module are read-only market context. They may influence the
Market Risk Calendar warning/restriction state, but they do not create trades,
routes, exits, rolls, or broker actions.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from macmarket_trader.config import Settings, settings
from macmarket_trader.domain.schemas import IndexRiskSignals
from macmarket_trader.domain.time import utc_now


REQUIRED_INDEX_SYMBOLS = ("SPX", "NDX", "RUT", "VIX")


def extract_index_risk_signals(
    index_context: object | None,
    *,
    cfg: Settings = settings,
    now: datetime | None = None,
    symbol: str | None = None,
) -> IndexRiskSignals | None:
    """Return deterministic index-risk signals from an IndexContextSummary-like object."""

    if not cfg.index_risk_enabled:
        return IndexRiskSignals(
            enabled=False,
            decision_effect="normal",
            risk_level_effect="normal",
            reasons=["Index risk signals disabled by configuration."],
        )
    points = _points_by_symbol(index_context)
    if not points:
        return IndexRiskSignals(
            index_data_stale_or_missing=True,
            decision_effect="normal",
            risk_level_effect="normal",
            reasons=["Index context unavailable; no automatic sit-out is applied."],
            data_quality_flags=["index_context_missing"],
            provenance={"symbol": (symbol or "").upper() or None},
        )

    current = (now or utc_now()).astimezone(UTC)
    spx = _point(points, "SPX")
    ndx = _point(points, "NDX")
    rut = _point(points, "RUT")
    vix = _point(points, "VIX")

    spx_change = _float_value(spx, "day_change_pct")
    ndx_change = _float_value(ndx, "day_change_pct")
    rut_change = _float_value(rut, "day_change_pct")
    vix_change = _float_value(vix, "day_change_pct")
    vix_level = _float_value(vix, "latest_value")
    ndx_rel = round(ndx_change - spx_change, 4) if ndx_change is not None and spx_change is not None else None
    rut_rel = round(rut_change - spx_change, 4) if rut_change is not None and spx_change is not None else None

    data_quality_flags = _data_quality_flags(points, current, int(cfg.index_data_stale_minutes))
    reasons: list[str] = []
    decision_effect = "normal"
    risk_level_effect = "normal"

    def add_reason(state: str, level: str, reason: str) -> None:
        nonlocal decision_effect, risk_level_effect
        reasons.append(reason)
        if _effect_rank(state) > _effect_rank(decision_effect):
            decision_effect = state
            risk_level_effect = level

    if vix_level is not None and vix_level >= float(cfg.vix_restricted_level):
        add_reason("restricted", "high", f"VIX above restricted threshold ({vix_level:.2f} >= {cfg.vix_restricted_level:.2f}).")
    elif vix_level is not None and vix_level >= float(cfg.vix_caution_level):
        add_reason("caution", "elevated", f"VIX above caution threshold ({vix_level:.2f} >= {cfg.vix_caution_level:.2f}).")

    if vix_change is not None and vix_change >= float(cfg.vix_spike_caution_pct):
        add_reason("caution", "elevated", f"VIX spike above caution threshold ({vix_change:.2f}% >= {cfg.vix_spike_caution_pct:.2f}%).")

    if spx_change is not None and spx_change <= -abs(float(cfg.spx_gap_restricted_pct)):
        add_reason("restricted", "high", f"SPX downside move exceeds restricted threshold ({spx_change:.2f}%).")
    elif spx_change is not None and spx_change <= -abs(float(cfg.spx_gap_caution_pct)):
        add_reason("caution", "elevated", f"SPX downside move exceeds caution threshold ({spx_change:.2f}%).")

    if spx_change is not None and vix_change is not None and spx_change < 0 and vix_change > 0:
        add_reason("caution", "elevated", "SPX down while VIX is rising.")

    if rut_rel is not None and rut_rel <= float(cfg.rut_underperform_caution_pct):
        add_reason("caution", "elevated", "RUT underperforming SPX; risk appetite weak.")

    if ndx_rel is not None and ndx_rel <= float(cfg.ndx_underperform_caution_pct):
        add_reason("caution", "elevated", "NDX underperforming SPX; growth/tech risk elevated.")

    if data_quality_flags:
        reasons.append("Index data stale or missing; warning only, no automatic no-trade.")

    equity_changes = [value for value in (spx_change, ndx_change, rut_change) if value is not None]
    broad_direction = _broad_index_direction(equity_changes)
    dispersion = _dispersion_state(equity_changes)
    risk_appetite = _risk_appetite_state(
        equity_changes=equity_changes,
        spx_change=spx_change,
        vix_level=vix_level,
        vix_change=vix_change,
        rut_relative_strength=rut_rel,
        vix_caution=float(cfg.vix_caution_level),
    )

    return IndexRiskSignals(
        vix_level=vix_level,
        vix_change_pct=vix_change,
        spx_change_pct=spx_change,
        ndx_change_pct=ndx_change,
        rut_change_pct=rut_change,
        ndx_vs_spx_relative_strength=ndx_rel,
        rut_vs_spx_relative_strength=rut_rel,
        broad_index_direction=broad_direction,
        market_dispersion_state=dispersion,
        risk_appetite_state=risk_appetite,
        index_data_stale_or_missing=bool(data_quality_flags),
        decision_effect=decision_effect,
        risk_level_effect=risk_level_effect,
        reasons=reasons,
        data_quality_flags=data_quality_flags,
        provenance={
            "source": "IndexContextSummary",
            "symbol": (symbol or "").upper() or None,
            "thresholds": {
                "vix_caution_level": cfg.vix_caution_level,
                "vix_restricted_level": cfg.vix_restricted_level,
                "vix_spike_caution_pct": cfg.vix_spike_caution_pct,
                "spx_gap_caution_pct": cfg.spx_gap_caution_pct,
                "spx_gap_restricted_pct": cfg.spx_gap_restricted_pct,
                "rut_underperform_caution_pct": cfg.rut_underperform_caution_pct,
                "ndx_underperform_caution_pct": cfg.ndx_underperform_caution_pct,
                "index_data_stale_minutes": cfg.index_data_stale_minutes,
            },
        },
    )


def _points_by_symbol(index_context: object | None) -> dict[str, object]:
    indices: object
    if index_context is None:
        return {}
    if isinstance(index_context, dict):
        indices = index_context.get("indices") or []
    else:
        indices = getattr(index_context, "indices", []) or []
    output: dict[str, object] = {}
    for point in indices if isinstance(indices, list) else []:
        symbol = str(_field(point, "symbol") or "").strip().upper()
        if symbol:
            output[symbol] = point
    return output


def _point(points: dict[str, object], symbol: str) -> object | None:
    return points.get(symbol.upper())


def _field(point: object | None, field_name: str) -> object | None:
    if point is None:
        return None
    if isinstance(point, dict):
        return point.get(field_name)
    return getattr(point, field_name, None)


def _float_value(point: object | None, field_name: str) -> float | None:
    value = _field(point, field_name)
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return round(parsed, 4)


def _data_quality_flags(points: dict[str, object], now: datetime, stale_minutes: int) -> list[str]:
    flags: list[str] = []
    for symbol in REQUIRED_INDEX_SYMBOLS:
        point = points.get(symbol)
        if point is None:
            flags.append(f"{symbol}:missing")
            continue
        if _float_value(point, "latest_value") is None:
            flags.append(f"{symbol}:latest_value_missing")
        if _float_value(point, "day_change_pct") is None:
            flags.append(f"{symbol}:day_change_pct_missing")
        if bool(_field(point, "stale")):
            flags.append(f"{symbol}:stale")
        as_of = _parse_as_of(_field(point, "as_of"))
        if as_of is None:
            flags.append(f"{symbol}:as_of_missing")
        elif stale_minutes > 0 and (now - as_of).total_seconds() > stale_minutes * 60:
            flags.append(f"{symbol}:as_of_stale")
        missing = _field(point, "missing_data")
        if isinstance(missing, list):
            flags.extend(f"{symbol}:{item}" for item in missing if str(item).strip())
    return sorted(set(flags))


def _parse_as_of(value: object | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _broad_index_direction(values: list[float]) -> str:
    if not values:
        return "unknown"
    average = sum(values) / len(values)
    if average >= 0.25:
        return "up"
    if average <= -0.25:
        return "down"
    return "mixed"


def _dispersion_state(values: list[float]) -> str:
    if len(values) < 2:
        return "unknown"
    span = max(values) - min(values)
    if span >= 1.5:
        return "high_dispersion"
    if span >= 0.75:
        return "moderate_dispersion"
    return "low_dispersion"


def _risk_appetite_state(
    *,
    equity_changes: list[float],
    spx_change: float | None,
    vix_level: float | None,
    vix_change: float | None,
    rut_relative_strength: float | None,
    vix_caution: float,
) -> str:
    if not equity_changes:
        return "unknown"
    average = sum(equity_changes) / len(equity_changes)
    if (
        (spx_change is not None and spx_change < 0 and vix_change is not None and vix_change > 0)
        or (vix_level is not None and vix_level >= vix_caution)
        or (rut_relative_strength is not None and rut_relative_strength <= -1.0)
    ):
        return "risk_off"
    if average >= 0.25 and (vix_change is None or vix_change <= 0):
        return "risk_on"
    return "mixed"


def _effect_rank(value: str) -> int:
    return {"normal": 0, "caution": 1, "restricted": 2}.get(value, 0)
