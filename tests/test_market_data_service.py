from __future__ import annotations

from datetime import UTC, datetime

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
    PolygonMarketDataProvider,
    ProviderUnavailableError,
    SymbolNotFoundError,
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
        datetime(2026, 4, 1, 13, 30, tzinfo=UTC),
        datetime(2026, 4, 1, 14, 30, tzinfo=UTC),
        datetime(2026, 4, 1, 15, 30, tzinfo=UTC),
        datetime(2026, 4, 1, 16, 30, tzinfo=UTC),
    ]

    def fake_request_json(path: str, query: dict[str, str]) -> dict[str, object]:
        assert path.startswith("/v2/aggs/ticker/GOOG/range/1/hour/")
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

    assert [bar.timestamp for bar in bars] == stamps[-2:]
    assert [bar.close for bar in bars] == [102.5, 103.5]
    assert all(bar.date.isoformat() == "2026-04-01" for bar in bars)
    assert provider.last_aggregate_request_metadata is not None
    assert provider.last_aggregate_request_metadata["sort"] == "desc"
    assert provider.last_aggregate_request_metadata["limit"] == 50_000
    assert provider.last_aggregate_request_metadata["returned_last_timestamp"] == "2026-04-01T16:30:00+00:00"


def test_polygon_intraday_wide_range_returns_latest_not_oldest(monkeypatch) -> None:
    monkeypatch.setattr(settings, "polygon_api_key", "polygon-key")
    provider = PolygonMarketDataProvider()
    old_stamps = [
        datetime(2025, 10, 13, 14, 0, tzinfo=UTC),
        datetime(2025, 10, 13, 15, 0, tzinfo=UTC),
    ]
    latest_stamps = [
        datetime(2026, 4, 30, 14, 0, tzinfo=UTC),
        datetime(2026, 4, 30, 15, 0, tzinfo=UTC),
        datetime(2026, 4, 30, 16, 0, tzinfo=UTC),
    ]
    response_stamps_desc = list(reversed(latest_stamps)) + list(reversed(old_stamps))

    def fake_request_json(path: str, query: dict[str, str]) -> dict[str, object]:
        assert path.startswith("/v2/aggs/ticker/AAPL/range/1/hour/")
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

    assert [bar.timestamp for bar in bars] == latest_stamps
    assert len({bar.timestamp for bar in bars}) == len(bars)
    assert provider.last_aggregate_request_metadata is not None
    assert provider.last_aggregate_request_metadata["response_first_timestamp"] == "2025-10-13T14:00:00+00:00"
    assert provider.last_aggregate_request_metadata["returned_first_timestamp"] == "2026-04-30T14:00:00+00:00"
    assert provider.last_aggregate_request_metadata["returned_last_timestamp"] == "2026-04-30T16:00:00+00:00"


def test_polygon_4h_intraday_returns_latest_ascending(monkeypatch) -> None:
    monkeypatch.setattr(settings, "polygon_api_key", "polygon-key")
    provider = PolygonMarketDataProvider()
    old_stamps = [
        datetime(2025, 10, 13, 14, 0, tzinfo=UTC),
        datetime(2025, 10, 13, 18, 0, tzinfo=UTC),
    ]
    latest_stamps = [
        datetime(2026, 4, 30, 14, 0, tzinfo=UTC),
        datetime(2026, 4, 30, 18, 0, tzinfo=UTC),
    ]
    response_stamps_desc = list(reversed(latest_stamps)) + list(reversed(old_stamps))

    def fake_request_json(path: str, query: dict[str, str]) -> dict[str, object]:
        assert path.startswith("/v2/aggs/ticker/AAPL/range/4/hour/")
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

    assert [bar.timestamp for bar in bars] == latest_stamps
    assert len({bar.timestamp for bar in bars}) == len(bars)


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
    assert alpaca_entry["configured"] is True
    assert alpaca_entry["selected_provider"] == "alpaca"
    assert alpaca_entry["probe_status"] == "unavailable"
    assert alpaca_entry["readiness_scope"] == "paper_provider"

    fred_entry = next(item for item in payload["providers"] if item["provider"] == "fred")
    assert fred_entry["status"] == "configured"
    assert fred_entry["configured"] is True
    assert fred_entry["selected_provider"] == "fred"
    assert fred_entry["probe_status"] == "unavailable"
    assert fred_entry["readiness_scope"] == "macro_context"

    news_entry = next(item for item in payload["providers"] if item["provider"] == "news")
    assert news_entry["status"] == "configured"
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
    assert "blocked" in market_entry["operational_impact"].lower()


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
    assert response.json()["timeframe"] == "4H"
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
