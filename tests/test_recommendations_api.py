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
        json={"symbol": "AAPL", "market_mode": "equities", "event_text": "Earnings beat with strong guidance", "bars": _bars()},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["thesis"]
    assert payload["market_mode"] == "equities"
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


def test_user_generation_non_equity_generates_recommendation() -> None:
    client = TestClient(app)
    _approve_default_user(client)
    response = client.post(
        "/user/recommendations/generate",
        headers={"Authorization": "Bearer user-token"},
        json={"symbol": "AAPL", "market_mode": "options", "event_text": "Iron condor research setup"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert "id" in payload
    assert payload["market_mode"] == "options"


def test_user_ranked_recommendation_queue_contract() -> None:
    client = TestClient(app)
    _approve_default_user(client)
    response = client.post(
        "/user/recommendations/queue",
        headers={"Authorization": "Bearer user-token"},
        json={"symbols": ["AAPL", "MSFT"], "timeframe": "1D", "market_mode": "equities", "top_n": 5},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["queue"]
    first = payload["queue"][0]
    for key in [
        "rank",
        "symbol",
        "strategy",
        "timeframe",
        "market_mode",
        "workflow_source",
        "status",
        "score",
        "score_breakdown",
        "expected_rr",
        "confidence",
        "thesis",
        "trigger",
        "entry_zone",
        "invalidation",
        "targets",
        "reason_text",
    ]:
        assert key in first


def test_user_ranked_queue_candidate_can_be_promoted() -> None:
    client = TestClient(app)
    _approve_default_user(client)
    queue = client.post(
        "/user/recommendations/queue",
        headers={"Authorization": "Bearer user-token"},
        json={"symbols": ["AAPL"], "market_mode": "equities"},
    )
    assert queue.status_code == 200
    candidate = queue.json()["queue"][0]

    promote = client.post(
        "/user/recommendations/queue/promote",
        headers={"Authorization": "Bearer user-token"},
        json=candidate,
    )
    assert promote.status_code == 200
    promoted = promote.json()
    assert promoted["symbol"] == "AAPL"
    assert promoted["recommendation_id"]

    detail = client.get(f"/user/recommendations/{promoted['id']}", headers={"Authorization": "Bearer user-token"})
    assert detail.status_code == 200
    detail_payload = detail.json()
    workflow = detail_payload["payload"]["workflow"]

    assert workflow["market_data_source"] == promoted["market_data_source"]
    assert workflow["fallback_mode"] == promoted["fallback_mode"]
    assert workflow["ranking_provenance"]["symbol"] == candidate["symbol"]
    assert workflow["ranking_provenance"]["strategy"] == candidate["strategy"]
    assert workflow["ranking_provenance"]["rank"] == candidate["rank"]
    assert workflow["ranking_provenance"]["score_breakdown"] == candidate["score_breakdown"]

    listing = client.get("/user/recommendations", headers={"Authorization": "Bearer user-token"})
    assert listing.status_code == 200
    match = next(row for row in listing.json() if row["id"] == promoted["id"])
    assert match["payload"]["workflow"]["ranking_provenance"]["reason_text"] == candidate["reason_text"]
