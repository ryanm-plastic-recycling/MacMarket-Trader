"""Pass 4 backend gates — Track A (display_id) and Track B (per-user
risk_dollars_per_trade)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from macmarket_trader.api.main import app
from macmarket_trader.config import settings
from macmarket_trader.domain.models import AppUserModel, RecommendationModel
from macmarket_trader.storage.db import SessionLocal
from macmarket_trader.storage.repositories import (
    _abbreviate_strategy,
    display_id_or_fallback,
    make_display_id,
)


client = TestClient(app)
_USER_AUTH = {"Authorization": "Bearer user-token"}


def _seed_approved_user(token: str = "user-token", external_id: str = "clerk_user") -> int:
    resp = client.get("/user/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    with SessionLocal() as session:
        user = session.execute(
            select(AppUserModel).where(AppUserModel.external_auth_user_id == external_id)
        ).scalar_one()
        user.approval_status = "approved"
        session.commit()
        return user.id


# ---------------------------------------------------------------------------
# Track A — display_id helper unit gates
# ---------------------------------------------------------------------------

class TestDisplayIdHelper:
    def test_known_strategy_event_continuation(self) -> None:
        assert _abbreviate_strategy("Event Continuation") == "EVCONT"

    def test_known_strategy_breakout(self) -> None:
        assert _abbreviate_strategy("Breakout / Prior-Day High") == "BRKOUT"

    def test_known_strategy_pullback(self) -> None:
        assert _abbreviate_strategy("Pullback / Trend Continuation") == "PULLBK"

    def test_known_strategy_iron_condor(self) -> None:
        assert _abbreviate_strategy("Iron Condor") == "ICOND"

    def test_unknown_strategy_truncates_to_six_uppercase_chars(self) -> None:
        # "Mean Reversion" → "MEANRE" (spaces stripped, first 6 upper chars)
        assert _abbreviate_strategy("Mean Reversion") == "MEANRE"

    def test_empty_strategy_returns_unknwn(self) -> None:
        assert _abbreviate_strategy(None) == "UNKNWN"
        assert _abbreviate_strategy("") == "UNKNWN"
        assert _abbreviate_strategy("   ") == "UNKNWN"

    def test_make_display_id_format(self) -> None:
        ts = datetime(2026, 4, 29, 8, 30, tzinfo=timezone.utc)
        assert make_display_id(symbol="AAPL", strategy="Event Continuation", created_at=ts) == "AAPL-EVCONT-20260429-0830"

    def test_make_display_id_naive_datetime_treated_as_utc(self) -> None:
        ts = datetime(2026, 4, 29, 8, 30)
        # Naive datetime is treated as UTC, so the format stays stable.
        assert make_display_id(symbol="MSFT", strategy="Iron Condor", created_at=ts) == "MSFT-ICOND-20260429-0830"


# ---------------------------------------------------------------------------
# Track A — display_id is unique per recommendation (uniqueness gate)
# ---------------------------------------------------------------------------

def test_display_id_unique_per_recommendation() -> None:
    """Two promotions of the same symbol+strategy at different minutes get
    different display_ids. The format includes HHMM, so even back-to-back
    promotions cannot collide unless they happen in the same minute (in
    which case the rec_<hex> guarantees uniqueness even if display_id
    repeats — display_id is a label, not a key)."""
    _seed_approved_user()
    queue_resp = client.post(
        "/user/recommendations/queue",
        headers=_USER_AUTH,
        json={"symbols": ["AAPL"], "timeframe": "1D", "market_mode": "equities"},
    )
    assert queue_resp.status_code == 200, queue_resp.text
    candidate = queue_resp.json()["queue"][0]

    promote1 = client.post(
        "/user/recommendations/queue/promote",
        headers=_USER_AUTH,
        json={**candidate, "action": "make_active"},
    )
    promote2 = client.post(
        "/user/recommendations/queue/promote",
        headers=_USER_AUTH,
        json={**candidate, "action": "make_active"},
    )
    assert promote1.status_code == 200
    assert promote2.status_code == 200
    body1 = promote1.json()
    body2 = promote2.json()
    # Different canonical recommendation_ids
    assert body1["recommendation_id"] != body2["recommendation_id"]
    # Both responses include a display_id field
    assert "display_id" in body1
    assert "display_id" in body2
    # display_id is in the expected format
    assert body1["display_id"].startswith("AAPL-EVCONT-")
    assert body2["display_id"].startswith("AAPL-EVCONT-")


# ---------------------------------------------------------------------------
# Track A — Legacy rec without display_id falls back in API response
# ---------------------------------------------------------------------------

def test_legacy_rec_without_display_id_returns_fallback() -> None:
    """Rows persisted before the display_id column existed have NULL
    display_id. The API must surface a synthesized 'Rec #...' fallback so
    the UI never has to render a blank slot."""
    user_id = _seed_approved_user()
    with SessionLocal() as session:
        session.add(
            RecommendationModel(
                recommendation_id="rec_legacy123abcdef",
                app_user_id=user_id,
                symbol="LEGCY",
                payload={"approved": True, "workflow": {"market_data_source": "polygon"}},
                display_id=None,
            )
        )
        session.commit()

    resp = client.get("/user/recommendations", headers=_USER_AUTH)
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    legacy = next((row for row in rows if row["recommendation_id"] == "rec_legacy123abcdef"), None)
    assert legacy is not None, "legacy row missing from list"
    assert legacy["display_id"] == "Rec #abcdef", legacy

    # Helper itself behaves the same way in isolation.
    assert display_id_or_fallback(None, "rec_legacy123abcdef") == "Rec #abcdef"
    assert display_id_or_fallback("AAPL-EVCONT-20260429-0830", "rec_xxx") == "AAPL-EVCONT-20260429-0830"


# ---------------------------------------------------------------------------
# Track B — PATCH /user/settings happy path
# ---------------------------------------------------------------------------

def test_patch_user_settings_updates_risk_dollars_per_trade() -> None:
    _seed_approved_user()
    resp = client.patch(
        "/user/settings",
        headers=_USER_AUTH,
        json={"risk_dollars_per_trade": 2500.0},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["risk_dollars_per_trade"] == 2500.0
    assert body["risk_dollars_per_trade_default"] == settings.risk_dollars_per_trade

    me = client.get("/user/me", headers=_USER_AUTH).json()
    assert me["risk_dollars_per_trade"] == 2500.0


def test_user_me_and_patch_settings_support_commission_fields() -> None:
    _seed_approved_user()

    me = client.get("/user/me", headers=_USER_AUTH)
    assert me.status_code == 200, me.text
    me_body = me.json()
    assert me_body["commission_per_trade"] is None
    assert me_body["commission_per_trade_default"] == settings.commission_per_trade
    assert me_body["commission_per_contract"] is None
    assert me_body["commission_per_contract_default"] == settings.commission_per_contract

    resp = client.patch(
        "/user/settings",
        headers=_USER_AUTH,
        json={"commission_per_trade": 1.25, "commission_per_contract": 0.95},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["commission_per_trade"] == 1.25
    assert body["commission_per_trade_default"] == settings.commission_per_trade
    assert body["commission_per_contract"] == 0.95
    assert body["commission_per_contract_default"] == settings.commission_per_contract

    me = client.get("/user/me", headers=_USER_AUTH).json()
    assert me["commission_per_trade"] == 1.25
    assert me["commission_per_contract"] == 0.95


# ---------------------------------------------------------------------------
# Track B — validation: <= 0, > 50000, non-numeric, missing key
# ---------------------------------------------------------------------------

def test_patch_user_settings_rejects_zero_or_negative() -> None:
    _seed_approved_user()
    for value in (0, -100, -0.01):
        resp = client.patch(
            "/user/settings",
            headers=_USER_AUTH,
            json={"risk_dollars_per_trade": value},
        )
        assert resp.status_code == 400, resp.text
        assert "> 0" in resp.json()["detail"] or "50000" in resp.json()["detail"]


def test_patch_user_settings_rejects_above_upper_bound() -> None:
    _seed_approved_user()
    resp = client.patch(
        "/user/settings",
        headers=_USER_AUTH,
        json={"risk_dollars_per_trade": 50000.01},
    )
    assert resp.status_code == 400, resp.text


def test_patch_user_settings_rejects_non_numeric() -> None:
    _seed_approved_user()
    resp = client.patch(
        "/user/settings",
        headers=_USER_AUTH,
        json={"risk_dollars_per_trade": "lots"},
    )
    assert resp.status_code == 400, resp.text


def test_patch_user_settings_rejects_invalid_commission_per_trade() -> None:
    _seed_approved_user()
    for payload in (
        {"commission_per_trade": -0.01},
        {"commission_per_trade": 1000.01},
        {"commission_per_trade": "fees"},
    ):
        resp = client.patch("/user/settings", headers=_USER_AUTH, json=payload)
        assert resp.status_code == 400, resp.text


def test_patch_user_settings_rejects_invalid_commission_per_contract() -> None:
    _seed_approved_user()
    for payload in (
        {"commission_per_contract": -0.01},
        {"commission_per_contract": 100.01},
        {"commission_per_contract": "contracts"},
    ):
        resp = client.patch("/user/settings", headers=_USER_AUTH, json=payload)
        assert resp.status_code == 400, resp.text


def test_patch_user_settings_requires_field() -> None:
    _seed_approved_user()
    resp = client.patch("/user/settings", headers=_USER_AUTH, json={})
    assert resp.status_code == 400, resp.text


# ---------------------------------------------------------------------------
# Track B — null override falls back to env default in sizing
# ---------------------------------------------------------------------------

def test_user_with_no_override_falls_back_to_env_default() -> None:
    """When the user has no risk_dollars_per_trade override, the
    recommendation's sizing.risk_dollars equals settings.risk_dollars_per_trade
    (the env default). Verified end-to-end via the promote endpoint."""
    _seed_approved_user()

    queue_resp = client.post(
        "/user/recommendations/queue",
        headers=_USER_AUTH,
        json={"symbols": ["AAPL"], "timeframe": "1D", "market_mode": "equities"},
    )
    candidate = queue_resp.json()["queue"][0]
    promote = client.post(
        "/user/recommendations/queue/promote",
        headers=_USER_AUTH,
        json={**candidate, "action": "make_active"},
    )
    assert promote.status_code == 200, promote.text

    # Pull the persisted recommendation and check sizing.risk_dollars
    rec_id = promote.json()["recommendation_id"]
    with SessionLocal() as session:
        row = session.execute(
            select(RecommendationModel).where(RecommendationModel.recommendation_id == rec_id)
        ).scalar_one()
        sizing = (row.payload or {}).get("sizing", {})
        assert float(sizing.get("risk_dollars", 0.0)) == float(settings.risk_dollars_per_trade)


def test_user_with_override_uses_override_in_sizing() -> None:
    """After PATCH /user/settings, subsequent promotions size against the
    override, not the env default."""
    _seed_approved_user()
    patched = client.patch(
        "/user/settings",
        headers=_USER_AUTH,
        json={"risk_dollars_per_trade": 3500.0},
    )
    assert patched.status_code == 200

    queue_resp = client.post(
        "/user/recommendations/queue",
        headers=_USER_AUTH,
        json={"symbols": ["AAPL"], "timeframe": "1D", "market_mode": "equities"},
    )
    candidate = queue_resp.json()["queue"][0]
    promote = client.post(
        "/user/recommendations/queue/promote",
        headers=_USER_AUTH,
        json={**candidate, "action": "make_active"},
    )
    assert promote.status_code == 200, promote.text

    rec_id = promote.json()["recommendation_id"]
    with SessionLocal() as session:
        row = session.execute(
            select(RecommendationModel).where(RecommendationModel.recommendation_id == rec_id)
        ).scalar_one()
        sizing = (row.payload or {}).get("sizing", {})
        assert float(sizing.get("risk_dollars", 0.0)) == 3500.0
