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
                    "underlying_ticker": symbol.upper(),
                    "limit": str(limit),
                    "sort": "expiration_date",
                    "order": "asc",
                    "expired": "false",
                },
            )
        except SymbolNotFoundError:
            return {"underlying": symbol, "reason": f"No options contracts found for {symbol}", "calls": None, "puts": None}
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
                "strike": r.get("strike_price"),
                "expiry": r.get("expiration_date"),
                "last_price": None,
                "volume": None,
            }

        calls = [_row(r) for r in expiry_contracts if r.get("contract_type") == "call"][:5]
        puts = [_row(r) for r in expiry_contracts if r.get("contract_type") == "put"][:5]

        return {
            "underlying": symbol,
            "expiry": nearest_expiry,
            "calls": calls if calls else None,
            "puts": puts if puts else None,
            "data_as_of": today,
            "source": "polygon_options_basic",
        }

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
