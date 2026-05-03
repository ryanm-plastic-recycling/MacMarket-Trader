import json

from fastapi.testclient import TestClient
from sqlalchemy import select

from macmarket_trader.api.main import app
from macmarket_trader.api.routes import admin as admin_routes
from macmarket_trader.domain.models import AppUserModel, RecommendationModel
from macmarket_trader.storage.db import SessionLocal


client = TestClient(app)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _seed_user(
    *,
    token: str,
    external_auth_user_id: str,
    approval_status: str = "approved",
    app_role: str = "user",
    mfa_enabled: bool = True,
) -> int:
    resp = client.get("/user/me", headers=_auth(token))
    assert resp.status_code == 200
    with SessionLocal() as session:
        user = session.execute(
            select(AppUserModel).where(AppUserModel.external_auth_user_id == external_auth_user_id)
        ).scalar_one()
        user.approval_status = approval_status
        user.app_role = app_role
        user.mfa_enabled = mfa_enabled
        session.commit()
        return user.id


def _create_recommendation(*, token: str, symbol: str = "AAPL") -> tuple[int, str]:
    resp = client.post(
        "/user/recommendations/generate",
        headers=_auth(token),
        json={
            "symbol": symbol,
            "strategy": "Event Continuation",
            "timeframe": "1D",
            "market_mode": "equities",
            "event_text": "Security-scope test seed with strong guidance follow-through.",
        },
    )
    assert resp.status_code == 200, resp.text
    recommendation_uid = resp.json()["recommendation_id"]
    listing = client.get("/user/recommendations", headers=_auth(token))
    assert listing.status_code == 200
    row = next(item for item in listing.json() if item["recommendation_id"] == recommendation_uid)
    return int(row["id"]), recommendation_uid


def test_recommendation_detail_and_approval_are_user_scoped() -> None:
    _seed_user(token="user-token", external_auth_user_id="clerk_user")
    _seed_user(token="admin-token", external_auth_user_id="clerk_admin")
    recommendation_db_id, recommendation_uid = _create_recommendation(token="user-token", symbol="AAPL")

    with SessionLocal() as session:
        row = session.execute(
            select(RecommendationModel).where(RecommendationModel.recommendation_id == recommendation_uid)
        ).scalar_one()
        payload = dict(row.payload or {})
        payload["approved"] = True
        row.payload = payload
        session.commit()

    detail = client.get(f"/user/recommendations/{recommendation_db_id}", headers=_auth("admin-token"))
    assert detail.status_code == 404

    approval = client.patch(
        f"/user/recommendations/{recommendation_uid}/approve",
        headers=_auth("admin-token"),
        json={"approved": False},
    )
    assert approval.status_code == 404

    with SessionLocal() as session:
        row = session.execute(
            select(RecommendationModel).where(RecommendationModel.recommendation_id == recommendation_uid)
        ).scalar_one()
        assert (row.payload or {}).get("approved") is True


def test_replay_and_paper_order_staging_reject_foreign_recommendation_uid() -> None:
    _seed_user(token="user-token", external_auth_user_id="clerk_user")
    _seed_user(token="admin-token", external_auth_user_id="clerk_admin")
    _, owner_recommendation_uid = _create_recommendation(token="user-token", symbol="MSFT")

    replay = client.post(
        "/user/replay-runs",
        headers=_auth("admin-token"),
        json={"guided": True, "recommendation_id": owner_recommendation_uid},
    )
    assert replay.status_code == 404

    order = client.post(
        "/user/orders",
        headers=_auth("admin-token"),
        json={"recommendation_id": owner_recommendation_uid},
    )
    assert order.status_code == 404


def test_strategy_schedule_run_now_is_user_scoped() -> None:
    _seed_user(token="user-token", external_auth_user_id="clerk_user")
    _seed_user(token="admin-token", external_auth_user_id="clerk_admin")
    created = client.post(
        "/user/strategy-schedules",
        headers=_auth("user-token"),
        json={
            "name": "Owner morning scan",
            "symbols": ["AAPL", "MSFT"],
            "enabled_strategies": ["Event Continuation"],
            "email_delivery_target": "owner@example.com",
        },
    )
    assert created.status_code == 200, created.text
    schedule_id = created.json()["id"]

    foreign_run = client.post(f"/user/strategy-schedules/{schedule_id}/run", headers=_auth("admin-token"))
    assert foreign_run.status_code == 404


def test_dashboard_counts_and_admin_metadata_are_not_global_for_regular_users() -> None:
    _seed_user(token="user-token", external_auth_user_id="clerk_user")
    _seed_user(token="admin-token", external_auth_user_id="clerk_admin")
    _create_recommendation(token="user-token", symbol="AAPL")
    _create_recommendation(token="admin-token", symbol="MSFT")

    resp = client.get("/user/dashboard", headers=_auth("user-token"))
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["counts"]["recommendations"] == 1
    assert payload["pending_admin_actions"] == []
    assert payload["recent_audit_events"] == []
    assert "/admin/users/pending" not in payload["quick_links"]


def test_suspended_admin_cannot_use_admin_routes() -> None:
    _seed_user(
        token="admin-token",
        external_auth_user_id="clerk_admin",
        approval_status="suspended",
        app_role="admin",
        mfa_enabled=True,
    )

    resp = client.get("/admin/provider-health", headers=_auth("admin-token"))
    assert resp.status_code == 403
    assert "Approval status is suspended" in resp.json()["detail"]


def test_provider_health_does_not_return_secret_values(monkeypatch) -> None:
    _seed_user(
        token="admin-token",
        external_auth_user_id="clerk_admin",
        approval_status="approved",
        app_role="admin",
        mfa_enabled=True,
    )
    fake_secret_values = [
        "sk_test_fake_clerk_secret_value",
        "sk-proj-fake-openai-secret-value",
        "fake_polygon_secret_value",
        "fake_alpaca_secret_value",
    ]
    monkeypatch.setattr(admin_routes.settings, "clerk_secret_key", fake_secret_values[0])
    monkeypatch.setattr(admin_routes.settings, "openai_api_key", fake_secret_values[1])
    monkeypatch.setattr(admin_routes.settings, "llm_api_key", fake_secret_values[1])
    monkeypatch.setattr(admin_routes.settings, "polygon_api_key", fake_secret_values[2])
    monkeypatch.setattr(admin_routes.settings, "alpaca_api_secret_key", fake_secret_values[3])

    resp = client.get("/admin/provider-health", headers=_auth("admin-token"))
    assert resp.status_code == 200
    payload_text = json.dumps(resp.json())
    for secret in fake_secret_values:
        assert secret not in payload_text
