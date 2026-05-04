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
OPTION_INDEX_UNDERLYINGS = {"SPX", "NDX", "RUT", "VIX"}


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
    return "index" if normalized in OPTION_INDEX_UNDERLYINGS else "equity"


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
        except DataNotEntitledError as exc:
            return {"underlying": symbol, "reason": f"Options endpoint not entitled: {exc}", "calls": None, "puts": None}
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
        payload = self._request_json("/v3/reference/options/contracts", query)
        return list(payload.get("results") or [])

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

    def _discover_options_health_samples(self, sample_symbol: str) -> tuple[list[OptionsHealthSample], str | None, bool]:
        if not isinstance(self._provider, PolygonMarketDataProvider):
            return [], "Options sample discovery requires Polygon/Massive market data.", False

        errors: list[str] = []
        today = date.today()
        for underlying in self._options_health_underlyings(sample_symbol):
            try:
                chain = self._provider.fetch_options_chain_preview(symbol=underlying, limit=100) or {}
            except (DataNotEntitledError, ProviderUnavailableError, SymbolNotFoundError, HTTPError, URLError, TimeoutError, ValueError, KeyError, OSError) as exc:
                reason = str(exc)[:300]
                if _is_entitlement_error_text(reason):
                    return [], reason, True
                errors.append(f"{underlying}: {reason}")
                continue

            reason = chain.get("reason")
            if reason:
                reason_text = str(reason)[:300]
                if _is_entitlement_error_text(reason_text):
                    return [], reason_text, True
                errors.append(f"{underlying}: {reason_text}")
                continue

            raw_candidates = [
                item
                for item in [*(chain.get("calls") or []), *(chain.get("puts") or [])]
                if isinstance(item, dict) and item.get("ticker")
            ]
            candidates: list[dict[str, Any]] = []
            for item in raw_candidates:
                expiration = _parse_expiration_date(item.get("expiry") or item.get("expiration_date"))
                if expiration is not None and expiration < today:
                    continue
                candidates.append(item)
            if not candidates:
                errors.append(f"{underlying}: no active option contracts returned")
                continue

            underlying_price: float | None = None
            try:
                underlying_price = _positive_float(self._provider.fetch_latest_snapshot(underlying, "1D").close)
            except (DataNotEntitledError, ProviderUnavailableError, SymbolNotFoundError, HTTPError, URLError, TimeoutError, ValueError, KeyError, OSError):
                underlying_price = None

            def _sort_key(item: dict[str, Any]) -> tuple[date, float, int, float]:
                expiration = _parse_expiration_date(item.get("expiry") or item.get("expiration_date")) or date.max
                strike = _finite_float(item.get("strike") or item.get("strike_price"))
                strike_distance = abs(strike - underlying_price) if strike is not None and underlying_price is not None else float("inf")
                option_type = str(item.get("option_type") or item.get("contract_type") or "").lower()
                right_rank = 0 if option_type.startswith("call") else 1
                liquidity = max(_finite_float(item.get("open_interest")) or 0.0, _finite_float(item.get("volume")) or 0.0)
                return (expiration, strike_distance, right_rank, -liquidity)

            ordered = sorted(candidates, key=_sort_key)
            return [
                OptionsHealthSample(
                    underlying=underlying,
                    option_symbol=str(item["ticker"]).upper().strip(),
                    selection_method="discovered",
                )
                for item in ordered[:OPTIONS_HEALTH_MAX_DISCOVERED_CANDIDATES]
            ], None, False

        return [], "; ".join(errors)[:300] if errors else "No active option contracts returned for sample underlyings.", False

    def _static_options_health_sample(self) -> OptionsHealthSample:
        return OptionsHealthSample(
            underlying=OPTIONS_HEALTH_STATIC_SAMPLE_UNDERLYING,
            option_symbol=OPTIONS_HEALTH_STATIC_SAMPLE_OPTION,
            selection_method="static_sample",
        )

    def options_data_health(self, sample_symbol: str = "SPY") -> dict[str, object]:
        cached = self._options_health_cache.get(f"options_health::{sample_symbol.upper()}")
        if cached is not None:
            return cached

        if not settings.polygon_enabled:
            result = {
                "probe_state": "skipped",
                "probe_status": "skipped",
                "details": "Options data readiness is disabled because Polygon market data is not selected.",
                "sample_underlying": sample_symbol.upper(),
                "sample_option_symbol": None,
                "sample_selection_method": "unavailable",
                "sample_mark_method": "unavailable",
                "latency_ms": None,
                "last_success_at": None,
            }
            self._options_health_cache.set(f"options_health::{sample_symbol.upper()}", result, settings.market_data_option_snapshot_cache_ttl_seconds)
            return result
        if not isinstance(self._provider, PolygonMarketDataProvider) or not self._provider.is_configured():
            result = {
                "probe_state": "unavailable",
                "probe_status": "unavailable",
                "details": "Options data readiness requires Polygon API key and base URL configuration.",
                "sample_underlying": sample_symbol.upper(),
                "sample_option_symbol": None,
                "sample_selection_method": "unavailable",
                "sample_mark_method": "unavailable",
                "latency_ms": None,
                "last_success_at": None,
            }
            self._options_health_cache.set(f"options_health::{sample_symbol.upper()}", result, settings.market_data_option_snapshot_cache_ttl_seconds)
            return result

        started = monotonic()
        try:
            samples, discovery_error, discovery_entitlement = self._discover_options_health_samples(sample_symbol)
            if discovery_entitlement:
                elapsed = round((monotonic() - started) * 1000, 2)
                result = {
                    "probe_state": "failed",
                    "probe_status": "failed",
                    "details": "Options sample discovery is not entitled to option reference data.",
                    "sample_underlying": sample_symbol.upper(),
                    "sample_option_symbol": None,
                    "sample_selection_method": "unavailable",
                    "sample_mark_method": "unavailable",
                    "latency_ms": elapsed,
                    "last_success_at": self._provider._last_success_at.isoformat() if self._provider._last_success_at else None,
                }
                self._options_health_cache.set(f"options_health::{sample_symbol.upper()}", result, settings.market_data_option_snapshot_cache_ttl_seconds)
                return result
            if not samples:
                samples = [self._static_options_health_sample()]

            last_snapshot: OptionContractSnapshot | None = None
            for sample in samples:
                snapshot = self.option_contract_snapshot(
                    underlying_symbol=sample.underlying,
                    option_symbol=sample.option_symbol,
                )
                last_snapshot = snapshot
                if snapshot.mark_method == "unavailable":
                    continue
                elapsed = round((monotonic() - started) * 1000, 2)
                result = {
                    "probe_state": "ok",
                    "probe_status": "ok",
                    "details": (
                        "Access verified; fresh quote/trade mark not available for sample; using prior_close_fallback."
                        if snapshot.mark_method == "prior_close_fallback"
                        else f"Polygon options snapshot probe succeeded using {snapshot.mark_method}."
                    ),
                    "sample_underlying": sample.underlying,
                    "sample_option_symbol": sample.option_symbol,
                    "sample_selection_method": sample.selection_method,
                    "sample_mark_method": snapshot.mark_method,
                    "latency_ms": elapsed,
                    "last_success_at": self._provider._last_success_at.isoformat() if self._provider._last_success_at else None,
                }
                self._options_health_cache.set(f"options_health::{sample_symbol.upper()}", result, settings.market_data_option_snapshot_cache_ttl_seconds)
                return result

            elapsed = round((monotonic() - started) * 1000, 2)
            failed_sample = samples[-1]
            result = {
                "probe_state": "failed",
                "probe_status": "failed",
                "details": (
                    last_snapshot.provider_error
                    if last_snapshot and last_snapshot.provider_error
                    else "Options snapshot probe did not return a usable mark."
                ),
                "sample_underlying": failed_sample.underlying,
                "sample_option_symbol": failed_sample.option_symbol,
                "sample_selection_method": failed_sample.selection_method,
                "sample_mark_method": last_snapshot.mark_method if last_snapshot else "unavailable",
                "latency_ms": elapsed,
                "last_success_at": self._provider._last_success_at.isoformat() if self._provider._last_success_at else None,
            }
        except (DataNotEntitledError, ProviderUnavailableError, SymbolNotFoundError, HTTPError, URLError, TimeoutError, ValueError, KeyError, OSError) as exc:
            elapsed = round((monotonic() - started) * 1000, 2)
            result = {
                "probe_state": "failed",
                "probe_status": "failed",
                "details": str(exc)[:300],
                "sample_underlying": sample_symbol.upper(),
                "sample_option_symbol": None,
                "sample_selection_method": "unavailable",
                "sample_mark_method": "unavailable",
                "latency_ms": elapsed,
                "last_success_at": self._provider._last_success_at.isoformat() if isinstance(self._provider, PolygonMarketDataProvider) and self._provider._last_success_at else None,
            }
        self._options_health_cache.set(f"options_health::{sample_symbol.upper()}", result, settings.market_data_option_snapshot_cache_ttl_seconds)
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
