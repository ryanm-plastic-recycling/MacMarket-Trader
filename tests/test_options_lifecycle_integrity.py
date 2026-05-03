from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from macmarket_trader.api.main import app
from macmarket_trader.domain.models import (
    AppUserModel,
    OrderModel,
    PaperOptionOrderLegModel,
    PaperOptionOrderModel,
    PaperOptionPositionLegModel,
    PaperOptionPositionModel,
    PaperOptionTradeLegModel,
    PaperOptionTradeModel,
    PaperPositionModel,
    PaperTradeModel,
)
from macmarket_trader.domain.time import utc_now
from macmarket_trader.storage.db import SessionLocal


client = TestClient(app)
_USER_AUTH = {"Authorization": "Bearer user-token"}
_ADMIN_AUTH = {"Authorization": "Bearer admin-token"}


def _approve_user(
    *,
    headers: dict[str, str],
    external_auth_user_id: str,
    app_role: str = "user",
    commission_per_contract: float | None = None,
) -> int:
    response = client.get("/user/me", headers=headers)
    assert response.status_code == 200, response.text
    with SessionLocal() as session:
        user = session.execute(
            select(AppUserModel).where(AppUserModel.external_auth_user_id == external_auth_user_id)
        ).scalar_one()
        user.approval_status = "approved"
        user.app_role = app_role
        user.commission_per_contract = commission_per_contract
        session.commit()
        return user.id


def _iron_condor_payload(*, symbol: str = "qqq", quantity: int = 2) -> dict[str, object]:
    expiration = (utc_now().date() + timedelta(days=45)).isoformat()
    return {
        "market_mode": "options",
        "structure_type": "iron_condor",
        "underlying_symbol": symbol,
        "legs": [
            {
                "action": "buy",
                "right": "put",
                "strike": 90.0,
                "expiration": expiration,
                "premium": 1.0,
                "quantity": quantity,
                "label": "long put wing",
            },
            {
                "action": "sell",
                "right": "put",
                "strike": 95.0,
                "expiration": expiration,
                "premium": 2.5,
                "quantity": quantity,
                "label": "short put body",
            },
            {
                "action": "sell",
                "right": "call",
                "strike": 105.0,
                "expiration": expiration,
                "premium": 2.0,
                "quantity": quantity,
                "label": "short call body",
            },
            {
                "action": "buy",
                "right": "call",
                "strike": 110.0,
                "expiration": expiration,
                "premium": 1.0,
                "quantity": quantity,
                "label": "long call wing",
            },
        ],
        "notes": "options lifecycle integrity audit",
    }


def _open_structure(headers: dict[str, str], *, symbol: str = "qqq", quantity: int = 2) -> dict[str, object]:
    response = client.post(
        "/user/options/paper-structures/open",
        headers=headers,
        json=_iron_condor_payload(symbol=symbol, quantity=quantity),
    )
    assert response.status_code == 200, response.text
    return response.json()


def _iron_condor_close_payload(open_payload: dict[str, object]) -> dict[str, object]:
    legs = open_payload["legs"]
    return {
        "settlement_mode": "manual_close",
        "legs": [
            {"position_leg_id": legs[0]["id"], "exit_premium": 0.4},
            {"position_leg_id": legs[1]["id"], "exit_premium": 1.0},
            {"position_leg_id": legs[2]["id"], "exit_premium": 0.8},
            {"position_leg_id": legs[3]["id"], "exit_premium": 0.3},
        ],
        "notes": "manual options lifecycle integrity close",
    }


def _count(model: type, *, app_user_id: int | None = None) -> int:
    with SessionLocal() as session:
        stmt = select(func.count()).select_from(model)
        if app_user_id is not None and hasattr(model, "app_user_id"):
            stmt = stmt.where(model.app_user_id == app_user_id)
        return session.execute(stmt).scalar_one()


def _assert_no_orphan_options_records() -> None:
    with SessionLocal() as session:
        order_ids = set(session.execute(select(PaperOptionOrderModel.id)).scalars())
        position_ids = set(session.execute(select(PaperOptionPositionModel.id)).scalars())
        trade_ids = set(session.execute(select(PaperOptionTradeModel.id)).scalars())
        for leg in session.execute(select(PaperOptionOrderLegModel)).scalars():
            assert leg.option_order_id in order_ids
        for leg in session.execute(select(PaperOptionPositionLegModel)).scalars():
            assert leg.position_id in position_ids
        for leg in session.execute(select(PaperOptionTradeLegModel)).scalars():
            assert leg.trade_id in trade_ids


def test_options_lifecycle_integrity_open_review_owner_scope_manual_close_and_equity_reset_boundary() -> None:
    user_a_id = _approve_user(
        headers=_USER_AUTH,
        external_auth_user_id="clerk_user",
        commission_per_contract=0.65,
    )
    user_b_id = _approve_user(
        headers=_ADMIN_AUTH,
        external_auth_user_id="clerk_admin",
        app_role="admin",
        commission_per_contract=0.65,
    )

    before_equity_orders = _count(OrderModel)
    before_equity_positions = _count(PaperPositionModel)
    before_equity_trades = _count(PaperTradeModel)

    user_a_open = _open_structure(_USER_AUTH, symbol="qqq", quantity=2)
    assert user_a_open["structure_type"] == "iron_condor"
    assert user_a_open["opening_commissions"] == 5.2
    assert len(user_a_open["legs"]) == 4

    assert _count(PaperOptionOrderModel, app_user_id=user_a_id) == 1
    assert _count(PaperOptionPositionModel, app_user_id=user_a_id) == 1
    assert _count(PaperOptionTradeModel, app_user_id=user_a_id) == 0
    assert _count(OrderModel) == before_equity_orders
    assert _count(PaperPositionModel) == before_equity_positions
    assert _count(PaperTradeModel) == before_equity_trades

    with SessionLocal() as session:
        position = session.get(PaperOptionPositionModel, user_a_open["position_id"])
        assert position is not None
        assert position.app_user_id == user_a_id
        assert position.status == "open"
        assert position.source_order_id == user_a_open["order_id"]
        assert session.execute(
            select(func.count()).select_from(PaperOptionPositionLegModel).where(
                PaperOptionPositionLegModel.position_id == position.id
            )
        ).scalar_one() == 4

    user_a_review = client.get("/user/options/paper-structures/review", headers=_USER_AUTH)
    assert user_a_review.status_code == 200, user_a_review.text
    assert [item["structure_id"] for item in user_a_review.json()["items"]] == [user_a_open["position_id"]]

    user_b_review_before_open = client.get("/user/options/paper-structures/review", headers=_ADMIN_AUTH)
    assert user_b_review_before_open.status_code == 200, user_b_review_before_open.text
    assert user_b_review_before_open.json()["items"] == []

    user_b_close_a = client.post(
        f"/user/options/paper-structures/{user_a_open['position_id']}/close",
        headers=_ADMIN_AUTH,
        json=_iron_condor_close_payload(user_a_open),
    )
    assert user_b_close_a.status_code == 404, user_b_close_a.text
    assert user_b_close_a.json()["detail"] == "option_position_not_found"

    user_b_open = _open_structure(_ADMIN_AUTH, symbol="spy", quantity=1)
    assert _count(PaperOptionPositionModel, app_user_id=user_b_id) == 1
    user_b_review_after_open = client.get("/user/options/paper-structures/review", headers=_ADMIN_AUTH)
    assert user_b_review_after_open.status_code == 200, user_b_review_after_open.text
    assert [item["structure_id"] for item in user_b_review_after_open.json()["items"]] == [user_b_open["position_id"]]

    close_response = client.post(
        f"/user/options/paper-structures/{user_a_open['position_id']}/close",
        headers=_USER_AUTH,
        json=_iron_condor_close_payload(user_a_open),
    )
    assert close_response.status_code == 200, close_response.text
    close_payload = close_response.json()
    assert close_payload["status"] == "closed"
    assert close_payload["settlement_mode"] == "manual_close"
    assert close_payload["gross_pnl"] == 280.0
    assert close_payload["opening_commissions"] == 5.2
    assert close_payload["closing_commissions"] == 5.2
    assert close_payload["total_commissions"] == 10.4
    assert close_payload["total_commissions"] != 1040.0
    assert close_payload["net_pnl"] == 269.6
    assert [leg["leg_gross_pnl"] for leg in close_payload["legs"]] == [-120.0, 300.0, 240.0, -140.0]

    with SessionLocal() as session:
        user_a_position = session.get(PaperOptionPositionModel, user_a_open["position_id"])
        user_a_trade = session.get(PaperOptionTradeModel, close_payload["trade_id"])
        assert user_a_position is not None
        assert user_a_trade is not None
        assert user_a_position.status == "closed"
        assert user_a_position.closed_at is not None
        assert user_a_trade.app_user_id == user_a_id
        assert user_a_trade.position_id == user_a_position.id
        assert user_a_trade.gross_pnl == 280.0
        assert user_a_trade.total_commissions == 10.4
        assert user_a_trade.net_pnl == 269.6

    _assert_no_orphan_options_records()

    user_a_review_after_close = client.get("/user/options/paper-structures/review", headers=_USER_AUTH)
    assert user_a_review_after_close.status_code == 200, user_a_review_after_close.text
    assert user_a_review_after_close.json()["items"] == []

    assert _count(PaperOptionPositionModel, app_user_id=user_b_id) == 1
    assert _count(PaperOptionTradeModel, app_user_id=user_b_id) == 0

    reset_response = client.post(
        "/user/paper/reset",
        headers=_USER_AUTH,
        json={"confirmation": "RESET"},
    )
    assert reset_response.status_code == 200, reset_response.text
    assert _count(PaperOptionPositionModel, app_user_id=user_a_id) == 1
    assert _count(PaperOptionTradeModel, app_user_id=user_a_id) == 1
    assert _count(PaperOptionPositionModel, app_user_id=user_b_id) == 1
    assert _count(PaperOptionTradeModel, app_user_id=user_b_id) == 0
    assert _count(OrderModel) == 0
    assert _count(PaperPositionModel) == 0
    assert _count(PaperTradeModel) == 0

    _assert_no_orphan_options_records()
