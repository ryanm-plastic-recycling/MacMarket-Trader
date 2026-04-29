from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from macmarket_trader.api.main import app
from macmarket_trader.api.routes import admin as admin_routes
from macmarket_trader.domain.models import AppUserModel
from macmarket_trader.domain.schemas import Bar, PortfolioSnapshot
from macmarket_trader.service import RecommendationService
from macmarket_trader.storage.db import SessionLocal, init_db


client = TestClient(app)
_USER_AUTH = {"Authorization": "Bearer user-token"}


def _bars() -> list[Bar]:
    base = date(2026, 2, 1)
    return [
        Bar(
            date=base + timedelta(days=i),
            open=180 + i,
            high=181 + i,
            low=179 + i,
            close=180.5 + i,
            volume=1_200_000 + i * 11_000,
            rel_volume=1.15,
        )
        for i in range(40)
    ]


def _approve_user() -> int:
    resp = client.get("/user/me", headers=_USER_AUTH)
    assert resp.status_code == 200, resp.text
    with SessionLocal() as session:
        user = session.execute(
            select(AppUserModel).where(AppUserModel.external_auth_user_id == "clerk_user")
        ).scalar_one()
        user.approval_status = "approved"
        session.commit()
        return user.id


def _set_equity_commission(user_id: int, commission_per_trade: float) -> None:
    with SessionLocal() as session:
        user = session.get(AppUserModel, user_id)
        assert user is not None
        user.commission_per_trade = commission_per_trade
        session.commit()


def setup_module() -> None:
    init_db()


def test_recommendation_fee_preview_helper_returns_explicit_equity_fields() -> None:
    rec = RecommendationService(persist_audit=False).generate(
        symbol="AAPL",
        bars=_bars(),
        event_text="Earnings beat with strong guidance and continuation follow-through",
        event=None,
        portfolio=PortfolioSnapshot(),
        user_is_approved=True,
        app_user_id=None,
    )

    preview = admin_routes._recommendation_fee_preview(rec, commission_per_trade=1.25)

    assert preview["estimated_entry_fee"] == 1.25
    assert preview["estimated_exit_fee"] == 1.25
    assert preview["estimated_total_fees"] == 2.5
    assert preview["fee_model"] == "equity_per_trade"
    if preview["projected_gross_pnl"] is not None:
        assert preview["projected_net_pnl"] == round(float(preview["projected_gross_pnl"]) - 2.5, 2)


def test_replay_order_and_position_routes_expose_fee_preview_fields() -> None:
    user_id = _approve_user()
    _set_equity_commission(user_id, 1.5)

    create_rec = client.post(
        "/user/recommendations/generate",
        headers=_USER_AUTH,
        json={
            "symbol": "MSFT",
            "strategy": "Event Continuation",
            "timeframe": "1D",
            "market_mode": "equities",
            "event_text": "Earnings beat with raised guidance and broad market confirmation",
        },
    )
    assert create_rec.status_code == 200, create_rec.text
    recommendation_id = create_rec.json()["recommendation_id"]

    replay = client.post(
        "/user/replay-runs",
        headers=_USER_AUTH,
        json={"guided": True, "recommendation_id": recommendation_id},
    )
    assert replay.status_code == 200, replay.text
    replay_body = replay.json()
    assert replay_body["estimated_entry_fee"] == 1.5
    assert replay_body["estimated_exit_fee"] == 1.5
    assert replay_body["estimated_total_fees"] == 3.0
    assert replay_body["fee_model"] == "equity_per_trade"

    run_id = replay_body["id"]
    detail = client.get(f"/user/replay-runs/{run_id}", headers=_USER_AUTH)
    assert detail.status_code == 200, detail.text
    detail_body = detail.json()
    assert detail_body["estimated_total_fees"] == 3.0
    assert detail_body["fee_model"] == "equity_per_trade"

    stage_order = client.post(
        "/user/orders",
        headers=_USER_AUTH,
        json={"guided": True, "recommendation_id": recommendation_id, "replay_run_id": run_id},
    )
    assert stage_order.status_code == 200, stage_order.text
    order_body = stage_order.json()
    assert order_body["estimated_entry_fee"] == 1.5
    assert order_body["estimated_exit_fee"] == 1.5
    assert order_body["estimated_total_fees"] == 3.0
    assert order_body["fee_model"] == "equity_per_trade"

    orders = client.get("/user/orders", headers=_USER_AUTH)
    assert orders.status_code == 200, orders.text
    listed_order = next(
        order for order in orders.json() if order["order_id"] == order_body["order_id"]
    )
    assert listed_order["estimated_total_fees"] == 3.0
    assert listed_order["fee_model"] == "equity_per_trade"

    positions = client.get("/user/paper-positions", headers=_USER_AUTH)
    assert positions.status_code == 200, positions.text
    open_position = next(
        position for position in positions.json() if position["order_id"] == order_body["order_id"]
    )
    assert open_position["estimated_close_fee"] == 1.5
    assert open_position["fee_model"] == "equity_per_trade"
