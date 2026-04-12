"""Phase 4 provider tests — news, macro calendar, broker."""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.error import HTTPError

import pytest

from macmarket_trader.config import settings
from macmarket_trader.data.providers.base import BrokerProvider, MacroCalendarProvider, NewsProvider
from macmarket_trader.data.providers.broker import AlpacaBrokerProvider
from macmarket_trader.data.providers.macro_calendar import FredMacroCalendarProvider
from macmarket_trader.data.providers.mock import MockBrokerProvider, MockMacroCalendarProvider, MockNewsProvider
from macmarket_trader.data.providers.news import PolygonNewsProvider
from macmarket_trader.data.providers.registry import build_broker_provider, build_macro_calendar_provider, build_news_provider


# ---------------------------------------------------------------------------
# PolygonNewsProvider
# ---------------------------------------------------------------------------


def test_polygon_news_normalization(monkeypatch) -> None:
    monkeypatch.setattr(settings, "polygon_api_key", "test-key")
    provider = PolygonNewsProvider()

    def fake_request(path: str, query: dict) -> dict:
        assert path == "/v2/reference/news"
        assert query["ticker"] == "AAPL"
        return {
            "results": [
                {
                    "id": "abc123",
                    "title": "Apple crushes earnings",
                    "published_utc": "2026-04-10T12:00:00Z",
                    "publisher": {"name": "Reuters"},
                    "article_url": "https://reuters.com/apple",
                    "description": "Apple posted record results.",
                    "keywords": ["earnings", "tech"],
                }
            ]
        }

    monkeypatch.setattr(provider, "_request_json", fake_request)
    articles = provider.fetch_latest("AAPL")

    assert len(articles) == 1
    a = articles[0]
    assert a["id"] == "abc123"
    assert a["headline"] == "Apple crushes earnings"
    assert a["symbol"] == "AAPL"
    assert a["source"] == "Reuters"
    assert a["url"] == "https://reuters.com/apple"
    assert a["published_utc"] == "2026-04-10T12:00:00Z"
    assert a["keywords"] == ["earnings", "tech"]
    assert a["description"] == "Apple posted record results."


def test_polygon_news_since_param_mapped(monkeypatch) -> None:
    monkeypatch.setattr(settings, "polygon_api_key", "test-key")
    provider = PolygonNewsProvider()
    captured: dict = {}

    def fake_request(path: str, query: dict) -> dict:
        captured.update(query)
        return {"results": []}

    monkeypatch.setattr(provider, "_request_json", fake_request)
    since = datetime(2026, 4, 1, 9, 30, tzinfo=UTC)
    provider.fetch_latest("TSLA", since=since)

    assert captured.get("published_utc.gte") == "2026-04-01T09:30:00Z"
    assert captured.get("ticker") == "TSLA"
    assert "published_utc.gte" not in captured or captured["published_utc.gte"] == "2026-04-01T09:30:00Z"


def test_polygon_news_no_since_omits_filter(monkeypatch) -> None:
    monkeypatch.setattr(settings, "polygon_api_key", "test-key")
    provider = PolygonNewsProvider()
    captured: dict = {}

    def fake_request(path: str, query: dict) -> dict:
        captured.update(query)
        return {"results": []}

    monkeypatch.setattr(provider, "_request_json", fake_request)
    provider.fetch_latest("MSFT")

    assert "published_utc.gte" not in captured


def test_polygon_news_http_error_returns_empty(monkeypatch) -> None:
    monkeypatch.setattr(settings, "polygon_api_key", "test-key")
    provider = PolygonNewsProvider()

    def fake_request(path: str, query: dict) -> dict:
        raise HTTPError(
            url="https://api.polygon.io/v2/reference/news",
            code=429,
            msg="Too Many Requests",
            hdrs=None,  # type: ignore[arg-type]
            fp=None,
        )

    monkeypatch.setattr(provider, "_request_json", fake_request)
    assert provider.fetch_latest("AAPL") == []


def test_polygon_news_empty_results(monkeypatch) -> None:
    monkeypatch.setattr(settings, "polygon_api_key", "test-key")
    provider = PolygonNewsProvider()
    monkeypatch.setattr(provider, "_request_json", lambda path, query: {"results": []})
    assert provider.fetch_latest("NFLX") == []


def test_polygon_news_missing_results_key(monkeypatch) -> None:
    monkeypatch.setattr(settings, "polygon_api_key", "test-key")
    provider = PolygonNewsProvider()
    monkeypatch.setattr(provider, "_request_json", lambda path, query: {})
    assert provider.fetch_latest("SPY") == []


def test_polygon_news_symbol_uppercased(monkeypatch) -> None:
    monkeypatch.setattr(settings, "polygon_api_key", "test-key")
    provider = PolygonNewsProvider()
    captured: dict = {}

    def fake_request(path: str, query: dict) -> dict:
        captured.update(query)
        return {"results": []}

    monkeypatch.setattr(provider, "_request_json", fake_request)
    provider.fetch_latest("aapl")
    assert captured["ticker"] == "AAPL"


def test_polygon_news_respects_max_articles_setting(monkeypatch) -> None:
    monkeypatch.setattr(settings, "polygon_api_key", "test-key")
    monkeypatch.setattr(settings, "news_polygon_max_articles", 5)
    provider = PolygonNewsProvider()
    captured: dict = {}

    def fake_request(path: str, query: dict) -> dict:
        captured.update(query)
        return {"results": []}

    monkeypatch.setattr(provider, "_request_json", fake_request)
    provider.fetch_latest("GOOG")
    assert captured["limit"] == "5"


def test_polygon_news_provider_implements_base(monkeypatch) -> None:
    monkeypatch.setattr(settings, "polygon_api_key", "key")
    assert isinstance(PolygonNewsProvider(), NewsProvider)


# ---------------------------------------------------------------------------
# build_news_provider factory
# ---------------------------------------------------------------------------


def test_build_news_provider_default_returns_mock(monkeypatch) -> None:
    monkeypatch.setattr(settings, "news_provider", "mock")
    assert isinstance(build_news_provider(), MockNewsProvider)


def test_build_news_provider_polygon(monkeypatch) -> None:
    monkeypatch.setattr(settings, "news_provider", "polygon")
    monkeypatch.setattr(settings, "polygon_api_key", "key")
    assert isinstance(build_news_provider(), PolygonNewsProvider)


def test_build_news_provider_unknown_falls_back_to_mock(monkeypatch) -> None:
    monkeypatch.setattr(settings, "news_provider", "unknown_provider")
    assert isinstance(build_news_provider(), MockNewsProvider)


# ---------------------------------------------------------------------------
# FredMacroCalendarProvider
# ---------------------------------------------------------------------------


def test_fred_macro_normalization(monkeypatch) -> None:
    monkeypatch.setattr(settings, "fred_api_key", "test-key")
    provider = FredMacroCalendarProvider()
    from_ts = datetime(2026, 4, 12, tzinfo=UTC)
    to_ts = datetime(2026, 4, 30, tzinfo=UTC)

    def fake_request(path: str, query: dict) -> dict:
        assert path == "/releases/dates"
        assert query["realtime_start"] == "2026-04-12"
        assert query["realtime_end"] == "2026-04-30"
        return {
            "release_dates": [
                {"release_id": 10, "release_name": "Consumer Price Index", "date": "2026-04-15"},
                {"release_id": 13, "release_name": "G.17 Industrial Production", "date": "2026-04-17"},
            ]
        }

    monkeypatch.setattr(provider, "_request_json", fake_request)
    events = provider.upcoming_events(from_ts, to_ts)

    assert len(events) == 2
    assert events[0]["event"] == "Consumer Price Index"
    assert events[0]["date"] == "2026-04-15"
    assert events[0]["release_id"] == 10
    assert events[1]["event"] == "G.17 Industrial Production"
    assert events[1]["release_id"] == 13


def test_fred_macro_from_to_preserved(monkeypatch) -> None:
    monkeypatch.setattr(settings, "fred_api_key", "test-key")
    provider = FredMacroCalendarProvider()
    from_ts = datetime(2026, 4, 12, tzinfo=UTC)
    to_ts = datetime(2026, 4, 20, tzinfo=UTC)

    monkeypatch.setattr(
        provider,
        "_request_json",
        lambda path, query: {"release_dates": [{"release_id": 1, "release_name": "FOMC", "date": "2026-04-15"}]},
    )
    events = provider.upcoming_events(from_ts, to_ts)

    assert events[0]["from"] == from_ts.isoformat()
    assert events[0]["to"] == to_ts.isoformat()


def test_fred_macro_http_error_returns_empty(monkeypatch) -> None:
    monkeypatch.setattr(settings, "fred_api_key", "test-key")
    provider = FredMacroCalendarProvider()

    def fake_request(path: str, query: dict) -> dict:
        raise HTTPError(
            url="https://api.stlouisfed.org/fred/releases/dates",
            code=403,
            msg="Forbidden",
            hdrs=None,  # type: ignore[arg-type]
            fp=None,
        )

    monkeypatch.setattr(provider, "_request_json", fake_request)
    assert provider.upcoming_events(datetime(2026, 4, 12, tzinfo=UTC), datetime(2026, 4, 30, tzinfo=UTC)) == []


def test_fred_macro_empty_release_dates(monkeypatch) -> None:
    monkeypatch.setattr(settings, "fred_api_key", "test-key")
    provider = FredMacroCalendarProvider()
    monkeypatch.setattr(provider, "_request_json", lambda path, query: {"release_dates": []})
    assert provider.upcoming_events(datetime(2026, 4, 12, tzinfo=UTC), datetime(2026, 4, 30, tzinfo=UTC)) == []


def test_fred_macro_implements_base(monkeypatch) -> None:
    monkeypatch.setattr(settings, "fred_api_key", "key")
    assert isinstance(FredMacroCalendarProvider(), MacroCalendarProvider)


# ---------------------------------------------------------------------------
# build_macro_calendar_provider factory
# ---------------------------------------------------------------------------


def test_build_macro_provider_default_returns_mock(monkeypatch) -> None:
    monkeypatch.setattr(settings, "macro_calendar_provider", "mock")
    assert isinstance(build_macro_calendar_provider(), MockMacroCalendarProvider)


def test_build_macro_provider_fred(monkeypatch) -> None:
    monkeypatch.setattr(settings, "macro_calendar_provider", "fred")
    monkeypatch.setattr(settings, "fred_api_key", "key")
    assert isinstance(build_macro_calendar_provider(), FredMacroCalendarProvider)


def test_build_macro_provider_unknown_falls_back_to_mock(monkeypatch) -> None:
    monkeypatch.setattr(settings, "macro_calendar_provider", "unknown")
    assert isinstance(build_macro_calendar_provider(), MockMacroCalendarProvider)


# ---------------------------------------------------------------------------
# AlpacaBrokerProvider
# ---------------------------------------------------------------------------


def test_alpaca_broker_order_payload(monkeypatch) -> None:
    monkeypatch.setattr(settings, "alpaca_api_key_id", "key")
    monkeypatch.setattr(settings, "alpaca_api_secret_key", "secret")
    monkeypatch.setattr(settings, "alpaca_paper_base_url", "https://paper-api.alpaca.markets")
    provider = AlpacaBrokerProvider()
    captured_body: dict = {}

    def fake_post(path: str, body: dict) -> dict:
        assert path == "/v2/orders"
        captured_body.update(body)
        return {
            "id": "order-uuid-123",
            "symbol": "AAPL",
            "side": "buy",
            "qty": "10",
            "limit_price": "150.00",
            "status": "accepted",
            "submitted_at": "2026-04-12T10:00:00Z",
        }

    monkeypatch.setattr(provider, "_post_json", fake_post)
    result = provider.place_paper_order("AAPL", "buy", 10, 150.0)

    assert captured_body["symbol"] == "AAPL"
    assert captured_body["side"] == "buy"
    assert captured_body["type"] == "limit"
    assert captured_body["qty"] == "10"
    assert captured_body["limit_price"] == "150.0"
    assert captured_body["time_in_force"] == "day"

    assert result["order_id"] == "order-uuid-123"
    assert result["symbol"] == "AAPL"
    assert result["side"] == "buy"
    assert result["shares"] == 10
    assert result["limit_price"] == 150.0
    assert result["status"] == "accepted"
    assert result["provider"] == "alpaca_paper"


def test_alpaca_broker_symbol_uppercased(monkeypatch) -> None:
    monkeypatch.setattr(settings, "alpaca_api_key_id", "key")
    monkeypatch.setattr(settings, "alpaca_api_secret_key", "secret")
    provider = AlpacaBrokerProvider()
    captured_body: dict = {}

    def fake_post(path: str, body: dict) -> dict:
        captured_body.update(body)
        return {"id": "x", "symbol": "TSLA", "side": "sell", "qty": "5", "limit_price": "200.0", "status": "accepted", "submitted_at": "2026-04-12T10:00:00Z"}

    monkeypatch.setattr(provider, "_post_json", fake_post)
    provider.place_paper_order("tsla", "sell", 5, 200.0)
    assert captured_body["symbol"] == "TSLA"
    assert captured_body["side"] == "sell"


def test_alpaca_broker_limit_price_rounded(monkeypatch) -> None:
    monkeypatch.setattr(settings, "alpaca_api_key_id", "key")
    monkeypatch.setattr(settings, "alpaca_api_secret_key", "secret")
    provider = AlpacaBrokerProvider()
    captured_body: dict = {}

    def fake_post(path: str, body: dict) -> dict:
        captured_body.update(body)
        return {"id": "x", "symbol": "META", "side": "buy", "qty": "3", "limit_price": "500.12", "status": "accepted", "submitted_at": "2026-04-12T10:00:00Z"}

    monkeypatch.setattr(provider, "_post_json", fake_post)
    provider.place_paper_order("META", "buy", 3, 500.123456)
    assert captured_body["limit_price"] == "500.12"


def test_alpaca_broker_implements_base(monkeypatch) -> None:
    monkeypatch.setattr(settings, "alpaca_api_key_id", "key")
    monkeypatch.setattr(settings, "alpaca_api_secret_key", "secret")
    assert isinstance(AlpacaBrokerProvider(), BrokerProvider)


# ---------------------------------------------------------------------------
# MockBrokerProvider
# ---------------------------------------------------------------------------


def test_mock_broker_returns_accepted_dict() -> None:
    provider = MockBrokerProvider()
    result = provider.place_paper_order("NVDA", "buy", 7, 900.0)

    assert result["symbol"] == "NVDA"
    assert result["side"] == "buy"
    assert result["shares"] == 7
    assert result["limit_price"] == 900.0
    assert result["status"] == "accepted"
    assert result["provider"] == "mock"
    assert "order_id" in result
    assert "submitted_at" in result


def test_mock_broker_implements_base() -> None:
    assert isinstance(MockBrokerProvider(), BrokerProvider)


# ---------------------------------------------------------------------------
# build_broker_provider factory
# ---------------------------------------------------------------------------


def test_build_broker_provider_default_returns_mock(monkeypatch) -> None:
    monkeypatch.setattr(settings, "broker_provider", "mock")
    assert isinstance(build_broker_provider(), MockBrokerProvider)


def test_build_broker_provider_alpaca(monkeypatch) -> None:
    monkeypatch.setattr(settings, "broker_provider", "alpaca")
    monkeypatch.setattr(settings, "alpaca_api_key_id", "key")
    monkeypatch.setattr(settings, "alpaca_api_secret_key", "secret")
    assert isinstance(build_broker_provider(), AlpacaBrokerProvider)


def test_build_broker_provider_unknown_falls_back_to_mock(monkeypatch) -> None:
    monkeypatch.setattr(settings, "broker_provider", "unknown")
    assert isinstance(build_broker_provider(), MockBrokerProvider)
