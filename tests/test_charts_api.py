from datetime import UTC, date, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from macmarket_trader.api.main import app
from macmarket_trader.api.routes import charts as charts_routes
from macmarket_trader.charts.haco_service import HacoChartService
from macmarket_trader.domain.models import AppUserModel, DailyBarModel
from macmarket_trader.domain.schemas import Bar
from macmarket_trader.storage.db import SessionLocal, init_db


def _bars() -> list[dict[str, object]]:
    base = date(2026, 1, 1)
    return [
        {
            "date": (base + timedelta(days=i)).isoformat(),
            "open": 100 + i,
            "high": 101 + i,
            "low": 99 + i,
            "close": 100.5 + i,
            "volume": 1_000_000 + i * 10_000,
            "rel_volume": 1.2,
        }
        for i in range(60)
    ]


def setup_module() -> None:
    init_db()


def _approve_default_user(client: TestClient) -> None:
    client.get("/user/me", headers={"Authorization": "Bearer user-token"})
    with SessionLocal() as session:
        user = session.execute(select(AppUserModel).where(AppUserModel.external_auth_user_id == "clerk_user")).scalar_one()
        user.approval_status = "approved"
        session.commit()


def test_haco_chart_payload_shape() -> None:
    client = TestClient(app)
    _approve_default_user(client)
    response = client.post(
        "/charts/haco",
        headers={"Authorization": "Bearer user-token"},
        json={"symbol": "AAPL", "timeframe": "1D", "include_heikin_ashi": True, "bars": _bars()},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["candles"]
    assert payload["haco_strip"]
    assert payload["hacolt_strip"]
    assert "current_haco_state" in payload["explanation"]
    assert len(payload["candles"]) == len(payload["haco_strip"]) == len(payload["hacolt_strip"])
    candle_indices = [c["index"] for c in payload["candles"]]
    assert candle_indices == list(range(len(payload["candles"])))
    assert [p["index"] for p in payload["haco_strip"]] == candle_indices
    assert [p["index"] for p in payload["hacolt_strip"]] == candle_indices


def test_haco_flip_markers_align_to_canonical_bars() -> None:
    client = TestClient(app)
    _approve_default_user(client)
    response = client.post(
        "/charts/haco",
        headers={"Authorization": "Bearer user-token"},
        json={"symbol": "AAPL", "timeframe": "1D", "include_heikin_ashi": True, "bars": _bars()},
    )
    assert response.status_code == 200
    payload = response.json()
    candles = payload["candles"]
    marker_indices = {m["index"] for m in payload["markers"]}
    assert all(0 <= idx < len(candles) for idx in marker_indices)
    marker_times = {m["time"] for m in payload["markers"]}
    candle_times = {c["time"] for c in candles}
    assert marker_times.issubset(candle_times)


def test_haco_all_layers_share_identical_time_domain() -> None:
    client = TestClient(app)
    _approve_default_user(client)
    response = client.post(
        "/charts/haco",
        headers={"Authorization": "Bearer user-token"},
        json={"symbol": "AAPL", "timeframe": "1D", "include_heikin_ashi": True, "bars": _bars()},
    )
    assert response.status_code == 200
    payload = response.json()

    candle_by_index = {c["index"]: c["time"] for c in payload["candles"]}
    haco_by_index = {point["index"]: point["time"] for point in payload["haco_strip"]}
    hacolt_by_index = {point["index"]: point["time"] for point in payload["hacolt_strip"]}

    assert haco_by_index == candle_by_index
    assert hacolt_by_index == candle_by_index
    for marker in payload["markers"]:
        assert candle_by_index[marker["index"]] == marker["time"]


def test_haco_intraday_1h_uses_unique_unix_second_times() -> None:
    service = HacoChartService()
    bars = [
        Bar(date=date(2026, 4, 1), timestamp=datetime(2026, 4, 1, 14, 30, tzinfo=UTC), open=100, high=101, low=99, close=100.5, volume=1000),
        Bar(date=date(2026, 4, 1), timestamp=datetime(2026, 4, 1, 15, 30, tzinfo=UTC), open=101, high=102, low=100, close=101.5, volume=1100),
    ]

    payload = service.build_payload("GOOG", "1H", bars)
    times = [candle.time for candle in payload.candles]

    assert times == [int(bar.timestamp.timestamp()) for bar in bars if bar.timestamp is not None]
    assert len(times) == len(set(times))
    assert [point.time for point in payload.haco_strip] == times
    assert [point.time for point in payload.hacolt_strip] == times


def test_haco_intraday_4h_sorts_by_timestamp_for_same_market_date() -> None:
    service = HacoChartService()
    bars = [
        Bar(date=date(2026, 4, 1), timestamp=datetime(2026, 4, 1, 18, 30, tzinfo=UTC), open=104, high=105, low=103, close=104.5, volume=1200),
        Bar(date=date(2026, 4, 1), timestamp=datetime(2026, 4, 1, 14, 30, tzinfo=UTC), open=100, high=101, low=99, close=100.5, volume=1000),
    ]

    payload = service.build_payload("GOOG", "4H", bars)
    times = [candle.time for candle in payload.candles]

    assert times == sorted(int(bar.timestamp.timestamp()) for bar in bars if bar.timestamp is not None)
    assert len(times) == len(set(times))
    assert [candle.close for candle in payload.candles] == [100.5, 104.5]


def test_haco_intraday_1h_final_bar_uses_latest_provider_window() -> None:
    service = HacoChartService()
    bars = [
        Bar(date=date(2025, 10, 13), timestamp=datetime(2025, 10, 13, 14, 0, tzinfo=UTC), open=90, high=91, low=89, close=90.5, volume=1000),
        Bar(date=date(2026, 4, 30), timestamp=datetime(2026, 4, 30, 14, 0, tzinfo=UTC), open=100, high=101, low=99, close=100.5, volume=1200),
        Bar(date=date(2026, 4, 30), timestamp=datetime(2026, 4, 30, 15, 0, tzinfo=UTC), open=101, high=102, low=100, close=101.5, volume=1300),
    ]

    payload = service.build_payload("AAPL", "1H", bars)
    times = [candle.time for candle in payload.candles]

    assert times == sorted(times)
    assert len(times) == len(set(times))
    assert times[-1] == int(datetime(2026, 4, 30, 15, 0, tzinfo=UTC).timestamp())


def test_haco_intraday_4h_final_bar_uses_latest_provider_window() -> None:
    service = HacoChartService()
    bars = [
        Bar(date=date(2025, 10, 13), timestamp=datetime(2025, 10, 13, 14, 0, tzinfo=UTC), open=90, high=91, low=89, close=90.5, volume=1000),
        Bar(date=date(2026, 4, 30), timestamp=datetime(2026, 4, 30, 14, 0, tzinfo=UTC), open=100, high=101, low=99, close=100.5, volume=1200),
        Bar(date=date(2026, 4, 30), timestamp=datetime(2026, 4, 30, 18, 0, tzinfo=UTC), open=101, high=102, low=100, close=101.5, volume=1300),
    ]

    payload = service.build_payload("AAPL", "4H", bars)
    times = [candle.time for candle in payload.candles]

    assert times == sorted(times)
    assert len(times) == len(set(times))
    assert times[-1] == int(datetime(2026, 4, 30, 18, 0, tzinfo=UTC).timestamp())


def test_haco_daily_payload_keeps_date_time_values() -> None:
    service = HacoChartService()
    payload = service.build_payload(
        "GOOG",
        "1D",
        [
            Bar(date=date(2026, 4, 1), timestamp=datetime(2026, 4, 1, 14, 30, tzinfo=UTC), open=100, high=101, low=99, close=100.5, volume=1000),
            Bar(date=date(2026, 4, 2), timestamp=datetime(2026, 4, 2, 14, 30, tzinfo=UTC), open=101, high=102, low=100, close=101.5, volume=1100),
        ],
    )

    assert [candle.time for candle in payload.candles] == ["2026-04-01", "2026-04-02"]


def test_haco_intraday_resolve_does_not_use_persisted_daily_bars(monkeypatch) -> None:
    with SessionLocal() as session:
        session.add(
            DailyBarModel(
                symbol="AAPL",
                bar_date=datetime.now(tz=UTC),
                open=1,
                high=2,
                low=0.5,
                close=1.5,
                volume=100,
            )
        )
        session.commit()

    calls: list[tuple[str, str, int]] = []

    class StubMarketDataService:
        def historical_bars(self, symbol: str, timeframe: str, limit: int):
            calls.append((symbol, timeframe, limit))
            if len(calls) == 1:
                return [], "provider-empty", False
            return [
                Bar(
                    date=date(2026, 4, 1),
                    timestamp=datetime(2026, 4, 1, 14, 30, tzinfo=UTC),
                    open=100,
                    high=101,
                    low=99,
                    close=100.5,
                    volume=1000,
                )
            ], "provider-intraday", False

    monkeypatch.setattr(charts_routes, "market_data_service", StubMarketDataService())

    bars, source, fallback = charts_routes._resolve_bars("AAPL", "1H", [])

    assert source == "provider-intraday"
    assert fallback is False
    assert bars[0].timestamp is not None
    assert len(calls) == 2


def test_haco_chart_requires_auth() -> None:
    client = TestClient(app)
    response = client.post("/charts/haco", json={"symbol": "AAPL", "bars": _bars()})
    assert response.status_code == 401
