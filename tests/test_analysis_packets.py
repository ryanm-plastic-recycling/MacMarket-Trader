from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from macmarket_trader import analysis_packets
from macmarket_trader.api.main import app
from macmarket_trader.analysis_packets import (
    IndexContextPoint,
    IndexContextSummary,
    analysis_packet_to_safe_dict,
    build_analysis_packet,
    build_index_context_summary,
    build_macro_context_summary,
    build_news_context_summary,
    render_analysis_packet_html,
    render_analysis_packet_markdown,
)
from macmarket_trader.data.providers.market_data import IndexMarketSnapshot
from macmarket_trader.domain.models import AppUserModel
from macmarket_trader.email_templates import render_strategy_report_html, render_strategy_report_text
from macmarket_trader.storage.db import SessionLocal


client = TestClient(app)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _seed_approved_user(token: str = "user-token", external_auth_user_id: str = "clerk_user") -> int:
    resp = client.get("/user/me", headers=_auth(token))
    assert resp.status_code == 200
    with SessionLocal() as session:
        user = session.execute(
            select(AppUserModel).where(AppUserModel.external_auth_user_id == external_auth_user_id)
        ).scalar_one()
        user.approval_status = "approved"
        session.commit()
        return user.id


def test_macro_context_maps_fred_series(monkeypatch) -> None:
    monkeypatch.setattr(analysis_packets.settings, "macro_calendar_provider", "fred")
    monkeypatch.setattr(analysis_packets.settings, "fred_api_key", "fred-secret-value")

    def fake_observations(series_id: str, *, limit: int = 2):
        assert limit == 2
        return [
            {"date": "2026-05-01", "value": "4.50"},
            {"date": "2026-04-30", "value": "4.40"},
        ]

    monkeypatch.setattr(analysis_packets, "_fred_observations", fake_observations)

    summary = build_macro_context_summary(now=datetime(2026, 5, 3, tzinfo=timezone.utc))

    assert summary.mode == "fred"
    assert {item.series_id for item in summary.series} >= {"DGS10", "DGS2", "UNRATE"}
    dgs10 = next(item for item in summary.series if item.series_id == "DGS10")
    assert dgs10.latest_value == 4.5
    assert dgs10.latest_date == "2026-05-01"
    assert dgs10.recent_change == 0.1


def test_news_context_maps_polygon_fields(monkeypatch) -> None:
    class FakeNewsProvider:
        def fetch_latest(self, symbol: str):
            assert symbol == "AAPL"
            return [
                {
                    "title": "AAPL supply chain update",
                    "publisher": "Example Wire",
                    "published_utc": "2026-05-03T14:00:00Z",
                    "article_url": "https://example.test/aapl",
                    "tickers": ["AAPL"],
                    "description": "Compact provider article.",
                    "insights": [{"sentiment": "positive", "insight": "margin support"}],
                }
            ]

    monkeypatch.setattr(analysis_packets.settings, "news_provider", "polygon")
    monkeypatch.setattr(analysis_packets, "build_news_provider", lambda: FakeNewsProvider())

    summary = build_news_context_summary("aapl", now=datetime(2026, 5, 3, 15, 0, tzinfo=timezone.utc))

    assert summary.provider == "polygon"
    assert summary.count == 1
    assert summary.headlines[0].title == "AAPL supply chain update"
    assert summary.headlines[0].publisher == "Example Wire"
    assert summary.headlines[0].sentiment == "positive"
    assert summary.newest_article_age_minutes == 60


def test_index_context_maps_provider_snapshots(monkeypatch) -> None:
    monkeypatch.setattr(analysis_packets.settings, "polygon_enabled", True)

    class FakeIndexService:
        def index_snapshot(self, symbol: str) -> IndexMarketSnapshot:
            return IndexMarketSnapshot(
                symbol=symbol,
                label=f"{symbol} index",
                latest_value=5000.0 if symbol != "VIX" else 18.0,
                previous_close=4975.0 if symbol != "VIX" else 19.0,
                day_change=25.0 if symbol != "VIX" else -1.0,
                day_change_pct=0.5 if symbol != "VIX" else -5.0,
                as_of=datetime(2026, 5, 4, 14, 30, tzinfo=timezone.utc),
                stale=False,
                provider="polygon",
                missing_data=[],
            )

    summary = build_index_context_summary(
        service=FakeIndexService(),
        now=datetime(2026, 5, 4, 15, 0, tzinfo=timezone.utc),
    )

    assert summary.mode == "polygon"
    assert {item.symbol for item in summary.indices} == {"SPX", "NDX", "RUT", "VIX"}
    assert summary.risk_summary == "risk_on"
    assert not summary.missing_data


def test_equity_analysis_packet_includes_key_fields_and_boundaries(monkeypatch) -> None:
    monkeypatch.setattr(analysis_packets, "build_news_context_summary", lambda symbol: analysis_packets.NewsContextSummary(symbol=symbol, missing_data=["recent_news"]))
    monkeypatch.setattr(analysis_packets, "build_macro_context_summary", lambda: analysis_packets.MacroContextSummary(missing_data=["fred_not_selected"]))
    monkeypatch.setattr(analysis_packets, "build_index_context_summary", lambda: analysis_packets.IndexContextSummary(missing_data=["polygon_not_selected"]))

    packet = build_analysis_packet(
        symbol="GOOG",
        market_mode="equities",
        timeframe="1D",
        source_payload={
            "symbol": "GOOG",
            "side": "long",
            "thesis": "Breakout continuation",
            "entry": {"zone_low": 100, "zone_high": 101},
            "invalidation": {"price": 98},
            "targets": {"target_1": 104, "target_2": 108},
            "quality": {"confidence": 0.66, "expected_rr": 2.1},
            "sizing": {"risk_dollars": 250, "shares": 10, "notional": 1000},
            "approved": True,
        },
        market_data_source="polygon",
        fallback_mode=False,
        session_policy="regular_hours",
    )

    assert packet.equity is not None
    assert packet.equity.symbol == "GOOG"
    assert packet.equity.stop == {"price": 98}
    assert packet.equity.targets == {"target_1": 104, "target_2": 108}
    assert packet.paper_only is True
    assert packet.no_live_trading is True
    assert packet.no_broker_routing is True
    assert packet.no_automatic_exits is True


def test_options_packet_reports_greeks_and_missing_snapshot_fields() -> None:
    packet = build_analysis_packet(
        symbol="SPY",
        market_mode="options",
        timeframe="1D",
        source_payload={
            "option_structure": {
                "type": "iron_condor",
                "expiration": "2026-05-16",
                "dte": 13,
                "max_profit": 120.0,
                "max_loss": 380.0,
                "legs": [
                    {
                        "label": "short call",
                        "action": "sell",
                        "right": "call",
                        "target_strike": 520,
                        "selected_listed_strike": 520,
                        "option_symbol": "O:SPY260516C00520000",
                        "current_mark_premium": 1.24,
                        "mark_method": "quote_mid",
                        "implied_volatility": 0.22,
                        "open_interest": 1234,
                        "delta": 0.18,
                        "gamma": 0.02,
                        "theta": -0.04,
                        "vega": 0.11,
                    },
                    {"label": "short put", "action": "sell", "right": "put", "selected_listed_strike": 480},
                ],
            }
        },
        market_data_source="polygon",
        fallback_mode=False,
        session_policy="regular_hours",
    )

    assert packet.options is not None
    first_leg = packet.options.legs[0]
    assert first_leg.implied_volatility == 0.22
    assert first_leg.open_interest == 1234
    assert first_leg.delta == 0.18
    assert "options:option_snapshot_marks" in packet.missing_data


def test_strategy_report_email_uses_analysis_packet_and_redacts_secret() -> None:
    secret = "sk-test-super-secret"
    packet = {
        "symbol": "SPY",
        "market_mode": "options",
        "timeframe": "1D",
        "provider": "polygon",
        "macro_context": {"series": [{"series_id": "DGS10", "label": "10Y Treasury yield", "latest_value": 4.5, "latest_date": "2026-05-01"}]},
        "news_context": {"headlines": [{"title": "SPY headline", "publisher": "Example Wire", "published_utc": "2026-05-03T14:00:00Z"}]},
        "options": {
            "strategy_type": "iron_condor",
            "expiration": "2026-05-16",
            "days_to_expiration": 13,
            "max_profit": 120,
            "max_loss": 380,
            "legs": [
                {
                    "role": "short call",
                    "side": "short",
                    "option_type": "call",
                    "selected_listed_strike": 520,
                    "option_symbol": "O:SPY260516C00520000",
                    "current_mark_premium": 1.24,
                    "mark_method": "quote_mid",
                    "implied_volatility": 0.22,
                    "open_interest": 1234,
                    "delta": 0.18,
                    "gamma": 0.02,
                    "theta": -0.04,
                    "vega": 0.11,
                }
            ],
        },
        "missing_data": [f"provider_error:{secret}"],
    }

    html = render_strategy_report_html(
        schedule_name="Desk scan",
        ran_at="2026-05-03T15:00:00Z",
        source="polygon",
        top_candidates=[],
        watchlist_only=[],
        no_trade=[],
        summary={},
        analysis_packets=[packet],
    )
    text = render_strategy_report_text(
        schedule_name="Desk scan",
        ran_at="2026-05-03T15:00:00Z",
        source="polygon",
        top_candidates=[],
        watchlist_only=[],
        no_trade=[],
        summary={},
        analysis_packets=[packet],
    )

    combined = html + text
    assert "Analysis Packet Context" in html
    assert "Macro Context" in html
    assert "News Context" in html
    assert "SPY headline" in combined
    assert "IV 0.22" in combined
    assert "OI 1234" in combined
    assert "No live trading" in combined
    assert secret not in combined


def test_analysis_packet_markdown_html_include_context_and_unavailable_fields() -> None:
    packet = build_analysis_packet(
        symbol="SPY",
        market_mode="options",
        timeframe="1D",
        source_payload={
            "option_structure": {
                "type": "iron_condor",
                "expiration": "2026-05-16",
                "dte": 13,
                "legs": [
                    {
                        "label": "short call",
                        "action": "sell",
                        "right": "call",
                        "target_strike": 520,
                        "selected_listed_strike": 520,
                        "option_symbol": "O:SPY260516C00520000",
                        "current_mark_premium": 1.24,
                        "mark_method": "quote_mid",
                        "implied_volatility": 0.22,
                        "open_interest": 1234,
                        "delta": 0.18,
                    },
                    {"label": "short put", "action": "sell", "right": "put", "selected_listed_strike": 480},
                ],
            },
            "expected_range": {"status": "computed", "lower_bound": 500, "upper_bound": 540},
        },
        market_data_source="polygon",
        fallback_mode=False,
        session_policy="regular_hours",
        macro_context=analysis_packets.MacroContextSummary(
            mode="fred",
            series=[analysis_packets.MacroSeriesPoint(series_id="DGS10", label="10Y Treasury yield", latest_value=4.5, latest_date="2026-05-01")],
        ),
        news_context=analysis_packets.NewsContextSummary(
            provider="polygon",
            symbol="SPY",
            headlines=[analysis_packets.NewsArticleSummary(title="SPY macro desk update", publisher="Example Wire", published_utc="2026-05-03T14:00:00Z")],
        ),
        index_context=IndexContextSummary(
            indices=[
                IndexContextPoint(
                    symbol="SPX",
                    label="S&P 500",
                    latest_value=5050.0,
                    previous_close=5000.0,
                    day_change=50.0,
                    day_change_pct=1.0,
                )
            ],
            risk_summary="risk_on",
        ),
    )

    markdown = render_analysis_packet_markdown(packet)
    html = render_analysis_packet_html(packet)
    combined = markdown + html

    assert "Macro Context" in combined
    assert "Index Context" in combined
    assert "News Context" in combined
    assert "SPX" in combined
    assert "10Y Treasury yield" in combined
    assert "SPY macro desk update" in combined
    assert "IV 0.22" in combined
    assert "OI 1234" in combined
    assert "gamma Unavailable" in combined
    assert "No live trading" in combined
    assert "No broker routing" in combined


def test_analysis_packet_export_redacts_secret_like_values() -> None:
    secret = "sk-export-secret-value"
    packet = {
        "symbol": "AAPL",
        "market_mode": "equities",
        "missing_data": [f"provider_error:{secret}"],
        "provider_context": {"api_key": secret, "provider_health_summary": f"failed {secret}"},
    }

    safe = analysis_packet_to_safe_dict(packet)
    markdown = render_analysis_packet_markdown(packet)
    html = render_analysis_packet_html(packet)
    combined = str(safe) + markdown + html

    assert secret not in combined
    assert "[redacted]" in combined


def test_recommendation_analysis_packet_endpoint_is_user_scoped() -> None:
    _seed_approved_user(token="user-token", external_auth_user_id="clerk_user")
    _seed_approved_user(token="admin-token", external_auth_user_id="clerk_admin")
    create = client.post(
        "/user/recommendations/generate",
        headers=_auth("user-token"),
        json={
            "symbol": "AAPL",
            "strategy": "Event Continuation",
            "timeframe": "1D",
            "market_mode": "equities",
            "event_text": "Analysis Packet export endpoint test seed.",
        },
    )
    assert create.status_code == 200, create.text
    rec_uid = create.json()["recommendation_id"]
    listing = client.get("/user/recommendations", headers=_auth("user-token"))
    assert listing.status_code == 200
    row = next(item for item in listing.json() if item["recommendation_id"] == rec_uid)

    owner = client.get(f"/user/recommendations/{row['id']}/analysis-packet", headers=_auth("user-token"))
    assert owner.status_code == 200, owner.text
    payload = owner.json()
    assert payload["packet"]["symbol"] == "AAPL"
    assert payload["formats"] == ["json", "markdown", "html"]
    assert "Macro Context" in payload["markdown"]
    assert "News Context" in payload["markdown"]
    assert "No live trading" in payload["markdown"]
    assert payload["email_send_available"] is False
    assert payload["email_send_status"] == "deferred"

    foreign = client.get(f"/user/recommendations/{row['id']}/analysis-packet", headers=_auth("admin-token"))
    assert foreign.status_code == 404
