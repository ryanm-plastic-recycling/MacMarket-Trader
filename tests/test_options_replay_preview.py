import math
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from macmarket_trader.api.main import app
from macmarket_trader.domain.models import (
    AppUserModel,
    AuditLogModel,
    OrderModel,
    RecommendationModel,
    ReplayRunModel,
)
from macmarket_trader.storage.db import SessionLocal, init_db


client = TestClient(app)
_USER_AUTH = {"Authorization": "Bearer user-token"}


def setup_module() -> None:
    init_db()


def _approve_default_user() -> None:
    response = client.get("/user/me", headers=_USER_AUTH)
    assert response.status_code == 200, response.text
    with SessionLocal() as session:
        user = session.execute(
            select(AppUserModel).where(AppUserModel.external_auth_user_id == "clerk_user")
        ).scalar_one()
        user.approval_status = "approved"
        session.commit()


def _payload_counts() -> dict[str, int]:
    with SessionLocal() as session:
        return {
            "recommendations": session.execute(
                select(func.count()).select_from(RecommendationModel)
            ).scalar_one(),
            "replay_runs": session.execute(
                select(func.count()).select_from(ReplayRunModel)
            ).scalar_one(),
            "orders": session.execute(
                select(func.count()).select_from(OrderModel)
            ).scalar_one(),
            "audit_logs": session.execute(
                select(func.count()).select_from(AuditLogModel)
            ).scalar_one(),
        }


def _post_preview(payload: dict[str, object]):
    _approve_default_user()
    return client.post(
        "/user/options/replay-preview",
        headers=_USER_AUTH,
        json=payload,
    )


def test_options_replay_preview_call_vertical_debit_spread_contract() -> None:
    response = _post_preview(
        {
            "structure_type": "vertical_debit_spread",
            "underlying_symbol": "AAPL",
            "expiration": date(2026, 5, 15).isoformat(),
            "legs": [
                {"action": "buy", "right": "call", "strike": 100, "premium": 6.0},
                {"action": "sell", "right": "call", "strike": 110, "premium": 2.0},
            ],
        }
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["execution_enabled"] is False
    assert payload["persistence_enabled"] is False
    assert payload["market_mode"] == "options"
    assert payload["preview_type"] == "expiration_payoff"
    assert payload["status"] == "ready"
    assert payload["structure_type"] == "vertical_debit_spread"
    assert payload["underlying_symbol"] == "AAPL"
    assert payload["replay_run_id"] is None
    assert payload["recommendation_id"] is None
    assert payload["order_id"] is None
    assert payload["is_defined_risk"] is True
    assert payload["net_debit"] == 4.0
    assert payload["net_credit"] is None
    assert payload["max_profit"] == 600.0
    assert payload["max_loss"] == 400.0
    assert payload["breakevens"] == [104.0]
    assert payload["blocked_reason"] is None
    assert payload["operator_disclaimer"] == "Options research only. Paper-only preview. Not execution support."

    payoff_points = payload["payoff_points"]
    assert [point["underlying_price"] for point in payoff_points] == [0.0, 90.0, 100.0, 104.0, 110.0, 120.0]
    assert payoff_points[0]["total_payoff"] == -400.0
    assert payoff_points[3]["total_payoff"] == 0.0
    assert payoff_points[-1]["total_payoff"] == 600.0
    for point in payoff_points:
        assert math.isfinite(point["underlying_price"])
        assert math.isfinite(point["total_payoff"])
        for leg_payoff in point["leg_payoffs"]:
            assert math.isfinite(leg_payoff["payoff"])


def test_options_replay_preview_put_vertical_debit_spread_contract() -> None:
    response = _post_preview(
        {
            "structure_type": "vertical_debit_spread",
            "underlying_symbol": "SPY",
            "legs": [
                {"action": "buy", "right": "put", "strike": 110, "premium": 7.0},
                {"action": "sell", "right": "put", "strike": 100, "premium": 3.0},
            ],
            "underlying_prices": [120, 110, 106, 100, 90],
        }
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["status"] == "ready"
    assert payload["net_debit"] == 4.0
    assert payload["max_profit"] == 600.0
    assert payload["max_loss"] == 400.0
    assert payload["breakevens"] == [106.0]
    assert [point["underlying_price"] for point in payload["payoff_points"]] == [90.0, 100.0, 106.0, 110.0, 120.0]
    assert payload["payoff_points"][0]["total_payoff"] == 600.0
    assert payload["payoff_points"][2]["total_payoff"] == 0.0
    assert payload["payoff_points"][-1]["total_payoff"] == -400.0


def test_options_replay_preview_iron_condor_contract() -> None:
    response = _post_preview(
        {
            "structure_type": "iron_condor",
            "underlying_symbol": "QQQ",
            "legs": [
                {"action": "buy", "right": "put", "strike": 90, "premium": 1.0, "label": "Long put wing"},
                {"action": "sell", "right": "put", "strike": 95, "premium": 2.5, "label": "Short put body"},
                {"action": "sell", "right": "call", "strike": 105, "premium": 2.0, "label": "Short call body"},
                {"action": "buy", "right": "call", "strike": 110, "premium": 1.0, "label": "Long call wing"},
            ],
            "underlying_prices": [85, 95, 100, 105, 115],
        }
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["status"] == "ready"
    assert payload["is_defined_risk"] is True
    assert payload["net_debit"] is None
    assert payload["net_credit"] == 2.5
    assert payload["max_profit"] == 250.0
    assert payload["max_loss"] == 250.0
    assert payload["breakevens"] == [92.5, 107.5]
    assert payload["warnings"] == []
    assert payload["legs"][0]["label"] == "Long put wing"
    assert payload["legs"][1]["label"] == "Short put body"
    assert payload["payoff_points"][0]["total_payoff"] == -250.0
    assert payload["payoff_points"][2]["total_payoff"] == 250.0
    assert payload["payoff_points"][-1]["total_payoff"] == -250.0


def test_options_replay_preview_blocks_naked_short_single_leg() -> None:
    response = _post_preview(
        {
            "structure_type": "long_call",
            "legs": [
                {"action": "sell", "right": "call", "strike": 100, "premium": 2.25},
            ],
        }
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["status"] == "blocked"
    assert payload["blocked_reason"] == "naked_short_option_not_supported"
    assert payload["execution_enabled"] is False
    assert payload["persistence_enabled"] is False
    assert payload["payoff_points"] == []


def test_options_replay_preview_blocks_invalid_payload_and_unknown_structure() -> None:
    invalid = _post_preview(
        {
            "structure_type": "vertical_debit_spread",
            "legs": [
                {"action": "buy", "right": "call", "strike": 100, "premium": -1.0},
                {"action": "sell", "right": "call", "strike": 110, "premium": 2.0},
            ],
        }
    )
    assert invalid.status_code == 200, invalid.text
    invalid_payload = invalid.json()
    assert invalid_payload["status"] == "blocked"
    assert invalid_payload["blocked_reason"] == "invalid_premium"
    assert invalid_payload["max_profit"] is None
    assert invalid_payload["max_loss"] is None

    unsupported = _post_preview(
        {
            "structure_type": "calendar_spread",
            "legs": [
                {"action": "buy", "right": "call", "strike": 100, "premium": 3.0},
            ],
        }
    )
    assert unsupported.status_code == 200, unsupported.text
    unsupported_payload = unsupported.json()
    assert unsupported_payload["status"] == "unsupported"
    assert unsupported_payload["blocked_reason"] == "unsupported_structure_type"
    assert unsupported_payload["execution_enabled"] is False
    assert unsupported_payload["persistence_enabled"] is False


def test_options_replay_preview_does_not_persist_rows() -> None:
    _approve_default_user()
    before = _payload_counts()

    response = client.post(
        "/user/options/replay-preview",
        headers=_USER_AUTH,
        json={
            "structure_type": "vertical_debit_spread",
            "underlying_symbol": "MSFT",
            "legs": [
                {"action": "buy", "right": "call", "strike": 100, "premium": 6.0},
                {"action": "sell", "right": "call", "strike": 110, "premium": 2.0},
            ],
        },
    )
    assert response.status_code == 200, response.text

    after = _payload_counts()
    assert after == before
