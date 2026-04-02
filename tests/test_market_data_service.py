from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from macmarket_trader.api.main import app
from macmarket_trader.api.routes import admin as admin_routes
from macmarket_trader.config import settings
from macmarket_trader.data.providers.market_data import AlpacaMarketDataProvider, MarketDataService, MarketProviderHealth


def test_market_data_fallback_when_alpaca_not_configured(monkeypatch) -> None:
    monkeypatch.setattr(settings, "market_data_provider", "alpaca")
    monkeypatch.setattr(settings, "market_data_enabled", False)

    service = MarketDataService()
    bars, source, fallback_mode = service.historical_bars("AAPL", "1D", 40)

    assert len(bars) == 40
    assert source == "deterministic_fallback"
    assert fallback_mode is True


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
    assert bars[0].open == 190.1
    assert bars[1].close == 193.0
    assert bars[1].volume == 150000


def test_latest_snapshot_normalization(monkeypatch) -> None:
    monkeypatch.setattr(settings, "alpaca_api_key_id", "key")
    monkeypatch.setattr(settings, "alpaca_api_secret_key", "secret")
    provider = AlpacaMarketDataProvider()

    def fake_request_json(path: str, query: dict[str, str]) -> dict[str, object]:
        assert path == "/v2/stocks/bars/latest"
        return {
            "bars": {
                "AAPL": {"t": "2026-04-02T19:59:00Z", "o": 190.5, "h": 191.0, "l": 190.4, "c": 190.9, "v": 22000}
            }
        }

    monkeypatch.setattr(provider, "_request_json", fake_request_json)
    snapshot = provider.fetch_latest_snapshot(symbol="AAPL", timeframe="1D")

    assert snapshot.symbol == "AAPL"
    assert snapshot.source == "alpaca_latest_bar"
    assert snapshot.close == 190.9
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
                source="alpaca_latest_bar",
                fallback_mode=False,
            )

        def provider_health(self, sample_symbol: str = "AAPL") -> MarketProviderHealth:
            return MarketProviderHealth(
                provider="market_data",
                mode="alpaca",
                status="ok",
                details="Alpaca latest bar probe succeeded.",
                configured=True,
                feed="iex",
                sample_symbol=sample_symbol,
                latency_ms=12.4,
                last_success_at=datetime(2026, 4, 2, tzinfo=UTC),
            )

    monkeypatch.setattr(admin_routes, "market_data_service", StubMarketDataService())

    client = TestClient(app)
    response = client.get("/admin/provider-health", headers={"Authorization": "Bearer admin-token"})
    assert response.status_code == 200
    payload = response.json()
    market_entry = next(item for item in payload["providers"] if item["provider"] == "market_data")
    assert market_entry["mode"] == "alpaca"
    assert market_entry["status"] == "ok"
    assert market_entry["feed"] == "iex"
    assert market_entry["sample_symbol"] == "AAPL"
    assert market_entry["latency_ms"] == 12.4
    assert market_entry["last_success_at"].startswith("2026-04-02")
