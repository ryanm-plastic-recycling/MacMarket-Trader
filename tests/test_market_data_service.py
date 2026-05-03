from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from macmarket_trader.api.main import app
from macmarket_trader.api.routes import admin as admin_routes
from macmarket_trader.config import settings
from macmarket_trader.data.providers.market_data import (
    AlpacaMarketDataProvider,
    DataNotEntitledError,
    DeterministicFallbackMarketDataProvider,
    INDEX_SYMBOLS,
    MarketDataService,
    MarketProviderHealth,
    MarketSnapshot,
    OptionContractSnapshot,
    OPTIONS_HEALTH_STATIC_SAMPLE_OPTION,
    OPTIONS_HEALTH_STATIC_SAMPLE_UNDERLYING,
    PolygonMarketDataProvider,
    ProviderUnavailableError,
    SymbolNotFoundError,
    build_polygon_option_ticker,
    normalize_polygon_ticker,
)


def test_market_data_fallback_when_polygon_disabled(monkeypatch) -> None:
    monkeypatch.setattr(settings, "polygon_enabled", False)
    monkeypatch.setattr(settings, "market_data_provider", "alpaca")
    monkeypatch.setattr(settings, "market_data_enabled", False)

    service = MarketDataService()
    bars, source, fallback_mode = service.historical_bars("AAPL", "1D", 40)

    assert len(bars) == 40
    assert source == "fallback"
    assert fallback_mode is True


def test_polygon_historical_bars_normalization(monkeypatch) -> None:
    monkeypatch.setattr(settings, "polygon_api_key", "polygon-key")
    provider = PolygonMarketDataProvider()

    def fake_request_json(path: str, query: dict[str, str]) -> dict[str, object]:
        assert path.startswith("/v2/aggs/ticker/AAPL/range/1/day/")
        assert query["limit"] == "2"
        assert query["sort"] == "asc"
        return {
            "results": [
                {"t": 1775088000000, "o": 190.1, "h": 192.0, "l": 189.4, "c": 191.2, "v": 123456},
                {"t": 1775174400000, "o": 191.2, "h": 193.5, "l": 190.7, "c": 193.0, "v": 150000},
            ]
        }

    monkeypatch.setattr(provider, "_request_json", fake_request_json)
    bars = provider.fetch_historical_bars(symbol="AAPL", timeframe="1D", limit=2)

    assert len(bars) == 2
    assert bars[0].date.isoformat() == "2026-04-01"
    assert bars[0].timestamp == datetime.fromtimestamp(1775088000000 / 1000, tz=UTC)
    assert bars[0].open == 190.1
    assert bars[1].close == 193.0
    assert bars[1].volume == 150000


def test_polygon_intraday_bars_preserve_timestamp_and_return_latest_ascending(monkeypatch) -> None:
    monkeypatch.setattr(settings, "polygon_api_key", "polygon-key")
    provider = PolygonMarketDataProvider()
    stamps = [
        datetime(2026, 4, 1, 12, 30, tzinfo=UTC),  # premarket, excluded
        datetime(2026, 4, 1, 13, 30, tzinfo=UTC),
        datetime(2026, 4, 1, 14, 0, tzinfo=UTC),
        datetime(2026, 4, 1, 14, 30, tzinfo=UTC),
        datetime(2026, 4, 1, 15, 0, tzinfo=UTC),
        datetime(2026, 4, 1, 20, 0, tzinfo=UTC),  # 16:00 ET, excluded
    ]

    def fake_request_json(path: str, query: dict[str, str]) -> dict[str, object]:
        assert path.startswith("/v2/aggs/ticker/GOOG/range/30/minute/")
        assert query["sort"] == "desc"
        assert query["limit"] == "50000"
        return {
            "results": [
                {"t": int(stamp.timestamp() * 1000), "o": 100 + idx, "h": 101 + idx, "l": 99 + idx, "c": 100.5 + idx, "v": 1000 + idx}
                for idx, stamp in enumerate(stamps)
            ]
        }

    monkeypatch.setattr(provider, "_request_json", fake_request_json)

    bars = provider.fetch_historical_bars(symbol="GOOG", timeframe="1H", limit=2)

    assert [bar.timestamp for bar in bars] == [datetime(2026, 4, 1, 13, 30, tzinfo=UTC), datetime(2026, 4, 1, 14, 30, tzinfo=UTC)]
    assert [bar.close for bar in bars] == [102.5, 104.5]
    assert [bar.volume for bar in bars] == [2003, 2007]
    assert all(bar.session_policy == "regular_hours" for bar in bars)
    assert all(bar.date.isoformat() == "2026-04-01" for bar in bars)
    assert provider.last_aggregate_request_metadata is not None
    assert provider.last_aggregate_request_metadata["sort"] == "desc"
    assert provider.last_aggregate_request_metadata["limit"] == 50_000
    assert provider.last_aggregate_request_metadata["source_timeframe"] == "30M"
    assert provider.last_aggregate_request_metadata["session_policy"] == "regular_hours"
    assert provider.last_aggregate_request_metadata["filtered_extended_hours_count"] == 2
    assert provider.last_aggregate_request_metadata["returned_last_timestamp"] == "2026-04-01T14:30:00+00:00"


def test_polygon_intraday_wide_range_returns_latest_not_oldest(monkeypatch) -> None:
    monkeypatch.setattr(settings, "polygon_api_key", "polygon-key")
    provider = PolygonMarketDataProvider()
    old_stamps = [
        datetime(2025, 10, 13, 14, 0, tzinfo=UTC),
        datetime(2025, 10, 13, 15, 0, tzinfo=UTC),
    ]
    latest_stamps = [
        datetime(2026, 4, 30, 13, 30, tzinfo=UTC),
        datetime(2026, 4, 30, 14, 0, tzinfo=UTC),
        datetime(2026, 4, 30, 14, 30, tzinfo=UTC),
        datetime(2026, 4, 30, 15, 0, tzinfo=UTC),
        datetime(2026, 4, 30, 15, 30, tzinfo=UTC),
        datetime(2026, 4, 30, 16, 0, tzinfo=UTC),
    ]
    response_stamps_desc = list(reversed(latest_stamps)) + list(reversed(old_stamps))

    def fake_request_json(path: str, query: dict[str, str]) -> dict[str, object]:
        assert path.startswith("/v2/aggs/ticker/AAPL/range/30/minute/")
        assert query["sort"] == "desc"
        assert query["limit"] == "50000"
        return {
            "results": [
                {"t": int(stamp.timestamp() * 1000), "o": 100 + idx, "h": 101 + idx, "l": 99 + idx, "c": 100.5 + idx, "v": 1000 + idx}
                for idx, stamp in enumerate(response_stamps_desc)
            ]
        }

    monkeypatch.setattr(provider, "_request_json", fake_request_json)

    bars = provider.fetch_historical_bars(symbol="AAPL", timeframe="1H", limit=3)

    assert [bar.timestamp for bar in bars] == [
        datetime(2026, 4, 30, 13, 30, tzinfo=UTC),
        datetime(2026, 4, 30, 14, 30, tzinfo=UTC),
        datetime(2026, 4, 30, 15, 30, tzinfo=UTC),
    ]
    assert len({bar.timestamp for bar in bars}) == len(bars)
    assert provider.last_aggregate_request_metadata is not None
    assert provider.last_aggregate_request_metadata["response_first_timestamp"] == "2025-10-13T14:00:00+00:00"
    assert provider.last_aggregate_request_metadata["returned_first_timestamp"] == "2026-04-30T13:30:00+00:00"
    assert provider.last_aggregate_request_metadata["returned_last_timestamp"] == "2026-04-30T15:30:00+00:00"


def test_polygon_4h_intraday_returns_latest_ascending(monkeypatch) -> None:
    monkeypatch.setattr(settings, "polygon_api_key", "polygon-key")
    provider = PolygonMarketDataProvider()
    old_stamps = [
        datetime(2025, 10, 13, 14, 0, tzinfo=UTC),
        datetime(2025, 10, 13, 18, 0, tzinfo=UTC),
    ]
    latest_stamps = [
        datetime(2026, 4, 30, 13, 30, tzinfo=UTC),
        datetime(2026, 4, 30, 14, 0, tzinfo=UTC),
        datetime(2026, 4, 30, 14, 30, tzinfo=UTC),
        datetime(2026, 4, 30, 15, 0, tzinfo=UTC),
        datetime(2026, 4, 30, 17, 30, tzinfo=UTC),
        datetime(2026, 4, 30, 18, 0, tzinfo=UTC),
        datetime(2026, 4, 30, 19, 30, tzinfo=UTC),
    ]
    response_stamps_desc = list(reversed(latest_stamps)) + list(reversed(old_stamps))

    def fake_request_json(path: str, query: dict[str, str]) -> dict[str, object]:
        assert path.startswith("/v2/aggs/ticker/AAPL/range/30/minute/")
        assert query["sort"] == "desc"
        assert query["limit"] == "50000"
        return {
            "results": [
                {"t": int(stamp.timestamp() * 1000), "o": 100 + idx, "h": 101 + idx, "l": 99 + idx, "c": 100.5 + idx, "v": 1000 + idx}
                for idx, stamp in enumerate(response_stamps_desc)
            ]
        }

    monkeypatch.setattr(provider, "_request_json", fake_request_json)

    bars = provider.fetch_historical_bars(symbol="AAPL", timeframe="4H", limit=2)

    assert [bar.timestamp for bar in bars] == [
        datetime(2026, 4, 30, 13, 30, tzinfo=UTC),
        datetime(2026, 4, 30, 17, 30, tzinfo=UTC),
    ]
    assert len({bar.timestamp for bar in bars}) == len(bars)


def test_polygon_rth_normalization_uses_new_york_dst_boundaries(monkeypatch) -> None:
    monkeypatch.setattr(settings, "polygon_api_key", "polygon-key")
    provider = PolygonMarketDataProvider()
    stamps = [
        datetime(2026, 7, 1, 13, 30, tzinfo=UTC),  # 09:30 ET during daylight time
        datetime(2026, 7, 1, 14, 0, tzinfo=UTC),
        datetime(2026, 12, 1, 14, 30, tzinfo=UTC),  # 09:30 ET during standard time
        datetime(2026, 12, 1, 15, 0, tzinfo=UTC),
    ]

    def fake_request_json(path: str, query: dict[str, str]) -> dict[str, object]:
        assert path.startswith("/v2/aggs/ticker/AAPL/range/30/minute/")
        return {
            "results": [
                {"t": int(stamp.timestamp() * 1000), "o": 100 + idx, "h": 101 + idx, "l": 99 + idx, "c": 100.5 + idx, "v": 1000 + idx}
                for idx, stamp in enumerate(stamps)
            ]
        }

    monkeypatch.setattr(provider, "_request_json", fake_request_json)

    bars = provider.fetch_historical_bars(symbol="AAPL", timeframe="1H", limit=2)

    assert [bar.date.isoformat() for bar in bars] == ["2026-07-01", "2026-12-01"]
    assert [bar.timestamp for bar in bars] == [
        datetime(2026, 7, 1, 13, 30, tzinfo=UTC),
        datetime(2026, 12, 1, 14, 30, tzinfo=UTC),
    ]
    assert all(bar.session_policy == "regular_hours" for bar in bars)


def test_alpaca_historical_bars_normalization(monkeypatch) -> None:
    monkeypatch.setattr(settings, "alpaca_api_key_id", "key")
    monkeypatch.setattr(settings, "alpaca_api_secret_key", "secret")
    provider = AlpacaMarketDataProvider()

    def fake_request_json(path: str, query: dict[str, str]) -> dict[str, object]:
        assert path == "/v2/stocks/bars"
        assert query["timeframe"] == "1Day"
        return {
            "bars": {
                "AAPL": [
                    {"t": "2026-04-01T20:00:00Z", "o": 190.1, "h": 192.0, "l": 189.4, "c": 191.2, "v": 123456},
                    {"t": "2026-04-02T20:00:00Z", "o": 191.2, "h": 193.5, "l": 190.7, "c": 193.0, "v": 150000},
                ]
            }
        }

    monkeypatch.setattr(provider, "_request_json", fake_request_json)
    bars = provider.fetch_historical_bars(symbol="AAPL", timeframe="1D", limit=2)

    assert len(bars) == 2
    assert bars[0].date.isoformat() == "2026-04-01"
    assert bars[0].timestamp == datetime(2026, 4, 1, 20, 0, tzinfo=UTC)
    assert bars[0].open == 190.1
    assert bars[1].close == 193.0
    assert bars[1].volume == 150000


def test_latest_snapshot_normalization(monkeypatch) -> None:
    monkeypatch.setattr(settings, "polygon_api_key", "polygon-key")
    provider = PolygonMarketDataProvider()

    def fake_request_json(path: str, query: dict[str, str]) -> dict[str, object]:
        assert path == "/v2/snapshot/locale/us/markets/stocks/tickers/AAPL"
        del query
        return {
            "ticker": {
                "day": {"o": 190.5, "h": 191.0, "l": 190.4, "c": 190.9, "v": 22000, "t": 1775174340000},
                "prevDay": {"c": 189.7},
                "lastTrade": {"p": 191.1, "t": 1775174345000},
            }
        }

    monkeypatch.setattr(provider, "_request_json", fake_request_json)
    snapshot = provider.fetch_latest_snapshot(symbol="AAPL", timeframe="1D")

    assert snapshot.symbol == "AAPL"
    assert snapshot.source == "polygon"
    assert snapshot.close == 191.1
    assert snapshot.fallback_mode is False


def test_polygon_option_snapshot_quote_mid_mark(monkeypatch) -> None:
    monkeypatch.setattr(settings, "polygon_api_key", "polygon-key")
    provider = PolygonMarketDataProvider()
    ts_ns = int(datetime.now(tz=UTC).timestamp() * 1_000_000_000)

    def fake_request_json(path: str, query: dict[str, str]) -> dict[str, object]:
        assert path == "/v3/snapshot/options/AAPL/O:AAPL260515C00205000"
        del query
        return {
            "results": {
                "last_quote": {"bid": 2.1, "ask": 2.4, "sip_timestamp": ts_ns},
                "last_trade": {"price": 2.3, "sip_timestamp": ts_ns},
                "day": {"close": 2.0},
                "implied_volatility": 0.32,
                "open_interest": 1200,
                "greeks": {"delta": 0.45, "gamma": 0.04, "theta": -0.08, "vega": 0.12},
                "underlying_asset": {"price": 205.5},
            }
        }

    monkeypatch.setattr(provider, "_request_json", fake_request_json)
    snapshot = provider.fetch_option_contract_snapshot(
        underlying_symbol="AAPL",
        option_symbol="O:AAPL260515C00205000",
    )

    assert snapshot.mark_price == 2.25
    assert snapshot.mark_method == "quote_mid"
    assert snapshot.stale is False
    assert snapshot.implied_volatility == 0.32
    assert snapshot.open_interest == 1200
    assert snapshot.delta == 0.45
    assert snapshot.underlying_price == 205.5


def test_polygon_option_snapshot_last_trade_fallback(monkeypatch) -> None:
    monkeypatch.setattr(settings, "polygon_api_key", "polygon-key")
    provider = PolygonMarketDataProvider()
    ts_ns = int(datetime.now(tz=UTC).timestamp() * 1_000_000_000)

    monkeypatch.setattr(
        provider,
        "_request_json",
        lambda path, query: {
            "results": {
                "last_quote": {"bid": None, "ask": None},
                "last_trade": {"price": 1.75, "sip_timestamp": ts_ns},
            }
        },
    )

    snapshot = provider.fetch_option_contract_snapshot(
        underlying_symbol="AAPL",
        option_symbol="O:AAPL260515C00205000",
    )

    assert snapshot.mark_price == 1.75
    assert snapshot.mark_method == "last_trade"
    assert snapshot.stale is False
    assert "bid" in snapshot.missing_fields
    assert "ask" in snapshot.missing_fields


def test_polygon_option_snapshot_missing_prices_returns_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(settings, "polygon_api_key", "polygon-key")
    provider = PolygonMarketDataProvider()
    monkeypatch.setattr(provider, "_request_json", lambda path, query: {"results": {"last_quote": {}, "last_trade": {}, "day": {}}})

    snapshot = provider.fetch_option_contract_snapshot(
        underlying_symbol="AAPL",
        option_symbol="O:AAPL260515C00205000",
    )

    assert snapshot.mark_price is None
    assert snapshot.mark_method == "unavailable"
    assert "option_mark_data" in snapshot.missing_fields


def test_polygon_option_snapshot_stale_trade_is_not_used_as_real_mark(monkeypatch) -> None:
    monkeypatch.setattr(settings, "polygon_api_key", "polygon-key")
    provider = PolygonMarketDataProvider()
    stale_ns = int(datetime(2025, 1, 1, tzinfo=UTC).timestamp() * 1_000_000_000)
    monkeypatch.setattr(
        provider,
        "_request_json",
        lambda path, query: {
            "results": {
                "last_quote": {},
                "last_trade": {"price": 1.75, "sip_timestamp": stale_ns},
                "day": {},
            }
        },
    )

    snapshot = provider.fetch_option_contract_snapshot(
        underlying_symbol="AAPL",
        option_symbol="O:AAPL260515C00205000",
    )

    assert snapshot.mark_price is None
    assert snapshot.mark_method == "unavailable"
    assert snapshot.stale is True
    assert "stale_trade" in snapshot.missing_fields


def test_polygon_option_snapshot_prior_close_is_explicit_stale_fallback(monkeypatch) -> None:
    monkeypatch.setattr(settings, "polygon_api_key", "polygon-key")
    provider = PolygonMarketDataProvider()
    monkeypatch.setattr(
        provider,
        "_request_json",
        lambda path, query: {
            "results": {
                "last_quote": {},
                "last_trade": {},
                "day": {"close": 1.55, "t": 1775088000000},
            }
        },
    )

    snapshot = provider.fetch_option_contract_snapshot(
        underlying_symbol="AAPL",
        option_symbol="O:AAPL260515C00205000",
    )

    assert snapshot.mark_price == 1.55
    assert snapshot.mark_method == "prior_close_fallback"
    assert snapshot.stale is True
    assert "fresh_option_mark" in snapshot.missing_fields


def test_build_polygon_option_ticker() -> None:
    assert build_polygon_option_ticker(
        underlying_symbol="aapl",
        expiration=datetime(2026, 5, 15, tzinfo=UTC).date(),
        option_type="call",
        strike=205.0,
    ) == "O:AAPL260515C00205000"


def _test_market_snapshot(symbol: str, close: float) -> MarketSnapshot:
    return MarketSnapshot(
        symbol=symbol,
        timeframe="1D",
        as_of=datetime(2026, 5, 3, 15, 0, tzinfo=UTC),
        open=close,
        high=close + 1,
        low=close - 1,
        close=close,
        volume=1_000_000,
        source="polygon",
        fallback_mode=False,
    )


def _test_option_snapshot(*, underlying: str, option_symbol: str, mark: float | None = 2.25, provider_error: str | None = None) -> OptionContractSnapshot:
    return OptionContractSnapshot(
        option_symbol=option_symbol,
        underlying_symbol=underlying,
        provider="polygon",
        endpoint=f"/v3/snapshot/options/{underlying}/{option_symbol}",
        mark_price=mark,
        mark_method="quote_mid" if mark is not None else "unavailable",
        as_of=datetime(2026, 5, 3, 15, 1, tzinfo=UTC) if mark is not None else None,
        stale=False,
        bid=mark - 0.05 if mark is not None else None,
        ask=mark + 0.05 if mark is not None else None,
        open_interest=1500 if mark is not None else None,
        fallback_mode=False,
        missing_fields=[] if mark is not None else ["option_mark_data"],
        provider_error=provider_error,
    )


def test_options_data_health_uses_discovered_near_money_sample(monkeypatch) -> None:
    monkeypatch.setattr(settings, "polygon_enabled", True)
    monkeypatch.setattr(settings, "polygon_api_key", "polygon-key")
    monkeypatch.setattr(settings, "polygon_base_url", "https://api.polygon.io")
    service = MarketDataService()
    provider = service._provider
    assert isinstance(provider, PolygonMarketDataProvider)
    expiry = (datetime.now(tz=UTC).date() + timedelta(days=14)).isoformat()
    chosen = "O:SPY990101C00450000"
    attempted: list[str] = []

    def fake_chain(symbol: str, limit: int = 50) -> dict[str, object]:
        assert symbol == "SPY"
        assert limit == 100
        return {
            "underlying": symbol,
            "expiry": expiry,
            "calls": [
                {"ticker": "O:SPY990101C00440000", "strike": 440.0, "expiry": expiry, "option_type": "call", "volume": 10},
                {"ticker": chosen, "strike": 450.0, "expiry": expiry, "option_type": "call", "volume": 100},
            ],
            "puts": [
                {"ticker": "O:SPY990101P00450000", "strike": 450.0, "expiry": expiry, "option_type": "put", "volume": 100},
            ],
        }

    def fake_option_snapshot(underlying_symbol: str, option_symbol: str) -> OptionContractSnapshot:
        attempted.append(option_symbol)
        return _test_option_snapshot(underlying=underlying_symbol, option_symbol=option_symbol)

    monkeypatch.setattr(provider, "fetch_options_chain_preview", fake_chain)
    monkeypatch.setattr(provider, "fetch_latest_snapshot", lambda symbol, timeframe: _test_market_snapshot(symbol, 451.0))
    monkeypatch.setattr(provider, "fetch_option_contract_snapshot", fake_option_snapshot)

    health = service.options_data_health(sample_symbol="SPY")

    assert health["probe_state"] == "ok"
    assert health["sample_underlying"] == "SPY"
    assert health["sample_option_symbol"] == chosen
    assert health["sample_selection_method"] == "discovered"
    assert attempted == [chosen]


def test_options_data_health_static_sample_fallback_is_labeled(monkeypatch) -> None:
    monkeypatch.setattr(settings, "polygon_enabled", True)
    monkeypatch.setattr(settings, "polygon_api_key", "polygon-key")
    monkeypatch.setattr(settings, "polygon_base_url", "https://api.polygon.io")
    service = MarketDataService()
    provider = service._provider
    assert isinstance(provider, PolygonMarketDataProvider)

    monkeypatch.setattr(
        provider,
        "fetch_options_chain_preview",
        lambda symbol, limit=50: {"underlying": symbol, "reason": "No active option contracts returned", "calls": None, "puts": None},
    )

    def fake_option_snapshot(underlying_symbol: str, option_symbol: str) -> OptionContractSnapshot:
        assert underlying_symbol == OPTIONS_HEALTH_STATIC_SAMPLE_UNDERLYING
        assert option_symbol == OPTIONS_HEALTH_STATIC_SAMPLE_OPTION
        return _test_option_snapshot(underlying=underlying_symbol, option_symbol=option_symbol)

    monkeypatch.setattr(provider, "fetch_option_contract_snapshot", fake_option_snapshot)

    health = service.options_data_health(sample_symbol="SPY")

    assert health["probe_state"] == "ok"
    assert health["sample_underlying"] == OPTIONS_HEALTH_STATIC_SAMPLE_UNDERLYING
    assert health["sample_option_symbol"] == OPTIONS_HEALTH_STATIC_SAMPLE_OPTION
    assert health["sample_selection_method"] == "static_sample"


def test_options_data_health_discovery_entitlement_is_clear_and_sanitized(monkeypatch) -> None:
    monkeypatch.setattr(settings, "polygon_enabled", True)
    monkeypatch.setattr(settings, "polygon_api_key", "polygon-secret-health")
    monkeypatch.setattr(settings, "polygon_base_url", "https://api.polygon.io")
    service = MarketDataService()
    provider = service._provider
    assert isinstance(provider, PolygonMarketDataProvider)

    monkeypatch.setattr(
        provider,
        "fetch_options_chain_preview",
        lambda symbol, limit=50: {
            "underlying": symbol,
            "reason": "Options endpoint not entitled: Not entitled to this data. Upgrade plan at https://polygon.io/pricing",
            "calls": None,
            "puts": None,
        },
    )

    health = service.options_data_health(sample_symbol="SPY")

    assert health["probe_state"] == "failed"
    assert health["sample_selection_method"] == "unavailable"
    assert health["sample_option_symbol"] is None
    assert health["details"] == "Options sample discovery is not entitled to option reference data."
    assert "polygon-secret-health" not in str(health)
    assert "https://polygon.io/pricing" not in str(health)


def test_provider_health_result_structure(monkeypatch) -> None:
    class StubMarketDataService:
        def latest_snapshot(self, symbol: str, timeframe: str):
            from macmarket_trader.data.providers.market_data import MarketSnapshot

            return MarketSnapshot(
                symbol=symbol,
                timeframe=timeframe,
                as_of=datetime(2026, 4, 2, tzinfo=UTC),
                open=100,
                high=101,
                low=99,
                close=100.5,
                volume=1000,
                source="polygon",
                fallback_mode=False,
            )

        def provider_health(self, sample_symbol: str = "AAPL") -> MarketProviderHealth:
            return MarketProviderHealth(
                provider="market_data",
                mode="polygon",
                status="ok",
                details="Polygon auth probe and sample snapshot succeeded.",
                configured=True,
                feed="stocks",
                sample_symbol=sample_symbol,
                latency_ms=12.4,
                last_success_at=datetime(2026, 4, 2, tzinfo=UTC),
            )

    monkeypatch.setattr(admin_routes, "market_data_service", StubMarketDataService())
    monkeypatch.setattr(settings, "polygon_enabled", True)
    monkeypatch.setattr(settings, "workflow_demo_fallback", False)
    monkeypatch.setattr(settings, "environment", "test")
    monkeypatch.setattr(settings, "broker_provider", "alpaca")
    monkeypatch.setattr(settings, "alpaca_api_key_id", "alpaca-key")
    monkeypatch.setattr(settings, "alpaca_api_secret_key", "alpaca-secret")
    monkeypatch.setattr(settings, "alpaca_paper_base_url", "https://paper-api.alpaca.markets")
    monkeypatch.setattr(settings, "macro_calendar_provider", "fred")
    monkeypatch.setattr(settings, "fred_api_key", "fred-key")
    monkeypatch.setattr(settings, "fred_base_url", "https://api.stlouisfed.org/fred")
    monkeypatch.setattr(settings, "news_provider", "polygon")
    monkeypatch.setattr(settings, "polygon_api_key", "polygon-key")
    monkeypatch.setattr(settings, "polygon_base_url", "https://api.polygon.io")

    client = TestClient(app)
    from macmarket_trader.domain.models import AppUserModel
    from macmarket_trader.storage.db import SessionLocal

    client.get("/user/me", headers={"Authorization": "Bearer admin-token"})
    with SessionLocal() as session:
        admin = session.execute(select(AppUserModel).where(AppUserModel.external_auth_user_id == "clerk_admin")).scalar_one()
        admin.app_role = "admin"
        admin.approval_status = "approved"
        admin.mfa_enabled = True
        session.commit()

    response = client.get("/admin/provider-health", headers={"Authorization": "Bearer admin-token"})
    assert response.status_code == 200
    payload = response.json()

    alpaca_entry = next(item for item in payload["providers"] if item["provider"] == "alpaca_paper")
    assert alpaca_entry["status"] == "configured"
    assert alpaca_entry["config_state"] == "configured"
    assert alpaca_entry["probe_state"] == "unavailable"
    assert alpaca_entry["configured"] is True
    assert alpaca_entry["selected_provider"] == "alpaca"
    assert alpaca_entry["probe_status"] == "unavailable"
    assert alpaca_entry["readiness_scope"] == "paper_provider"

    fred_entry = next(item for item in payload["providers"] if item["provider"] == "fred")
    assert fred_entry["status"] == "configured"
    assert fred_entry["config_state"] == "configured"
    assert fred_entry["probe_state"] == "unavailable"
    assert fred_entry["configured"] is True
    assert fred_entry["selected_provider"] == "fred"
    assert fred_entry["probe_status"] == "unavailable"
    assert fred_entry["readiness_scope"] == "macro_context"

    news_entry = next(item for item in payload["providers"] if item["provider"] == "news")
    assert news_entry["status"] == "configured"
    assert news_entry["config_state"] == "configured"
    assert news_entry["probe_state"] == "unavailable"
    assert news_entry["configured"] is True
    assert news_entry["selected_provider"] == "polygon"
    assert news_entry["probe_status"] == "unavailable"
    assert news_entry["readiness_scope"] == "news_context"

    market_entry = next(item for item in payload["providers"] if item["provider"] == "market_data")
    assert market_entry["configured_provider"] == "polygon"
    assert market_entry["effective_read_mode"] == "polygon"
    assert market_entry["workflow_execution_mode"] == "provider"
    assert market_entry["mode"] == "polygon"
    assert market_entry["status"] == "ok"
    assert market_entry["config_state"] == "configured"
    assert market_entry["probe_state"] == "ok"
    assert market_entry["feed"] == "stocks"
    assert market_entry["sample_symbol"] == "AAPL"
    assert market_entry["latency_ms"] == 12.4
    assert market_entry["last_success_at"].startswith("2026-04-02")


def test_provider_health_reports_blocked_workflows_when_probe_fails_and_demo_fallback_disabled(monkeypatch) -> None:
    class StubMarketDataService:
        def provider_health(self, sample_symbol: str = "AAPL") -> MarketProviderHealth:
            return MarketProviderHealth(
                provider="market_data",
                mode="polygon",
                status="warning",
                details="Polygon probe failed: HTTP Error 403: Forbidden",
                configured=True,
                feed="stocks",
                sample_symbol=sample_symbol,
            )

    monkeypatch.setattr(admin_routes, "market_data_service", StubMarketDataService())
    monkeypatch.setattr(settings, "polygon_enabled", True)
    monkeypatch.setattr(settings, "workflow_demo_fallback", False)
    monkeypatch.setattr(settings, "environment", "local")

    summary = admin_routes.provider_health_summary()
    assert summary["configured_provider"] == "polygon"
    assert summary["effective_read_mode"] == "fallback"
    assert summary["workflow_execution_mode"] == "blocked"

    payload = admin_routes.provider_health()
    market_entry = next(item for item in payload["providers"] if item["provider"] == "market_data")
    assert market_entry["workflow_execution_mode"] == "blocked"
    assert market_entry["config_state"] == "configured"
    assert market_entry["probe_state"] == "failed"
    assert "blocked" in market_entry["operational_impact"].lower()


def test_provider_health_separates_config_state_from_probe_state_for_optional_providers(monkeypatch) -> None:
    monkeypatch.setattr(settings, "broker_provider", "mock")
    monkeypatch.setattr(settings, "alpaca_api_key_id", "alpaca-key")
    monkeypatch.setattr(settings, "alpaca_api_secret_key", "alpaca-secret")
    monkeypatch.setattr(settings, "alpaca_paper_base_url", "https://paper-api.alpaca.markets")
    monkeypatch.setattr(settings, "macro_calendar_provider", "fred")
    monkeypatch.setattr(settings, "fred_api_key", "fred-key")
    monkeypatch.setattr(settings, "fred_base_url", "https://api.stlouisfed.org/fred")
    monkeypatch.setattr(settings, "news_provider", "polygon")
    monkeypatch.setattr(settings, "polygon_api_key", "polygon-key")
    monkeypatch.setattr(settings, "polygon_base_url", "https://api.polygon.io")

    alpaca_entry = admin_routes._alpaca_paper_readiness()
    fred_entry = admin_routes._fred_readiness()
    news_entry = admin_routes._news_readiness()

    assert alpaca_entry["config_state"] == "configured"
    assert alpaca_entry["probe_state"] == "unavailable"
    assert alpaca_entry["selected_provider"] == "mock"
    assert "mock broker mode" in str(alpaca_entry["operational_impact"])
    assert fred_entry["config_state"] == "configured"
    assert fred_entry["probe_state"] == "unavailable"
    assert fred_entry["status"] == "configured"
    assert news_entry["config_state"] == "configured"
    assert news_entry["probe_state"] == "unavailable"
    assert news_entry["status"] == "configured"


def test_provider_health_reports_missing_config_separately_from_probe(monkeypatch) -> None:
    monkeypatch.setattr(settings, "macro_calendar_provider", "fred")
    monkeypatch.setattr(settings, "fred_api_key", "")
    monkeypatch.setattr(settings, "fred_base_url", "https://api.stlouisfed.org/fred")

    fred_entry = admin_routes._fred_readiness()

    assert fred_entry["status"] == "unconfigured"
    assert fred_entry["config_state"] == "missing_config"
    assert fred_entry["probe_state"] == "unavailable"


def test_provider_health_reports_options_data_probe_ok(monkeypatch) -> None:
    class StubMarketDataService:
        def provider_health(self, sample_symbol: str = "AAPL") -> MarketProviderHealth:
            return MarketProviderHealth(
                provider="market_data",
                mode="polygon",
                status="ok",
                details="Polygon snapshot probe succeeded.",
                configured=True,
                feed="stocks",
                sample_symbol=sample_symbol,
            )

        def options_data_health(self, sample_symbol: str = "AAPL") -> dict[str, object]:
            return {
                "probe_state": "ok",
                "probe_status": "ok",
                "details": "Polygon options snapshot probe succeeded using quote_mid.",
                "sample_underlying": sample_symbol,
                "sample_option_symbol": "O:AAPL260515C00205000",
                "sample_selection_method": "discovered",
                "latency_ms": 14.2,
                "last_success_at": "2026-05-03T20:00:00+00:00",
            }

    monkeypatch.setattr(admin_routes, "market_data_service", StubMarketDataService())
    monkeypatch.setattr(settings, "polygon_enabled", True)
    monkeypatch.setattr(settings, "polygon_api_key", "polygon-key")
    monkeypatch.setattr(settings, "polygon_base_url", "https://api.polygon.io")

    entry = admin_routes._options_data_readiness()

    assert entry["provider"] == "options_data"
    assert entry["status"] == "ok"
    assert entry["config_state"] == "configured"
    assert entry["probe_state"] == "ok"
    assert entry["sample_option_symbol"] == "O:AAPL260515C00205000"
    assert entry["sample_underlying"] == "SPY"
    assert entry["sample_selection_method"] == "discovered"
    assert "does not enable live trading" in str(entry["operational_impact"])


def test_provider_health_options_data_probe_failure_sanitizes_error(monkeypatch) -> None:
    secret = "polygon-secret-health"

    class StubMarketDataService:
        def provider_health(self, sample_symbol: str = "AAPL") -> MarketProviderHealth:
            return MarketProviderHealth(
                provider="market_data",
                mode="polygon",
                status="ok",
                details="Polygon snapshot probe succeeded.",
                configured=True,
                feed="stocks",
                sample_symbol=sample_symbol,
            )

        def options_data_health(self, sample_symbol: str = "AAPL") -> dict[str, object]:
            return {
                "probe_state": "failed",
                "probe_status": "failed",
                "details": f"Invalid sample option probe failed with apiKey={secret}",
                "sample_underlying": sample_symbol,
                "sample_option_symbol": "O:AAPL260515C00205000",
                "sample_selection_method": "discovered",
            }

    monkeypatch.setattr(admin_routes, "market_data_service", StubMarketDataService())
    monkeypatch.setattr(settings, "polygon_enabled", True)
    monkeypatch.setattr(settings, "polygon_api_key", secret)
    monkeypatch.setattr(settings, "polygon_base_url", "https://api.polygon.io")

    entry = admin_routes._options_data_readiness()

    assert entry["status"] == "degraded"
    assert entry["probe_state"] == "failed"
    assert entry["sample_selection_method"] == "discovered"
    assert secret not in str(entry)
    assert "[redacted]" in str(entry["details"])
    assert "does not enable live trading" in str(entry["operational_impact"])
    assert "broker routing" in str(entry["operational_impact"])


def test_provider_health_options_data_not_entitled_is_clear_without_enabling_execution(monkeypatch) -> None:
    class StubMarketDataService:
        def provider_health(self, sample_symbol: str = "AAPL") -> MarketProviderHealth:
            return MarketProviderHealth(
                provider="market_data",
                mode="polygon",
                status="ok",
                details="Polygon snapshot probe succeeded.",
                configured=True,
                feed="stocks",
                sample_symbol=sample_symbol,
            )

        def options_data_health(self, sample_symbol: str = "AAPL") -> dict[str, object]:
            return {
                "probe_state": "failed",
                "probe_status": "failed",
                "details": "Not entitled to this data.",
                "sample_underlying": sample_symbol,
                "sample_option_symbol": "O:AAPL260515C00205000",
                "sample_selection_method": "discovered",
            }

    monkeypatch.setattr(admin_routes, "market_data_service", StubMarketDataService())
    monkeypatch.setattr(settings, "polygon_enabled", True)
    monkeypatch.setattr(settings, "polygon_api_key", "polygon-key")
    monkeypatch.setattr(settings, "polygon_base_url", "https://api.polygon.io")

    entry = admin_routes._options_data_readiness()

    assert entry["status"] == "degraded"
    assert entry["probe_state"] == "failed"
    assert entry["sample_selection_method"] == "discovered"
    assert entry["entitlement_state"] == "not_entitled"
    assert entry["details"] == "Option marks unavailable: provider plan is not entitled to option snapshot data."
    assert "mark_unavailable rather than fake P&L" in str(entry["operational_impact"])
    assert "does not enable live trading" in str(entry["operational_impact"])


def test_normalize_polygon_ticker_maps_index_symbols() -> None:
    # Every known index should get the I: prefix
    for sym in INDEX_SYMBOLS:
        assert normalize_polygon_ticker(sym) == f"I:{sym}"
    # Case-insensitive input
    assert normalize_polygon_ticker("spx") == "I:SPX"
    assert normalize_polygon_ticker("vix") == "I:VIX"
    assert normalize_polygon_ticker("oex") == "I:OEX"
    # Equity symbols pass through unchanged
    assert normalize_polygon_ticker("AAPL") == "AAPL"
    assert normalize_polygon_ticker("msft") == "MSFT"
    assert normalize_polygon_ticker("SPY") == "SPY"


def test_polygon_historical_bars_uses_normalized_ticker(monkeypatch) -> None:
    monkeypatch.setattr(settings, "polygon_api_key", "polygon-key")
    provider = PolygonMarketDataProvider()

    captured_paths: list[str] = []

    def fake_request_json(path: str, query: dict[str, str]) -> dict[str, object]:
        captured_paths.append(path)
        return {
            "results": [
                {"t": 1775088000000, "o": 5200.0, "h": 5210.0, "l": 5190.0, "c": 5205.0, "v": 1_000_000},
            ]
        }

    monkeypatch.setattr(provider, "_request_json", fake_request_json)
    bars = provider.fetch_historical_bars(symbol="SPX", timeframe="1D", limit=1)

    assert len(bars) == 1
    assert any("I:SPX" in p for p in captured_paths), f"Expected I:SPX in path, got: {captured_paths}"


def test_polygon_snapshot_uses_normalized_ticker(monkeypatch) -> None:
    monkeypatch.setattr(settings, "polygon_api_key", "polygon-key")
    provider = PolygonMarketDataProvider()

    captured_paths: list[str] = []

    def fake_request_json(path: str, query: dict[str, str]) -> dict[str, object]:
        captured_paths.append(path)
        return {
            "ticker": {
                "day": {"o": 5200.0, "h": 5210.0, "l": 5190.0, "c": 5205.0, "v": 500_000, "t": 1775174340000},
                "prevDay": {"c": 5195.0},
                "lastTrade": {"p": 5206.0, "t": 1775174345000},
            }
        }

    monkeypatch.setattr(provider, "_request_json", fake_request_json)
    snapshot = provider.fetch_latest_snapshot(symbol="VIX", timeframe="1D")

    assert snapshot.symbol == "VIX"
    assert any("I:VIX" in p for p in captured_paths), f"Expected I:VIX in path, got: {captured_paths}"


def test_symbol_not_found_raised_when_polygon_returns_empty_results(monkeypatch) -> None:
    import pytest

    monkeypatch.setattr(settings, "polygon_api_key", "polygon-key")
    provider = PolygonMarketDataProvider()

    def fake_request_json(path: str, query: dict[str, str]) -> dict[str, object]:
        return {"resultsCount": 0, "results": []}

    monkeypatch.setattr(provider, "_request_json", fake_request_json)

    with pytest.raises(SymbolNotFoundError):
        provider.fetch_historical_bars(symbol="FAKE", timeframe="1D", limit=5)


def test_symbol_not_found_raised_when_polygon_snapshot_missing(monkeypatch) -> None:
    import pytest

    monkeypatch.setattr(settings, "polygon_api_key", "polygon-key")
    provider = PolygonMarketDataProvider()

    def fake_request_json(path: str, query: dict[str, str]) -> dict[str, object]:
        return {"ticker": None, "status": "OK"}

    monkeypatch.setattr(provider, "_request_json", fake_request_json)

    with pytest.raises(SymbolNotFoundError):
        provider.fetch_latest_snapshot(symbol="FAKE", timeframe="1D")


def test_market_data_service_propagates_symbol_not_found(monkeypatch) -> None:
    import pytest

    monkeypatch.setattr(settings, "polygon_enabled", True)
    monkeypatch.setattr(settings, "polygon_api_key", "polygon-key")

    service = MarketDataService()

    def fake_fetch(symbol: str, timeframe: str, limit: int) -> list:
        raise SymbolNotFoundError(f"No data for {symbol}")

    monkeypatch.setattr(service._provider, "fetch_historical_bars", fake_fetch)

    with pytest.raises(SymbolNotFoundError):
        service.historical_bars("FAKE", "1D", 10)


def test_workflow_bars_returns_400_for_unknown_symbol(monkeypatch) -> None:
    from fastapi.testclient import TestClient
    from sqlalchemy import select

    from macmarket_trader.api.main import app
    from macmarket_trader.api.routes import admin as admin_routes
    from macmarket_trader.domain.models import AppUserModel
    from macmarket_trader.storage.db import SessionLocal

    class StubMarketDataService:
        def historical_bars(self, symbol: str, timeframe: str, limit: int):  # type: ignore[override]
            raise SymbolNotFoundError(f"No data for {symbol}")

        def latest_snapshot(self, symbol: str, timeframe: str):  # type: ignore[override]
            from macmarket_trader.data.providers.market_data import MarketSnapshot
            return MarketSnapshot(
                symbol=symbol, timeframe=timeframe,
                as_of=datetime(2026, 4, 2, tzinfo=UTC),
                open=100, high=101, low=99, close=100.5, volume=1000,
                source="fallback", fallback_mode=True,
            )

        def provider_health(self, sample_symbol: str = "AAPL") -> MarketProviderHealth:
            return MarketProviderHealth(
                provider="market_data", mode="fallback", status="warning",
                details="stub", configured=False, feed="none", sample_symbol=sample_symbol,
            )

    monkeypatch.setattr(admin_routes, "market_data_service", StubMarketDataService())
    monkeypatch.setattr(settings, "polygon_enabled", True)
    monkeypatch.setattr(settings, "workflow_demo_fallback", False)
    monkeypatch.setattr(settings, "environment", "test")

    client = TestClient(app)
    client.get("/user/me", headers={"Authorization": "Bearer admin-token"})
    with SessionLocal() as session:
        admin = session.execute(select(AppUserModel).where(AppUserModel.external_auth_user_id == "clerk_admin")).scalar_one()
        admin.app_role = "admin"
        admin.approval_status = "approved"
        admin.mfa_enabled = True
        session.commit()
    client.get("/user/me", headers={"Authorization": "Bearer user-token"})
    with SessionLocal() as session:
        user = session.execute(select(AppUserModel).where(AppUserModel.external_auth_user_id == "clerk_user")).scalar_one()
        user.approval_status = "approved"
        session.commit()

    resp = client.get(
        "/user/analysis/setup",
        params={"req_symbol": "FAKE"},
        headers={"Authorization": "Bearer user-token"},
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["detail"]["error"] == "symbol_not_found"
    assert "FAKE" in payload["detail"]["message"]


def test_analysis_setup_passes_requested_timeframe_to_market_data(monkeypatch) -> None:
    calls: list[tuple[str, str, int]] = []

    class StubMarketDataService:
        def historical_bars(self, symbol: str, timeframe: str, limit: int):  # type: ignore[override]
            calls.append((symbol, timeframe, limit))
            return DeterministicFallbackMarketDataProvider().fetch_historical_bars(symbol, timeframe, limit), "polygon", False

        def latest_snapshot(self, symbol: str, timeframe: str):  # type: ignore[override]
            return DeterministicFallbackMarketDataProvider().fetch_latest_snapshot(symbol, timeframe)

        def options_chain_preview(self, symbol: str, limit: int = 50):  # type: ignore[override]
            return None

        def provider_health(self, sample_symbol: str = "AAPL") -> MarketProviderHealth:
            return MarketProviderHealth(
                provider="market_data", mode="polygon", status="ok",
                details="stub", configured=True, feed="stocks", sample_symbol=sample_symbol,
            )

    monkeypatch.setattr(admin_routes, "market_data_service", StubMarketDataService())
    monkeypatch.setattr(settings, "polygon_enabled", True)
    monkeypatch.setattr(settings, "workflow_demo_fallback", False)
    monkeypatch.setattr(settings, "environment", "test")

    client = TestClient(app)
    client.get("/user/me", headers={"Authorization": "Bearer user-token"})
    from macmarket_trader.domain.models import AppUserModel
    from macmarket_trader.storage.db import SessionLocal

    with SessionLocal() as session:
        user = session.execute(select(AppUserModel).where(AppUserModel.external_auth_user_id == "clerk_user")).scalar_one()
        user.approval_status = "approved"
        session.commit()

    response = client.get(
        "/user/analysis/setup",
        params={"req_symbol": "GOOG", "timeframe": "4H"},
        headers={"Authorization": "Bearer user-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["timeframe"] == "4H"
    assert payload["session_policy"] == "regular_hours"
    assert payload["data_quality"]["session_policy"] == "regular_hours"
    assert calls == [("GOOG", "4H", 120)]


def test_data_not_entitled_raised_on_polygon_403(monkeypatch) -> None:
    import pytest
    from urllib.error import HTTPError
    import macmarket_trader.data.providers.market_data as md_module

    monkeypatch.setattr(settings, "polygon_api_key", "polygon-key")
    provider = PolygonMarketDataProvider()

    def fake_urlopen(request, timeout):  # type: ignore[override]
        raise HTTPError(url="", code=403, msg="Forbidden", hdrs=None, fp=None)  # type: ignore[arg-type]

    monkeypatch.setattr(md_module, "urlopen", fake_urlopen)

    with pytest.raises(DataNotEntitledError, match="Not entitled"):
        provider.fetch_historical_bars(symbol="SPX", timeframe="1D", limit=5)


def test_market_data_service_propagates_data_not_entitled(monkeypatch) -> None:
    import pytest

    monkeypatch.setattr(settings, "polygon_enabled", True)
    monkeypatch.setattr(settings, "polygon_api_key", "polygon-key")

    service = MarketDataService()

    def fake_fetch(symbol: str, timeframe: str, limit: int) -> list:
        raise DataNotEntitledError("Not entitled to this data")

    monkeypatch.setattr(service._provider, "fetch_historical_bars", fake_fetch)

    with pytest.raises(DataNotEntitledError):
        service.historical_bars("SPX", "1D", 10)


def test_workflow_bars_returns_402_for_entitled_data(monkeypatch) -> None:
    from fastapi.testclient import TestClient
    from sqlalchemy import select

    from macmarket_trader.api.main import app
    from macmarket_trader.api.routes import admin as admin_routes
    from macmarket_trader.domain.models import AppUserModel
    from macmarket_trader.storage.db import SessionLocal

    class StubMarketDataService:
        def historical_bars(self, symbol: str, timeframe: str, limit: int):  # type: ignore[override]
            raise DataNotEntitledError("Not entitled to this data")

        def latest_snapshot(self, symbol: str, timeframe: str):  # type: ignore[override]
            from macmarket_trader.data.providers.market_data import DeterministicFallbackMarketDataProvider
            return DeterministicFallbackMarketDataProvider().fetch_latest_snapshot(symbol, timeframe)

        def options_chain_preview(self, symbol: str, limit: int = 50):  # type: ignore[override]
            return None

        def provider_health(self, sample_symbol: str = "AAPL") -> MarketProviderHealth:
            return MarketProviderHealth(
                provider="market_data", mode="polygon", status="ok",
                details="stub", configured=True, feed="stocks", sample_symbol=sample_symbol,
            )

    monkeypatch.setattr(admin_routes, "market_data_service", StubMarketDataService())
    monkeypatch.setattr(settings, "polygon_enabled", True)
    monkeypatch.setattr(settings, "workflow_demo_fallback", False)
    monkeypatch.setattr(settings, "environment", "test")

    client = TestClient(app)
    client.get("/user/me", headers={"Authorization": "Bearer user-token"})
    with SessionLocal() as session:
        user = session.execute(select(AppUserModel).where(AppUserModel.external_auth_user_id == "clerk_user")).scalar_one()
        user.approval_status = "approved"
        session.commit()

    resp = client.get(
        "/user/analysis/setup",
        params={"req_symbol": "SPX"},
        headers={"Authorization": "Bearer user-token"},
    )
    assert resp.status_code == 402
    payload = resp.json()
    assert payload["detail"]["error"] == "data_not_entitled"
    assert "SPX" in payload["detail"]["message"]
    assert "plan upgrade" in payload["detail"]["message"]


def test_options_chain_preview_returns_calls_and_puts(monkeypatch) -> None:
    monkeypatch.setattr(settings, "polygon_api_key", "polygon-key")
    provider = PolygonMarketDataProvider()

    def fake_request_json(path: str, query: dict[str, str]) -> dict[str, object]:
        assert path == "/v3/reference/options/contracts"
        assert query["underlying_ticker"] == "AAPL"
        return {
            "results": [
                {"contract_type": "call", "strike_price": 190.0, "expiration_date": "2026-05-16", "underlying_ticker": "AAPL"},
                {"contract_type": "call", "strike_price": 195.0, "expiration_date": "2026-05-16", "underlying_ticker": "AAPL"},
                {"contract_type": "put", "strike_price": 185.0, "expiration_date": "2026-05-16", "underlying_ticker": "AAPL"},
                {"contract_type": "put", "strike_price": 180.0, "expiration_date": "2026-05-16", "underlying_ticker": "AAPL"},
            ],
            "status": "OK",
        }

    monkeypatch.setattr(provider, "_request_json", fake_request_json)
    result = provider.fetch_options_chain_preview(symbol="AAPL")

    assert result["underlying"] == "AAPL"
    assert result["expiry"] == "2026-05-16"
    assert result["source"] == "polygon_options_basic"
    assert isinstance(result["calls"], list)
    assert len(result["calls"]) == 2
    assert result["calls"][0]["strike"] == 190.0
    assert result["calls"][0]["last_price"] is None
    assert isinstance(result["puts"], list)
    assert len(result["puts"]) == 2
    assert "reason" not in result or result.get("reason") is None


def test_options_chain_preview_null_when_no_results(monkeypatch) -> None:
    monkeypatch.setattr(settings, "polygon_api_key", "polygon-key")
    provider = PolygonMarketDataProvider()

    def fake_request_json(path: str, query: dict[str, str]) -> dict[str, object]:
        return {"results": [], "status": "OK"}

    monkeypatch.setattr(provider, "_request_json", fake_request_json)
    result = provider.fetch_options_chain_preview(symbol="FAKE")

    assert result["calls"] is None
    assert result["puts"] is None
    assert "reason" in result
    assert result["reason"]


def test_options_chain_preview_null_when_provider_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(settings, "polygon_api_key", "polygon-key")
    provider = PolygonMarketDataProvider()

    def fake_request_json(path: str, query: dict[str, str]) -> dict[str, object]:
        raise ProviderUnavailableError("Connection refused")

    monkeypatch.setattr(provider, "_request_json", fake_request_json)
    result = provider.fetch_options_chain_preview(symbol="AAPL")

    assert result["calls"] is None
    assert result["puts"] is None
    assert "reason" in result


def test_analysis_setup_includes_options_chain_preview_for_options_mode(monkeypatch) -> None:
    from fastapi.testclient import TestClient
    from sqlalchemy import select

    from macmarket_trader.api.main import app
    from macmarket_trader.api.routes import admin as admin_routes
    from macmarket_trader.domain.models import AppUserModel
    from macmarket_trader.storage.db import SessionLocal

    chain_preview = {
        "underlying": "AAPL",
        "expiry": "2026-05-16",
        "calls": [{"strike": 190.0, "expiry": "2026-05-16", "last_price": None, "volume": None}],
        "puts": [{"strike": 185.0, "expiry": "2026-05-16", "last_price": None, "volume": None}],
        "data_as_of": "2026-04-16",
        "source": "polygon_options_basic",
    }

    class StubMarketDataService:
        def historical_bars(self, symbol: str, timeframe: str, limit: int):  # type: ignore[override]
            from macmarket_trader.data.providers.market_data import DeterministicFallbackMarketDataProvider
            return DeterministicFallbackMarketDataProvider().fetch_historical_bars(symbol, timeframe, limit), "fallback", True

        def latest_snapshot(self, symbol: str, timeframe: str):  # type: ignore[override]
            from macmarket_trader.data.providers.market_data import DeterministicFallbackMarketDataProvider
            return DeterministicFallbackMarketDataProvider().fetch_latest_snapshot(symbol, timeframe)

        def options_chain_preview(self, symbol: str, limit: int = 50):  # type: ignore[override]
            return chain_preview

        def provider_health(self, sample_symbol: str = "AAPL") -> MarketProviderHealth:
            return MarketProviderHealth(
                provider="market_data", mode="fallback", status="warning",
                details="stub", configured=False, feed="none", sample_symbol=sample_symbol,
            )

    monkeypatch.setattr(admin_routes, "market_data_service", StubMarketDataService())
    monkeypatch.setattr(settings, "polygon_enabled", False)
    monkeypatch.setattr(settings, "workflow_demo_fallback", True)
    monkeypatch.setattr(settings, "environment", "test")

    client = TestClient(app)
    client.get("/user/me", headers={"Authorization": "Bearer user-token"})
    with SessionLocal() as session:
        user = session.execute(select(AppUserModel).where(AppUserModel.external_auth_user_id == "clerk_user")).scalar_one()
        user.approval_status = "approved"
        session.commit()

    resp = client.get(
        "/user/analysis/setup",
        params={"req_symbol": "AAPL", "market_mode": "options"},
        headers={"Authorization": "Bearer user-token"},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert "options_chain_preview" in payload
    preview = payload["options_chain_preview"]
    assert preview is not None
    assert preview["underlying"] == "AAPL"
    assert preview["expiry"] == "2026-05-16"
    assert preview["source"] == "polygon_options_basic"
    assert len(preview["calls"]) == 1
    assert len(preview["puts"]) == 1


def test_analysis_setup_options_chain_preview_none_when_provider_not_polygon(monkeypatch) -> None:
    from fastapi.testclient import TestClient
    from sqlalchemy import select

    from macmarket_trader.api.main import app
    from macmarket_trader.api.routes import admin as admin_routes
    from macmarket_trader.domain.models import AppUserModel
    from macmarket_trader.storage.db import SessionLocal

    class StubMarketDataService:
        def historical_bars(self, symbol: str, timeframe: str, limit: int):  # type: ignore[override]
            from macmarket_trader.data.providers.market_data import DeterministicFallbackMarketDataProvider
            return DeterministicFallbackMarketDataProvider().fetch_historical_bars(symbol, timeframe, limit), "fallback", True

        def latest_snapshot(self, symbol: str, timeframe: str):  # type: ignore[override]
            from macmarket_trader.data.providers.market_data import DeterministicFallbackMarketDataProvider
            return DeterministicFallbackMarketDataProvider().fetch_latest_snapshot(symbol, timeframe)

        def options_chain_preview(self, symbol: str, limit: int = 50):  # type: ignore[override]
            return None  # Non-Polygon provider

        def provider_health(self, sample_symbol: str = "AAPL") -> MarketProviderHealth:
            return MarketProviderHealth(
                provider="market_data", mode="fallback", status="warning",
                details="stub", configured=False, feed="none", sample_symbol=sample_symbol,
            )

    monkeypatch.setattr(admin_routes, "market_data_service", StubMarketDataService())
    monkeypatch.setattr(settings, "polygon_enabled", False)
    monkeypatch.setattr(settings, "workflow_demo_fallback", True)
    monkeypatch.setattr(settings, "environment", "test")

    client = TestClient(app)
    client.get("/user/me", headers={"Authorization": "Bearer user-token"})
    with SessionLocal() as session:
        user = session.execute(select(AppUserModel).where(AppUserModel.external_auth_user_id == "clerk_user")).scalar_one()
        user.approval_status = "approved"
        session.commit()

    resp = client.get(
        "/user/analysis/setup",
        params={"req_symbol": "AAPL", "market_mode": "options"},
        headers={"Authorization": "Bearer user-token"},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert "options_chain_preview" in payload
    assert payload["options_chain_preview"] is None


def test_provider_health_reports_demo_fallback_when_probe_fails_and_demo_fallback_enabled(monkeypatch) -> None:
    class StubMarketDataService:
        def provider_health(self, sample_symbol: str = "AAPL") -> MarketProviderHealth:
            return MarketProviderHealth(
                provider="market_data",
                mode="polygon",
                status="warning",
                details="Polygon probe failed: HTTP Error 403: Forbidden",
                configured=True,
                feed="stocks",
                sample_symbol=sample_symbol,
            )

    monkeypatch.setattr(admin_routes, "market_data_service", StubMarketDataService())
    monkeypatch.setattr(settings, "polygon_enabled", True)
    monkeypatch.setattr(settings, "workflow_demo_fallback", True)
    monkeypatch.setattr(settings, "environment", "local")

    summary = admin_routes.provider_health_summary()
    assert summary["configured_provider"] == "polygon"
    assert summary["effective_read_mode"] == "fallback"
    assert summary["workflow_execution_mode"] == "demo_fallback"

    payload = admin_routes.provider_health()
    market_entry = next(item for item in payload["providers"] if item["provider"] == "market_data")
    assert market_entry["workflow_execution_mode"] == "demo_fallback"
    assert "explicit deterministic demo fallback bars" in market_entry["operational_impact"].lower()
