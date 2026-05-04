"""Reusable analysis packet and provider-context summaries.

The packet models are intentionally presentation-oriented: they collect
already-deterministic recommendation/research context, provider provenance,
macro/news read-only context, and paper-only safety boundaries for UI, email,
and future exports. They do not decide trades or alter strategy math.
"""

from __future__ import annotations

import html
import json
import re
from datetime import UTC, date, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from pydantic import BaseModel, Field

from macmarket_trader.config import settings
from macmarket_trader.data.providers.registry import build_news_provider
from macmarket_trader.domain.time import utc_now


FRED_MACRO_SERIES: tuple[tuple[str, str], ...] = (
    ("DGS10", "10Y Treasury yield"),
    ("DGS2", "2Y Treasury yield"),
    ("T10Y2Y", "10Y minus 2Y spread"),
    ("DFF", "Effective Fed funds rate"),
    ("CPIAUCSL", "Consumer price index"),
    ("UNRATE", "Unemployment rate"),
    ("VIXCLS", "VIX close"),
)

_SECRETISH_RE = re.compile(r"(?i)(sk-[A-Za-z0-9_-]{6,}|pk_[A-Za-z0-9_-]{6,}|rk_[A-Za-z0-9_-]{6,}|key-[A-Za-z0-9_-]{6,})")
_SECRETISH_KEYS = ("api_key", "apikey", "secret", "token", "authorization", "password", "private_key")


class MacroSeriesPoint(BaseModel):
    series_id: str
    label: str
    latest_value: float | None = None
    latest_date: str | None = None
    recent_change: float | None = None
    stale: bool = False
    missing_data: list[str] = Field(default_factory=list)


class MacroContextSummary(BaseModel):
    provider: str = "fred"
    mode: str = "mock"
    generated_at: datetime = Field(default_factory=utc_now)
    series: list[MacroSeriesPoint] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class NewsArticleSummary(BaseModel):
    title: str
    publisher: str | None = None
    published_utc: str | None = None
    article_url: str | None = None
    tickers: list[str] = Field(default_factory=list)
    description: str | None = None
    sentiment: str | None = None
    insights: list[str] = Field(default_factory=list)


class NewsContextSummary(BaseModel):
    provider: str = "news"
    symbol: str
    generated_at: datetime = Field(default_factory=utc_now)
    headlines: list[NewsArticleSummary] = Field(default_factory=list)
    count: int = 0
    newest_article_age_minutes: int | None = None
    sentiment_summary: str | None = None
    missing_data: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ProviderContextSummary(BaseModel):
    market_data_source: str | None = None
    market_data_fallback_mode: bool = False
    session_policy: str | None = None
    macro_provider: str = "mock"
    news_provider: str = "mock"
    options_data_provider: str | None = None
    provider_health_summary: str | None = None
    missing_data: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


class RiskCalendarSummary(BaseModel):
    decision_state: str | None = None
    risk_level: str | None = None
    recommended_action: str | None = None
    warning_summary: str | None = None
    block_reason: str | None = None
    missing_data: list[str] = Field(default_factory=list)


class LlmExplanationSummary(BaseModel):
    summary: str | None = None
    provider: str | None = None
    model: str | None = None
    fallback_used: bool = False
    explanation_only: bool = True
    missing_data: list[str] = Field(default_factory=list)


class PaperLifecycleSummary(BaseModel):
    already_open: bool = False
    open_position_id: int | None = None
    active_review_action_classification: str | None = None
    active_review_summary: str | None = None
    paper_only: bool = True
    review_only: bool = True


class OptionsLegAnalysisPacket(BaseModel):
    role: str | None = None
    side: str | None = None
    option_type: str | None = None
    target_strike: float | None = None
    selected_listed_strike: float | None = None
    strike_snap_distance: float | None = None
    option_symbol: str | None = None
    bid: float | None = None
    ask: float | None = None
    current_mark_premium: float | None = None
    mark_method: str | None = None
    implied_volatility: float | None = None
    open_interest: int | None = None
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
    stale: bool = False
    missing_data: list[str] = Field(default_factory=list)


class OptionsAnalysisPacket(BaseModel):
    underlying: str
    strategy_type: str | None = None
    timeframe: str | None = None
    expiration: str | None = None
    days_to_expiration: int | None = None
    structure_status: str | None = None
    listed_contract_validation_status: str | None = None
    legs: list[OptionsLegAnalysisPacket] = Field(default_factory=list)
    net_debit: float | None = None
    net_credit: float | None = None
    max_profit: float | None = None
    max_loss: float | None = None
    breakevens: list[float] = Field(default_factory=list)
    expected_range: dict[str, Any] | None = None
    payoff_preview_summary: str | None = None
    expiration_settlement_summary: str | None = None
    assignment_exercise_risk_summary: str | None = None
    provider_option_mark_readiness: str | None = None
    warnings: list[str] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)


class EquityAnalysisPacket(BaseModel):
    symbol: str
    side: str | None = None
    timeframe: str | None = None
    setup_name: str | None = None
    thesis: str | None = None
    approval_status: str | None = None
    rank: int | None = None
    score: float | None = None
    confidence: float | None = None
    expected_rr: float | None = None
    entry_zone: dict[str, Any] | str | None = None
    stop: dict[str, Any] | str | None = None
    targets: dict[str, Any] | list[Any] | str | None = None
    expected_range: dict[str, Any] | None = None
    risk_budget_at_stop: float | None = None
    max_paper_order_value: float | None = None
    final_shares: int | None = None
    final_notional: float | None = None
    missing_data: list[str] = Field(default_factory=list)


class AnalysisPacket(BaseModel):
    packet_id: str = Field(default_factory=lambda: f"pkt_{uuid4().hex[:12]}")
    symbol: str
    market_mode: str
    timeframe: str | None = None
    generated_at: datetime = Field(default_factory=utc_now)
    provider: str | None = None
    source: str | None = None
    session_policy: str | None = None
    paper_only: bool = True
    review_only: bool = True
    no_live_trading: bool = True
    no_broker_routing: bool = True
    no_automatic_exits: bool = True
    missing_data: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
    provider_context: ProviderContextSummary | None = None
    macro_context: MacroContextSummary | None = None
    news_context: NewsContextSummary | None = None
    risk_calendar: RiskCalendarSummary | None = None
    llm_explanation: LlmExplanationSummary | None = None
    paper_lifecycle: PaperLifecycleSummary | None = None
    equity: EquityAnalysisPacket | None = None
    options: OptionsAnalysisPacket | None = None


def _safe_float(value: object) -> float | None:
    try:
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if parsed == parsed and parsed not in {float("inf"), float("-inf")} else None


def _safe_int(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _redacted_error(exc: BaseException) -> str:
    text = str(exc)
    for secret in (
        settings.fred_api_key,
        settings.polygon_api_key,
        settings.openai_api_key,
        settings.resend_api_key,
    ):
        if secret:
            text = text.replace(secret, "[redacted]")
    return text[:240]


def redact_analysis_packet_text(value: object) -> str:
    """Redact secret-looking values without masking valid OCC option symbols."""
    text = _SECRETISH_RE.sub("[redacted]", str(value))
    for secret in (
        settings.fred_api_key,
        settings.polygon_api_key,
        settings.openai_api_key,
        settings.resend_api_key,
        settings.clerk_secret_key,
        getattr(settings, "alpaca_api_key_id", ""),
        getattr(settings, "alpaca_api_secret_key", ""),
    ):
        if secret:
            text = text.replace(secret, "[redacted]")
    return text


def _redact_packet_value(value: Any, *, key_name: str | None = None) -> Any:
    if isinstance(value, BaseModel):
        return _redact_packet_value(value.model_dump(mode="json"), key_name=key_name)
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            if any(marker in key.lower() for marker in _SECRETISH_KEYS):
                cleaned[key] = "[redacted]" if raw_value not in (None, "") else raw_value
            else:
                cleaned[key] = _redact_packet_value(raw_value, key_name=key)
        return cleaned
    if isinstance(value, list):
        return [_redact_packet_value(item, key_name=key_name) for item in value]
    if isinstance(value, tuple):
        return [_redact_packet_value(item, key_name=key_name) for item in value]
    if isinstance(value, str):
        if key_name and any(marker in key_name.lower() for marker in _SECRETISH_KEYS):
            return "[redacted]" if value else value
        return redact_analysis_packet_text(value)
    return value


def analysis_packet_to_safe_dict(packet: AnalysisPacket | dict[str, Any]) -> dict[str, Any]:
    raw = packet.model_dump(mode="json") if isinstance(packet, AnalysisPacket) else dict(packet)
    cleaned = _redact_packet_value(raw)
    return cleaned if isinstance(cleaned, dict) else {}


def _packet_dict(packet: AnalysisPacket | dict[str, Any]) -> dict[str, Any]:
    return analysis_packet_to_safe_dict(packet)


def _format_packet_value(value: object, fallback: str = "Unavailable") -> str:
    if value is None or value == "":
        return fallback
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.4g}"
    return redact_analysis_packet_text(value)


def _packet_macro_lines(packet: dict[str, Any], *, limit: int = 6) -> list[str]:
    macro = packet.get("macro_context") if isinstance(packet.get("macro_context"), dict) else {}
    series = macro.get("series") if isinstance(macro.get("series"), list) else []
    lines: list[str] = []
    for item in series[:limit]:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or item.get("series_id") or "").strip()
        if not label:
            continue
        latest_date = str(item.get("latest_date") or "").strip()
        suffix = f" ({latest_date})" if latest_date else ""
        lines.append(f"{label}: {_format_packet_value(item.get('latest_value'))}{suffix}")
    missing = macro.get("missing_data") if isinstance(macro.get("missing_data"), list) else []
    if not lines and missing:
        lines.append("Macro context unavailable: " + ", ".join(_format_packet_value(item) for item in missing[:4]))
    return lines


def _packet_news_lines(packet: dict[str, Any], *, limit: int = 5) -> list[str]:
    news = packet.get("news_context") if isinstance(packet.get("news_context"), dict) else {}
    headlines = news.get("headlines") if isinstance(news.get("headlines"), list) else []
    lines: list[str] = []
    for item in headlines[:limit]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        publisher = str(item.get("publisher") or "").strip()
        published = str(item.get("published_utc") or "").strip()
        sentiment = str(item.get("sentiment") or "").strip()
        suffix = " | ".join(part for part in (publisher, published[:10], sentiment) if part)
        lines.append(f"{redact_analysis_packet_text(title)}{f' ({redact_analysis_packet_text(suffix)})' if suffix else ''}")
    missing = news.get("missing_data") if isinstance(news.get("missing_data"), list) else []
    if not lines and missing:
        lines.append("News context unavailable: " + ", ".join(_format_packet_value(item) for item in missing[:4]))
    return lines


def _packet_option_leg_line(leg: dict[str, Any]) -> str:
    label = _format_packet_value(leg.get("role") or leg.get("label") or "leg")
    side = _format_packet_value(leg.get("side") or leg.get("action"), "")
    option_type = _format_packet_value(leg.get("option_type") or leg.get("right"), "").upper()
    target = _format_packet_value(leg.get("target_strike"))
    listed = _format_packet_value(leg.get("selected_listed_strike") or leg.get("strike"))
    symbol = _format_packet_value(leg.get("option_symbol"))
    mark = _format_packet_value(leg.get("current_mark_premium") or leg.get("mark_price"))
    method = _format_packet_value(leg.get("mark_method"))
    iv = _format_packet_value(leg.get("implied_volatility"))
    oi = _format_packet_value(leg.get("open_interest"))
    greeks = " / ".join(
        f"{name} {_format_packet_value(leg.get(name))}"
        for name in ("delta", "gamma", "theta", "vega")
    )
    missing = leg.get("missing_data") if isinstance(leg.get("missing_data"), list) else []
    missing_suffix = f" | missing {', '.join(_format_packet_value(item) for item in missing[:3])}" if missing else ""
    return (
        f"{label}: {side} {option_type} target {target} -> listed {listed} | "
        f"{symbol} | mark {mark} ({method}) | IV {iv} | OI {oi} | {greeks}{missing_suffix}"
    )


def _markdown_list(lines: list[str]) -> str:
    if not lines:
        return "- Unavailable"
    return "\n".join(f"- {line}" for line in lines)


def render_analysis_packet_markdown(packet: AnalysisPacket | dict[str, Any]) -> str:
    safe = _packet_dict(packet)
    symbol = _format_packet_value(safe.get("symbol"), "Unknown symbol")
    mode = _format_packet_value(safe.get("market_mode"))
    timeframe = _format_packet_value(safe.get("timeframe"))
    provider = _format_packet_value(safe.get("provider") or safe.get("source"))
    generated_at = _format_packet_value(safe.get("generated_at"))
    lines = [
        f"# Analysis Packet - {symbol}",
        "",
        "## Top Summary",
        f"- Symbol: {symbol}",
        f"- Market mode: {mode}",
        f"- Timeframe: {timeframe}",
        f"- Provider/source: {provider}",
        f"- Generated at: {generated_at}",
        "- Paper only. No live trading. No broker routing. No automatic exits.",
        "- LLM context can explain only; deterministic engines own approval, entry, stop, target, sizing, risk gates, and paper order creation.",
        "",
    ]

    equity = safe.get("equity") if isinstance(safe.get("equity"), dict) else None
    if equity:
        lines.extend(
            [
                "## Equity Details",
                f"- Setup: {_format_packet_value(equity.get('setup_name'))}",
                f"- Side: {_format_packet_value(equity.get('side'))}",
                f"- Thesis: {_format_packet_value(equity.get('thesis'))}",
                f"- Approval/status: {_format_packet_value(equity.get('approval_status'))}",
                f"- Rank/score/confidence/RR: {_format_packet_value(equity.get('rank'))} / {_format_packet_value(equity.get('score'))} / {_format_packet_value(equity.get('confidence'))} / {_format_packet_value(equity.get('expected_rr'))}",
                f"- Entry zone: {_format_packet_value(equity.get('entry_zone'))}",
                f"- Stop/invalidation: {_format_packet_value(equity.get('stop'))}",
                f"- Targets: {_format_packet_value(equity.get('targets'))}",
                f"- Risk budget at stop: {_format_packet_value(equity.get('risk_budget_at_stop'))}",
                f"- Max paper order value: {_format_packet_value(equity.get('max_paper_order_value'))}",
                "",
            ]
        )

    options = safe.get("options") if isinstance(safe.get("options"), dict) else None
    if options:
        legs = [leg for leg in (options.get("legs") or []) if isinstance(leg, dict)]
        lines.extend(
            [
                "## Options Details",
                f"- Strategy: {_format_packet_value(options.get('strategy_type'))}",
                f"- Expiration / DTE: {_format_packet_value(options.get('expiration'))} / {_format_packet_value(options.get('days_to_expiration'))}",
                f"- Structure status: {_format_packet_value(options.get('structure_status'))}",
                f"- Listed-contract validation: {_format_packet_value(options.get('listed_contract_validation_status'))}",
                f"- Net debit/credit: {_format_packet_value(options.get('net_debit'))} / {_format_packet_value(options.get('net_credit'))}",
                f"- Max profit / max loss: {_format_packet_value(options.get('max_profit'))} / {_format_packet_value(options.get('max_loss'))}",
                f"- Breakevens: {_format_packet_value(options.get('breakevens'))}",
                f"- Expiration/settlement: {_format_packet_value(options.get('expiration_settlement_summary'))}",
                f"- Assignment/exercise risk: {_format_packet_value(options.get('assignment_exercise_risk_summary'))}",
                "",
                "### Option Legs",
                _markdown_list([_packet_option_leg_line(leg) for leg in legs]),
                "",
            ]
        )

    risk = safe.get("risk_calendar") if isinstance(safe.get("risk_calendar"), dict) else None
    if risk:
        lines.extend(
            [
                "## Risk Calendar",
                f"- State: {_format_packet_value(risk.get('decision_state'))}",
                f"- Risk level: {_format_packet_value(risk.get('risk_level'))}",
                f"- Recommended action: {_format_packet_value(risk.get('recommended_action'))}",
                f"- Warning/block: {_format_packet_value(risk.get('warning_summary') or risk.get('block_reason'))}",
                "",
            ]
        )

    provider_context = safe.get("provider_context") if isinstance(safe.get("provider_context"), dict) else None
    if provider_context:
        lines.extend(
            [
                "## Provider Context",
                f"- Market data source: {_format_packet_value(provider_context.get('market_data_source'))}",
                f"- Fallback mode: {_format_packet_value(provider_context.get('market_data_fallback_mode'))}",
                f"- Session policy: {_format_packet_value(provider_context.get('session_policy'))}",
                f"- Macro provider: {_format_packet_value(provider_context.get('macro_provider'))}",
                f"- News provider: {_format_packet_value(provider_context.get('news_provider'))}",
                f"- Options data provider: {_format_packet_value(provider_context.get('options_data_provider'))}",
                "",
            ]
        )

    lines.extend(
        [
            "## Macro Context",
            _markdown_list(_packet_macro_lines(safe)),
            "",
            "## News Context",
            _markdown_list(_packet_news_lines(safe)),
            "",
        ]
    )

    llm = safe.get("llm_explanation") if isinstance(safe.get("llm_explanation"), dict) else None
    if llm:
        lines.extend(
            [
                "## LLM Explanation",
                f"- Summary: {_format_packet_value(llm.get('summary'))}",
                f"- Provider/model: {_format_packet_value(llm.get('provider'))} / {_format_packet_value(llm.get('model'))}",
                f"- Fallback used: {_format_packet_value(llm.get('fallback_used'))}",
                "- Boundary: explanation only; deterministic engine owns trade fields and paper order creation.",
                "",
            ]
        )

    missing = [_format_packet_value(item) for item in safe.get("missing_data") or []]
    warnings = [_format_packet_value(item) for item in safe.get("warnings") or []]
    lines.extend(
        [
            "## Missing Data",
            _markdown_list(missing),
            "",
            "## Warnings",
            _markdown_list(warnings),
            "",
            "## Provenance",
            f"- Schema: {_format_packet_value((safe.get('provenance') or {}).get('schema') if isinstance(safe.get('provenance'), dict) else None)}",
            f"- No provider keys included: {_format_packet_value((safe.get('provenance') or {}).get('no_provider_keys_included') if isinstance(safe.get('provenance'), dict) else None)}",
            "",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def render_analysis_packet_html(packet: AnalysisPacket | dict[str, Any]) -> str:
    markdown = render_analysis_packet_markdown(packet)
    html_lines: list[str] = []
    in_list = False
    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if line.startswith("# "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("## "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("### "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h3>{html.escape(line[4:])}</h3>")
        elif line.startswith("- "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{html.escape(line[2:])}</li>")
        elif line:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<p>{html.escape(line)}</p>")
    if in_list:
        html_lines.append("</ul>")
    return (
        '<div style="font-family:Arial,sans-serif;font-size:13px;line-height:1.5;color:#d8e2ee;'
        'background:#0f1722;padding:16px;border:1px solid #26384d;border-radius:8px;">'
        + "".join(html_lines)
        + "</div>"
    )


def _fred_observations(series_id: str, *, limit: int = 2) -> list[dict[str, Any]]:
    query = {
        "series_id": series_id,
        "api_key": settings.fred_api_key.strip(),
        "file_type": "json",
        "sort_order": "desc",
        "limit": str(limit),
    }
    url = f"{settings.fred_base_url.rstrip('/')}/series/observations?{urlencode(query)}"
    request = Request(url=url, headers={"Accept": "application/json"}, method="GET")
    with urlopen(request, timeout=float(settings.fred_timeout_seconds)) as response:  # noqa: S310
        payload = json.loads(response.read().decode("utf-8"))
    observations = payload.get("observations") if isinstance(payload, dict) else None
    return list(observations or [])


def build_macro_context_summary(*, now: datetime | None = None) -> MacroContextSummary:
    current = now or utc_now()
    mode = settings.macro_calendar_provider.strip().lower() or "mock"
    summary = MacroContextSummary(mode=mode, generated_at=current)
    if mode != "fred":
        summary.missing_data.append("fred_not_selected")
        summary.warnings.append("Macro context uses provider readiness only because MACRO_CALENDAR_PROVIDER is not fred.")
        return summary
    if not settings.fred_api_key.strip():
        summary.missing_data.append("fred_api_key")
        summary.warnings.append("FRED macro context unavailable: API key is missing.")
        return summary

    for series_id, label in FRED_MACRO_SERIES:
        point = MacroSeriesPoint(series_id=series_id, label=label)
        try:
            observations = _fred_observations(series_id)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError) as exc:
            point.missing_data.append(f"{series_id}:provider_error")
            summary.warnings.append(f"{series_id} unavailable: {_redacted_error(exc)}")
            summary.series.append(point)
            continue
        numeric_observations: list[tuple[str, float]] = []
        for item in observations:
            if not isinstance(item, dict):
                continue
            value = _safe_float(item.get("value"))
            obs_date = str(item.get("date") or "")
            if value is not None and obs_date:
                numeric_observations.append((obs_date, value))
        if not numeric_observations:
            point.missing_data.append(f"{series_id}:latest_value")
        else:
            point.latest_date, point.latest_value = numeric_observations[0]
            if len(numeric_observations) > 1:
                point.recent_change = round(numeric_observations[0][1] - numeric_observations[1][1], 4)
            try:
                latest_date = date.fromisoformat(point.latest_date)
                point.stale = (current.date() - latest_date).days > 60
            except ValueError:
                point.stale = True
        summary.series.append(point)
    if not summary.series:
        summary.missing_data.append("fred_series")
    return summary


def _published_age_minutes(value: str | None, *, now: datetime) -> int | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None
    return max(0, int((now.astimezone(UTC) - parsed).total_seconds() // 60))


def build_news_context_summary(symbol: str, *, limit: int = 5, now: datetime | None = None) -> NewsContextSummary:
    current = now or utc_now()
    normalized = symbol.upper().strip()
    provider_name = settings.news_provider.strip().lower() or "mock"
    summary = NewsContextSummary(provider=provider_name, symbol=normalized, generated_at=current)
    try:
        articles = build_news_provider().fetch_latest(normalized)[: max(1, min(limit, 10))]
    except Exception as exc:  # noqa: BLE001
        summary.missing_data.append("news_provider")
        summary.warnings.append(f"News context unavailable: {_redacted_error(exc)}")
        return summary

    for item in articles:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("headline") or "").strip()
        if not title:
            continue
        insights = item.get("insights") if isinstance(item.get("insights"), list) else []
        sentiment = item.get("sentiment")
        if sentiment is None and insights:
            first = next((entry for entry in insights if isinstance(entry, dict)), None)
            if first is not None:
                sentiment = first.get("sentiment")
        summary.headlines.append(
            NewsArticleSummary(
                title=title,
                publisher=str(item.get("publisher") or item.get("source") or "") or None,
                published_utc=str(item.get("published_utc") or "") or None,
                article_url=str(item.get("article_url") or item.get("url") or "") or None,
                tickers=[str(ticker).upper() for ticker in (item.get("tickers") or [normalized]) if str(ticker).strip()],
                description=str(item.get("description") or "") or None,
                sentiment=str(sentiment) if sentiment else None,
                insights=[
                    str(entry.get("insight") or entry.get("summary") or entry.get("sentiment") or entry)
                    for entry in insights
                    if str(entry).strip()
                ][:3],
            )
        )
    summary.count = len(summary.headlines)
    if summary.headlines:
        summary.newest_article_age_minutes = _published_age_minutes(summary.headlines[0].published_utc, now=current)
        sentiments = [item.sentiment for item in summary.headlines if item.sentiment]
        if sentiments:
            summary.sentiment_summary = ", ".join(sorted(set(sentiments))[:3])
    else:
        summary.missing_data.append("recent_news")
    return summary


def build_provider_context_summary(
    *,
    market_data_source: str | None,
    fallback_mode: bool = False,
    session_policy: str | None = None,
    market_mode: str | None = None,
) -> ProviderContextSummary:
    missing: list[str] = []
    if not market_data_source:
        missing.append("market_data_source")
    if market_mode == "options" and not settings.polygon_api_key:
        missing.append("options_provider_config")
    return ProviderContextSummary(
        market_data_source=market_data_source,
        market_data_fallback_mode=fallback_mode,
        session_policy=session_policy,
        macro_provider=settings.macro_calendar_provider.strip().lower() or "mock",
        news_provider=settings.news_provider.strip().lower() or "mock",
        options_data_provider=settings.market_data_provider.strip().lower() if market_mode == "options" else None,
        provider_health_summary="provider-backed context shown when configured; missing fields are explicit",
        missing_data=missing,
        provenance={
            "no_provider_keys_included": True,
            "market_mode": market_mode,
        },
    )


def risk_calendar_summary_from_payload(value: object) -> RiskCalendarSummary | None:
    if not isinstance(value, dict):
        return None
    decision = value.get("decision") if isinstance(value.get("decision"), dict) else {}
    return RiskCalendarSummary(
        decision_state=str(decision.get("decision_state") or "") or None,
        risk_level=str(decision.get("risk_level") or "") or None,
        recommended_action=str(decision.get("recommended_action") or "") or None,
        warning_summary=str(decision.get("warning_summary") or "") or None,
        block_reason=str(decision.get("block_reason") or "") or None,
        missing_data=[str(item) for item in decision.get("missing_evidence") or [] if str(item).strip()],
    )


def _llm_summary_from_payload(payload: dict[str, Any]) -> LlmExplanationSummary | None:
    explanation = payload.get("ai_explanation") if isinstance(payload.get("ai_explanation"), dict) else None
    provenance = payload.get("llm_provenance") if isinstance(payload.get("llm_provenance"), dict) else {}
    if explanation is None and not provenance:
        return None
    return LlmExplanationSummary(
        summary=str(explanation.get("summary") or "") if explanation else None,
        provider=str(provenance.get("provider") or "") or None,
        model=str(provenance.get("model") or "") or None,
        fallback_used=bool(provenance.get("fallback_used", False)),
        missing_data=[] if explanation else ["ai_explanation"],
    )


def _options_leg_packet(leg: dict[str, Any]) -> OptionsLegAnalysisPacket:
    action = str(leg.get("action") or "").lower()
    side = "long" if action == "buy" else "short" if action == "sell" else None
    return OptionsLegAnalysisPacket(
        role=str(leg.get("label") or leg.get("role") or "") or None,
        side=side,
        option_type=str(leg.get("right") or leg.get("option_type") or "") or None,
        target_strike=_safe_float(leg.get("target_strike")),
        selected_listed_strike=_safe_float(leg.get("selected_listed_strike") or leg.get("strike")),
        strike_snap_distance=_safe_float(leg.get("strike_snap_distance")),
        option_symbol=str(leg.get("option_symbol") or "") or None,
        bid=_safe_float(leg.get("bid")),
        ask=_safe_float(leg.get("ask")),
        current_mark_premium=_safe_float(leg.get("current_mark_premium") or leg.get("mark_price")),
        mark_method=str(leg.get("mark_method") or "") or None,
        implied_volatility=_safe_float(leg.get("implied_volatility")),
        open_interest=_safe_int(leg.get("open_interest")),
        delta=_safe_float(leg.get("delta")),
        gamma=_safe_float(leg.get("gamma")),
        theta=_safe_float(leg.get("theta")),
        vega=_safe_float(leg.get("vega")),
        stale=bool(leg.get("stale", False)),
        missing_data=[str(item) for item in leg.get("missing_data") or [] if str(item).strip()],
    )


def options_packet_from_structure(
    *,
    symbol: str,
    timeframe: str | None,
    option_structure: dict[str, Any] | None,
    expected_range: dict[str, Any] | None = None,
) -> OptionsAnalysisPacket | None:
    if not isinstance(option_structure, dict):
        return None
    raw_legs = [leg for leg in option_structure.get("legs") or [] if isinstance(leg, dict)]
    breakevens = [
        value
        for value in (_safe_float(option_structure.get("breakeven_low")), _safe_float(option_structure.get("breakeven_high")))
        if value is not None
    ]
    warnings = [
        *[str(item) for item in option_structure.get("contract_resolution_warnings") or [] if str(item).strip()],
        *[str(item) for item in option_structure.get("structure_validation_warnings") or [] if str(item).strip()],
    ]
    missing = []
    if not raw_legs:
        missing.append("option_structure_legs")
    if any(not leg.get("option_symbol") for leg in raw_legs):
        missing.append("listed_option_symbols")
    if any("current_mark_premium" not in leg for leg in raw_legs):
        missing.append("option_snapshot_marks")
    return OptionsAnalysisPacket(
        underlying=symbol.upper(),
        strategy_type=str(option_structure.get("type") or "") or None,
        timeframe=timeframe,
        expiration=str(option_structure.get("expiration") or "") or None,
        days_to_expiration=_safe_int(option_structure.get("dte")),
        structure_status=str(option_structure.get("structure_validation_status") or "") or None,
        listed_contract_validation_status=str(option_structure.get("contract_resolution_status") or "") or None,
        legs=[_options_leg_packet(dict(leg)) for leg in raw_legs],
        net_debit=_safe_float(option_structure.get("net_debit")),
        net_credit=_safe_float(option_structure.get("net_credit")),
        max_profit=_safe_float(option_structure.get("max_profit")),
        max_loss=_safe_float(option_structure.get("max_loss")),
        breakevens=breakevens,
        expected_range=expected_range,
        payoff_preview_summary="Defined-risk payoff fields are deterministic research context only.",
        expiration_settlement_summary="Expiration/settlement review is paper-only and requires explicit manual confirmation where available.",
        assignment_exercise_risk_summary="Assignment/exercise risk is informational only; no automation is enabled.",
        provider_option_mark_readiness="available_when_selected_contract_snapshots_include_marks",
        warnings=sorted(set(warnings)),
        missing_data=sorted(set(missing)),
    )


def equity_packet_from_payload(
    *,
    symbol: str,
    timeframe: str | None,
    payload: dict[str, Any],
) -> EquityAnalysisPacket:
    workflow = payload.get("workflow") if isinstance(payload.get("workflow"), dict) else {}
    ranking = workflow.get("ranking_provenance") if isinstance(workflow.get("ranking_provenance"), dict) else {}
    quality = payload.get("quality") if isinstance(payload.get("quality"), dict) else {}
    sizing = payload.get("sizing") if isinstance(payload.get("sizing"), dict) else {}
    return EquityAnalysisPacket(
        symbol=symbol.upper(),
        side=str(payload.get("side") or "") or None,
        timeframe=timeframe,
        setup_name=str(ranking.get("strategy") or payload.get("setup_type") or payload.get("strategy") or "") or None,
        thesis=str(payload.get("thesis") or ranking.get("thesis") or "") or None,
        approval_status="approved" if payload.get("approved") is True else "rejected" if payload.get("approved") is False else None,
        rank=_safe_int(ranking.get("rank")),
        score=_safe_float(ranking.get("score") or quality.get("score")),
        confidence=_safe_float(ranking.get("confidence") or quality.get("confidence") or payload.get("confidence")),
        expected_rr=_safe_float(ranking.get("expected_rr") or quality.get("expected_rr")),
        entry_zone=payload.get("entry") or ranking.get("entry_zone") or payload.get("entry_zone"),
        stop=payload.get("invalidation") or ranking.get("invalidation"),
        targets=payload.get("targets") or ranking.get("targets"),
        expected_range=payload.get("expected_range") if isinstance(payload.get("expected_range"), dict) else None,
        risk_budget_at_stop=_safe_float(sizing.get("risk_dollars")),
        max_paper_order_value=float(settings.paper_max_order_notional),
        final_shares=_safe_int(sizing.get("shares")),
        final_notional=_safe_float(sizing.get("notional")),
        missing_data=[],
    )


def build_analysis_packet(
    *,
    symbol: str,
    market_mode: str,
    timeframe: str | None,
    source_payload: dict[str, Any],
    market_data_source: str | None,
    fallback_mode: bool = False,
    session_policy: str | None = None,
    macro_context: MacroContextSummary | None = None,
    news_context: NewsContextSummary | None = None,
    provider_context: ProviderContextSummary | None = None,
    risk_calendar: dict[str, Any] | None = None,
    paper_lifecycle: PaperLifecycleSummary | None = None,
) -> AnalysisPacket:
    normalized_mode = market_mode or "equities"
    missing: list[str] = []
    if macro_context is None:
        macro_context = build_macro_context_summary()
    if news_context is None:
        news_context = build_news_context_summary(symbol)
    if provider_context is None:
        provider_context = build_provider_context_summary(
            market_data_source=market_data_source,
            fallback_mode=fallback_mode,
            session_policy=session_policy,
            market_mode=normalized_mode,
        )
    option_structure = source_payload.get("option_structure") if isinstance(source_payload.get("option_structure"), dict) else None
    expected_range = source_payload.get("expected_range") if isinstance(source_payload.get("expected_range"), dict) else None
    options = options_packet_from_structure(
        symbol=symbol,
        timeframe=timeframe,
        option_structure=option_structure,
        expected_range=expected_range,
    ) if normalized_mode == "options" else None
    equity = equity_packet_from_payload(symbol=symbol, timeframe=timeframe, payload=source_payload) if normalized_mode == "equities" else None
    if macro_context.missing_data:
        missing.extend(f"macro:{item}" for item in macro_context.missing_data)
    if news_context.missing_data:
        missing.extend(f"news:{item}" for item in news_context.missing_data)
    if options and options.missing_data:
        missing.extend(f"options:{item}" for item in options.missing_data)
    return AnalysisPacket(
        symbol=symbol.upper(),
        market_mode=normalized_mode,
        timeframe=timeframe,
        provider=market_data_source,
        source=market_data_source,
        session_policy=session_policy,
        missing_data=sorted(set(missing)),
        warnings=sorted(set([*macro_context.warnings, *news_context.warnings])),
        provenance={
            "schema": "analysis_packet.v1",
            "generated_from": "backend_deterministic_context",
            "no_provider_keys_included": True,
            "llm_cannot_change_trade_fields": True,
        },
        provider_context=provider_context,
        macro_context=macro_context,
        news_context=news_context,
        risk_calendar=risk_calendar_summary_from_payload(risk_calendar),
        llm_explanation=_llm_summary_from_payload(source_payload),
        paper_lifecycle=paper_lifecycle,
        equity=equity,
        options=options,
    )
