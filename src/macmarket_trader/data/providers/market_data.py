"""Market-data provider abstraction with Polygon + Alpaca scaffolds + deterministic fallback."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
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


def normalize_polygon_ticker(symbol: str) -> str:
    """Map known index symbols to their Polygon I: prefixed form; pass all others through unchanged."""
    upper = symbol.upper()
    if upper in INDEX_SYMBOLS:
        return f"I:{upper}"
    return upper


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
        del symbol, timeframe
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
        return Bar(
            date=ts.date(),
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

    def _map_polygon_range(self, timeframe: str, limit: int) -> tuple[int, str, str, str]:
        tf = timeframe.upper()
        now = datetime.now(tz=UTC)
        if tf == "1H":
            # add 24h buffer to account for market hours gaps
            start = now - timedelta(hours=max(limit, 1) + 24)
            return 1, "hour", str(int(start.timestamp() * 1000)), str(int(now.timestamp() * 1000))
        if tf == "4H":
            # 4H bars: each bar = 4 calendar hours; buffer 2 bars
            start = now - timedelta(hours=max(limit, 1) * 4 + 8)
            return 4, "hour", str(int(start.timestamp() * 1000)), str(int(now.timestamp() * 1000))
        if tf == "1M":
            start = now - timedelta(minutes=max(limit, 1) + 5)
            return 1, "minute", str(int(start.timestamp() * 1000)), str(int(now.timestamp() * 1000))
        start = (now - timedelta(days=max(limit, 1) + 5)).date().isoformat()
        return 1, "day", start, now.date().isoformat()

    def _normalize_polygon_bar(self, bar: dict[str, Any]) -> Bar:
        ts_ms = int(bar.get("t") or 0)
        ts = datetime.fromtimestamp(ts_ms / 1000, tz=UTC)
        market_date = ts.astimezone(ZoneInfo("America/New_York")).date()
        return Bar(
            date=market_date,
            open=float(bar["o"]),
            high=float(bar["h"]),
            low=float(bar["l"]),
            close=float(bar["c"]),
            volume=int(bar.get("v") or 0),
            rel_volume=None,
        )

    def get_historical_bars(self, symbol: str, timeframe: str, limit: int = 120) -> list[Bar]:
        ticker = normalize_polygon_ticker(symbol)
        multiplier, timespan, from_ts, to_ts = self._map_polygon_range(timeframe=timeframe, limit=limit)
        payload = self._request_json(
            f"/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from_ts}/{to_ts}",
            {"adjusted": "true", "sort": "asc", "limit": str(limit)},
        )
        results: list[dict[str, Any]] = list(payload.get("results") or [])
        # Follow Polygon pagination (next_url) until we have enough bars (max 3 extra pages).
        page = 0
        while "next_url" in payload and len(results) < limit and page < 3:
            page += 1
            next_url = str(payload["next_url"])
            sep = "&" if "?" in next_url else "?"
            payload = self._fetch_url(f"{next_url}{sep}apiKey={self.api_key}")
            results.extend(payload.get("results") or [])
        if not results:
            raise SymbolNotFoundError(f"No bar data returned for symbol {symbol}")
        return [self._normalize_polygon_bar(item) for item in results][-limit:]

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

    def _build_provider(self) -> MarketDataProvider:
        if settings.polygon_enabled:
            return PolygonMarketDataProvider()

        mode = settings.market_data_provider.strip().lower()
        if settings.market_data_enabled and mode == "alpaca":
            return AlpacaMarketDataProvider()
        return DeterministicFallbackMarketDataProvider()

    def _fallback_result(self, symbol: str, timeframe: str, limit: int) -> tuple[list[Bar], str, bool]:
        bars = self._fallback_provider.fetch_historical_bars(symbol=symbol, timeframe=timeframe, limit=limit)
        return bars, "fallback", True

    def historical_bars(self, symbol: str, timeframe: str = "1D", limit: int = 120) -> tuple[list[Bar], str, bool]:
        cache_key = f"hist::{symbol.upper()}::{timeframe}::{limit}"
        cached = self._historical_cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            bars = self._provider.fetch_historical_bars(symbol=symbol, timeframe=timeframe, limit=limit)
            if not bars:
                result = self._fallback_result(symbol=symbol, timeframe=timeframe, limit=limit)
            else:
                source = self._provider.name if self._provider.name != "fallback" else "fallback"
                result = (bars, source, self._provider.name == "fallback")
        except (SymbolNotFoundError, DataNotEntitledError):
            raise
        except Exception:
            result = self._fallback_result(symbol=symbol, timeframe=timeframe, limit=limit)

        self._historical_cache.set(cache_key, result, settings.market_data_historical_cache_ttl_seconds)
        return result

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
