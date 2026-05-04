from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from macmarket_trader.api.main import app
from macmarket_trader.api.routes import admin as admin_routes
from macmarket_trader.config import settings
from macmarket_trader.data.providers.market_data import OptionContractResolution
from macmarket_trader.domain.models import (
    AppUserModel,
    OrderModel,
    PaperOptionOrderLegModel,
    PaperOptionOrderModel,
    PaperOptionPositionLegModel,
    PaperOptionPositionModel,
    PaperOptionTradeModel,
    PaperPositionModel,
    PaperTradeModel,
    RecommendationModel,
    ReplayRunModel,
)
from macmarket_trader.storage.db import SessionLocal


client = TestClient(app)
_USER_AUTH = {"Authorization": "Bearer user-token"}


def _approve_default_user(*, commission_per_contract: float | None = None) -> int:
    response = client.get("/user/me", headers=_USER_AUTH)
    assert response.status_code == 200, response.text
    with SessionLocal() as session:
        user = session.execute(
            select(AppUserModel).where(AppUserModel.external_auth_user_id == "clerk_user")
        ).scalar_one()
        user.approval_status = "approved"
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
        "notes": "paper open test",
    }


def _iron_condor_payload() -> dict[str, object]:
    expiration = date(2026, 5, 16).isoformat()
    return {
        "market_mode": "options",
        "structure_type": "iron_condor",
        "underlying_symbol": "qqq",
        "expiration": expiration,
        "legs": [
            {"action": "buy", "right": "put", "strike": 470.0, "expiration": expiration, "premium": 0.5, "label": "lower long put"},
            {"action": "sell", "right": "put", "strike": 480.0, "expiration": expiration, "premium": 2.0, "label": "short put"},
            {"action": "sell", "right": "call", "strike": 520.0, "expiration": expiration, "premium": 2.0, "label": "short call"},
            {"action": "buy", "right": "call", "strike": 530.0, "expiration": expiration, "premium": 0.5, "label": "higher long call"},
        ],
        "notes": "paper iron condor open test",
    }


def test_open_option_paper_structure_creates_order_and_position_only() -> None:
    user_id = _approve_default_user(commission_per_contract=0.75)
    before = _counts()

    response = client.post(
        "/user/options/paper-structures/open",
        headers=_USER_AUTH,
        json=_vertical_debit_payload(),
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["market_mode"] == "options"
    assert payload["structure_type"] == "vertical_debit_spread"
    assert payload["underlying_symbol"] == "AAPL"
    assert payload["status"] == "open"
    assert payload["order_status"] == "opened"
    assert payload["position_status"] == "open"
    assert payload["opening_net_debit"] == 2.6
    assert payload["opening_net_credit"] is None
    assert payload["commission_per_contract"] == 0.75
    assert payload["opening_commissions"] == 1.5
    assert payload["max_profit"] == 740.0
    assert payload["max_loss"] == 260.0
    assert payload["breakevens"] == [207.6]
    assert payload["execution_enabled"] is False
    assert payload["persistence_enabled"] is True
    assert payload["paper_only"] is True
    assert "paper fee modeling only" in payload["operator_disclaimer"]
    assert len(payload["legs"]) == 2
    assert payload["legs"][0]["entry_premium"] == 4.2
    assert payload["legs"][0]["quantity"] == 1
    assert payload["legs"][0]["multiplier"] == 100

    after = _counts()
    assert after["option_orders"] == before["option_orders"] + 1
    assert after["option_order_legs"] == before["option_order_legs"] + 2
    assert after["option_positions"] == before["option_positions"] + 1
    assert after["option_position_legs"] == before["option_position_legs"] + 2
    assert after["option_trades"] == before["option_trades"]
    assert after["equity_orders"] == before["equity_orders"]
    assert after["equity_positions"] == before["equity_positions"]
    assert after["equity_trades"] == before["equity_trades"]
    assert after["recommendations"] == before["recommendations"]
    assert after["replay_runs"] == before["replay_runs"]

    with SessionLocal() as session:
        order_row = session.get(PaperOptionOrderModel, payload["order_id"])
        position_row = session.get(PaperOptionPositionModel, payload["position_id"])
        assert order_row is not None
        assert position_row is not None
        assert order_row.app_user_id == user_id
        assert position_row.app_user_id == user_id
        assert order_row.execution_enabled is False
        assert order_row.status == "opened"
        assert position_row.status == "open"
        assert position_row.source_order_id == order_row.id


def test_open_option_paper_structure_snaps_to_listed_contracts_when_provider_configured(monkeypatch) -> None:
    monkeypatch.setattr(settings, "polygon_enabled", True)
    monkeypatch.setattr(settings, "polygon_api_key", "polygon-key")
    monkeypatch.setattr(settings, "polygon_base_url", "https://api.polygon.io")
    _approve_default_user()
    expiration = date(2026, 5, 15)
    selections: list[tuple[str, float]] = []

    class ContractResolvingService:
        def resolve_option_contract(self, *, underlying_symbol: str, expiration, option_type: str, target_strike: float):
            del expiration
            selections.append((option_type, target_strike))
            selected = 206.0 if target_strike == 205.0 else 216.0
            right = "C" if option_type == "call" else "P"
            return OptionContractResolution(
                requested_underlying=underlying_symbol.upper(),
                underlying_asset_type="equity",
                target_expiration=date(2026, 5, 15),
                selected_expiration=date(2026, 5, 15),
                option_type=option_type,
                target_strike=target_strike,
                selected_strike=selected,
                option_symbol=f"O:AAPL260515{right}{int(selected * 1000):08d}",
                provider="polygon",
                contract_selection_method="provider_reference_exact_expiration",
                strike_snap_distance=abs(selected - target_strike),
            )

    monkeypatch.setattr(admin_routes, "market_data_service", ContractResolvingService())

    response = client.post(
        "/user/options/paper-structures/open",
        headers=_USER_AUTH,
        json=_vertical_debit_payload(),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert selections == [("call", 205.0), ("call", 215.0)]
    assert payload["legs"][0]["option_symbol"] == "O:AAPL260515C00206000"
    assert payload["legs"][0]["strike"] == 206.0
    assert payload["legs"][0]["target_strike"] == 205.0
    assert payload["legs"][0]["contract_selection"]["selected_listed_strike"] == 206.0

    with SessionLocal() as session:
        position_leg = session.execute(
            select(PaperOptionPositionLegModel).where(PaperOptionPositionLegModel.id == payload["legs"][0]["id"])
        ).scalar_one()
        assert position_leg.option_symbol == "O:AAPL260515C00206000"
        assert position_leg.target_strike == 205.0
        assert position_leg.contract_selection["contract_selection_method"] == "provider_reference_exact_expiration"


def test_open_option_paper_structure_blocks_unresolvable_contracts_when_provider_configured(monkeypatch) -> None:
    monkeypatch.setattr(settings, "polygon_enabled", True)
    monkeypatch.setattr(settings, "polygon_api_key", "polygon-key")
    monkeypatch.setattr(settings, "polygon_base_url", "https://api.polygon.io")
    _approve_default_user()
    before = _counts()

    class UnresolvableService:
        def resolve_option_contract(self, *, underlying_symbol: str, expiration, option_type: str, target_strike: float):
            return OptionContractResolution(
                requested_underlying=underlying_symbol.upper(),
                underlying_asset_type="equity",
                target_expiration=expiration,
                selected_expiration=None,
                option_type=option_type,
                target_strike=target_strike,
                selected_strike=None,
                option_symbol=None,
                provider="polygon",
                contract_selection_method="provider_reference_unavailable",
                unavailable_reason="No listed option contracts matched requested strike.",
            )

    monkeypatch.setattr(admin_routes, "market_data_service", UnresolvableService())

    response = client.post(
        "/user/options/paper-structures/open",
        headers=_USER_AUTH,
        json=_vertical_debit_payload(),
    )

    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "listed_option_contract_resolution_required"
    assert _counts() == before


def test_open_option_paper_structure_rejects_iron_condor_when_listed_chain_is_incomplete(monkeypatch) -> None:
    monkeypatch.setattr(settings, "polygon_enabled", True)
    monkeypatch.setattr(settings, "polygon_api_key", "polygon-key")
    monkeypatch.setattr(settings, "polygon_base_url", "https://api.polygon.io")
    _approve_default_user()
    before = _counts()

    class CallsOnlyOptionsService:
        def option_contracts(self, *, underlying_symbol: str, expiration, option_type: str | None = None, limit: int = 1000):
            del underlying_symbol, expiration, option_type, limit
            return [
                {"ticker": "O:QQQ260516C00520000", "contract_type": "call", "strike_price": 520.0, "expiration_date": "2026-05-16"},
                {"ticker": "O:QQQ260516C00530000", "contract_type": "call", "strike_price": 530.0, "expiration_date": "2026-05-16"},
            ]

    monkeypatch.setattr(admin_routes, "market_data_service", CallsOnlyOptionsService())

    response = client.post(
        "/user/options/paper-structures/open",
        headers=_USER_AUTH,
        json=_iron_condor_payload(),
    )

    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "listed_option_contract_resolution_required"
    assert _counts() == before


def test_open_option_paper_structure_blocks_naked_short_and_persists_nothing() -> None:
    _approve_default_user()
    before = _counts()

    response = client.post(
        "/user/options/paper-structures/open",
        headers=_USER_AUTH,
        json={
            "market_mode": "options",
            "structure_type": "long_call",
            "underlying_symbol": "SPY",
            "legs": [
                {
                    "action": "sell",
                    "right": "call",
                    "strike": 500.0,
                    "expiration": date(2026, 5, 15).isoformat(),
                    "premium": 4.5,
                }
            ],
        },
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "naked_short_option_not_supported"
    assert _counts() == before


def test_open_option_paper_structure_blocks_invalid_leg_data_and_persists_nothing() -> None:
    _approve_default_user()
    before = _counts()
    payload = _vertical_debit_payload()
    payload["legs"][0]["premium"] = -1.0

    response = client.post(
        "/user/options/paper-structures/open",
        headers=_USER_AUTH,
        json=payload,
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "invalid_premium"
    assert _counts() == before
