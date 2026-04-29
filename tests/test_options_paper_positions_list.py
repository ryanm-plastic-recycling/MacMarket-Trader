from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import select

from macmarket_trader.api.main import app
from macmarket_trader.domain.models import AppUserModel
from macmarket_trader.storage.db import SessionLocal, init_db


client = TestClient(app)
_USER_AUTH = {"Authorization": "Bearer user-token"}
_ADMIN_AUTH = {"Authorization": "Bearer admin-token"}


def setup_module() -> None:
    init_db()


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


def _vertical_debit_payload(symbol: str) -> dict[str, object]:
    return {
        "market_mode": "options",
        "structure_type": "vertical_debit_spread",
        "underlying_symbol": symbol,
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
        "notes": "paper positions list test",
    }


def _open_position(*, headers: dict[str, str], symbol: str) -> dict[str, object]:
    response = client.post(
        "/user/options/paper-structures/open",
        headers=headers,
        json=_vertical_debit_payload(symbol),
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
        "notes": "manual close for durable list test",
    }


def test_list_option_paper_structures_returns_open_and_closed_rows_for_current_user_only() -> None:
    _approve_user(
        headers=_USER_AUTH,
        external_auth_user_id="clerk_user",
        commission_per_contract=0.75,
    )
    _approve_user(
        headers=_ADMIN_AUTH,
        external_auth_user_id="clerk_admin",
        app_role="admin",
        commission_per_contract=0.5,
    )

    closed_position = _open_position(headers=_USER_AUTH, symbol="AAPL")
    close_response = client.post(
        f"/user/options/paper-structures/{closed_position['position_id']}/close",
        headers=_USER_AUTH,
        json=_close_payload(open_payload=closed_position, long_exit=6.3, short_exit=0.7),
    )
    assert close_response.status_code == 200, close_response.text

    _open_position(headers=_USER_AUTH, symbol="SPY")
    _open_position(headers=_ADMIN_AUTH, symbol="QQQ")

    response = client.get("/user/options/paper-structures", headers=_USER_AUTH)
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["market_mode"] == "options"
    assert payload["paper_only"] is True
    assert "No broker execution" in payload["operator_disclaimer"]

    items = payload["items"]
    assert len(items) == 2
    assert {item["underlying_symbol"] for item in items} == {"AAPL", "SPY"}
    assert "QQQ" not in {item["underlying_symbol"] for item in items}

    open_item = next(item for item in items if item["status"] == "open")
    assert open_item["trade_id"] is None
    assert open_item["gross_pnl"] is None
    assert open_item["opening_commissions"] is None
    assert open_item["closing_commissions"] is None
    assert open_item["total_commissions"] is None
    assert open_item["net_pnl"] is None
    assert open_item["contract_count"] == 1
    assert open_item["leg_count"] == 2
    assert open_item["execution_enabled"] is False
    assert open_item["persistence_enabled"] is True
    assert open_item["paper_only"] is True
    assert all(leg["exit_premium"] is None for leg in open_item["legs"])

    closed_item = next(item for item in items if item["status"] == "closed")
    assert closed_item["trade_id"] is not None
    assert closed_item["gross_pnl"] == 300.0
    assert closed_item["opening_commissions"] == 1.5
    assert closed_item["closing_commissions"] == 1.5
    assert closed_item["total_commissions"] == 3.0
    assert closed_item["net_pnl"] == 297.0
    assert closed_item["settlement_mode"] == "manual_close"
    assert closed_item["contract_count"] == 1
    assert closed_item["leg_count"] == 2
    assert closed_item["legs"][0]["exit_premium"] == 6.3
    assert closed_item["legs"][0]["leg_commission"] == 1.5
    assert closed_item["legs"][1]["exit_premium"] == 0.7
    assert closed_item["legs"][1]["leg_commission"] == 1.5
