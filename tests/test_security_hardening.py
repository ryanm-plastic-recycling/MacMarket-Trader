from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from macmarket_trader.api import security
from macmarket_trader.api.main import _api_docs_kwargs, app
from macmarket_trader.domain.models import AppInviteModel, AppUserModel
from macmarket_trader.storage.db import SessionLocal


client = TestClient(app)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _seed_user(
    *,
    token: str = "user-token",
    external_id: str = "clerk_user",
    approval_status: str = "approved",
    app_role: str = "user",
) -> int:
    resp = client.get("/user/me", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    with SessionLocal() as session:
        user = session.execute(
            select(AppUserModel).where(AppUserModel.external_auth_user_id == external_id)
        ).scalar_one()
        user.approval_status = approval_status
        user.app_role = app_role
        user.mfa_enabled = True
        session.commit()
        return int(user.id)


def _bars(count: int) -> list[dict[str, object]]:
    base = date(2026, 1, 1)
    return [
        {
            "date": (base + timedelta(days=idx)).isoformat(),
            "open": 100 + idx,
            "high": 101 + idx,
            "low": 99 + idx,
            "close": 100.5 + idx,
            "volume": 1_000_000,
        }
        for idx in range(count)
    ]


def test_high_cost_provider_health_is_rate_limited(monkeypatch) -> None:
    security.rate_limiter.reset()
    monkeypatch.setitem(
        security.HIGH_COST_ROUTE_LIMITS,
        "/admin/provider-health",
        security.RateLimit(limit=2, window_seconds=60),
    )
    _seed_user(token="admin-token", external_id="clerk_admin", app_role="admin")

    assert client.get("/admin/provider-health", headers=_auth("admin-token")).status_code == 200
    assert client.get("/admin/provider-health", headers=_auth("admin-token")).status_code == 200
    limited = client.get("/admin/provider-health", headers=_auth("admin-token"))

    assert limited.status_code == 429
    assert limited.headers["Retry-After"]
    assert limited.json()["detail"] == "Rate limit exceeded."
    security.rate_limiter.reset()


def test_mutating_backend_route_rejects_unexpected_origin() -> None:
    resp = client.post(
        "/user/recommendations/queue",
        headers={**_auth("user-token"), "Origin": "https://evil.example"},
        json={"symbols": ["AAPL"], "market_mode": "equities"},
    )

    assert resp.status_code == 403
    assert resp.json()["detail"] == "Request origin is not allowed."


def test_mutating_backend_route_allows_configured_origin() -> None:
    _seed_user()
    resp = client.post(
        "/user/recommendations/queue",
        headers={**_auth("user-token"), "Origin": "https://macmarket.io"},
        json={"symbols": ["AAPL"], "market_mode": "equities", "top_n": 1},
    )

    assert resp.status_code == 200, resp.text


def test_recommendation_queue_caps_bulk_symbols_and_top_n() -> None:
    _seed_user()
    too_many_symbols = [f"A{idx}" for idx in range(security.MAX_BULK_SYMBOLS + 1)]
    too_many = client.post(
        "/user/recommendations/queue",
        headers=_auth("user-token"),
        json={"symbols": too_many_symbols, "market_mode": "equities"},
    )
    assert too_many.status_code == 400
    assert "at most" in too_many.json()["detail"]

    top_n = client.post(
        "/user/recommendations/queue",
        headers=_auth("user-token"),
        json={"symbols": ["AAPL"], "market_mode": "equities", "top_n": security.MAX_QUEUE_TOP_N + 1},
    )
    assert top_n.status_code == 400
    assert "top_n" in top_n.json()["detail"]


def test_watchlist_rejects_invalid_symbol() -> None:
    _seed_user()
    resp = client.post(
        "/user/watchlists",
        headers=_auth("user-token"),
        json={"name": "Bad symbols", "symbols": ["AAPL", "bad<script>"]},
    )

    assert resp.status_code == 400
    assert "watchlist symbols" in resp.json()["detail"]


def test_haco_chart_rejects_oversized_request_bars() -> None:
    _seed_user()
    resp = client.post(
        "/charts/haco",
        headers=_auth("user-token"),
        json={"symbol": "AAPL", "timeframe": "1D", "bars": _bars(501)},
    )

    assert resp.status_code == 422


def test_production_fastapi_docs_are_disabled_by_default() -> None:
    assert _api_docs_kwargs("production", True) == {
        "docs_url": None,
        "redoc_url": None,
        "openapi_url": None,
    }
    assert _api_docs_kwargs("test", True)["docs_url"] == "/docs"


def test_admin_invite_tokens_are_masked_in_api_payloads() -> None:
    _seed_user(token="admin-token", external_id="clerk_admin", app_role="admin")
    created = client.post(
        "/admin/invites",
        headers=_auth("admin-token"),
        json={"email": "masked-invite@example.com", "display_name": "Masked Invite"},
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["invite_token_masked"] is True

    with SessionLocal() as session:
        row = session.execute(
            select(AppInviteModel).where(AppInviteModel.email == "masked-invite@example.com")
        ).scalar_one()
        actual_token = row.invite_token

    assert body["invite_token"] != actual_token
    assert "..." in body["invite_token"]

    listing = client.get("/admin/invites", headers=_auth("admin-token"))
    listed = next(item for item in listing.json() if item["email"] == "masked-invite@example.com")
    assert listed["invite_token"] != actual_token
    assert listed["invite_token_masked"] is True
