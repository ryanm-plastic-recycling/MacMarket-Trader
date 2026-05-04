"""Market-data provider abstraction with Polygon + Alpaca scaffolds + deterministic fallback."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from time import monotonic
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from macmarket_trader.config import settings
from macmarket_trader.domain.schemas import Bar


class ProviderUnavailableError(Exception):
    """Raised when the configured market data provider cannot be reached or returns an error."""


class SymbolNotFoundError(Exception):
    """Raised when the provider has no data for the requested symbol (not a connectivity failure)."""


class DataNotEntitledError(Exception):
    """Raised when the current data plan does not include access to the requested data."""


# Polygon uses the I: prefix for index tickers.
INDEX_SYMBOLS = {"SPX", "NDX", "RUT", "VIX", "DJI", "COMP", "OEX"}
POLYGON_AGGREGATE_MAX_LIMIT = 50_000
US_EQUITY_TIMEZONE = ZoneInfo("America/New_York")
RTH_SOURCE_TIMEFRAME = "30M"
RTH_SOURCE_MULTIPLIER = 30
RTH_SOURCE_TIMESPAN = "minute"
RTH_BUCKETS_BY_TIMEFRAME = {
    "1H": [(570, 630), (630, 690), (690, 750), (750, 810), (810, 870), (870, 930), (930, 960)],
    "4H": [(570, 810), (810, 960)],
}
OPTIONS_HEALTH_DEFAULT_UNDERLYINGS = ("SPY", "AAPL")
OPTIONS_HEALTH_STATIC_SAMPLE_UNDERLYING = "AAPL"
OPTIONS_HEALTH_STATIC_SAMPLE_OPTION = "O:AAPL260504C00200000"
OPTIONS_HEALTH_MAX_DISCOVERED_CANDIDATES = 8
OPTIONS_HEALTH_MIN_DTE = 7
OPTIONS_HEALTH_MAX_DTE = 45
OPTION_INDEX_UNDERLYINGS = {"SPX", "NDX", "RUT", "VIX"}
OPTION_ETF_UNDERLYINGS = {
    "DIA",
    "EEM",
    "EFA",
    "GLD",
    "IWM",
    "QQQ",
    "SLV",
    "SPY",
    "TLT",
    "XLE",
    "XLF",
    "XLK",
    "XLV",
}
OPTION_CONTRACT_REFERENCE_MAX_PAGES = 8


def _finite_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in {float("inf"), float("-inf")}:
        return None
    return number


def _positive_float(value: Any) -> float | None:
    number = _finite_float(value)
    if number is None or number <= 0:
        return None
    return number


def _timestamp_from_provider_value(value: Any) -> datetime | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric <= 0:
        return None
    # Polygon snapshot timestamps may arrive as nanoseconds, milliseconds, or seconds.
    if numeric > 10_000_000_000_000:
        numeric = numeric / 1_000_000_000
    elif numeric > 10_000_000_000:
        numeric = numeric / 1_000
    try:
        return datetime.fromtimestamp(numeric, tz=UTC)
    except (OverflowError, OSError, ValueError):
        return None


def _timestamp_from_provider_object(payload: dict[str, Any], *keys: str) -> datetime | None:
    for key in keys:
        value = payload.get(key)
        parsed = _timestamp_from_provider_value(value)
        if parsed is not None:
            return parsed
    return None


def _is_stale(as_of: datetime | None, *, now: datetime | None = None) -> bool:
    if as_of is None:
        return False
    reference = now or datetime.now(tz=UTC)
    return (reference - as_of.astimezone(UTC)).total_seconds() > settings.market_data_option_snapshot_stale_seconds


def _is_entitlement_error_text(value: object) -> bool:
    text = str(value or "").lower()
    return any(marker in text for marker in ("not entitled", "entitlement", "permission", "upgrade plan"))


def _redact_provider_text(value: object) -> str:
    text = str(value or "").replace("\n", " ").replace("\r", " ").strip()
    for secret in (
        settings.polygon_api_key,
        settings.alpaca_api_key_id,
        settings.alpaca_api_secret_key,
        settings.fred_api_key,
    ):
        if secret and secret.strip():
            text = text.replace(secret.strip(), "[redacted]")
    if "apiKey=" in text:
        prefix, _sep, rest = text.partition("apiKey=")
        suffix = ""
        if "&" in rest:
            suffix = "&" + rest.split("&", 1)[1]
        text = f"{prefix}apiKey=[redacted]{suffix}"
    return text[:300]


def _parse_expiration_date(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def build_polygon_option_ticker(
    *,
    underlying_symbol: str,
    expiration: date,
    option_type: str,
    strike: float,
) -> str:
    """Build Polygon's OCC-style option ticker, e.g. O:AAPL260515C00205000."""
    underlying = "".join(ch for ch in underlying_symbol.upper().strip() if ch.isalnum())
    right = "C" if str(option_type).strip().lower().startswith("c") else "P"
    strike_mills = int(round(float(strike) * 1000))
    return f"O:{underlying}{expiration.strftime('%y%m%d')}{right}{strike_mills:08d}"


def option_reference_underlying_ticker(symbol: str) -> str:
    """Polygon reference contracts expect the raw underlying ticker, even for index options."""
    return symbol.upper().strip().removeprefix("I:")


def option_snapshot_underlying_ticker(symbol: str) -> str:
    """Polygon option snapshots use I: for index underlyings such as SPX."""
    normalized = option_reference_underlying_ticker(symbol)
    if normalized in OPTION_INDEX_UNDERLYINGS:
        return f"I:{normalized}"
    return normalized


def option_underlying_asset_type(symbol: str) -> str:
    normalized = option_reference_underlying_ticker(symbol)
    if normalized in OPTION_INDEX_UNDERLYINGS:
        return "index"
    if normalized in OPTION_ETF_UNDERLYINGS:
        return "etf"
    return "equity"


def unavailable_option_contract_snapshot(
    *,
    underlying_symbol: str,
    option_symbol: str,
    provider: str,
    endpoint: str = "unavailable",
    missing_fields: list[str] | None = None,
    provider_error: str | None = None,
    fallback_mode: bool = False,
    stale: bool = False,
) -> OptionContractSnapshot:
    return OptionContractSnapshot(
        option_symbol=option_symbol.upper().strip(),
        underlying_symbol=underlying_symbol.upper().strip(),
        provider=provider,
        endpoint=endpoint,
        mark_price=None,
        mark_method="unavailable",
        as_of=None,
        stale=stale,
        fallback_mode=fallback_mode,
        missing_fields=missing_fields or ["option_mark_data"],
        provider_error=provider_error,
    )


def normalize_polygon_ticker(symbol: str) -> str:
    """Map known index symbols to their Polygon I: prefixed form; pass all others through unchanged."""
    upper = symbol.upper()
    if upper in INDEX_SYMBOLS:
        return f"I:{upper}"
    return upper


def _minute_of_day(value: datetime) -> int:
    local = value.astimezone(US_EQUITY_TIMEZONE)
    return local.hour * 60 + local.minute


def _session_timestamp(session_day: date, minute_of_day: int) -> datetime:
    local = datetime.combine(
        session_day,
        time(hour=minute_of_day // 60, minute=minute_of_day % 60),
        tzinfo=US_EQUITY_TIMEZONE,
    )
    return local.astimezone(UTC)


def _rth_bucket_for(timestamp: datetime, timeframe: str) -> tuple[date, int, int] | None:
    local = timestamp.astimezone(US_EQUITY_TIMEZONE)
    minute = local.hour * 60 + local.minute
    for start_minute, end_minute in RTH_BUCKETS_BY_TIMEFRAME.get(timeframe.upper(), []):
        if start_minute <= minute < end_minute:
            return local.date(), start_minute, end_minute
    return None


def _aggregate_regular_hours_intraday_bars(
    bars: list[Bar],
    *,
    output_timeframe: str,
    limit: int,
    provider: str,
    source_timeframe: str = RTH_SOURCE_TIMEFRAME,
    source_session_policy: str = "provider_session",
) -> tuple[list[Bar], dict[str, object]]:
    ordered = sorted(
        (bar for bar in bars if bar.timestamp is not None),
        key=lambda bar: bar.timestamp or datetime.combine(bar.date, datetime.min.time(), tzinfo=UTC),
    )
    filtered_extended_hours_count = 0
    buckets: dict[tuple[date, int, int], list[Bar]] = {}
    for bar in ordered:
        if bar.timestamp is None:
            continue
        bucket_key = _rth_bucket_for(bar.timestamp, output_timeframe)
        if bucket_key is None:
            filtered_extended_hours_count += 1
            continue
        buckets.setdefault(bucket_key, []).append(bar)

    aggregated: list[Bar] = []
    for (session_day, start_minute, _end_minute), bucket_bars in sorted(buckets.items()):
        if not bucket_bars:
            continue
        aggregated.append(
            Bar(
                date=session_day,
                timestamp=_session_timestamp(session_day, start_minute),
                open=bucket_bars[0].open,
                high=max(bar.high for bar in bucket_bars),
                low=min(bar.low for bar in bucket_bars),
                close=bucket_bars[-1].close,
                volume=sum(bar.volume for bar in bucket_bars),
                rel_volume=None,
                session_policy="regular_hours",
                source_session_policy=source_session_policy,
                source_timeframe=source_timeframe,
                provider=provider,
            )
        )

    selected = aggregated[-limit:] if limit > 0 else aggregated
    metadata = {
        "provider": provider,
        "source_timeframe": source_timeframe,
        "output_timeframe": output_timeframe.upper(),
        "session_policy": "regular_hours",
        "source_session_policy": source_session_policy,
        "filtered_extended_hours_count": filtered_extended_hours_count,
        "rth_bucket_count": len(selected),
        "first_bar_timestamp": selected[0].timestamp.isoformat() if selected and selected[0].timestamp else None,
        "last_bar_timestamp": selected[-1].timestamp.isoformat() if selected and selected[-1].timestamp else None,
    }
    return selected, metadata


@dataclass
class MarketSnapshot:
    symbol: str
    timeframe: str
    as_of: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    source: str
    fallback_mode: bool


@dataclass
class MarketProviderHealth:
    provider: str
    mode: str
    status: str
    details: str
    configured: bool
    feed: str
    sample_symbol: str
    latency_ms: float | None = None
    last_success_at: datetime | None = None


@dataclass
class OptionContractSnapshot:
    option_symbol: str
    underlying_symbol: str
    provider: str
    endpoint: str
    mark_price: float | None
    mark_method: str
    as_of: datetime | None
    stale: bool
    bid: float | None = None
    ask: float | None = None
    latest_trade_price: float | None = None
    prior_close: float | None = None
    implied_volatility: float | None = None
    open_interest: int | None = None
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
    underlying_price: float | None = None
    fallback_mode: bool = False
    missing_fields: list[str] | None = None
    provider_error: str | None = None


@dataclass(frozen=True)
class OptionsHealthSample:
    underlying: str
    option_symbol: str
    selection_method: str
    expiration: date | None = None
    strike: float | None = None
    option_type: str | None = None
    dte: int | None = None
    open_interest: int | None = None
    volume: int | None = None


@dataclass(frozen=True)
class OptionsHealthDiscovery:
    samples: list[OptionsHealthSample]
    error: str | None = None
    entitlement_error: bool = False
    underlying_price: float | None = None
    underlying_error: str | None = None
    underlying_entitlement_error: bool = False


@dataclass(frozen=True)
class OptionContractResolution:
    requested_underlying: str
    underlying_asset_type: str
    target_expiration: date
    selected_expiration: date | None
    option_type: str
    target_strike: float
    selected_strike: float | None
    option_symbol: str | None
    provider: str
    contract_selection_method: str
    strike_snap_distance: float | None = None
    unavailable_reason: str | None = None
    warnings: tuple[str, ...] = ()

    @property
    def resolved(self) -> bool:
        return bool(self.option_symbol and self.selected_strike is not None and self.selected_expiration is not None)

    def as_dict(self) -> dict[str, Any]:
        return {
            "resolved": self.resolved,
            "requested_underlying": self.requested_underlying,
            "underlying_asset_type": self.underlying_asset_type,
            "target_expiration": self.target_expiration.isoformat(),
            "selected_expiration": self.selected_expiration.isoformat() if self.selected_expiration else None,
            "option_type": self.option_type,
            "target_strike": self.target_strike,
            "selected_listed_strike": self.selected_strike,
            "strike_snap_distance": self.strike_snap_distance,
            "provider": self.provider,
            "provider_contract_symbol": self.option_symbol,
            "contract_selection_method": self.contract_selection_method,
            "unavailable_reason": self.unavailable_reason,
            "warnings": list(self.warnings),
        }


class TTLCache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        item = self._store.get(key)
        if item is None:
            return None
        expires_at, value = item
        if monotonic() >= expires_at:
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        ttl = max(1, int(ttl_seconds))
        self._store[key] = (monotonic() + ttl, value)


class MarketDataProvider:
    name = "base"

    def fetch_historical_bars(self, symbol: str, timeframe: str, limit: int) -> list[Bar]:
        raise NotImplementedError

    def fetch_latest_snapshot(self, symbol: str, timeframe: str) -> MarketSnapshot:
        raise NotImplementedError

    def fetch_option_contract_snapshot(self, underlying_symbol: str, option_symbol: str) -> OptionContractSnapshot:
        raise NotImplementedError

    def fetch_option_contracts(
        self,
        *,
        underlying_symbol: str,
        expiration: date | None = None,
        option_type: str | None = None,
        strike_gte: float | None = None,
        strike_lte: float | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    def resolve_option_contract(
        self,
        *,
        underlying_symbol: str,
        expiration: date,
        option_type: str,
        target_strike: float,
    ) -> OptionContractResolution:
        raise NotImplementedError

    def health_check(self, sample_symbol: str) -> MarketProviderHealth:
        raise NotImplementedError


class DeterministicFallbackMarketDataProvider(MarketDataProvider):
    name = "fallback"

    def _bars(self, symbol: str, timeframe: str, limit: int) -> list[Bar]:
        del symbol
        tf = timeframe.upper()
        if tf in {"1H", "4H"}:
            bucket_starts = [start for start, _end in RTH_BUCKETS_BY_TIMEFRAME[tf]]
            base_day = date(2025, 1, 1)
            bars: list[Bar] = []
            idx = 0
            day_offset = 0
            target_count = max(10, limit)
            while len(bars) < target_count:
                session_day = base_day + timedelta(days=day_offset)
                day_offset += 1
                if session_day.weekday() >= 5:
                    continue
                for start_minute in bucket_starts:
                    price = 100 + idx * 0.25
                    ts = _session_timestamp(session_day, start_minute)
                    bars.append(
                        Bar(
                            date=session_day,
                            timestamp=ts,
                            open=price,
                            high=price + 1.2,
                            low=price - 1.0,
                            close=price + 0.35,
                            volume=1_000_000 + idx * 5000,
                            rel_volume=1.0,
                            session_policy="regular_hours",
                            source_session_policy="regular_hours",
                            source_timeframe=tf,
                            provider="fallback",
                        )
                    )
                    idx += 1
            return bars[-limit:]

        base = date(2025, 1, 1)
        bars: list[Bar] = []
        for idx in range(max(10, limit)):
            t = base + timedelta(days=idx)
            price = 100 + idx * 0.25
            bars.append(
                Bar(
                    date=t,
                    open=price,
                    high=price + 1.2,
                    low=price - 1.0,
                    close=price + 0.35,
                    volume=1_000_000 + idx * 5000,
                    rel_volume=1.0,
                )
            )
        return bars[-limit:]

    def fetch_historical_bars(self, symbol: str, timeframe: str, limit: int) -> list[Bar]:
        return self._bars(symbol=symbol, timeframe=timeframe, limit=limit)

    def fetch_latest_snapshot(self, symbol: str, timeframe: str) -> MarketSnapshot:
        bar = self._bars(symbol=symbol, timeframe=timeframe, limit=1)[-1]
        return MarketSnapshot(
            symbol=symbol,
            timeframe=timeframe,
            as_of=datetime.combine(bar.date, datetime.min.time(), tzinfo=UTC),
            open=bar.open,
            high=bar.high,
            low=bar.low,
            close=bar.close,
            volume=bar.volume,
            source="fallback",
            fallback_mode=True,
        )

    def health_check(self, sample_symbol: str) -> MarketProviderHealth:
        return MarketProviderHealth(
            provider="market_data",
            mode=self.name,
            status="warning",
            details="Deterministic fallback bars are active because provider-backed market data is disabled or unavailable.",
            configured=False,
            feed="none",
            sample_symbol=sample_symbol,
        )


class AlpacaMarketDataProvider(MarketDataProvider):
    """Kept intact as a scaffolded alternate provider."""

    name = "alpaca"

    def __init__(self) -> None:
        self.base_url = settings.alpaca_market_data_base_url.rstrip("/")
        self.api_key = settings.alpaca_api_key_id.strip()
        self.api_secret = settings.alpaca_api_secret_key.strip()
        self.feed = settings.alpaca_market_data_feed.strip().lower() or "iex"
        self.timeout_seconds = settings.market_data_request_timeout_seconds
        self._last_success_at: datetime | None = None

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_secret and self.base_url)

    def _headers(self) -> dict[str, str]:
        return {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.api_secret,
            "Accept": "application/json",
        }

    def _request_json(self, path: str, query: dict[str, str]) -> dict[str, Any]:
        url = f"{self.base_url}{path}?{urlencode(query)}"
        request = Request(url=url, headers=self._headers(), method="GET")
        with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
            self._last_success_at = datetime.now(tz=UTC)
            return payload

    def _map_timeframe(self, timeframe: str) -> str:
        tf = timeframe.upper()
        mapping = {"1D": "1Day", "1H": "1Hour", "4H": "4Hour"}
        return mapping.get(tf, "1Day")

    def _normalize_bar(self, bar: dict[str, Any]) -> Bar:
        ts = datetime.fromisoformat(str(bar["t"]).replace("Z", "+00:00"))
        ts_utc = ts.astimezone(UTC)
        return Bar(
            date=ts_utc.astimezone(ZoneInfo("America/New_York")).date(),
            timestamp=ts_utc,
            open=float(bar["o"]),
            high=float(bar["h"]),
            low=float(bar["l"]),
            close=float(bar["c"]),
            volume=int(bar.get("v") or 0),
            rel_volume=None,
        )

    def fetch_historical_bars(self, symbol: str, timeframe: str, limit: int) -> list[Bar]:
        payload = self._request_json(
            "/v2/stocks/bars",
            {
                "symbols": symbol.upper(),
                "timeframe": self._map_timeframe(timeframe),
                "limit": str(limit),
                "feed": self.feed,
                "adjustment": "raw",
                "sort": "asc",
            },
        )
        bars = payload.get("bars", {}).get(symbol.upper(), [])
        return [self._normalize_bar(item) for item in bars]

    def fetch_latest_snapshot(self, symbol: str, timeframe: str) -> MarketSnapshot:
        payload = self._request_json(
            "/v2/stocks/bars/latest",
            {"symbols": symbol.upper(), "feed": self.feed},
        )
        latest = payload.get("bars", {}).get(symbol.upper())
        if not latest:
            raise ValueError(f"No latest bar returned for {symbol}")
        bar = self._normalize_bar(latest)
        as_of = datetime.fromisoformat(str(latest["t"]).replace("Z", "+00:00"))
        return MarketSnapshot(
            symbol=symbol.upper(),
            timeframe=timeframe,
            as_of=as_of,
            open=bar.open,
            high=bar.high,
            low=bar.low,
            close=bar.close,
            volume=bar.volume,
            source="alpaca",
            fallback_mode=False,
        )

    def health_check(self, sample_symbol: str) -> MarketProviderHealth:
        if not self.is_configured():
            return MarketProviderHealth(
                provider="market_data",
                mode=self.name,
                status="warning",
                details="Alpaca market-data credentials/config are missing; deterministic fallback remains active.",
                configured=False,
                feed=self.feed,
                sample_symbol=sample_symbol,
            )

        started = monotonic()
        try:
            self.fetch_latest_snapshot(sample_symbol, "1D")
            elapsed = round((monotonic() - started) * 1000, 2)
            return MarketProviderHealth(
                provider="market_data",
                mode=self.name,
                status="ok",
                details="Alpaca latest bar probe succeeded.",
                configured=True,
                feed=self.feed,
                sample_symbol=sample_symbol,
                latency_ms=elapsed,
                last_success_at=self._last_success_at,
            )
        except (HTTPError, URLError, TimeoutError, ValueError, KeyError, OSError) as exc:
            elapsed = round((monotonic() - started) * 1000, 2)
            return MarketProviderHealth(
                provider="market_data",
                mode=self.name,
                status="warning",
                details=f"Alpaca probe failed: {exc}",
                configured=True,
                feed=self.feed,
                sample_symbol=sample_symbol,
                latency_ms=elapsed,
                last_success_at=self._last_success_at,
            )


class PolygonMarketDataProvider(MarketDataProvider):
    name = "polygon"

    def __init__(self) -> None:
        self.base_url = settings.polygon_base_url.rstrip("/")
        self.api_key = settings.polygon_api_key.strip()
        self.timeout_seconds = settings.polygon_timeout_seconds
        self._last_success_at: datetime | None = None
        self.last_aggregate_request_metadata: dict[str, object] | None = None

    def is_configured(self) -> bool:
        return bool(self.api_key and self.base_url)

    def _fetch_url(self, url: str) -> dict[str, Any]:
        """Fetch a fully-formed URL (used for both primary requests and next_url pagination)."""
        request = Request(url=url, headers={"Accept": "application/json"}, method="GET")
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
                payload = json.loads(response.read().decode("utf-8"))
                self._last_success_at = datetime.now(tz=UTC)
                return payload
        except HTTPError as exc:
            if exc.code == 403:
                raise DataNotEntitledError(
                    "Not entitled to this data. Upgrade plan at https://polygon.io/pricing"
                ) from exc
            if exc.code == 404:
                raise SymbolNotFoundError(f"Polygon returned 404 — ticker not found") from exc
            raise ProviderUnavailableError(f"Polygon HTTP {exc.code}: {exc.reason}") from exc
        except URLError as exc:
            raise ProviderUnavailableError(f"Polygon connection error: {exc.reason}") from exc
        except TimeoutError as exc:
            raise ProviderUnavailableError(f"Polygon request timed out after {self.timeout_seconds}s") from exc

    def _request_json(self, path: str, query: dict[str, str]) -> dict[str, Any]:
        effective_query = {**query, "apiKey": self.api_key}
        url = f"{self.base_url}{path}?{urlencode(effective_query)}"
        return self._fetch_url(url)

    def _polygon_next_url(self, next_url: object) -> str | None:
        url = str(next_url or "").strip()
        if not url:
            return None
        if "apiKey=" in url:
            return url
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}apiKey={self.api_key}"

    def _map_polygon_range(self, timeframe: str, limit: int) -> tuple[int, str, str, str, int]:
        tf = timeframe.upper()
        now = datetime.now(tz=UTC)
        if tf == "1H":
            calendar_days = max(20, int((limit / 7) * 1.8) + 10)
            start = now - timedelta(days=calendar_days)
            return RTH_SOURCE_MULTIPLIER, RTH_SOURCE_TIMESPAN, str(int(start.timestamp() * 1000)), str(int(now.timestamp() * 1000)), POLYGON_AGGREGATE_MAX_LIMIT
        if tf == "4H":
            calendar_days = max(40, int((limit / 2) * 1.8) + 10)
            start = now - timedelta(days=calendar_days)
            return RTH_SOURCE_MULTIPLIER, RTH_SOURCE_TIMESPAN, str(int(start.timestamp() * 1000)), str(int(now.timestamp() * 1000)), POLYGON_AGGREGATE_MAX_LIMIT
        if tf == "1M":
            start = now - timedelta(minutes=max(limit, 1) + 5)
            return 1, "minute", str(int(start.timestamp() * 1000)), str(int(now.timestamp() * 1000)), limit
        start = (now - timedelta(days=max(limit, 1) + 5)).date().isoformat()
        return 1, "day", start, now.date().isoformat(), limit

    def _is_intraday_timeframe(self, timeframe: str) -> bool:
        return timeframe.upper() in {"1M", "1H", "4H"}

    def _normalize_polygon_bar(self, bar: dict[str, Any]) -> Bar:
        ts_ms = int(bar.get("t") or 0)
        ts = datetime.fromtimestamp(ts_ms / 1000, tz=UTC)
        market_date = ts.astimezone(ZoneInfo("America/New_York")).date()
        return Bar(
            date=market_date,
            timestamp=ts,
            open=float(bar["o"]),
            high=float(bar["h"]),
            low=float(bar["l"]),
            close=float(bar["c"]),
            volume=int(bar.get("v") or 0),
            rel_volume=None,
        )

    def get_historical_bars(self, symbol: str, timeframe: str, limit: int = 120) -> list[Bar]:
        ticker = normalize_polygon_ticker(symbol)
        multiplier, timespan, from_ts, to_ts, request_limit = self._map_polygon_range(timeframe=timeframe, limit=limit)
        is_intraday = self._is_intraday_timeframe(timeframe)
        sort_direction = "desc" if is_intraday else "asc"
        needs_rth_normalization = timeframe.upper() in RTH_BUCKETS_BY_TIMEFRAME
        target_result_count = request_limit if needs_rth_normalization else (min(limit, request_limit) if is_intraday else request_limit)
        payload = self._request_json(
            f"/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from_ts}/{to_ts}",
            {"adjusted": "true", "sort": sort_direction, "limit": str(request_limit)},
        )
        results: list[dict[str, Any]] = list(payload.get("results") or [])
        self.last_aggregate_request_metadata = {
            "symbol": ticker,
            "timeframe": timeframe,
            "from": from_ts,
            "to": to_ts,
            "sort": sort_direction,
            "limit": request_limit,
            "requested_bars": limit,
            "results_count": len(results),
        }
        # Follow Polygon pagination only until the requested latest bar window is available.
        page = 0
        while "next_url" in payload and len(results) < target_result_count and page < 3:
            page += 1
            next_url = str(payload["next_url"])
            sep = "&" if "?" in next_url else "?"
            payload = self._fetch_url(f"{next_url}{sep}apiKey={self.api_key}")
            results.extend(payload.get("results") or [])
        if not results:
            raise SymbolNotFoundError(f"No bar data returned for symbol {symbol}")
        normalized = [self._normalize_polygon_bar(item) for item in results]
        normalized.sort(key=lambda bar: bar.timestamp or datetime.combine(bar.date, datetime.min.time(), tzinfo=UTC))
        if needs_rth_normalization:
            selected, rth_metadata = _aggregate_regular_hours_intraday_bars(
                normalized,
                output_timeframe=timeframe,
                limit=limit,
                provider=self.name,
                source_timeframe=RTH_SOURCE_TIMEFRAME,
                source_session_policy="provider_session",
            )
        else:
            selected = normalized[-limit:]
            rth_metadata = {}
        if self.last_aggregate_request_metadata is not None:
            self.last_aggregate_request_metadata.update(
                {
                    "pages_followed": page,
                    "results_count": len(results),
                    "response_first_timestamp": normalized[0].timestamp.isoformat() if normalized[0].timestamp else None,
                    "response_last_timestamp": normalized[-1].timestamp.isoformat() if normalized[-1].timestamp else None,
                    "returned_first_timestamp": selected[0].timestamp.isoformat() if selected and selected[0].timestamp else None,
                    "returned_last_timestamp": selected[-1].timestamp.isoformat() if selected and selected[-1].timestamp else None,
                    **rth_metadata,
                }
            )
        return selected

    def fetch_historical_bars(self, symbol: str, timeframe: str, limit: int) -> list[Bar]:
        return self.get_historical_bars(symbol=symbol, timeframe=timeframe, limit=limit)

    def get_latest_snapshot(self, symbol: str, timeframe: str = "1D") -> MarketSnapshot:
        ticker_param = normalize_polygon_ticker(symbol)
        payload = self._request_json(
            f"/v2/snapshot/locale/us/markets/stocks/tickers/{ticker_param}",
            {},
        )
        ticker = payload.get("ticker")
        if not ticker:
            raise SymbolNotFoundError(f"No snapshot returned for symbol {symbol}")

        day = ticker.get("day") or {}
        prev_day = ticker.get("prevDay") or {}
        last_trade = ticker.get("lastTrade") or {}

        if not day:
            raise ValueError(f"Snapshot missing current bar for {symbol}")

        ts_ms = int(last_trade.get("t") or day.get("t") or 0)
        as_of = datetime.fromtimestamp(ts_ms / 1000, tz=UTC)
        close = float(last_trade.get("p") or day.get("c") or prev_day.get("c") or 0.0)

        return MarketSnapshot(
            symbol=symbol.upper(),
            timeframe=timeframe,
            as_of=as_of,
            open=float(day.get("o") or prev_day.get("o") or close),
            high=float(day.get("h") or close),
            low=float(day.get("l") or close),
            close=close,
            volume=int(day.get("v") or 0),
            source="polygon",
            fallback_mode=False,
        )

    def fetch_latest_snapshot(self, symbol: str, timeframe: str) -> MarketSnapshot:
        return self.get_latest_snapshot(symbol=symbol, timeframe=timeframe)

    def fetch_options_chain_preview(self, symbol: str, limit: int = 50) -> dict[str, Any]:
        """Fetch options contract reference data for research-preview mode.

        Uses the Polygon /v3/reference/options/contracts endpoint (Options Basic plan).
        Returns calls and puts for the nearest expiry. No greeks or execution data.
        """
        try:
            payload = self._request_json(
                "/v3/reference/options/contracts",
                {
                    "underlying_ticker": option_reference_underlying_ticker(symbol),
                    "limit": str(limit),
                    "sort": "expiration_date",
                    "order": "asc",
                    "expired": "false",
                },
            )
        except SymbolNotFoundError:
            return {"underlying": symbol, "reason": f"No options contracts found for {symbol}", "calls": None, "puts": None}
        except DataNotEntitledError:
            reason = (
                "Index data entitlement required for SPX/index options reference data."
                if option_underlying_asset_type(symbol) == "index"
                else "Options endpoint not entitled to option reference data."
            )
            return {"underlying": symbol, "reason": reason, "calls": None, "puts": None}
        except ProviderUnavailableError as exc:
            return {"underlying": symbol, "reason": f"Options endpoint unavailable: {exc}", "calls": None, "puts": None}
        except Exception as exc:
            return {"underlying": symbol, "reason": f"Options fetch failed: {exc}", "calls": None, "puts": None}

        results: list[dict[str, Any]] = payload.get("results") or []
        if not results:
            return {
                "underlying": symbol,
                "reason": "No options contracts returned for this symbol",
                "calls": None,
                "puts": None,
            }

        today = date.today().isoformat()
        upcoming = [r for r in results if str(r.get("expiration_date", "")) >= today]
        if not upcoming:
            upcoming = results

        nearest_expiry = min(
            (str(r["expiration_date"]) for r in upcoming if r.get("expiration_date")),
            default=None,
        )
        if not nearest_expiry:
            return {"underlying": symbol, "reason": "Could not determine nearest expiry date", "calls": None, "puts": None}

        expiry_contracts = [r for r in upcoming if r.get("expiration_date") == nearest_expiry]

        def _row(r: dict[str, Any]) -> dict[str, Any]:
            return {
                "ticker": r.get("ticker"),
                "strike": r.get("strike_price"),
                "expiry": r.get("expiration_date"),
                "option_type": r.get("contract_type"),
                "last_price": None,
                "volume": None,
            }

        calls = [_row(r) for r in expiry_contracts if r.get("contract_type") == "call"][:5]
        puts = [_row(r) for r in expiry_contracts if r.get("contract_type") == "put"][:5]

        return {
            "underlying": option_reference_underlying_ticker(symbol),
            "expiry": nearest_expiry,
            "calls": calls if calls else None,
            "puts": puts if puts else None,
            "data_as_of": today,
            "source": "polygon_options_basic",
        }

    def fetch_option_contract_snapshot(self, underlying_symbol: str, option_symbol: str) -> OptionContractSnapshot:
        underlying = option_snapshot_underlying_ticker(underlying_symbol)
        option_ticker = option_symbol.upper().strip()
        endpoint = f"/v3/snapshot/options/{underlying}/{option_ticker}"
        payload = self._request_json(endpoint, {})
        result = payload.get("results")
        if not isinstance(result, dict):
            raise SymbolNotFoundError(f"No option snapshot returned for {option_ticker}")

        quote = result.get("last_quote") if isinstance(result.get("last_quote"), dict) else {}
        trade = result.get("last_trade") if isinstance(result.get("last_trade"), dict) else {}
        day = result.get("day") if isinstance(result.get("day"), dict) else {}
        greeks = result.get("greeks") if isinstance(result.get("greeks"), dict) else {}
        underlying_asset = result.get("underlying_asset") if isinstance(result.get("underlying_asset"), dict) else {}

        bid = _positive_float(quote.get("bid") or quote.get("bp"))
        ask = _positive_float(quote.get("ask") or quote.get("ap"))
        last_price = _positive_float(trade.get("price") or trade.get("p"))
        prior_close = _positive_float(day.get("close") or day.get("c") or day.get("previous_close"))
        quote_as_of = _timestamp_from_provider_object(quote, "sip_timestamp", "participant_timestamp", "t", "timestamp")
        trade_as_of = _timestamp_from_provider_object(trade, "sip_timestamp", "participant_timestamp", "t", "timestamp")
        day_as_of = _timestamp_from_provider_object(day, "last_updated", "t", "timestamp")

        missing_fields: list[str] = []
        mark_price: float | None = None
        mark_method = "unavailable"
        as_of: datetime | None = None
        stale = False

        quote_is_stale = _is_stale(quote_as_of)
        trade_is_stale = _is_stale(trade_as_of)

        if bid is not None and ask is not None and ask >= bid and not quote_is_stale:
            mark_price = round((bid + ask) / 2, 4)
            mark_method = "quote_mid"
            as_of = quote_as_of
            if quote_as_of is None:
                missing_fields.append("quote_timestamp")
        elif last_price is not None and not trade_is_stale:
            mark_price = round(last_price, 4)
            mark_method = "last_trade"
            as_of = trade_as_of
            if trade_as_of is None:
                missing_fields.append("trade_timestamp")
        elif prior_close is not None:
            mark_price = round(prior_close, 4)
            mark_method = "prior_close_fallback"
            as_of = day_as_of
            stale = True
            missing_fields.append("fresh_option_mark")
        else:
            stale = quote_is_stale or trade_is_stale
            missing_fields.append("option_mark_data")

        if quote_as_of is not None and quote_is_stale:
            missing_fields.append("stale_quote")
        if trade_as_of is not None and trade_is_stale:
            missing_fields.append("stale_trade")
        if bid is None:
            missing_fields.append("bid")
        if ask is None:
            missing_fields.append("ask")
        if last_price is None:
            missing_fields.append("latest_trade_price")

        return OptionContractSnapshot(
            option_symbol=option_ticker,
            underlying_symbol=underlying,
            provider="polygon",
            endpoint=endpoint,
            mark_price=mark_price,
            mark_method=mark_method,
            as_of=as_of,
            stale=stale,
            bid=bid,
            ask=ask,
            latest_trade_price=last_price,
            prior_close=prior_close,
            implied_volatility=_finite_float(result.get("implied_volatility")),
            open_interest=int(result["open_interest"]) if _finite_float(result.get("open_interest")) is not None else None,
            delta=_finite_float(greeks.get("delta")),
            gamma=_finite_float(greeks.get("gamma")),
            theta=_finite_float(greeks.get("theta")),
            vega=_finite_float(greeks.get("vega")),
            underlying_price=_finite_float(underlying_asset.get("price") or underlying_asset.get("value")),
            fallback_mode=False,
            missing_fields=sorted(set(missing_fields)),
        )

    def fetch_option_contracts(
        self,
        *,
        underlying_symbol: str,
        expiration: date | None = None,
        option_type: str | None = None,
        strike_gte: float | None = None,
        strike_lte: float | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        query: dict[str, str] = {
            "underlying_ticker": option_reference_underlying_ticker(underlying_symbol),
            "limit": str(limit),
            "sort": "strike_price",
            "order": "asc",
            "expired": "false",
        }
        if expiration is not None:
            query["expiration_date"] = expiration.isoformat()
        if option_type:
            normalized_type = str(option_type).strip().lower()
            if normalized_type in {"call", "put"}:
                query["contract_type"] = normalized_type
        if strike_gte is not None:
            query["strike_price.gte"] = str(round(float(strike_gte), 4))
        if strike_lte is not None:
            query["strike_price.lte"] = str(round(float(strike_lte), 4))
        payload = self._request_json("/v3/reference/options/contracts", query)
        results = list(payload.get("results") or [])
        page = 0
        while payload.get("next_url") and page < OPTION_CONTRACT_REFERENCE_MAX_PAGES:
            next_url = self._polygon_next_url(payload.get("next_url"))
            if not next_url:
                break
            page += 1
            payload = self._fetch_url(next_url)
            results.extend(payload.get("results") or [])
        return results

    def resolve_option_contract(
        self,
        *,
        underlying_symbol: str,
        expiration: date,
        option_type: str,
        target_strike: float,
    ) -> OptionContractResolution:
        normalized_underlying = option_reference_underlying_ticker(underlying_symbol)
        normalized_type = "call" if str(option_type).strip().lower().startswith("c") else "put"
        target = float(target_strike)
        asset_type = option_underlying_asset_type(normalized_underlying)
        strike_window = max(25.0, abs(target) * 0.10)
        strike_gte = max(0.0, target - strike_window)
        strike_lte = target + strike_window

        def _unresolved(reason: str, *, method: str = "unavailable") -> OptionContractResolution:
            return OptionContractResolution(
                requested_underlying=normalized_underlying,
                underlying_asset_type=asset_type,
                target_expiration=expiration,
                selected_expiration=None,
                option_type=normalized_type,
                target_strike=target,
                selected_strike=None,
                option_symbol=None,
                provider=self.name,
                contract_selection_method=method,
                unavailable_reason=str(reason)[:300],
            )

        try:
            candidates = self.fetch_option_contracts(
                underlying_symbol=normalized_underlying,
                expiration=expiration,
                option_type=normalized_type,
                strike_gte=strike_gte,
                strike_lte=strike_lte,
                limit=1000,
            )
        except (DataNotEntitledError, ProviderUnavailableError, SymbolNotFoundError, HTTPError, URLError, TimeoutError, ValueError, KeyError, OSError) as exc:
            return _unresolved(str(exc), method="provider_reference_unavailable")

        selection_method = "provider_reference_exact_expiration"
        warnings: list[str] = []
        if not candidates:
            try:
                candidates = self.fetch_option_contracts(
                    underlying_symbol=normalized_underlying,
                    expiration=None,
                    option_type=normalized_type,
                    strike_gte=strike_gte,
                    strike_lte=strike_lte,
                    limit=1000,
                )
            except (DataNotEntitledError, ProviderUnavailableError, SymbolNotFoundError, HTTPError, URLError, TimeoutError, ValueError, KeyError, OSError) as exc:
                return _unresolved(str(exc), method="provider_reference_unavailable")
            selection_method = "provider_reference_nearest_expiration"
            warnings.append("Exact expiration was unavailable; selected closest listed expiration from provider reference data.")

        normalized_candidates: list[tuple[date, float, str, dict[str, Any]]] = []
        for item in candidates:
            contract_type = str(item.get("contract_type") or item.get("option_type") or "").lower()
            if contract_type != normalized_type:
                continue
            option_symbol = str(item.get("ticker") or "").upper().strip()
            selected_expiration = _parse_expiration_date(item.get("expiration_date") or item.get("expiry"))
            selected_strike = _finite_float(item.get("strike_price") or item.get("strike"))
            if not option_symbol or selected_expiration is None or selected_strike is None:
                continue
            normalized_candidates.append((selected_expiration, selected_strike, option_symbol, item))

        if not normalized_candidates:
            return _unresolved("No listed option contracts matched requested type/expiration.", method=selection_method)

        def _sort_key(item: tuple[date, float, str, dict[str, Any]]) -> tuple[int, float, float, str]:
            selected_expiration, selected_strike, option_symbol, row = item
            expiration_distance = abs((selected_expiration - expiration).days)
            strike_distance = abs(selected_strike - target)
            liquidity = max(_finite_float(row.get("open_interest")) or 0.0, _finite_float(row.get("volume")) or 0.0)
            return (expiration_distance, strike_distance, -liquidity, option_symbol)

        selected_expiration, selected_strike, option_symbol, _row = sorted(normalized_candidates, key=_sort_key)[0]
        if selected_expiration != expiration and not warnings:
            warnings.append("Selected option contract uses closest available provider expiration.")

        return OptionContractResolution(
            requested_underlying=normalized_underlying,
            underlying_asset_type=asset_type,
            target_expiration=expiration,
            selected_expiration=selected_expiration,
            option_type=normalized_type,
            target_strike=target,
            selected_strike=round(float(selected_strike), 4),
            option_symbol=option_symbol,
            provider=self.name,
            contract_selection_method=selection_method,
            strike_snap_distance=round(abs(float(selected_strike) - target), 4),
            warnings=tuple(warnings),
        )

    def get_provider_health(self, sample_symbol: str = "AAPL") -> MarketProviderHealth:
        return self.health_check(sample_symbol=sample_symbol)

    def health_check(self, sample_symbol: str) -> MarketProviderHealth:
        if not self.is_configured():
            return MarketProviderHealth(
                provider="market_data",
                mode=self.name,
                status="warning",
                details="Polygon API key/config are missing; deterministic fallback remains active.",
                configured=False,
                feed="stocks",
                sample_symbol=sample_symbol,
            )

        started = monotonic()
        try:
            self.get_latest_snapshot(sample_symbol, "1D")
            elapsed = round((monotonic() - started) * 1000, 2)
            return MarketProviderHealth(
                provider="market_data",
                mode=self.name,
                status="ok",
                details="Polygon snapshot probe succeeded.",
                configured=True,
                feed="stocks",
                sample_symbol=sample_symbol,
                latency_ms=elapsed,
                last_success_at=self._last_success_at,
            )
        except (ProviderUnavailableError, HTTPError, URLError, TimeoutError, ValueError, KeyError, OSError) as exc:
            elapsed = round((monotonic() - started) * 1000, 2)
            return MarketProviderHealth(
                provider="market_data",
                mode=self.name,
                status="warning",
                details=f"Polygon probe failed: {exc}",
                configured=True,
                feed="stocks",
                sample_symbol=sample_symbol,
                latency_ms=elapsed,
                last_success_at=self._last_success_at,
            )


class MarketDataService:
    def __init__(self) -> None:
        self._historical_cache = TTLCache()
        self._latest_cache = TTLCache()
        self._option_snapshot_cache = TTLCache()
        self._options_health_cache = TTLCache()
        self._provider = self._build_provider()
        self._fallback_provider = DeterministicFallbackMarketDataProvider()
        self.last_historical_metadata: dict[str, object] | None = None

    def _build_provider(self) -> MarketDataProvider:
        if settings.polygon_enabled:
            return PolygonMarketDataProvider()

        mode = settings.market_data_provider.strip().lower()
        if settings.market_data_enabled and mode == "alpaca":
            return AlpacaMarketDataProvider()
        return DeterministicFallbackMarketDataProvider()

    def _metadata_from_bars(
        self,
        bars: list[Bar],
        *,
        symbol: str,
        timeframe: str,
        provider: str,
        fallback_mode: bool,
    ) -> dict[str, object]:
        first = bars[0] if bars else None
        last = bars[-1] if bars else None
        return {
            "symbol": symbol.upper(),
            "timeframe": timeframe,
            "provider": provider,
            "fallback_mode": fallback_mode,
            "session_policy": first.session_policy if first else None,
            "source_session_policy": first.source_session_policy if first else None,
            "source_timeframe": first.source_timeframe if first else None,
            "output_timeframe": timeframe.upper(),
            "filtered_extended_hours_count": 0 if first and first.session_policy == "regular_hours" else None,
            "rth_bucket_count": len(bars) if first and first.session_policy == "regular_hours" else None,
            "first_bar_timestamp": first.timestamp.isoformat() if first and first.timestamp else None,
            "last_bar_timestamp": last.timestamp.isoformat() if last and last.timestamp else None,
        }

    def _fallback_result(self, symbol: str, timeframe: str, limit: int) -> tuple[list[Bar], str, bool, dict[str, object]]:
        bars = self._fallback_provider.fetch_historical_bars(symbol=symbol, timeframe=timeframe, limit=limit)
        metadata = self._metadata_from_bars(
            bars,
            symbol=symbol,
            timeframe=timeframe,
            provider="fallback",
            fallback_mode=True,
        )
        return bars, "fallback", True, metadata

    def historical_bars(self, symbol: str, timeframe: str = "1D", limit: int = 120) -> tuple[list[Bar], str, bool]:
        cache_key = f"hist::{symbol.upper()}::{timeframe}::{limit}"
        cached = self._historical_cache.get(cache_key)
        if cached is not None:
            bars, source, fallback_mode, metadata = cached
            self.last_historical_metadata = metadata
            return bars, source, fallback_mode

        try:
            bars = self._provider.fetch_historical_bars(symbol=symbol, timeframe=timeframe, limit=limit)
            if not bars:
                result = self._fallback_result(symbol=symbol, timeframe=timeframe, limit=limit)
            else:
                source = self._provider.name if self._provider.name != "fallback" else "fallback"
                provider_metadata = getattr(self._provider, "last_aggregate_request_metadata", None)
                metadata = (
                    dict(provider_metadata)
                    if isinstance(provider_metadata, dict)
                    else self._metadata_from_bars(
                        bars,
                        symbol=symbol,
                        timeframe=timeframe,
                        provider=source,
                        fallback_mode=self._provider.name == "fallback",
                    )
                )
                metadata.setdefault("symbol", symbol.upper())
                metadata.setdefault("timeframe", timeframe)
                metadata.setdefault("provider", source)
                metadata.setdefault("fallback_mode", self._provider.name == "fallback")
                result = (bars, source, self._provider.name == "fallback", metadata)
        except (SymbolNotFoundError, DataNotEntitledError):
            raise
        except Exception:
            result = self._fallback_result(symbol=symbol, timeframe=timeframe, limit=limit)

        self._historical_cache.set(cache_key, result, settings.market_data_historical_cache_ttl_seconds)
        bars, source, fallback_mode, metadata = result
        self.last_historical_metadata = metadata
        return bars, source, fallback_mode

    def latest_snapshot(self, symbol: str, timeframe: str = "1D") -> MarketSnapshot:
        cache_key = f"latest::{symbol.upper()}::{timeframe}"
        cached = self._latest_cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            snapshot = self._provider.fetch_latest_snapshot(symbol=symbol, timeframe=timeframe)
        except (SymbolNotFoundError, DataNotEntitledError):
            raise
        except Exception:
            snapshot = self._fallback_provider.fetch_latest_snapshot(symbol=symbol, timeframe=timeframe)

        self._latest_cache.set(cache_key, snapshot, settings.market_data_latest_cache_ttl_seconds)
        return snapshot

    def options_chain_preview(self, symbol: str, limit: int = 50) -> dict[str, Any] | None:
        """Returns options chain preview dict if provider is Polygon; None otherwise."""
        if not isinstance(self._provider, PolygonMarketDataProvider):
            return None
        return self._provider.fetch_options_chain_preview(symbol=symbol, limit=limit)

    def resolve_option_contract(
        self,
        *,
        underlying_symbol: str,
        expiration: date,
        option_type: str,
        target_strike: float,
    ) -> OptionContractResolution:
        normalized_underlying = option_reference_underlying_ticker(underlying_symbol)
        normalized_type = "call" if str(option_type).strip().lower().startswith("c") else "put"
        target = float(target_strike)
        if not isinstance(self._provider, PolygonMarketDataProvider):
            return OptionContractResolution(
                requested_underlying=normalized_underlying,
                underlying_asset_type=option_underlying_asset_type(normalized_underlying),
                target_expiration=expiration,
                selected_expiration=None,
                option_type=normalized_type,
                target_strike=target,
                selected_strike=None,
                option_symbol=None,
                provider=self._provider.name,
                contract_selection_method="provider_reference_not_supported",
                unavailable_reason="Listed option contract resolution requires Polygon/Massive reference data.",
            )
        if not self._provider.is_configured():
            return OptionContractResolution(
                requested_underlying=normalized_underlying,
                underlying_asset_type=option_underlying_asset_type(normalized_underlying),
                target_expiration=expiration,
                selected_expiration=None,
                option_type=normalized_type,
                target_strike=target,
                selected_strike=None,
                option_symbol=None,
                provider="polygon",
                contract_selection_method="provider_reference_missing_config",
                unavailable_reason="Polygon/Massive API key or base URL is missing.",
            )
        return self._provider.resolve_option_contract(
            underlying_symbol=normalized_underlying,
            expiration=expiration,
            option_type=normalized_type,
            target_strike=target,
        )

    def option_contracts(
        self,
        *,
        underlying_symbol: str,
        expiration: date | None = None,
        option_type: str | None = None,
        strike_gte: float | None = None,
        strike_lte: float | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        normalized_underlying = option_reference_underlying_ticker(underlying_symbol)
        if not isinstance(self._provider, PolygonMarketDataProvider):
            return []
        if not self._provider.is_configured():
            return []
        fetcher = getattr(self._provider, "fetch_option_contracts", None)
        if not callable(fetcher):
            return []
        return fetcher(
            underlying_symbol=normalized_underlying,
            expiration=expiration,
            option_type=option_type,
            strike_gte=strike_gte,
            strike_lte=strike_lte,
            limit=limit,
        )

    def option_contract_snapshot(self, *, underlying_symbol: str, option_symbol: str) -> OptionContractSnapshot:
        normalized_underlying = option_reference_underlying_ticker(underlying_symbol)
        normalized_option = option_symbol.upper().strip()
        cache_key = f"option_snapshot::{normalized_underlying}::{normalized_option}"
        cached = self._option_snapshot_cache.get(cache_key)
        if cached is not None:
            return cached

        if not isinstance(self._provider, PolygonMarketDataProvider):
            snapshot = unavailable_option_contract_snapshot(
                underlying_symbol=normalized_underlying,
                option_symbol=normalized_option,
                provider=self._provider.name,
                missing_fields=["provider_option_snapshot_not_supported"],
                fallback_mode=self._provider.name == "fallback",
            )
        elif not self._provider.is_configured():
            snapshot = unavailable_option_contract_snapshot(
                underlying_symbol=normalized_underlying,
                option_symbol=normalized_option,
                provider="polygon",
                missing_fields=["provider_option_snapshot_missing_config"],
            )
        else:
            try:
                snapshot = self._provider.fetch_option_contract_snapshot(
                    underlying_symbol=normalized_underlying,
                    option_symbol=normalized_option,
                )
            except DataNotEntitledError as exc:
                snapshot = unavailable_option_contract_snapshot(
                    underlying_symbol=normalized_underlying,
                    option_symbol=normalized_option,
                    provider="polygon",
                    endpoint="/v3/snapshot/options/{underlying}/{option}",
                    missing_fields=["provider_option_snapshot_not_entitled"],
                    provider_error=str(exc)[:300],
                )
            except SymbolNotFoundError as exc:
                snapshot = unavailable_option_contract_snapshot(
                    underlying_symbol=normalized_underlying,
                    option_symbol=normalized_option,
                    provider="polygon",
                    endpoint="/v3/snapshot/options/{underlying}/{option}",
                    missing_fields=["provider_option_snapshot_not_found"],
                    provider_error=str(exc)[:300],
                )
            except (ProviderUnavailableError, HTTPError, URLError, TimeoutError, ValueError, KeyError, OSError) as exc:
                snapshot = unavailable_option_contract_snapshot(
                    underlying_symbol=normalized_underlying,
                    option_symbol=normalized_option,
                    provider="polygon",
                    endpoint="/v3/snapshot/options/{underlying}/{option}",
                    missing_fields=["provider_option_snapshot_unavailable"],
                    provider_error=str(exc)[:300],
                )

        self._option_snapshot_cache.set(cache_key, snapshot, settings.market_data_option_snapshot_cache_ttl_seconds)
        return snapshot

    def _options_health_underlyings(self, sample_symbol: str) -> list[str]:
        requested = sample_symbol.upper().strip() or OPTIONS_HEALTH_DEFAULT_UNDERLYINGS[0]
        ordered = [requested, *OPTIONS_HEALTH_DEFAULT_UNDERLYINGS]
        seen: set[str] = set()
        unique: list[str] = []
        for symbol in ordered:
            if symbol and symbol not in seen:
                unique.append(symbol)
                seen.add(symbol)
        return unique

    def _option_health_sample_from_row(
        self,
        *,
        underlying: str,
        item: dict[str, Any],
        selection_method: str,
        today: date,
    ) -> OptionsHealthSample | None:
        expiration = _parse_expiration_date(item.get("expiry") or item.get("expiration_date"))
        strike = _finite_float(item.get("strike") or item.get("strike_price"))
        option_symbol = str(item.get("ticker") or "").upper().strip()
        option_type = str(item.get("option_type") or item.get("contract_type") or "").lower().strip()
        if not option_symbol or expiration is None or strike is None:
            return None
        if expiration < today:
            return None
        open_interest_value = _finite_float(item.get("open_interest"))
        volume_value = _finite_float(item.get("volume"))
        return OptionsHealthSample(
            underlying=underlying,
            option_symbol=option_symbol,
            selection_method=selection_method,
            expiration=expiration,
            strike=round(float(strike), 4),
            option_type="call" if option_type.startswith("call") else "put" if option_type.startswith("put") else option_type or None,
            dte=max(0, (expiration - today).days),
            open_interest=int(open_interest_value) if open_interest_value is not None else None,
            volume=int(volume_value) if volume_value is not None else None,
        )

    def _rank_options_health_samples(
        self,
        samples: list[OptionsHealthSample],
        *,
        underlying_price: float | None,
    ) -> list[OptionsHealthSample]:
        if not samples:
            return []
        preferred = [item for item in samples if item.dte is not None and OPTIONS_HEALTH_MIN_DTE <= item.dte <= OPTIONS_HEALTH_MAX_DTE]
        if preferred:
            candidates = preferred
        else:
            future = [item for item in samples if item.dte is not None and item.dte > 0]
            candidates = future if future else samples

        def _sort_key(item: OptionsHealthSample) -> tuple[int, float, float, int, int, str]:
            dte = item.dte if item.dte is not None else 9999
            dte_distance = abs(dte - 21)
            strike_distance = (
                abs(float(item.strike) - underlying_price)
                if item.strike is not None and underlying_price is not None
                else float("inf")
            )
            right_rank = 0 if item.option_type == "call" else 1
            liquidity = max(item.open_interest or 0, item.volume or 0)
            return (dte_distance, strike_distance, -liquidity, right_rank, dte, item.option_symbol)

        return sorted(candidates, key=_sort_key)[:OPTIONS_HEALTH_MAX_DISCOVERED_CANDIDATES]

    def _discover_options_health_samples(self, sample_symbol: str) -> OptionsHealthDiscovery:
        if not isinstance(self._provider, PolygonMarketDataProvider):
            return OptionsHealthDiscovery(samples=[], error="Options sample discovery requires Polygon/Massive market data.")

        errors: list[str] = []
        today = date.today()
        for underlying in self._options_health_underlyings(sample_symbol):
            asset_type = option_underlying_asset_type(underlying)
            underlying_price: float | None = None
            try:
                underlying_price = _positive_float(self._provider.fetch_latest_snapshot(underlying, "1D").close)
            except (DataNotEntitledError, ProviderUnavailableError, SymbolNotFoundError, HTTPError, URLError, TimeoutError, ValueError, KeyError, OSError) as exc:
                reason = _redact_provider_text(exc)
                if _is_entitlement_error_text(reason):
                    if asset_type == "index":
                        return OptionsHealthDiscovery(
                            samples=[],
                            underlying_error=reason,
                            underlying_entitlement_error=True,
                        )
                    return OptionsHealthDiscovery(samples=[], error=reason, entitlement_error=True)
                if asset_type == "index":
                    return OptionsHealthDiscovery(samples=[], underlying_error=reason)
                errors.append(f"{underlying}: {reason}")
            if asset_type == "index":
                if underlying_price is None:
                    return OptionsHealthDiscovery(samples=[], underlying_error=f"{underlying}: underlying index value unavailable")
                try:
                    strike_window = max(250.0, underlying_price * 0.12)
                    rows = self._provider.fetch_option_contracts(
                        underlying_symbol=underlying,
                        expiration=None,
                        strike_gte=max(0.0, underlying_price - strike_window),
                        strike_lte=underlying_price + strike_window,
                        limit=1000,
                    )
                except (DataNotEntitledError, ProviderUnavailableError, SymbolNotFoundError, HTTPError, URLError, TimeoutError, ValueError, KeyError, OSError) as exc:
                    reason = _redact_provider_text(exc)
                    if _is_entitlement_error_text(reason):
                        return OptionsHealthDiscovery(samples=[], error=reason, entitlement_error=True, underlying_price=underlying_price)
                    return OptionsHealthDiscovery(samples=[], error=reason, underlying_price=underlying_price)

                samples = [
                    sample
                    for item in rows or []
                    if isinstance(item, dict)
                    if (sample := self._option_health_sample_from_row(
                        underlying=underlying,
                        item=item,
                        selection_method="discovered",
                        today=today,
                    )) is not None
                ]
                ranked = self._rank_options_health_samples(samples, underlying_price=underlying_price)
                if ranked:
                    return OptionsHealthDiscovery(samples=ranked, underlying_price=underlying_price)
                errors.append(f"{underlying}: no active 7-45DTE index option contracts returned near the underlying value")
                continue

            try:
                chain = self._provider.fetch_options_chain_preview(symbol=underlying, limit=100) or {}
            except (DataNotEntitledError, ProviderUnavailableError, SymbolNotFoundError, HTTPError, URLError, TimeoutError, ValueError, KeyError, OSError) as exc:
                reason = _redact_provider_text(exc)
                if _is_entitlement_error_text(reason):
                    return OptionsHealthDiscovery(samples=[], error=reason, entitlement_error=True)
                errors.append(f"{underlying}: {reason}")
                continue

            reason = chain.get("reason")
            if reason:
                reason_text = _redact_provider_text(reason)
                if _is_entitlement_error_text(reason_text):
                    return OptionsHealthDiscovery(samples=[], error=reason_text, entitlement_error=True)
                errors.append(f"{underlying}: {reason_text}")
                continue

            samples = [
                sample
                for item in [*(chain.get("calls") or []), *(chain.get("puts") or [])]
                if isinstance(item, dict) and item.get("ticker")
                if (sample := self._option_health_sample_from_row(
                    underlying=underlying,
                    item=item,
                    selection_method="discovered",
                    today=today,
                )) is not None
            ]
            if not samples:
                errors.append(f"{underlying}: no active option contracts returned")
                continue

            ranked = self._rank_options_health_samples(samples, underlying_price=underlying_price)
            return OptionsHealthDiscovery(samples=ranked, underlying_price=underlying_price)

        return OptionsHealthDiscovery(
            samples=[],
            error="; ".join(errors)[:300] if errors else "No active option contracts returned for sample underlyings.",
        )

    def _static_options_health_sample(self) -> OptionsHealthSample:
        return OptionsHealthSample(
            underlying=OPTIONS_HEALTH_STATIC_SAMPLE_UNDERLYING,
            option_symbol=OPTIONS_HEALTH_STATIC_SAMPLE_OPTION,
            selection_method="static_sample",
        )

    def _option_health_attempt_payload(
        self,
        *,
        sample: OptionsHealthSample,
        snapshot: OptionContractSnapshot | None = None,
        error: object | None = None,
        underlying_index_value_exists: bool | None = None,
    ) -> dict[str, object]:
        has_bid_ask = bool(snapshot and snapshot.bid is not None and snapshot.ask is not None)
        has_last_trade = bool(snapshot and snapshot.latest_trade_price is not None)
        has_prior_close = bool(snapshot and snapshot.prior_close is not None)
        if error is not None:
            sanitized = _redact_provider_text(error)
            result = "error_not_entitled" if _is_entitlement_error_text(sanitized) else "error"
        elif snapshot is None:
            sanitized = None
            result = "no_mark"
        elif snapshot.mark_method == "prior_close_fallback":
            sanitized = None
            result = "prior_close"
        elif snapshot.mark_method in {"quote_mid", "last_trade"}:
            sanitized = None
            result = snapshot.mark_method
        else:
            sanitized = snapshot.provider_error
            result = "error_not_entitled" if _is_entitlement_error_text(snapshot.provider_error) else "no_mark"
        payload: dict[str, object] = {
            "option_symbol": sample.option_symbol,
            "expiration": sample.expiration.isoformat() if sample.expiration is not None else None,
            "strike": sample.strike,
            "option_type": sample.option_type,
            "dte": sample.dte,
            "result": result,
            "mark_method": snapshot.mark_method if snapshot else "unavailable",
            "stale": bool(snapshot.stale) if snapshot else False,
            "has_bid_ask": has_bid_ask,
            "has_last_trade": has_last_trade,
            "has_prior_close": has_prior_close,
            "underlying_index_value_exists": underlying_index_value_exists,
        }
        if sanitized:
            payload["error"] = _redact_provider_text(sanitized)
        return payload

    def _options_health_result(
        self,
        *,
        sample_symbol: str,
        probe_state: str,
        details: str,
        elapsed_ms: float | None,
        sample: OptionsHealthSample | None = None,
        snapshot: OptionContractSnapshot | None = None,
        candidate_attempts: list[dict[str, object]] | None = None,
        underlying_price: float | None = None,
        entitlement_status: str = "unknown",
        sample_selection_method: str | None = None,
    ) -> dict[str, object]:
        return {
            "probe_state": probe_state,
            "probe_status": probe_state,
            "details": _redact_provider_text(details),
            "sample_underlying": sample.underlying if sample else sample_symbol.upper(),
            "sample_option_symbol": sample.option_symbol if sample else None,
            "sample_selection_method": sample.selection_method if sample else (sample_selection_method or "unavailable"),
            "sample_mark_method": snapshot.mark_method if snapshot else "unavailable",
            "sample_expiration": sample.expiration.isoformat() if sample and sample.expiration is not None else None,
            "sample_strike": sample.strike if sample else None,
            "sample_option_type": sample.option_type if sample else None,
            "sample_dte": sample.dte if sample else None,
            "sample_has_bid_ask": bool(snapshot and snapshot.bid is not None and snapshot.ask is not None),
            "sample_has_last_trade": bool(snapshot and snapshot.latest_trade_price is not None),
            "sample_has_prior_close": bool(snapshot and snapshot.prior_close is not None),
            "underlying_index_value_exists": underlying_price is not None if option_underlying_asset_type(sample_symbol) == "index" else None,
            "sample_stale": bool(snapshot.stale) if snapshot else False,
            "entitlement_status": entitlement_status,
            "candidate_attempts": candidate_attempts or [],
            "latency_ms": elapsed_ms,
            "last_success_at": self._provider._last_success_at.isoformat() if isinstance(self._provider, PolygonMarketDataProvider) and self._provider._last_success_at else None,
        }

    def options_data_health(self, sample_symbol: str = "SPY") -> dict[str, object]:
        sample_symbol = sample_symbol.upper().strip() or "SPY"
        is_index_probe = option_underlying_asset_type(sample_symbol) == "index"
        cached = self._options_health_cache.get(f"options_health::{sample_symbol}")
        if cached is not None:
            return cached

        if not settings.polygon_enabled:
            result = self._options_health_result(
                sample_symbol=sample_symbol,
                probe_state="skipped",
                details="Options data readiness is disabled because Polygon market data is not selected.",
                elapsed_ms=None,
            )
            self._options_health_cache.set(f"options_health::{sample_symbol}", result, settings.market_data_option_snapshot_cache_ttl_seconds)
            return result
        if not isinstance(self._provider, PolygonMarketDataProvider) or not self._provider.is_configured():
            result = self._options_health_result(
                sample_symbol=sample_symbol,
                probe_state="unavailable",
                details="Options data readiness requires Polygon API key and base URL configuration.",
                elapsed_ms=None,
            )
            self._options_health_cache.set(f"options_health::{sample_symbol}", result, settings.market_data_option_snapshot_cache_ttl_seconds)
            return result

        started = monotonic()
        try:
            discovery = self._discover_options_health_samples(sample_symbol)
            elapsed = round((monotonic() - started) * 1000, 2)
            if discovery.underlying_error:
                result = self._options_health_result(
                    sample_symbol=sample_symbol,
                    probe_state="failed_underlying_index_data",
                    details=(
                        "SPX underlying index snapshot unavailable. "
                        + (
                            "Index data entitlement required for SPX/index underlying snapshots."
                            if discovery.underlying_entitlement_error
                            else discovery.underlying_error
                        )
                    ),
                    elapsed_ms=elapsed,
                    underlying_price=discovery.underlying_price,
                    entitlement_status="not_entitled" if discovery.underlying_entitlement_error else "unknown",
                )
                self._options_health_cache.set(f"options_health::{sample_symbol}", result, settings.market_data_option_snapshot_cache_ttl_seconds)
                return result
            if discovery.entitlement_error:
                elapsed = round((monotonic() - started) * 1000, 2)
                result = self._options_health_result(
                    sample_symbol=sample_symbol,
                    probe_state="failed_not_entitled",
                    details="Options sample discovery is not entitled to option reference data.",
                    elapsed_ms=elapsed,
                    underlying_price=discovery.underlying_price,
                    entitlement_status="not_entitled",
                )
                self._options_health_cache.set(f"options_health::{sample_symbol}", result, settings.market_data_option_snapshot_cache_ttl_seconds)
                return result
            samples = discovery.samples
            if not samples and not is_index_probe:
                samples = [self._static_options_health_sample()]
            if not samples:
                elapsed = round((monotonic() - started) * 1000, 2)
                result = self._options_health_result(
                    sample_symbol=sample_symbol,
                    probe_state="degraded",
                    details=discovery.error or "SPX index options discovery did not return an active non-expired sample contract.",
                    elapsed_ms=elapsed,
                    underlying_price=discovery.underlying_price,
                    entitlement_status="unknown",
                )
                self._options_health_cache.set(f"options_health::{sample_symbol}", result, settings.market_data_option_snapshot_cache_ttl_seconds)
                return result

            last_snapshot: OptionContractSnapshot | None = None
            last_sample: OptionsHealthSample | None = None
            warn_snapshot: OptionContractSnapshot | None = None
            warn_sample: OptionsHealthSample | None = None
            candidate_attempts: list[dict[str, object]] = []
            underlying_exists = discovery.underlying_price is not None if is_index_probe else None
            for sample in samples:
                last_sample = sample
                try:
                    snapshot = self.option_contract_snapshot(
                        underlying_symbol=sample.underlying,
                        option_symbol=sample.option_symbol,
                    )
                except DataNotEntitledError as exc:
                    candidate_attempts.append(
                        self._option_health_attempt_payload(
                            sample=sample,
                            error=exc,
                            underlying_index_value_exists=underlying_exists,
                        )
                    )
                    elapsed = round((monotonic() - started) * 1000, 2)
                    result = self._options_health_result(
                        sample_symbol=sample_symbol,
                        probe_state="failed_not_entitled",
                        details="Options snapshot probe is not entitled to sampled option data.",
                        elapsed_ms=elapsed,
                        sample=sample,
                        candidate_attempts=candidate_attempts,
                        underlying_price=discovery.underlying_price,
                        entitlement_status="not_entitled",
                    )
                    self._options_health_cache.set(f"options_health::{sample_symbol}", result, settings.market_data_option_snapshot_cache_ttl_seconds)
                    return result
                except (ProviderUnavailableError, SymbolNotFoundError, HTTPError, URLError, TimeoutError, ValueError, KeyError, OSError) as exc:
                    candidate_attempts.append(
                        self._option_health_attempt_payload(
                            sample=sample,
                            error=exc,
                            underlying_index_value_exists=underlying_exists,
                        )
                    )
                    continue
                last_snapshot = snapshot
                candidate_attempts.append(
                    self._option_health_attempt_payload(
                        sample=sample,
                        snapshot=snapshot,
                        underlying_index_value_exists=underlying_exists,
                    )
                )
                if snapshot.provider_error and _is_entitlement_error_text(snapshot.provider_error):
                    elapsed = round((monotonic() - started) * 1000, 2)
                    result = self._options_health_result(
                        sample_symbol=sample_symbol,
                        probe_state="failed_not_entitled",
                        details="Options snapshot probe is not entitled to sampled option data.",
                        elapsed_ms=elapsed,
                        sample=sample,
                        snapshot=snapshot,
                        candidate_attempts=candidate_attempts,
                        underlying_price=discovery.underlying_price,
                        entitlement_status="not_entitled",
                    )
                    self._options_health_cache.set(f"options_health::{sample_symbol}", result, settings.market_data_option_snapshot_cache_ttl_seconds)
                    return result
                if snapshot.mark_method in {"quote_mid", "last_trade"} and not snapshot.stale:
                    elapsed = round((monotonic() - started) * 1000, 2)
                    result = self._options_health_result(
                        sample_symbol=sample_symbol,
                        probe_state="ok",
                        details=f"Polygon options snapshot probe succeeded using {snapshot.mark_method}.",
                        elapsed_ms=elapsed,
                        sample=sample,
                        snapshot=snapshot,
                        candidate_attempts=candidate_attempts,
                        underlying_price=discovery.underlying_price,
                        entitlement_status="entitled",
                    )
                    self._options_health_cache.set(f"options_health::{sample_symbol}", result, settings.market_data_option_snapshot_cache_ttl_seconds)
                    return result
                if snapshot.mark_method == "prior_close_fallback" and warn_snapshot is None:
                    warn_snapshot = snapshot
                    warn_sample = sample
                    continue

            if warn_snapshot is not None and warn_sample is not None:
                elapsed = round((monotonic() - started) * 1000, 2)
                result = self._options_health_result(
                    sample_symbol=sample_symbol,
                    probe_state="warn",
                    details="Access verified; fresh quote/trade mark was not available for sampled contracts; prior_close_fallback is stale context only.",
                    elapsed_ms=elapsed,
                    sample=warn_sample,
                    snapshot=warn_snapshot,
                    candidate_attempts=candidate_attempts,
                    underlying_price=discovery.underlying_price,
                    entitlement_status="entitled",
                )
                self._options_health_cache.set(f"options_health::{sample_symbol}", result, settings.market_data_option_snapshot_cache_ttl_seconds)
                return result

            elapsed = round((monotonic() - started) * 1000, 2)
            detail = (
                "SPX index options discovered, but no fresh usable mark was returned for sampled contracts."
                if is_index_probe
                else "Options contracts discovered, but no fresh usable mark was returned for sampled contracts."
            )
            if last_snapshot and last_snapshot.provider_error and _is_entitlement_error_text(last_snapshot.provider_error):
                result = self._options_health_result(
                    sample_symbol=sample_symbol,
                    probe_state="failed_not_entitled",
                    details="Options snapshot probe is not entitled to sampled option data.",
                    elapsed_ms=elapsed,
                    sample=last_sample,
                    snapshot=last_snapshot,
                    candidate_attempts=candidate_attempts,
                    underlying_price=discovery.underlying_price,
                    entitlement_status="not_entitled",
                )
            else:
                result = self._options_health_result(
                    sample_symbol=sample_symbol,
                    probe_state="degraded",
                    details=detail,
                    elapsed_ms=elapsed,
                    sample=last_sample,
                    snapshot=last_snapshot,
                    candidate_attempts=candidate_attempts,
                    underlying_price=discovery.underlying_price,
                    entitlement_status="entitled" if candidate_attempts else "unknown",
                )
        except (DataNotEntitledError, ProviderUnavailableError, SymbolNotFoundError, HTTPError, URLError, TimeoutError, ValueError, KeyError, OSError) as exc:
            elapsed = round((monotonic() - started) * 1000, 2)
            state = "failed_not_entitled" if _is_entitlement_error_text(exc) else "degraded"
            result = self._options_health_result(
                sample_symbol=sample_symbol,
                probe_state=state,
                details=_redact_provider_text(exc),
                elapsed_ms=elapsed,
                entitlement_status="not_entitled" if state == "failed_not_entitled" else "unknown",
            )
        self._options_health_cache.set(f"options_health::{sample_symbol}", result, settings.market_data_option_snapshot_cache_ttl_seconds)
        return result

    def provider_health(self, sample_symbol: str = "AAPL") -> MarketProviderHealth:
        health = self._provider.health_check(sample_symbol=sample_symbol)
        if health.status == "ok":
            return health
        if self._provider.name != "fallback":
            fallback = self._fallback_provider.health_check(sample_symbol=sample_symbol)
            fallback.details = f"{health.details} Fallback remains available and active for chart/snapshot reads."
            return MarketProviderHealth(
                provider=health.provider,
                mode=health.mode,
                status=health.status,
                details=fallback.details,
                configured=health.configured,
                feed=health.feed,
                sample_symbol=health.sample_symbol,
                latency_ms=health.latency_ms,
                last_success_at=health.last_success_at,
            )
        return health
