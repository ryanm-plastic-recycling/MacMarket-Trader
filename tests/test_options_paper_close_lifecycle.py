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


def _vertical_debit_payload(*, quantity: int = 1) -> dict[str, object]:
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
                "quantity": quantity,
                "label": "long call",
            },
            {
                "action": "sell",
                "right": "call",
                "strike": 215.0,
                "expiration": date(2026, 5, 15).isoformat(),
                "premium": 1.6,
                "quantity": quantity,
                "label": "short call",
            },
        ],
        "notes": "paper close test",
    }


def _iron_condor_payload(*, quantity: int = 1) -> dict[str, object]:
    expiration = date(2026, 5, 15).isoformat()
    return {
        "market_mode": "options",
        "structure_type": "iron_condor",
        "underlying_symbol": "qqq",
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
        "notes": "paper iron condor close test",
    }


def _open_vertical_position(*, quantity: int = 1) -> dict[str, object]:
    response = client.post(
        "/user/options/paper-structures/open",
        headers=_USER_AUTH,
        json=_vertical_debit_payload(quantity=quantity),
    )
    assert response.status_code == 200, response.text
    return response.json()


def _open_iron_condor_position(*, quantity: int = 1) -> dict[str, object]:
    response = client.post(
        "/user/options/paper-structures/open",
        headers=_USER_AUTH,
        json=_iron_condor_payload(quantity=quantity),
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


def test_iron_condor_open_close_lifecycle_keeps_options_isolated_and_commissions_per_contract() -> None:
    user_id = _approve_user(
        headers=_USER_AUTH,
        external_auth_user_id="clerk_user",
        commission_per_contract=0.65,
    )
    before_open = _counts()
    open_payload = _open_iron_condor_position(quantity=2)

    assert open_payload["structure_type"] == "iron_condor"
    assert len(open_payload["legs"]) == 4

    after_open = _counts()
    assert after_open["option_orders"] == before_open["option_orders"] + 1
    assert after_open["option_order_legs"] == before_open["option_order_legs"] + 4
    assert after_open["option_positions"] == before_open["option_positions"] + 1
    assert after_open["option_position_legs"] == before_open["option_position_legs"] + 4
    assert after_open["option_trades"] == before_open["option_trades"]
    assert after_open["option_trade_legs"] == before_open["option_trade_legs"]
    assert after_open["equity_orders"] == before_open["equity_orders"]
    assert after_open["equity_positions"] == before_open["equity_positions"]
    assert after_open["equity_trades"] == before_open["equity_trades"]
    assert after_open["recommendations"] == before_open["recommendations"]
    assert after_open["replay_runs"] == before_open["replay_runs"]

    close_payload = {
        "settlement_mode": "manual_close",
        "legs": [
            {"position_leg_id": open_payload["legs"][0]["id"], "exit_premium": 0.4},
            {"position_leg_id": open_payload["legs"][1]["id"], "exit_premium": 1.0},
            {"position_leg_id": open_payload["legs"][2]["id"], "exit_premium": 0.8},
            {"position_leg_id": open_payload["legs"][3]["id"], "exit_premium": 0.3},
        ],
        "notes": "manual iron condor close test",
    }
    response = client.post(
        f"/user/options/paper-structures/{open_payload['position_id']}/close",
        headers=_USER_AUTH,
        json=close_payload,
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["structure_type"] == "iron_condor"
    assert payload["settlement_mode"] == "manual_close"
    assert payload["gross_pnl"] == 280.0
    assert payload["commission_per_contract"] == 0.65
    assert payload["opening_commissions"] == 5.2
    assert payload["closing_commissions"] == 5.2
    assert payload["total_commissions"] == 10.4
    assert payload["total_commissions"] != 1040.0
    assert payload["net_pnl"] == 269.6
    assert len(payload["legs"]) == 4
    assert [leg["leg_gross_pnl"] for leg in payload["legs"]] == [-120.0, 300.0, 240.0, -140.0]
    assert [leg["leg_commission"] for leg in payload["legs"]] == [2.6, 2.6, 2.6, 2.6]

    after_close = _counts()
    assert after_close["option_orders"] == before_open["option_orders"] + 1
    assert after_close["option_order_legs"] == before_open["option_order_legs"] + 4
    assert after_close["option_positions"] == before_open["option_positions"] + 1
    assert after_close["option_position_legs"] == before_open["option_position_legs"] + 4
    assert after_close["option_trades"] == before_open["option_trades"] + 1
    assert after_close["option_trade_legs"] == before_open["option_trade_legs"] + 4
    assert after_close["equity_orders"] == before_open["equity_orders"]
    assert after_close["equity_positions"] == before_open["equity_positions"]
    assert after_close["equity_trades"] == before_open["equity_trades"]
    assert after_close["recommendations"] == before_open["recommendations"]
    assert after_close["replay_runs"] == before_open["replay_runs"]

    with SessionLocal() as session:
        position_row = session.get(PaperOptionPositionModel, open_payload["position_id"])
        trade_row = session.get(PaperOptionTradeModel, payload["trade_id"])
        assert position_row is not None
        assert trade_row is not None
        assert position_row.app_user_id == user_id
        assert position_row.status == "closed"
        assert trade_row.gross_pnl == 280.0
        assert trade_row.total_commissions == 10.4
        assert trade_row.net_pnl == 269.6


def test_manual_close_option_structure_creates_trade_and_closes_position() -> None:
    user_id = _approve_user(
        headers=_USER_AUTH,
        external_auth_user_id="clerk_user",
        commission_per_contract=0.75,
    )
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
    assert payload["commission_per_contract"] == 0.75
    assert payload["opening_commissions"] == 1.5
    assert payload["closing_commissions"] == 1.5
    assert payload["gross_pnl"] == 300.0
    assert payload["net_pnl"] == 297.0
    assert payload["total_commissions"] == 3.0
    assert payload["execution_enabled"] is False
    assert payload["persistence_enabled"] is True
    assert payload["paper_only"] is True
    assert "paper contract commission modeling only" in payload["operator_disclaimer"]
    assert len(payload["legs"]) == 2
    assert payload["legs"][0]["entry_premium"] == 4.2
    assert payload["legs"][0]["exit_premium"] == 6.3
    assert payload["legs"][0]["leg_gross_pnl"] == 210.0
    assert payload["legs"][0]["leg_commission"] == 1.5
    assert payload["legs"][0]["leg_net_pnl"] == 208.5
    assert payload["legs"][1]["entry_premium"] == 1.6
    assert payload["legs"][1]["exit_premium"] == 0.7
    assert payload["legs"][1]["leg_gross_pnl"] == 90.0
    assert payload["legs"][1]["leg_commission"] == 1.5
    assert payload["legs"][1]["leg_net_pnl"] == 88.5

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
        assert trade_row.total_commissions == 3.0
        assert trade_row.net_pnl == 297.0
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


def test_manual_close_option_structure_zero_commission_keeps_net_equal_gross() -> None:
    _approve_user(
        headers=_USER_AUTH,
        external_auth_user_id="clerk_user",
        commission_per_contract=0.0,
    )
    open_payload = _open_vertical_position()

    response = client.post(
        f"/user/options/paper-structures/{open_payload['position_id']}/close",
        headers=_USER_AUTH,
        json=_close_payload(open_payload=open_payload, long_exit=1.2, short_exit=3.1),
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["gross_pnl"] == -450.0
    assert payload["net_pnl"] == -450.0
    assert payload["total_commissions"] == 0.0
    assert [leg["leg_gross_pnl"] for leg in payload["legs"]] == [-300.0, -150.0]
    assert [leg["leg_commission"] for leg in payload["legs"]] == [0.0, 0.0]
    assert [leg["leg_net_pnl"] for leg in payload["legs"]] == [-300.0, -150.0]


def test_manual_close_option_structure_commission_is_per_contract_not_multiplier() -> None:
    _approve_user(
        headers=_USER_AUTH,
        external_auth_user_id="clerk_user",
        commission_per_contract=0.5,
    )
    open_payload = _open_vertical_position(quantity=3)

    response = client.post(
        f"/user/options/paper-structures/{open_payload['position_id']}/close",
        headers=_USER_AUTH,
        json=_close_payload(open_payload=open_payload, long_exit=6.3, short_exit=0.7),
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["gross_pnl"] == 900.0
    assert payload["opening_commissions"] == 3.0
    assert payload["closing_commissions"] == 3.0
    assert payload["total_commissions"] == 6.0
    assert payload["net_pnl"] == 894.0
    assert [leg["leg_commission"] for leg in payload["legs"]] == [3.0, 3.0]
    assert [leg["leg_net_pnl"] for leg in payload["legs"]] == [627.0, 267.0]


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


def test_expiration_settlement_close_is_rejected_without_creating_trade() -> None:
    _approve_user(headers=_USER_AUTH, external_auth_user_id="clerk_user")
    open_payload = _open_vertical_position()
    before = _counts()

    response = client.post(
        f"/user/options/paper-structures/{open_payload['position_id']}/close",
        headers=_USER_AUTH,
        json={
            "settlement_mode": "expiration",
            "underlying_settlement_price": 210.0,
            "legs": [
                {
                    "position_leg_id": leg["id"],
                    "exit_premium": 0.0,
                }
                for leg in open_payload["legs"]
            ],
        },
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "expiration_settlement_not_yet_supported"
    assert _counts() == before

    with SessionLocal() as session:
        position_row = session.get(PaperOptionPositionModel, open_payload["position_id"])
        assert position_row is not None
        assert position_row.status == "open"
