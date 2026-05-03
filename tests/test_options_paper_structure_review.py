from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from macmarket_trader.api.main import app
from macmarket_trader.api.routes import admin as admin_routes
from macmarket_trader.data.providers.market_data import MarketSnapshot, OptionContractSnapshot, build_polygon_option_ticker, unavailable_option_contract_snapshot
from macmarket_trader.domain.models import AppUserModel, OrderModel, PaperOptionTradeModel, PaperPositionModel, PaperTradeModel
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


class _StubOptionMarkService:
    def __init__(self, snapshots: dict[str, OptionContractSnapshot], underlying_marks: dict[str, float] | None = None) -> None:
        self.snapshots = snapshots
        self.underlying_marks = underlying_marks or {}

    def option_contract_snapshot(self, *, underlying_symbol: str, option_symbol: str) -> OptionContractSnapshot:
        del underlying_symbol
        return self.snapshots.get(
            option_symbol,
            unavailable_option_contract_snapshot(
                underlying_symbol="UNKNOWN",
                option_symbol=option_symbol,
                provider="polygon",
                missing_fields=["option_mark_data"],
            ),
        )

    def latest_snapshot(self, symbol: str, timeframe: str = "1D") -> MarketSnapshot:
        del timeframe
        normalized = symbol.upper()
        if normalized not in self.underlying_marks:
            raise RuntimeError("underlying mark unavailable")
        mark = self.underlying_marks[normalized]
        return MarketSnapshot(
            symbol=normalized,
            timeframe="1D",
            as_of=datetime(2026, 5, 3, 20, 0, tzinfo=UTC),
            open=mark,
            high=mark,
            low=mark,
            close=mark,
            volume=1000,
            source="polygon",
            fallback_mode=False,
        )


def _iron_condor_payload(*, symbol: str = "qqq", quantity: int = 1, days_to_expiration: int = 30) -> dict[str, object]:
    expiration = (utc_now().date() + timedelta(days=days_to_expiration)).isoformat()
    return {
        "market_mode": "options",
        "structure_type": "iron_condor",
        "underlying_symbol": symbol,
        "legs": [
            {"action": "buy", "right": "put", "strike": 90.0, "expiration": expiration, "premium": 1.0, "quantity": quantity, "label": "long put wing"},
            {"action": "sell", "right": "put", "strike": 95.0, "expiration": expiration, "premium": 2.5, "quantity": quantity, "label": "short put body"},
            {"action": "sell", "right": "call", "strike": 105.0, "expiration": expiration, "premium": 2.0, "quantity": quantity, "label": "short call body"},
            {"action": "buy", "right": "call", "strike": 110.0, "expiration": expiration, "premium": 1.0, "quantity": quantity, "label": "long call wing"},
        ],
        "notes": "paper options expiration review test",
    }


def _open_iron_condor(*, symbol: str = "qqq", quantity: int = 1, days_to_expiration: int = 30) -> dict[str, object]:
    response = client.post(
        "/user/options/paper-structures/open",
        headers=_USER_AUTH,
        json=_iron_condor_payload(symbol=symbol, quantity=quantity, days_to_expiration=days_to_expiration),
    )
    assert response.status_code == 200, response.text
    return response.json()


def _count_rows(model: type) -> int:
    with SessionLocal() as session:
        return len(session.execute(select(model)).scalars().all())


def _option_symbol(*, underlying: str, expiration: str, option_type: str, strike: float) -> str:
    return build_polygon_option_ticker(
        underlying_symbol=underlying,
        expiration=datetime.fromisoformat(expiration).date(),
        option_type=option_type,
        strike=strike,
    )


def _snapshot(
    *,
    underlying: str,
    option_symbol: str,
    mark: float | None,
    method: str = "quote_mid",
    stale: bool = False,
    missing: list[str] | None = None,
    provider_error: str | None = None,
    iv: float | None = 0.31,
) -> OptionContractSnapshot:
    return OptionContractSnapshot(
        option_symbol=option_symbol,
        underlying_symbol=underlying,
        provider="polygon",
        endpoint=f"/v3/snapshot/options/{underlying}/{option_symbol}",
        mark_price=mark,
        mark_method=method if mark is not None else "unavailable",
        as_of=datetime(2026, 5, 3, 20, 0, tzinfo=UTC) if mark is not None else None,
        stale=stale,
        bid=mark - 0.05 if mark is not None else None,
        ask=mark + 0.05 if mark is not None else None,
        latest_trade_price=mark,
        implied_volatility=iv,
        open_interest=1200,
        delta=0.45,
        gamma=0.04,
        theta=-0.08,
        vega=0.12,
        underlying_price=205.5,
        missing_fields=missing or ([] if mark is not None else ["option_mark_data"]),
        provider_error=provider_error,
    )


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
    assert "option_mark_data" in review["legs"][0]["missing_data"]
    assert "provider_option_snapshot_not_supported" in review["legs"][0]["missing_data"]


def test_options_position_review_uses_provider_quote_mid_marks_for_structure_pnl(monkeypatch) -> None:
    _approve_user(
        headers=_USER_AUTH,
        external_auth_user_id="clerk_user",
        commission_per_contract=0.65,
    )
    opened = _open_vertical_position(symbol="goog", quantity=1, days_to_expiration=30)
    long_symbol = _option_symbol(
        underlying="GOOG",
        expiration=opened["legs"][0]["expiration"],
        option_type="call",
        strike=205.0,
    )
    short_symbol = _option_symbol(
        underlying="GOOG",
        expiration=opened["legs"][1]["expiration"],
        option_type="call",
        strike=215.0,
    )
    monkeypatch.setattr(
        admin_routes,
        "market_data_service",
        _StubOptionMarkService(
            {
                long_symbol: _snapshot(underlying="GOOG", option_symbol=long_symbol, mark=5.2),
                short_symbol: _snapshot(underlying="GOOG", option_symbol=short_symbol, mark=1.0),
            }
        ),
    )

    response = client.get("/user/options/paper-structures/review", headers=_USER_AUTH)
    assert response.status_code == 200, response.text
    review = response.json()["items"][0]

    assert review["action_classification"] == "profitable_hold"
    assert review["current_mark_debit_credit"] == 4.2
    assert review["current_mark_debit_credit_type"] == "debit"
    assert review["estimated_unrealized_gross_pnl"] == 160.0
    assert review["estimated_unrealized_pnl"] == 157.4
    assert review["estimated_total_commissions"] == 2.6
    assert review["estimated_unrealized_return_pct"] == 60.54
    assert review["provenance"]["provider_option_marks_available"] is True
    assert "option_mark_data" not in review["missing_data"]
    assert review["legs"][0]["current_mark_premium"] == 5.2
    assert review["legs"][0]["mark_method"] == "quote_mid"
    assert review["legs"][0]["implied_volatility"] == 0.31
    assert review["legs"][0]["open_interest"] == 1200
    assert review["legs"][0]["delta"] == 0.45


def test_options_position_review_uses_last_trade_mark_method(monkeypatch) -> None:
    _approve_user(headers=_USER_AUTH, external_auth_user_id="clerk_user")
    opened = _open_vertical_position(symbol="goog", quantity=1, days_to_expiration=30)
    long_symbol = _option_symbol(underlying="GOOG", expiration=opened["legs"][0]["expiration"], option_type="call", strike=205.0)
    short_symbol = _option_symbol(underlying="GOOG", expiration=opened["legs"][1]["expiration"], option_type="call", strike=215.0)
    monkeypatch.setattr(
        admin_routes,
        "market_data_service",
        _StubOptionMarkService(
            {
                long_symbol: _snapshot(underlying="GOOG", option_symbol=long_symbol, mark=4.7, method="last_trade"),
                short_symbol: _snapshot(underlying="GOOG", option_symbol=short_symbol, mark=1.4, method="last_trade"),
            }
        ),
    )

    response = client.get("/user/options/paper-structures/review", headers=_USER_AUTH)
    assert response.status_code == 200, response.text
    review = response.json()["items"][0]

    assert review["action_classification"] == "profitable_hold"
    assert [leg["mark_method"] for leg in review["legs"]] == ["last_trade", "last_trade"]
    assert review["estimated_unrealized_pnl"] == 67.4


def test_options_position_review_keeps_structure_pnl_unavailable_when_any_leg_mark_missing(monkeypatch) -> None:
    _approve_user(headers=_USER_AUTH, external_auth_user_id="clerk_user")
    opened = _open_vertical_position(symbol="goog", quantity=1, days_to_expiration=30)
    long_symbol = _option_symbol(underlying="GOOG", expiration=opened["legs"][0]["expiration"], option_type="call", strike=205.0)
    short_symbol = _option_symbol(underlying="GOOG", expiration=opened["legs"][1]["expiration"], option_type="call", strike=215.0)
    monkeypatch.setattr(
        admin_routes,
        "market_data_service",
        _StubOptionMarkService(
            {
                long_symbol: _snapshot(underlying="GOOG", option_symbol=long_symbol, mark=5.2),
                short_symbol: _snapshot(underlying="GOOG", option_symbol=short_symbol, mark=None),
            }
        ),
    )

    response = client.get("/user/options/paper-structures/review", headers=_USER_AUTH)
    assert response.status_code == 200, response.text
    review = response.json()["items"][0]

    assert review["action_classification"] == "mark_unavailable"
    assert review["current_mark_debit_credit"] is None
    assert review["estimated_unrealized_pnl"] is None
    assert "option_mark_data" in review["missing_data"]


def test_options_position_review_stale_snapshot_is_not_used_for_structure_pnl(monkeypatch) -> None:
    _approve_user(headers=_USER_AUTH, external_auth_user_id="clerk_user")
    opened = _open_vertical_position(symbol="goog", quantity=1, days_to_expiration=30)
    long_symbol = _option_symbol(underlying="GOOG", expiration=opened["legs"][0]["expiration"], option_type="call", strike=205.0)
    short_symbol = _option_symbol(underlying="GOOG", expiration=opened["legs"][1]["expiration"], option_type="call", strike=215.0)
    monkeypatch.setattr(
        admin_routes,
        "market_data_service",
        _StubOptionMarkService(
            {
                long_symbol: _snapshot(underlying="GOOG", option_symbol=long_symbol, mark=5.2, stale=True, missing=["stale_option_mark"]),
                short_symbol: _snapshot(underlying="GOOG", option_symbol=short_symbol, mark=1.0),
            }
        ),
    )

    response = client.get("/user/options/paper-structures/review", headers=_USER_AUTH)
    assert response.status_code == 200, response.text
    review = response.json()["items"][0]

    assert review["action_classification"] == "mark_unavailable"
    assert review["estimated_unrealized_pnl"] is None
    assert "stale_option_mark" in review["missing_data"]
    assert review["legs"][0]["stale"] is True


def test_options_position_review_classifies_max_profit_near_when_marks_support_it(monkeypatch) -> None:
    _approve_user(headers=_USER_AUTH, external_auth_user_id="clerk_user")
    opened = _open_vertical_position(symbol="goog", quantity=1, days_to_expiration=30)
    long_symbol = _option_symbol(underlying="GOOG", expiration=opened["legs"][0]["expiration"], option_type="call", strike=205.0)
    short_symbol = _option_symbol(underlying="GOOG", expiration=opened["legs"][1]["expiration"], option_type="call", strike=215.0)
    monkeypatch.setattr(
        admin_routes,
        "market_data_service",
        _StubOptionMarkService(
            {
                long_symbol: _snapshot(underlying="GOOG", option_symbol=long_symbol, mark=9.9),
                short_symbol: _snapshot(underlying="GOOG", option_symbol=short_symbol, mark=0.1),
            }
        ),
    )

    response = client.get("/user/options/paper-structures/review", headers=_USER_AUTH)
    assert response.status_code == 200, response.text
    review = response.json()["items"][0]

    assert review["action_classification"] == "max_profit_near"
    assert review["estimated_unrealized_pnl"] == 717.4


def test_options_position_review_sanitizes_provider_permission_errors(monkeypatch) -> None:
    secret = "polygon-review-secret"
    monkeypatch.setattr(admin_routes.settings, "polygon_api_key", secret)
    _approve_user(headers=_USER_AUTH, external_auth_user_id="clerk_user")
    opened = _open_vertical_position(symbol="goog", quantity=1, days_to_expiration=30)
    long_symbol = _option_symbol(underlying="GOOG", expiration=opened["legs"][0]["expiration"], option_type="call", strike=205.0)
    short_symbol = _option_symbol(underlying="GOOG", expiration=opened["legs"][1]["expiration"], option_type="call", strike=215.0)
    monkeypatch.setattr(
        admin_routes,
        "market_data_service",
        _StubOptionMarkService(
            {
                long_symbol: _snapshot(
                    underlying="GOOG",
                    option_symbol=long_symbol,
                    mark=None,
                    provider_error=f"not entitled apiKey={secret}",
                    missing=["provider_option_snapshot_not_entitled"],
                ),
                short_symbol: _snapshot(underlying="GOOG", option_symbol=short_symbol, mark=1.0),
            }
        ),
    )

    response = client.get("/user/options/paper-structures/review", headers=_USER_AUTH)
    assert response.status_code == 200, response.text
    serialized = response.text

    assert secret not in serialized
    assert "not entitled" in serialized
    assert "provider_option_snapshot_not_entitled" in serialized


def test_options_position_review_aggregates_repeated_entitlement_warnings(monkeypatch) -> None:
    _approve_user(headers=_USER_AUTH, external_auth_user_id="clerk_user")
    opened = _open_iron_condor(symbol="qqq", quantity=1, days_to_expiration=30)
    snapshots = {}
    for leg in opened["legs"]:
        option_symbol = _option_symbol(
            underlying="QQQ",
            expiration=leg["expiration"],
            option_type=leg["right"],
            strike=leg["strike"],
        )
        snapshots[option_symbol] = _snapshot(
            underlying="QQQ",
            option_symbol=option_symbol,
            mark=None,
            provider_error="Not entitled to this data. Upgrade URL: https://example.invalid/upgrade",
            missing=["provider_option_snapshot_not_entitled"],
        )
    monkeypatch.setattr(admin_routes, "market_data_service", _StubOptionMarkService(snapshots))

    response = client.get("/user/options/paper-structures/review", headers=_USER_AUTH)
    assert response.status_code == 200, response.text
    review = response.json()["items"][0]

    entitlement_warnings = [item for item in review["warnings"] if "not entitled to option snapshot data" in item]
    assert entitlement_warnings == [
        "Option marks unavailable: provider plan is not entitled to option snapshot data. 4 legs affected."
    ]
    assert not any("Upgrade URL" in item for item in review["warnings"])
    assert "Option marks unavailable: provider plan is not entitled to option snapshot data. 4 legs affected." in review["action_summary"]
    assert all("provider_option_snapshot_not_entitled" in leg["missing_data"] for leg in review["legs"])


def test_options_position_review_aggregates_old_synthetic_contract_not_found(monkeypatch) -> None:
    _approve_user(headers=_USER_AUTH, external_auth_user_id="clerk_user")
    _open_iron_condor(symbol="spy", quantity=1, days_to_expiration=30)

    class NotFoundService(_StubOptionMarkService):
        def option_contract_snapshot(self, *, underlying_symbol: str, option_symbol: str) -> OptionContractSnapshot:
            return unavailable_option_contract_snapshot(
                underlying_symbol=underlying_symbol,
                option_symbol=option_symbol,
                provider="polygon",
                endpoint="/v3/snapshot/options/{underlying}/{option}",
                missing_fields=["provider_option_snapshot_not_found"],
                provider_error="Polygon returned 404 - ticker not found",
            )

    monkeypatch.setattr(admin_routes, "market_data_service", NotFoundService({}))

    response = client.get("/user/options/paper-structures/review", headers=_USER_AUTH)
    assert response.status_code == 200, response.text
    review = response.json()["items"][0]

    synthetic_warnings = [item for item in review["warnings"] if "older synthetic/generated strike" in item]
    assert synthetic_warnings == [
        "Saved leg contract was not found by provider. This may be an older synthetic/generated strike. Create a fresh paper options structure after provider contract resolution."
    ]
    assert all("provider_option_snapshot_not_found" in leg["missing_data"] for leg in review["legs"])
    assert not any("ticker not found" in item.lower() for item in review["warnings"])


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


def test_options_position_review_active_iron_condor_has_active_expiration_status(monkeypatch) -> None:
    _approve_user(headers=_USER_AUTH, external_auth_user_id="clerk_user")
    opened = _open_iron_condor(symbol="qqq", days_to_expiration=30)
    monkeypatch.setattr(admin_routes, "market_data_service", _StubOptionMarkService({}, {"QQQ": 100.0}))

    response = client.get("/user/options/paper-structures/review", headers=_USER_AUTH)
    assert response.status_code == 200, response.text
    review = response.json()["items"][0]

    assert review["structure_id"] == opened["position_id"]
    assert review["expiration_status"] == "active"
    assert review["days_to_expiration"] == 30
    assert review["settlement_required"] is False
    assert review["underlying_mark_price"] == 100.0


def test_options_position_review_spx_uses_index_cash_settlement_language(monkeypatch) -> None:
    _approve_user(headers=_USER_AUTH, external_auth_user_id="clerk_user")
    _open_iron_condor(symbol="spx", days_to_expiration=5)
    monkeypatch.setattr(admin_routes, "market_data_service", _StubOptionMarkService({}, {"SPX": 5000.0}))

    response = client.get("/user/options/paper-structures/review", headers=_USER_AUTH)
    assert response.status_code == 200, response.text
    review = response.json()["items"][0]

    assert review["underlying_symbol"] == "SPX"
    assert review["underlying_asset_type"] == "index"
    assert review["settlement_style"] == "cash_settled"
    assert review["deliverable_type"] == "cash_index"
    assert "Cash-settled. No share delivery modeled." in " ".join(review["warnings"])
    assert "cash-settlement" in review["assignment_risk_summary"]
    assert "cash-settlement" in review["expiration_action_summary"]
    assert "share assignment" not in review["assignment_risk_summary"].lower()
    assert review["provenance"]["settlement_style"] == "cash_settled"


def test_options_position_review_expires_today_uses_expiration_due_classification(monkeypatch) -> None:
    _approve_user(headers=_USER_AUTH, external_auth_user_id="clerk_user")
    _open_vertical_position(symbol="goog", days_to_expiration=0)
    monkeypatch.setattr(admin_routes, "market_data_service", _StubOptionMarkService({}, {"GOOG": 207.0}))

    response = client.get("/user/options/paper-structures/review", headers=_USER_AUTH)
    assert response.status_code == 200, response.text
    review = response.json()["items"][0]

    assert review["expiration_status"] == "expires_today"
    assert review["action_classification"] == "expiration_due"
    assert review["legs"][0]["moneyness"] == "itm"
    assert review["legs"][0]["exercise_risk"] == "high"
    assert "no automatic exercise or assignment" in review["expiration_action_summary"].lower()


def test_options_position_review_expired_otm_iron_condor_has_max_profit_settlement_preview(monkeypatch) -> None:
    _approve_user(headers=_USER_AUTH, external_auth_user_id="clerk_user", commission_per_contract=0.65)
    _open_iron_condor(symbol="qqq", days_to_expiration=-1)
    monkeypatch.setattr(admin_routes, "market_data_service", _StubOptionMarkService({}, {"QQQ": 100.0}))

    response = client.get("/user/options/paper-structures/review", headers=_USER_AUTH)
    assert response.status_code == 200, response.text
    review = response.json()["items"][0]

    assert review["expiration_status"] == "expired_unsettled"
    assert review["action_classification"] == "settlement_available"
    assert review["settlement_required"] is True
    assert review["settlement_available"] is True
    assert review["settlement_preview"]["gross_settlement_pnl"] == 250.0
    assert review["settlement_preview"]["net_realized_pnl_estimate"] == 244.8
    assert review["settlement_preview"]["total_commissions"] == 5.2
    assert review["settlement_preview"]["max_profit_loss_comparison"] == "near_or_at_max_profit"
    assert all(leg["intrinsic_value"] == 0.0 for leg in review["legs"])


def test_options_position_review_expired_breached_iron_condor_has_loss_preview(monkeypatch) -> None:
    _approve_user(headers=_USER_AUTH, external_auth_user_id="clerk_user", commission_per_contract=0.65)
    _open_iron_condor(symbol="qqq", days_to_expiration=-1)
    monkeypatch.setattr(admin_routes, "market_data_service", _StubOptionMarkService({}, {"QQQ": 112.0}))

    response = client.get("/user/options/paper-structures/review", headers=_USER_AUTH)
    assert response.status_code == 200, response.text
    review = response.json()["items"][0]

    assert review["action_classification"] == "settlement_available"
    assert review["settlement_preview"]["gross_settlement_pnl"] == -250.0
    assert review["settlement_preview"]["net_realized_pnl_estimate"] == -255.2
    assert review["settlement_preview"]["max_profit_loss_comparison"] == "near_or_at_max_loss"
    assert review["legs"][2]["moneyness"] == "itm"
    assert review["legs"][2]["assignment_risk"] == "high"


def test_options_position_review_blocks_expired_settlement_when_underlying_mark_missing(monkeypatch) -> None:
    _approve_user(headers=_USER_AUTH, external_auth_user_id="clerk_user")
    _open_iron_condor(symbol="qqq", days_to_expiration=-1)
    monkeypatch.setattr(admin_routes, "market_data_service", _StubOptionMarkService({}))

    response = client.get("/user/options/paper-structures/review", headers=_USER_AUTH)
    assert response.status_code == 200, response.text
    review = response.json()["items"][0]

    assert review["expiration_status"] == "expired_unsettled"
    assert review["action_classification"] == "settlement_blocked_missing_underlying"
    assert review["settlement_required"] is True
    assert review["settlement_available"] is False
    assert review["settlement_preview"] is None
    assert "underlying_mark_price" in review["missing_data"]


def test_options_position_review_flags_assignment_risk_for_near_expiration_short_itm_leg(monkeypatch) -> None:
    _approve_user(headers=_USER_AUTH, external_auth_user_id="clerk_user")
    _open_iron_condor(symbol="qqq", days_to_expiration=2)
    monkeypatch.setattr(admin_routes, "market_data_service", _StubOptionMarkService({}, {"QQQ": 107.0}))

    response = client.get("/user/options/paper-structures/review", headers=_USER_AUTH)
    assert response.status_code == 200, response.text
    review = response.json()["items"][0]

    assert review["expiration_status"] == "expiration_warning"
    assert review["action_classification"] == "assignment_risk_review"
    assert review["legs"][2]["moneyness"] == "itm"
    assert review["legs"][2]["assignment_risk"] == "elevated"
    assert "assignment risk" in review["assignment_risk_summary"].lower()


def test_options_expiration_settlement_requires_confirmation_and_is_idempotent(monkeypatch) -> None:
    user_id = _approve_user(headers=_USER_AUTH, external_auth_user_id="clerk_user", commission_per_contract=0.65)
    before_equity_orders = _count_rows(OrderModel)
    before_equity_positions = _count_rows(PaperPositionModel)
    before_equity_trades = _count_rows(PaperTradeModel)
    opened = _open_iron_condor(symbol="qqq", days_to_expiration=-1)
    monkeypatch.setattr(admin_routes, "market_data_service", _StubOptionMarkService({}, {"QQQ": 100.0}))

    missing_confirmation = client.post(
        f"/user/options/paper-structures/{opened['position_id']}/settle-expiration",
        headers=_USER_AUTH,
        json={"confirmation": "NOPE", "underlying_settlement_price": 100.0},
    )
    assert missing_confirmation.status_code == 400, missing_confirmation.text
    assert missing_confirmation.json()["detail"] == "settlement_confirmation_required"

    response = client.post(
        f"/user/options/paper-structures/{opened['position_id']}/settle-expiration",
        headers=_USER_AUTH,
        json={"confirmation": "SETTLE", "underlying_settlement_price": 100.0},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "closed"
    assert payload["settlement_mode"] == "expiration"
    assert payload["gross_pnl"] == 250.0
    assert payload["opening_commissions"] == 2.6
    assert payload["closing_commissions"] == 2.6
    assert payload["total_commissions"] == 5.2
    assert payload["net_pnl"] == 244.8
    assert payload["execution_enabled"] is False
    assert payload["paper_only"] is True

    second = client.post(
        f"/user/options/paper-structures/{opened['position_id']}/settle-expiration",
        headers=_USER_AUTH,
        json={"confirmation": "SETTLE", "underlying_settlement_price": 100.0},
    )
    assert second.status_code == 409, second.text
    assert second.json()["detail"] == "option_position_not_open"

    with SessionLocal() as session:
        trade_count = session.execute(
            select(PaperOptionTradeModel).where(PaperOptionTradeModel.app_user_id == user_id)
        ).scalars().all()
        assert len(trade_count) == 1
        assert trade_count[0].settlement_mode == "expiration"

    review_after_settlement = client.get("/user/options/paper-structures/review", headers=_USER_AUTH)
    assert review_after_settlement.status_code == 200, review_after_settlement.text
    assert review_after_settlement.json()["items"] == []
    assert _count_rows(OrderModel) == before_equity_orders
    assert _count_rows(PaperPositionModel) == before_equity_positions
    assert _count_rows(PaperTradeModel) == before_equity_trades


def test_options_expiration_settlement_is_user_scoped(monkeypatch) -> None:
    _approve_user(headers=_USER_AUTH, external_auth_user_id="clerk_user")
    _approve_user(headers=_ADMIN_AUTH, external_auth_user_id="clerk_admin", app_role="admin")
    opened = _open_iron_condor(symbol="qqq", days_to_expiration=-1)
    monkeypatch.setattr(admin_routes, "market_data_service", _StubOptionMarkService({}, {"QQQ": 100.0}))

    response = client.post(
        f"/user/options/paper-structures/{opened['position_id']}/settle-expiration",
        headers=_ADMIN_AUTH,
        json={"confirmation": "SETTLE", "underlying_settlement_price": 100.0},
    )

    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "option_position_not_found"


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
