from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from macmarket_trader.api.main import app
from macmarket_trader.api.routes import admin as admin_routes
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
            "rel_volume": 1.1,
        }
        for i in range(25)
    ]


def setup_module() -> None:
    init_db()


def _approve_default_user(client: TestClient) -> None:
    client.get('/user/me', headers={'Authorization': 'Bearer user-token'})
    with SessionLocal() as session:
        user = session.execute(select(AppUserModel).where(AppUserModel.external_auth_user_id == 'clerk_user')).scalar_one()
        user.approval_status = 'approved'
        session.commit()


def test_recommendations_generate_contract() -> None:
    client = TestClient(app)
    _approve_default_user(client)
    response = client.post(
        "/recommendations/generate",
        headers={'Authorization': 'Bearer user-token'},
        json={"symbol": "AAPL", "event_text": "Earnings beat with strong guidance", "bars": _bars()},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["thesis"]
    assert payload["catalyst"]["type"]
    assert payload["entry"]["zone_low"] < payload["targets"]["target_2"]
    assert payload["constraints"]["final_share_count"] >= payload["sizing"]["shares"]
    assert payload["evidence"]["headlines"] == []


def test_recommendation_requires_approved_user() -> None:
    client = TestClient(app)
    response = client.post('/recommendations/generate', json={"symbol": "AAPL", "event_text": "x", "bars": _bars()})
    assert response.status_code == 401


def test_user_recommendation_listing_is_data_backed() -> None:
    client = TestClient(app)
    _approve_default_user(client)
    create = client.post(
        "/recommendations/generate",
        headers={'Authorization': 'Bearer user-token'},
        json={"symbol": "AAPL", "event_text": "Earnings beat with strong guidance", "bars": _bars()},
    )
    assert create.status_code == 200

    listing = client.get("/user/recommendations", headers={'Authorization': 'Bearer user-token'})
    assert listing.status_code == 200
    rows = listing.json()
    assert len(rows) >= 1
    assert rows[0]["payload"]["thesis"]


def test_user_generation_blocks_hidden_fallback_when_provider_expected(monkeypatch) -> None:
    client = TestClient(app)
    _approve_default_user(client)

    class StubMarketData:
        def historical_bars(self, symbol: str, timeframe: str, limit: int):
            del symbol, timeframe, limit
            return _bars(), "fallback", True

    monkeypatch.setattr(admin_routes, "market_data_service", StubMarketData())
    monkeypatch.setattr(admin_routes.settings, "market_data_enabled", True)
    monkeypatch.setattr(admin_routes.settings, "polygon_enabled", False)

    response = client.post(
        "/user/recommendations/generate",
        headers={"Authorization": "Bearer user-token"},
        json={"symbol": "AAPL", "event_text": "Operator trigger"},
    )
    assert response.status_code == 503
    assert "hidden demo fallback" in response.json()["detail"]
