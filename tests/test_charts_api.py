from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from macmarket_trader.api.main import app
from macmarket_trader.domain.models import AppUserModel
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


def test_haco_chart_requires_auth() -> None:
    client = TestClient(app)
    response = client.post("/charts/haco", json={"symbol": "AAPL", "bars": _bars()})
    assert response.status_code == 401
