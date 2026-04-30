from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from macmarket_trader.api.main import app
from macmarket_trader.domain.models import (
    AppUserModel,
    RecommendationModel,
    StrategyReportScheduleModel,
    WatchlistModel,
)
from macmarket_trader.storage.db import SessionLocal
from macmarket_trader.storage.repositories import SymbolUniverseRepository

client = TestClient(app)


def _seed_and_approve_user(
    token: str = "user-token",
    *,
    external_auth_user_id: str = "clerk_user",
) -> int:
    client.get("/user/me", headers={"Authorization": f"Bearer {token}"})
    with SessionLocal() as session:
        user = session.execute(
            select(AppUserModel).where(
                AppUserModel.external_auth_user_id == external_auth_user_id
            )
        ).scalar_one()
        user.approval_status = "approved"
        session.commit()
        return user.id


def _create_watchlist(name: str, symbols: list[str], *, token: str = "user-token") -> int:
    response = client.post(
        "/user/watchlists",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": name, "symbols": symbols},
    )
    assert response.status_code == 200
    return int(response.json()["id"])


def test_preview_manual_symbols_normalizes_dedupes_and_does_not_call_providers(monkeypatch) -> None:
    _seed_and_approve_user()
    from macmarket_trader.api.routes import admin as admin_routes

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("symbol universe preview must not call market data providers")

    monkeypatch.setattr(admin_routes.market_data_service, "historical_bars", fail_if_called)

    response = client.post(
        "/user/symbol-universe/preview",
        headers={"Authorization": "Bearer user-token"},
        json={
            "source_type": "manual",
            "manual_symbols": [" spy, qqq ", "SPY", "", "msft\nqqq"],
            "excluded_symbols": ["MSFT"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["resolved_symbols"] == ["SPY", "QQQ"]
    assert body["symbol_count"] == 2
    assert body["duplicates_ignored"] == 2
    assert body["exclusions_applied"] == 1
    assert body["preview_only"] is True
    assert body["execution_enabled"] is False
    assert body["does_not_submit_recommendations"] is True
    assert body["provider_metadata_available"] is False


def test_preview_watchlist_resolves_legacy_watchlist_snapshot() -> None:
    _seed_and_approve_user()
    watchlist_id = _create_watchlist("Sector ETFs", ["xlk", "xlf", "xlk"])

    response = client.post(
        "/user/symbol-universe/preview",
        headers={"Authorization": "Bearer user-token"},
        json={"source_type": "watchlist", "watchlist_id": watchlist_id},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["resolved_symbols"] == ["XLK", "XLF"]
    assert body["source_type"] == "watchlist"
    assert body["resolved_source"] == "watchlist"
    assert body["source_label"] == "Watchlist: Sector ETFs"
    assert body["provenance"]["watchlist_ids"] == [watchlist_id]


def test_preview_watchlist_plus_manual_combines_pinned_manual_and_watchlist_order() -> None:
    _seed_and_approve_user()
    watchlist_id = _create_watchlist("Blend", ["QQQ", "IWM"])

    response = client.post(
        "/user/symbol-universe/preview",
        headers={"Authorization": "Bearer user-token"},
        json={
            "source_type": "watchlist_plus_manual",
            "watchlist_id": watchlist_id,
            "manual_symbols": ["aapl", "qqq"],
            "pinned_symbols": ["spy"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["resolved_symbols"] == ["SPY", "AAPL", "QQQ", "IWM"]
    assert body["pinned_symbols_applied"] == ["SPY"]
    assert body["duplicates_ignored"] == 1
    assert body["source_label"] == "Watchlist plus manual: Blend"


def test_preview_all_active_uses_user_symbol_universe_without_inactive_rows() -> None:
    app_user_id = _seed_and_approve_user()
    repo = SymbolUniverseRepository(SessionLocal)
    repo.upsert_user_symbol(app_user_id=app_user_id, symbol="AAPL")
    repo.upsert_user_symbol(app_user_id=app_user_id, symbol="MSFT", active=False)

    response = client.post(
        "/user/symbol-universe/preview",
        headers={"Authorization": "Bearer user-token"},
        json={"source_type": "all_active"},
    )

    assert response.status_code == 200
    assert response.json()["resolved_symbols"] == ["AAPL"]

    include_inactive = client.post(
        "/user/symbol-universe/preview",
        headers={"Authorization": "Bearer user-token"},
        json={"source_type": "all_active", "active_only": False},
    )
    assert include_inactive.status_code == 200
    assert include_inactive.json()["resolved_symbols"] == ["AAPL", "MSFT"]


def test_preview_blocks_wrong_user_watchlist_access() -> None:
    _seed_and_approve_user("admin-token", external_auth_user_id="clerk_admin")
    admin_watchlist_id = _create_watchlist("Admin only", ["AAPL"], token="admin-token")
    _seed_and_approve_user()

    response = client.post(
        "/user/symbol-universe/preview",
        headers={"Authorization": "Bearer user-token"},
        json={"source_type": "watchlist", "watchlist_id": admin_watchlist_id},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "watchlist not found"


def test_preview_empty_result_returns_warning_not_server_error() -> None:
    _seed_and_approve_user()

    response = client.post(
        "/user/symbol-universe/preview",
        headers={"Authorization": "Bearer user-token"},
        json={"source_type": "manual", "manual_symbols": ["  ", "\n"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["resolved_symbols"] == []
    assert body["symbol_count"] == 0
    assert "resolved_universe_empty" in body["warnings"]


def test_preview_rejects_unknown_source_type() -> None:
    _seed_and_approve_user()

    response = client.post(
        "/user/symbol-universe/preview",
        headers={"Authorization": "Bearer user-token"},
        json={"source_type": "provider_search", "manual_symbols": ["AAPL"]},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "unsupported_symbol_universe_source_type"


def test_preview_does_not_create_recommendations_or_mutate_watchlists_or_schedules() -> None:
    _seed_and_approve_user()
    watchlist_id = _create_watchlist("Stable", ["SPY", "QQQ"])
    schedule = client.post(
        "/user/strategy-schedules",
        headers={"Authorization": "Bearer user-token"},
        json={"name": "Stable schedule", "symbols": ["AAPL"], "market_mode": "equities"},
    )
    assert schedule.status_code == 200

    with SessionLocal() as session:
        recommendation_count_before = session.scalar(select(func.count(RecommendationModel.id)))
        schedule_count_before = session.scalar(select(func.count(StrategyReportScheduleModel.id)))
        watchlist_before = session.execute(
            select(WatchlistModel).where(WatchlistModel.id == watchlist_id)
        ).scalar_one()
        watchlist_symbols_before = list(watchlist_before.symbols)

    response = client.post(
        "/user/symbol-universe/preview",
        headers={"Authorization": "Bearer user-token"},
        json={
            "source_type": "watchlist_plus_manual",
            "watchlist_id": watchlist_id,
            "manual_symbols": ["MSFT"],
        },
    )
    assert response.status_code == 200

    with SessionLocal() as session:
        assert session.scalar(select(func.count(RecommendationModel.id))) == recommendation_count_before
        assert session.scalar(select(func.count(StrategyReportScheduleModel.id))) == schedule_count_before
        watchlist_after = session.execute(
            select(WatchlistModel).where(WatchlistModel.id == watchlist_id)
        ).scalar_one()
        assert watchlist_after.symbols == watchlist_symbols_before
