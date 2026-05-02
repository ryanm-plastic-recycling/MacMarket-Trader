from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from macmarket_trader.api.main import app
from macmarket_trader.domain.enums import Direction, EventSourceType, RegimeType, SetupType
from macmarket_trader.domain.models import AppUserModel, AuditLogModel
from macmarket_trader.domain.schemas import (
    CatalystMetadata,
    ConstraintCheck,
    ConstraintReport,
    EntryMetadata,
    EvidenceBundle,
    InvalidationMetadata,
    NewsEvent,
    QualityMetadata,
    RegimeContext,
    SizingMetadata,
    TargetsMetadata,
    TechnicalContext,
    TimeStopMetadata,
    TradeRecommendation,
)
from macmarket_trader.storage.db import SessionLocal
from macmarket_trader.storage.repositories import RecommendationRepository


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


def _set_paper_max_notional(user_id: int, value: float) -> None:
    with SessionLocal() as session:
        user = session.get(AppUserModel, user_id)
        assert user is not None
        user.paper_max_order_notional = value
        session.commit()


def _seed_recommendation(
    *,
    app_user_id: int,
    symbol: str = "GOOG",
    shares: int = 224,
    entry: float = 354.40,
    stop: float = 350.00,
) -> str:
    now = datetime(2026, 5, 2, 14, 30, tzinfo=timezone.utc)
    rec = TradeRecommendation(
        symbol=symbol,
        side=Direction.LONG,
        thesis="Synthetic approved recommendation for paper sizing tests.",
        event=NewsEvent(
            symbol=symbol,
            source_type=EventSourceType.NEWS,
            source_timestamp=now,
            headline="Test catalyst",
            summary="Deterministic test catalyst.",
            sentiment_score=0.5,
        ),
        catalyst=CatalystMetadata(
            type="news",
            novelty="high",
            source_quality="primary",
            event_timestamp=now,
        ),
        regime_context=RegimeContext(
            market_regime=RegimeType.RISK_ON_TREND,
            volatility_regime="moderate",
            breadth_state="supportive",
        ),
        technical_context=TechnicalContext(
            prior_day_high=entry + 2,
            prior_day_low=entry - 5,
            recent_20d_high=entry + 10,
            recent_20d_low=entry - 20,
            atr14=4.0,
            event_day_range=6.0,
            rel_volume=1.4,
        ),
        entry=EntryMetadata(
            setup_type=SetupType.EVENT_CONTINUATION,
            zone_low=entry,
            zone_high=entry,
            trigger_text="Test trigger",
        ),
        invalidation=InvalidationMetadata(price=stop, reason="Test invalidation"),
        targets=TargetsMetadata(target_1=entry + 8, target_2=entry + 16, trailing_rule="Trail after target 1"),
        time_stop=TimeStopMetadata(max_holding_days=5, reason="Test time stop"),
        sizing=SizingMetadata(risk_dollars=1000.0, stop_distance=abs(entry - stop), shares=shares),
        quality=QualityMetadata(expected_rr=1.8, confidence=0.7, risk_score=0.3),
        approved=True,
        constraints=ConstraintReport(
            checks=[ConstraintCheck(name="test", passed=True, details="synthetic")],
            risk_based_share_cap=shares,
            notional_share_cap=shares,
            final_share_count=shares,
        ),
        evidence=EvidenceBundle(
            event_id="evt_test",
            source_type=EventSourceType.NEWS,
            source_timestamp=now,
            regime_version="test",
            setup_engine_version="test",
            risk_engine_version="test",
            explanatory_notes=["synthetic"],
        ),
    )
    RecommendationRepository(SessionLocal).create(rec, app_user_id=app_user_id, strategy="Event Continuation")
    return rec.recommendation_id


def test_notional_cap_reduces_stage_size_and_preserves_recommendation_sizing() -> None:
    user_id = _seed_approved_user()
    _set_paper_max_notional(user_id, 1000.0)
    rec_uid = _seed_recommendation(app_user_id=user_id)

    resp = client.post("/user/orders", headers=_USER_AUTH, json={"recommendation_id": rec_uid})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["recommended_shares"] == 224
    assert body["final_order_shares"] == 2
    assert body["shares"] == 2
    assert body["notional_cap_shares"] == 2
    assert body["max_paper_order_notional"] == 1000.0
    assert body["estimated_notional"] == 708.8
    assert body["risk_at_stop"] == 8.8
    assert body["notional_cap_reduced"] is True
    assert body["sizing_mode"] == "risk_and_notional_capped"

    orders = client.get("/user/orders", headers=_USER_AUTH)
    listed = next(order for order in orders.json() if order["order_id"] == body["order_id"])
    assert listed["recommended_shares"] == 224
    assert listed["final_order_shares"] == 2
    assert listed["estimated_notional"] == 708.8

    positions = client.get("/user/paper-positions", headers=_USER_AUTH)
    position = next(position for position in positions.json() if position["order_id"] == body["order_id"])
    assert position["remaining_qty"] == 2.0
    assert position["open_notional"] == 708.8

    recs = client.get("/user/recommendations", headers=_USER_AUTH)
    persisted = next(row for row in recs.json() if row["recommendation_id"] == rec_uid)
    assert persisted["payload"]["sizing"]["shares"] == 224


def test_override_shares_lower_than_cap_is_accepted() -> None:
    user_id = _seed_approved_user()
    _set_paper_max_notional(user_id, 1000.0)
    rec_uid = _seed_recommendation(app_user_id=user_id)

    resp = client.post(
        "/user/orders",
        headers=_USER_AUTH,
        json={"recommendation_id": rec_uid, "override_shares": 1},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["recommended_shares"] == 224
    assert body["final_order_shares"] == 1
    assert body["operator_override_shares"] == 1
    assert body["shares"] == 1


def test_override_shares_above_recommendation_is_rejected() -> None:
    user_id = _seed_approved_user()
    _set_paper_max_notional(user_id, 100000.0)
    rec_uid = _seed_recommendation(app_user_id=user_id, shares=10)

    resp = client.post(
        "/user/orders",
        headers=_USER_AUTH,
        json={"recommendation_id": rec_uid, "override_shares": 11},
    )
    assert resp.status_code == 409, resp.text
    assert "recommended shares" in resp.json()["detail"]


def test_override_shares_above_notional_cap_is_rejected() -> None:
    user_id = _seed_approved_user()
    _set_paper_max_notional(user_id, 1000.0)
    rec_uid = _seed_recommendation(app_user_id=user_id)

    resp = client.post(
        "/user/orders",
        headers=_USER_AUTH,
        json={"recommendation_id": rec_uid, "override_shares": 3},
    )
    assert resp.status_code == 409, resp.text
    assert "paper_max_order_notional" in resp.json()["detail"]


def test_reset_endpoint_deletes_only_current_user_paper_records_and_keeps_settings_and_recommendations() -> None:
    user_id = _seed_approved_user()
    _set_paper_max_notional(user_id, 1000.0)
    rec_uid = _seed_recommendation(app_user_id=user_id)
    order_resp = client.post("/user/orders", headers=_USER_AUTH, json={"recommendation_id": rec_uid})
    assert order_resp.status_code == 200, order_resp.text
    position = client.get("/user/paper-positions", headers=_USER_AUTH).json()[0]
    close_resp = client.post(
        f"/user/paper-positions/{position['id']}/close",
        headers=_USER_AUTH,
        json={"mark_price": 360.0, "reason": "cleanup test"},
    )
    assert close_resp.status_code == 200, close_resp.text

    other_user_id = _seed_approved_user(token="admin-token", external_id="clerk_admin")
    other_rec_uid = _seed_recommendation(app_user_id=other_user_id, symbol="MSFT", entry=250.0, stop=245.0)
    other_order = client.post(
        "/user/orders",
        headers={"Authorization": "Bearer admin-token"},
        json={"recommendation_id": other_rec_uid},
    )
    assert other_order.status_code == 200, other_order.text

    reset = client.post("/user/paper/reset", headers=_USER_AUTH, json={"confirmation": "RESET"})
    assert reset.status_code == 200, reset.text
    counts = reset.json()["counts"]
    assert counts["orders"] == 1
    assert counts["fills"] == 1
    assert counts["paper_positions"] == 1
    assert counts["paper_trades"] == 1

    assert client.get("/user/orders", headers=_USER_AUTH).json() == []
    assert client.get("/user/paper-positions?status=all", headers=_USER_AUTH).json() == []
    assert client.get("/user/paper-trades", headers=_USER_AUTH).json() == []

    recs = client.get("/user/recommendations", headers=_USER_AUTH)
    assert any(row["recommendation_id"] == rec_uid for row in recs.json())
    settings_resp = client.get("/user/settings", headers=_USER_AUTH)
    assert settings_resp.json()["paper_max_order_notional"] == 1000.0

    other_orders = client.get("/user/orders", headers={"Authorization": "Bearer admin-token"})
    assert any(order["order_id"] == other_order.json()["order_id"] for order in other_orders.json())

    with SessionLocal() as session:
        audit = session.execute(select(AuditLogModel).where(AuditLogModel.payload["event"].as_string() == "paper_sandbox_reset")).scalar_one()
        assert audit.payload["counts"] == counts
