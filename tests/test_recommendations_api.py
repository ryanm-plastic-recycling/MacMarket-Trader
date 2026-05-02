from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from macmarket_trader.api.main import app
from macmarket_trader.api.routes import admin as admin_routes
from macmarket_trader.data.providers.market_data import DeterministicFallbackMarketDataProvider
from macmarket_trader.domain.models import AppUserModel
from macmarket_trader.storage.db import SessionLocal, init_db
from macmarket_trader.storage.repositories import PaperPortfolioRepository


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


def _approve_default_user(client: TestClient) -> int:
    client.get('/user/me', headers={'Authorization': 'Bearer user-token'})
    with SessionLocal() as session:
        user = session.execute(select(AppUserModel).where(AppUserModel.external_auth_user_id == 'clerk_user')).scalar_one()
        user.approval_status = 'approved'
        session.commit()
        return user.id


def _seed_open_position(app_user_id: int, *, symbol: str, quantity: float = 12, entry: float = 101.25) -> int:
    position = PaperPortfolioRepository(SessionLocal).create_position(
        app_user_id=app_user_id,
        symbol=symbol,
        side="long",
        quantity=quantity,
        average_price=entry,
        recommendation_id=None,
        order_id=f"test-{symbol.lower()}-open",
    )
    return position.id


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
    assert payload["recommendation_id"] == payload["id"]
    assert payload["market_mode"] == "options"


def test_user_generation_uses_requested_timeframe(monkeypatch) -> None:
    calls: list[tuple[str, str, int]] = []

    class StubMarketData:
        def historical_bars(self, symbol: str, timeframe: str, limit: int):
            calls.append((symbol, timeframe, limit))
            return DeterministicFallbackMarketDataProvider().fetch_historical_bars(symbol, timeframe, limit), "polygon", False

    monkeypatch.setattr(admin_routes, "market_data_service", StubMarketData())

    client = TestClient(app)
    _approve_default_user(client)
    response = client.post(
        "/user/recommendations/generate",
        headers={"Authorization": "Bearer user-token"},
        json={"symbol": "GOOG", "timeframe": "1H", "event_text": "Operator trigger"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert calls == [("GOOG", "1H", 60)]
    assert payload["session_policy"] == "regular_hours"


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
        "recommendation_id",
        "risk_calendar",
    ]:
        assert key in first
    assert first["recommendation_id"].startswith("queue:")
    assert first["already_open"] is False
    assert first["open_position_id"] is None
    assert first["risk_calendar"]["decision"]["decision_state"] in {
        "normal",
        "caution",
        "restricted",
        "no_trade",
        "requires_event_evidence",
        "data_quality_block",
    }


def test_user_ranked_recommendation_queue_uses_requested_timeframe(monkeypatch) -> None:
    calls: list[tuple[str, str, int]] = []

    class StubMarketData:
        def historical_bars(self, symbol: str, timeframe: str, limit: int):
            calls.append((symbol, timeframe, limit))
            return DeterministicFallbackMarketDataProvider().fetch_historical_bars(symbol, timeframe, limit), "polygon", False

    monkeypatch.setattr(admin_routes, "market_data_service", StubMarketData())

    client = TestClient(app)
    _approve_default_user(client)
    response = client.post(
        "/user/recommendations/queue",
        headers={"Authorization": "Bearer user-token"},
        json={"symbols": ["GOOG"], "timeframe": "1H", "market_mode": "equities", "top_n": 1},
    )

    assert response.status_code == 200
    assert response.json()["timeframe"] == "1H"
    assert response.json()["queue"][0]["session_policy"] == "regular_hours"
    assert response.json()["queue"][0]["data_quality"]["source_timeframe"] == "1H"
    assert calls == [("GOOG", "1H", 120)]


def test_user_ranked_queue_marks_already_open_symbol_without_changing_rank_or_score() -> None:
    client = TestClient(app)
    user_id = _approve_default_user(client)
    baseline = client.post(
        "/user/recommendations/queue",
        headers={"Authorization": "Bearer user-token"},
        json={"symbols": ["GOOG", "MSFT"], "timeframe": "1D", "market_mode": "equities", "top_n": 10},
    )
    assert baseline.status_code == 200
    baseline_goog = next(item for item in baseline.json()["queue"] if item["symbol"] == "GOOG")

    position_id = _seed_open_position(user_id, symbol="GOOG", quantity=14, entry=102.5)
    response = client.post(
        "/user/recommendations/queue",
        headers={"Authorization": "Bearer user-token"},
        json={"symbols": ["GOOG", "MSFT"], "timeframe": "1D", "market_mode": "equities", "top_n": 10},
    )

    assert response.status_code == 200
    queue = response.json()["queue"]
    goog = next(item for item in queue if item["symbol"] == "GOOG" and item["strategy"] == baseline_goog["strategy"])
    msft = next(item for item in queue if item["symbol"] == "MSFT")
    assert goog["already_open"] is True
    assert goog["open_position_id"] == position_id
    assert goog["open_position_quantity"] == 14
    assert goog["open_position_average_entry"] == 102.5
    assert goog["open_position_review_path"] == "/orders#active-position-review"
    assert goog["rank"] == baseline_goog["rank"]
    assert goog["score"] == baseline_goog["score"]
    assert goog["status"] == baseline_goog["status"]
    assert msft["already_open"] is False
    assert msft["open_position_id"] is None


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


def test_stored_recommendation_marks_already_open_symbol_in_list_detail_and_promote() -> None:
    client = TestClient(app)
    user_id = _approve_default_user(client)
    create = client.post(
        "/user/recommendations/generate",
        headers={"Authorization": "Bearer user-token"},
        json={"symbol": "GOOG", "event_text": "Operator trigger"},
    )
    assert create.status_code == 200
    rec_id = create.json()["recommendation_id"]
    position_id = _seed_open_position(user_id, symbol="GOOG", quantity=9, entry=100.0)

    listing = client.get("/user/recommendations", headers={"Authorization": "Bearer user-token"})
    assert listing.status_code == 200
    row = next(item for item in listing.json() if item["recommendation_id"] == rec_id)
    assert row["already_open"] is True
    assert row["open_position_id"] == position_id
    assert row["open_position_quantity"] == 9
    assert row["open_position_average_entry"] == 100.0

    detail = client.get(f"/user/recommendations/{row['id']}", headers={"Authorization": "Bearer user-token"})
    assert detail.status_code == 200
    assert detail.json()["already_open"] is True
    assert detail.json()["open_position_id"] == position_id

    queue = client.post(
        "/user/recommendations/queue",
        headers={"Authorization": "Bearer user-token"},
        json={"symbols": ["GOOG"], "market_mode": "equities", "top_n": 1},
    )
    assert queue.status_code == 200
    promote = client.post(
        "/user/recommendations/queue/promote",
        headers={"Authorization": "Bearer user-token"},
        json=queue.json()["queue"][0],
    )
    assert promote.status_code == 200
    promoted = promote.json()
    assert promoted["already_open"] is True
    assert promoted["open_position_id"] == position_id
    assert "order_id" not in promoted


def test_promoted_recommendation_provenance_timeframe_matches_bars_used(monkeypatch) -> None:
    calls: list[tuple[str, str, int]] = []

    class StubMarketData:
        def historical_bars(self, symbol: str, timeframe: str, limit: int):
            calls.append((symbol, timeframe, limit))
            return DeterministicFallbackMarketDataProvider().fetch_historical_bars(symbol, timeframe, limit), "polygon", False

    monkeypatch.setattr(admin_routes, "market_data_service", StubMarketData())

    client = TestClient(app)
    _approve_default_user(client)
    queue = client.post(
        "/user/recommendations/queue",
        headers={"Authorization": "Bearer user-token"},
        json={"symbols": ["GOOG"], "timeframe": "4H", "market_mode": "equities", "top_n": 1},
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

    detail = client.get(f"/user/recommendations/{promoted['id']}", headers={"Authorization": "Bearer user-token"})
    workflow = detail.json()["payload"]["workflow"]

    assert calls == [("GOOG", "4H", 120), ("GOOG", "4H", 60)]
    assert workflow["ranking_provenance"]["timeframe"] == "4H"
    assert workflow["session_policy"] == "regular_hours"
    assert workflow["ranking_provenance"]["data_quality"]["session_policy"] == "regular_hours"


def test_user_ranked_queue_candidate_can_be_saved_as_alternative() -> None:
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
        json={**candidate, "action": "save_alternative"},
    )
    assert promote.status_code == 200
    result = promote.json()
    assert result["symbol"] == "AAPL"
    assert result["recommendation_id"]
    assert result["action"] == "save_alternative"

    detail = client.get(f"/user/recommendations/{result['id']}", headers={"Authorization": "Bearer user-token"})
    assert detail.status_code == 200
    workflow = detail.json()["payload"]["workflow"]
    assert workflow["ranking_provenance"]["action"] == "save_alternative"
    assert workflow["ranking_provenance"]["symbol"] == candidate["symbol"]
