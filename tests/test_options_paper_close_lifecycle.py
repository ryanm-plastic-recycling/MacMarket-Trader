from __future__ import annotations

from datetime import date

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
    RecommendationModel,
    ReplayRunModel,
)
from macmarket_trader.storage.db import SessionLocal


client = TestClient(app)
_USER_AUTH = {"Authorization": "Bearer user-token"}
_ADMIN_AUTH = {"Authorization": "Bearer admin-token"}


def _approve_user(*, headers: dict[str, str], external_auth_user_id: str, app_role: str = "user") -> int:
    response = client.get("/user/me", headers=headers)
    assert response.status_code == 200, response.text
    with SessionLocal() as session:
        user = session.execute(
            select(AppUserModel).where(AppUserModel.external_auth_user_id == external_auth_user_id)
        ).scalar_one()
        user.approval_status = "approved"
        user.app_role = app_role
        session.commit()
        return user.id


def _counts() -> dict[str, int]:
    with SessionLocal() as session:
        return {
            "equity_orders": session.execute(select(func.count()).select_from(OrderModel)).scalar_one(),
            "equity_positions": session.execute(select(func.count()).select_from(PaperPositionModel)).scalar_one(),
            "equity_trades": session.execute(select(func.count()).select_from(PaperTradeModel)).scalar_one(),
            "recommendations": session.execute(
                select(func.count()).select_from(RecommendationModel)
            ).scalar_one(),
            "replay_runs": session.execute(select(func.count()).select_from(ReplayRunModel)).scalar_one(),
            "option_orders": session.execute(
                select(func.count()).select_from(PaperOptionOrderModel)
            ).scalar_one(),
            "option_order_legs": session.execute(
                select(func.count()).select_from(PaperOptionOrderLegModel)
            ).scalar_one(),
            "option_positions": session.execute(
                select(func.count()).select_from(PaperOptionPositionModel)
            ).scalar_one(),
            "option_position_legs": session.execute(
                select(func.count()).select_from(PaperOptionPositionLegModel)
            ).scalar_one(),
            "option_trades": session.execute(
                select(func.count()).select_from(PaperOptionTradeModel)
            ).scalar_one(),
            "option_trade_legs": session.execute(
                select(func.count()).select_from(PaperOptionTradeLegModel)
            ).scalar_one(),
        }


def _vertical_debit_payload() -> dict[str, object]:
    return {
        "market_mode": "options",
        "structure_type": "vertical_debit_spread",
        "underlying_symbol": "aapl",
        "legs": [
            {
                "action": "buy",
                "right": "call",
                "strike": 205.0,
                "expiration": date(2026, 5, 15).isoformat(),
                "premium": 4.2,
                "label": "long call",
            },
            {
                "action": "sell",
                "right": "call",
                "strike": 215.0,
                "expiration": date(2026, 5, 15).isoformat(),
                "premium": 1.6,
                "label": "short call",
            },
        ],
        "notes": "paper close test",
    }


def _open_vertical_position() -> dict[str, object]:
    response = client.post(
        "/user/options/paper-structures/open",
        headers=_USER_AUTH,
        json=_vertical_debit_payload(),
    )
    assert response.status_code == 200, response.text
    return response.json()


def _close_payload(*, open_payload: dict[str, object], long_exit: float, short_exit: float) -> dict[str, object]:
    legs = open_payload["legs"]
    return {
        "settlement_mode": "manual_close",
        "legs": [
            {
                "position_leg_id": legs[0]["id"],
                "exit_premium": long_exit,
            },
            {
                "position_leg_id": legs[1]["id"],
                "exit_premium": short_exit,
            },
        ],
        "notes": "manual close test",
    }


def test_manual_close_option_structure_creates_trade_and_closes_position() -> None:
    user_id = _approve_user(headers=_USER_AUTH, external_auth_user_id="clerk_user")
    open_payload = _open_vertical_position()
    before_close = _counts()

    response = client.post(
        f"/user/options/paper-structures/{open_payload['position_id']}/close",
        headers=_USER_AUTH,
        json=_close_payload(open_payload=open_payload, long_exit=6.3, short_exit=0.7),
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["market_mode"] == "options"
    assert payload["position_id"] == open_payload["position_id"]
    assert payload["structure_type"] == "vertical_debit_spread"
    assert payload["underlying_symbol"] == "AAPL"
    assert payload["status"] == "closed"
    assert payload["position_status"] == "closed"
    assert payload["settlement_mode"] == "manual_close"
    assert payload["gross_pnl"] == 300.0
    assert payload["net_pnl"] is None
    assert payload["total_commissions"] is None
    assert payload["execution_enabled"] is False
    assert payload["persistence_enabled"] is True
    assert payload["paper_only"] is True
    assert "Gross P&L only" in payload["operator_disclaimer"]
    assert len(payload["legs"]) == 2
    assert payload["legs"][0]["entry_premium"] == 4.2
    assert payload["legs"][0]["exit_premium"] == 6.3
    assert payload["legs"][0]["leg_gross_pnl"] == 210.0
    assert payload["legs"][1]["entry_premium"] == 1.6
    assert payload["legs"][1]["exit_premium"] == 0.7
    assert payload["legs"][1]["leg_gross_pnl"] == 90.0

    after_close = _counts()
    assert after_close["option_orders"] == before_close["option_orders"]
    assert after_close["option_order_legs"] == before_close["option_order_legs"]
    assert after_close["option_positions"] == before_close["option_positions"]
    assert after_close["option_position_legs"] == before_close["option_position_legs"]
    assert after_close["option_trades"] == before_close["option_trades"] + 1
    assert after_close["option_trade_legs"] == before_close["option_trade_legs"] + 2
    assert after_close["equity_orders"] == before_close["equity_orders"]
    assert after_close["equity_positions"] == before_close["equity_positions"]
    assert after_close["equity_trades"] == before_close["equity_trades"]
    assert after_close["recommendations"] == before_close["recommendations"]
    assert after_close["replay_runs"] == before_close["replay_runs"]

    with SessionLocal() as session:
        position_row = session.get(PaperOptionPositionModel, open_payload["position_id"])
        trade_row = session.get(PaperOptionTradeModel, payload["trade_id"])
        assert position_row is not None
        assert trade_row is not None
        assert position_row.app_user_id == user_id
        assert position_row.status == "closed"
        assert position_row.closed_at is not None
        assert trade_row.app_user_id == user_id
        assert trade_row.position_id == position_row.id
        assert trade_row.gross_pnl == 300.0
        assert trade_row.total_commissions is None
        assert trade_row.net_pnl is None
        assert trade_row.settlement_mode == "manual_close"

        position_legs = list(
            session.execute(
                select(PaperOptionPositionLegModel)
                .where(PaperOptionPositionLegModel.position_id == position_row.id)
                .order_by(PaperOptionPositionLegModel.id.asc())
            ).scalars()
        )
        assert [leg.status for leg in position_legs] == ["closed", "closed"]
        assert [leg.exit_premium for leg in position_legs] == [6.3, 0.7]


def test_manual_close_option_structure_can_realize_loss() -> None:
    _approve_user(headers=_USER_AUTH, external_auth_user_id="clerk_user")
    open_payload = _open_vertical_position()

    response = client.post(
        f"/user/options/paper-structures/{open_payload['position_id']}/close",
        headers=_USER_AUTH,
        json=_close_payload(open_payload=open_payload, long_exit=1.2, short_exit=3.1),
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["gross_pnl"] == -450.0
    assert payload["net_pnl"] is None
    assert payload["total_commissions"] is None
    assert [leg["leg_gross_pnl"] for leg in payload["legs"]] == [-300.0, -150.0]


def test_manual_close_option_structure_blocks_double_close() -> None:
    _approve_user(headers=_USER_AUTH, external_auth_user_id="clerk_user")
    open_payload = _open_vertical_position()
    close_payload = _close_payload(open_payload=open_payload, long_exit=6.3, short_exit=0.7)

    first = client.post(
        f"/user/options/paper-structures/{open_payload['position_id']}/close",
        headers=_USER_AUTH,
        json=close_payload,
    )
    assert first.status_code == 200, first.text

    before_second = _counts()
    second = client.post(
        f"/user/options/paper-structures/{open_payload['position_id']}/close",
        headers=_USER_AUTH,
        json=close_payload,
    )
    assert second.status_code == 409, second.text
    assert second.json()["detail"] == "option_position_not_open"
    assert _counts() == before_second


def test_manual_close_option_structure_blocks_wrong_user() -> None:
    _approve_user(headers=_USER_AUTH, external_auth_user_id="clerk_user")
    _approve_user(headers=_ADMIN_AUTH, external_auth_user_id="clerk_admin", app_role="admin")
    open_payload = _open_vertical_position()

    before = _counts()
    response = client.post(
        f"/user/options/paper-structures/{open_payload['position_id']}/close",
        headers=_ADMIN_AUTH,
        json=_close_payload(open_payload=open_payload, long_exit=6.3, short_exit=0.7),
    )
    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "option_position_not_found"
    assert _counts() == before


def test_manual_close_option_structure_blocks_negative_exit_premium() -> None:
    _approve_user(headers=_USER_AUTH, external_auth_user_id="clerk_user")
    open_payload = _open_vertical_position()

    before = _counts()
    payload = _close_payload(open_payload=open_payload, long_exit=6.3, short_exit=0.7)
    payload["legs"][0]["exit_premium"] = -1.0
    response = client.post(
        f"/user/options/paper-structures/{open_payload['position_id']}/close",
        headers=_USER_AUTH,
        json=payload,
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "invalid_exit_premium"
    assert _counts() == before


def test_manual_close_option_structure_requires_all_legs() -> None:
    _approve_user(headers=_USER_AUTH, external_auth_user_id="clerk_user")
    open_payload = _open_vertical_position()

    before = _counts()
    response = client.post(
        f"/user/options/paper-structures/{open_payload['position_id']}/close",
        headers=_USER_AUTH,
        json={
            "settlement_mode": "manual_close",
            "legs": [
                {
                    "position_leg_id": open_payload["legs"][0]["id"],
                    "exit_premium": 6.3,
                }
            ],
        },
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "all_position_legs_must_be_closed_together"
    assert _counts() == before
