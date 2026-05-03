from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from macmarket_trader.api.main import app
from macmarket_trader.domain.models import AppUserModel
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
    approval_status: str = "approved",
    commission_per_contract: float | None = None,
) -> int:
    response = client.get("/user/me", headers=headers)
    assert response.status_code == 200, response.text
    with SessionLocal() as session:
        user = session.execute(
            select(AppUserModel).where(AppUserModel.external_auth_user_id == external_auth_user_id)
        ).scalar_one()
        user.approval_status = approval_status
        user.app_role = app_role
        user.commission_per_contract = commission_per_contract
        session.commit()
        return user.id


def _vertical_debit_payload(*, symbol: str = "goog", quantity: int = 1, days_to_expiration: int = 30) -> dict[str, object]:
    expiration = (utc_now().date() + timedelta(days=days_to_expiration)).isoformat()
    return {
        "market_mode": "options",
        "structure_type": "vertical_debit_spread",
        "underlying_symbol": symbol,
        "legs": [
            {
                "action": "buy",
                "right": "call",
                "strike": 205.0,
                "expiration": expiration,
                "premium": 4.2,
                "quantity": quantity,
                "label": "long call",
            },
            {
                "action": "sell",
                "right": "call",
                "strike": 215.0,
                "expiration": expiration,
                "premium": 1.6,
                "quantity": quantity,
                "label": "short call",
            },
        ],
        "notes": "paper options review test",
    }


def _open_vertical_position(*, symbol: str = "goog", quantity: int = 1, days_to_expiration: int = 30) -> dict[str, object]:
    response = client.post(
        "/user/options/paper-structures/open",
        headers=_USER_AUTH,
        json=_vertical_debit_payload(symbol=symbol, quantity=quantity, days_to_expiration=days_to_expiration),
    )
    assert response.status_code == 200, response.text
    return response.json()


def _close_payload(open_payload: dict[str, object]) -> dict[str, object]:
    legs = open_payload["legs"]
    return {
        "settlement_mode": "manual_close",
        "legs": [
            {"position_leg_id": legs[0]["id"], "exit_premium": 6.3},
            {"position_leg_id": legs[1]["id"], "exit_premium": 0.7},
        ],
        "notes": "manual review-test close",
    }


def test_options_position_review_returns_open_structure_with_leg_shape_and_mark_unavailable() -> None:
    _approve_user(
        headers=_USER_AUTH,
        external_auth_user_id="clerk_user",
        commission_per_contract=0.65,
    )
    opened = _open_vertical_position(symbol="goog", quantity=2, days_to_expiration=30)

    response = client.get("/user/options/paper-structures/review", headers=_USER_AUTH)
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["market_mode"] == "options"
    assert payload["paper_only"] is True
    assert payload["review_only"] is True
    assert len(payload["items"]) == 1
    review = payload["items"][0]
    assert review["structure_id"] == opened["position_id"]
    assert review["underlying_symbol"] == "GOOG"
    assert review["strategy_type"] == "vertical_debit_spread"
    assert review["contracts"] == 2
    assert review["quantity"] == 2
    assert review["multiplier_assumption"] == 100
    assert review["opening_debit_credit_type"] == "debit"
    assert review["opening_debit_credit"] == 2.6
    assert review["opening_commissions"] == 2.6
    assert review["current_mark_debit_credit"] is None
    assert review["estimated_unrealized_pnl"] is None
    assert review["action_classification"] == "mark_unavailable"
    assert "option_mark_data" in review["missing_data"]
    assert "no_automatic_rolling" in review["provenance"]
    assert review["provenance"]["fallback_option_marks_used"] is False
    assert review["risk_calendar"]["symbol"] == "GOOG"
    assert len(review["legs"]) == 2
    assert review["legs"][0]["side"] == "long"
    assert review["legs"][0]["option_type"] == "call"
    assert review["legs"][0]["current_mark_premium"] is None
    assert review["legs"][0]["missing_data"] == ["option_mark_data"]


def test_options_position_review_adds_expiration_warning_without_auto_close() -> None:
    _approve_user(headers=_USER_AUTH, external_auth_user_id="clerk_user")
    _open_vertical_position(symbol="aapl", days_to_expiration=5)

    response = client.get("/user/options/paper-structures/review", headers=_USER_AUTH)
    assert response.status_code == 200, response.text
    review = response.json()["items"][0]

    assert review["expiration_status"] == "expiration_warning"
    assert review["action_classification"] == "mark_unavailable"
    assert any("Expiration is within seven calendar days" in item for item in review["warnings"])
    assert "automatic" not in review["action_summary"].lower() or "no automatic" in review["action_summary"].lower()


def test_options_position_review_is_user_scoped_and_excludes_closed_structures() -> None:
    _approve_user(headers=_USER_AUTH, external_auth_user_id="clerk_user")
    _approve_user(headers=_ADMIN_AUTH, external_auth_user_id="clerk_admin", app_role="admin")
    opened = _open_vertical_position(symbol="msft")

    other_user_response = client.get("/user/options/paper-structures/review", headers=_ADMIN_AUTH)
    assert other_user_response.status_code == 200, other_user_response.text
    assert other_user_response.json()["items"] == []

    close_response = client.post(
        f"/user/options/paper-structures/{opened['position_id']}/close",
        headers=_USER_AUTH,
        json=_close_payload(opened),
    )
    assert close_response.status_code == 200, close_response.text

    response = client.get("/user/options/paper-structures/review", headers=_USER_AUTH)
    assert response.status_code == 200, response.text
    assert response.json()["items"] == []


def test_suspended_user_cannot_access_options_position_review() -> None:
    _approve_user(
        headers=_USER_AUTH,
        external_auth_user_id="clerk_user",
        approval_status="suspended",
    )

    response = client.get("/user/options/paper-structures/review", headers=_USER_AUTH)
    assert response.status_code == 403, response.text


def test_rejected_user_cannot_access_options_position_review() -> None:
    _approve_user(
        headers=_USER_AUTH,
        external_auth_user_id="clerk_user",
        approval_status="rejected",
    )

    response = client.get("/user/options/paper-structures/review", headers=_USER_AUTH)
    assert response.status_code == 403, response.text


def test_options_position_review_does_not_expose_provider_secrets() -> None:
    _approve_user(headers=_USER_AUTH, external_auth_user_id="clerk_user")
    _open_vertical_position(symbol="qqq")

    response = client.get("/user/options/paper-structures/review", headers=_USER_AUTH)
    assert response.status_code == 200, response.text
    serialized = response.text.lower()
    assert "sk-proj" not in serialized
    assert "sk-live" not in serialized
    assert "sk-test" not in serialized
    assert "secret" not in serialized
    assert "api_key" not in serialized
