from __future__ import annotations

from sqlalchemy import select

from macmarket_trader.domain.models import AppUserModel
from macmarket_trader.storage.db import SessionLocal
from macmarket_trader.storage.repositories import (
    SymbolUniverseRepository,
    SymbolUniverseResolver,
    WatchlistRepository,
)


def _create_user(external_id: str, email: str) -> int:
    with SessionLocal() as session:
        user = AppUserModel(
            external_auth_user_id=external_id,
            email=email,
            display_name=email.split("@")[0],
            approval_status="approved",
            app_role="user",
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user.id


def test_user_symbol_upsert_supports_manual_metadata_and_updates_existing_row() -> None:
    app_user_id = _create_user("symbol-user", "symbol-user@example.com")
    repo = SymbolUniverseRepository(SessionLocal)

    created = repo.upsert_user_symbol(
        app_user_id=app_user_id,
        symbol=" brk.b ",
        notes="Manual add",
        tags=["Core"],
    )
    updated = repo.upsert_user_symbol(
        app_user_id=app_user_id,
        symbol="BRK.B",
        display_name="Berkshire Hathaway",
        asset_type="equity",
        exchange="NYSE",
        notes="Updated manual row",
        active=False,
        tags=["Core", "Watch Only"],
    )

    assert updated.id == created.id
    assert updated.normalized_symbol == "BRK.B"
    assert updated.provider_source is None
    assert updated.provider_symbol is None
    assert updated.display_name == "Berkshire Hathaway"
    assert updated.asset_type == "equity"
    assert updated.active is False
    assert updated.tags == ["Core", "Watch Only"]

    assert repo.get_user_symbol(app_user_id=app_user_id, symbol="brk.b").id == created.id
    assert repo.list_user_symbols(app_user_id=app_user_id, active=True) == []
    all_symbols = repo.list_user_symbols(app_user_id=app_user_id, active=None)
    assert [row.normalized_symbol for row in all_symbols] == ["BRK.B"]


def test_user_symbol_active_filtering_and_user_scope() -> None:
    first_user_id = _create_user("first-user", "first@example.com")
    second_user_id = _create_user("second-user", "second@example.com")
    repo = SymbolUniverseRepository(SessionLocal)

    repo.upsert_user_symbol(app_user_id=first_user_id, symbol="AAPL")
    repo.upsert_user_symbol(app_user_id=first_user_id, symbol="MSFT", active=False)
    repo.upsert_user_symbol(app_user_id=second_user_id, symbol="AAPL")

    assert [row.normalized_symbol for row in repo.list_user_symbols(app_user_id=first_user_id)] == [
        "AAPL"
    ]
    inactive_symbols = repo.list_user_symbols(app_user_id=first_user_id, active=False)
    assert [row.normalized_symbol for row in inactive_symbols] == ["MSFT"]

    repo.set_user_symbol_active(app_user_id=first_user_id, symbol="MSFT", active=True)
    assert [row.normalized_symbol for row in repo.list_user_symbols(app_user_id=first_user_id)] == [
        "AAPL",
        "MSFT",
    ]
    assert repo.get_user_symbol(app_user_id=second_user_id, symbol="MSFT") is None


def test_watchlist_membership_supports_linked_and_snapshot_only_rows() -> None:
    app_user_id = _create_user("membership-user", "membership@example.com")
    symbol_repo = SymbolUniverseRepository(SessionLocal)
    watchlist_repo = WatchlistRepository(SessionLocal)
    watchlist = watchlist_repo.upsert(
        app_user_id=app_user_id,
        name="Candidates",
        symbols=["SPY", "QQQ"],
    )
    linked_symbol = symbol_repo.upsert_user_symbol(app_user_id=app_user_id, symbol="SPY")

    linked = symbol_repo.add_watchlist_symbol(
        app_user_id=app_user_id,
        watchlist_id=watchlist.id,
        user_symbol_id=linked_symbol.id,
        symbol="spy",
        sort_order=2,
    )
    snapshot = symbol_repo.add_watchlist_symbol(
        app_user_id=app_user_id,
        watchlist_id=watchlist.id,
        symbol="qqq",
        sort_order=1,
    )

    assert linked is not None
    assert snapshot is not None
    assert snapshot.user_symbol_id is None
    assert watchlist.symbols == ["SPY", "QQQ"]
    assert [
        row.normalized_symbol
        for row in symbol_repo.list_watchlist_symbols(
            app_user_id=app_user_id,
            watchlist_id=watchlist.id,
        )
    ] == ["QQQ", "SPY"]

    symbol_repo.remove_watchlist_symbol(
        app_user_id=app_user_id,
        watchlist_id=watchlist.id,
        symbol="QQQ",
    )
    assert [
        row.normalized_symbol
        for row in symbol_repo.list_watchlist_symbols(
            app_user_id=app_user_id,
            watchlist_id=watchlist.id,
        )
    ] == ["SPY"]
    assert [
        row.normalized_symbol
        for row in symbol_repo.list_watchlist_symbols(
            app_user_id=app_user_id,
            watchlist_id=watchlist.id,
            active=False,
        )
    ] == ["QQQ"]


def test_watchlist_membership_enforces_user_scope() -> None:
    first_user_id = _create_user("scope-first", "scope-first@example.com")
    second_user_id = _create_user("scope-second", "scope-second@example.com")
    symbol_repo = SymbolUniverseRepository(SessionLocal)
    watchlist_repo = WatchlistRepository(SessionLocal)
    first_watchlist = watchlist_repo.upsert(
        app_user_id=first_user_id,
        name="First",
        symbols=["AAPL"],
    )
    second_symbol = symbol_repo.upsert_user_symbol(app_user_id=second_user_id, symbol="MSFT")

    assert (
        symbol_repo.add_watchlist_symbol(
            app_user_id=first_user_id,
            watchlist_id=first_watchlist.id,
            user_symbol_id=second_symbol.id,
            symbol="MSFT",
        )
        is None
    )
    assert (
        symbol_repo.add_watchlist_symbol(
            app_user_id=second_user_id,
            watchlist_id=first_watchlist.id,
            symbol="MSFT",
        )
        is None
    )
    assert (
        symbol_repo.list_watchlist_symbols(
            app_user_id=second_user_id,
            watchlist_id=first_watchlist.id,
        )
        == []
    )


def test_resolver_normalizes_and_dedupes_manual_symbols() -> None:
    assert SymbolUniverseResolver.normalize_symbols(
        [" spy, qqq ", "", "SPY", "aapl\nmsft", "   "]
    ) == ["SPY", "QQQ", "AAPL", "MSFT"]

    resolved = SymbolUniverseResolver.resolve(
        manual_symbols=[" spy ", "SPY", "qqq"],
        exclusions=["QQQ"],
    )

    assert resolved.symbols == ["SPY"]
    assert resolved.source == "manual"
    assert resolved.provenance["excluded_count"] == 1


def test_repository_resolver_combines_manual_watchlist_and_active_universe() -> None:
    app_user_id = _create_user("resolver-user", "resolver@example.com")
    symbol_repo = SymbolUniverseRepository(SessionLocal)
    watchlist_repo = WatchlistRepository(SessionLocal)
    watchlist = watchlist_repo.upsert(
        app_user_id=app_user_id,
        name="Resolver",
        symbols=["XLK", "XLF"],
    )
    symbol_repo.upsert_user_symbol(app_user_id=app_user_id, symbol="AAPL")
    symbol_repo.upsert_user_symbol(app_user_id=app_user_id, symbol="MSFT", active=False)
    symbol_repo.add_watchlist_symbol(
        app_user_id=app_user_id,
        watchlist_id=watchlist.id,
        symbol="QQQ",
        sort_order=1,
    )

    resolved = symbol_repo.resolve_symbols(
        app_user_id=app_user_id,
        manual_symbols=["aapl", "spy"],
        watchlist_ids=[watchlist.id],
        include_all_active=True,
        pinned_symbols=["IWM"],
    )

    assert resolved.symbols == ["IWM", "AAPL", "SPY", "QQQ"]
    assert resolved.source == "mixed"
    assert resolved.provenance["duplicate_count"] == 1
    assert resolved.provenance["watchlist_ids"] == [watchlist.id]


def test_repository_resolver_can_fall_back_to_legacy_watchlist_symbols() -> None:
    app_user_id = _create_user("legacy-user", "legacy@example.com")
    symbol_repo = SymbolUniverseRepository(SessionLocal)
    watchlist_repo = WatchlistRepository(SessionLocal)
    watchlist = watchlist_repo.upsert(
        app_user_id=app_user_id,
        name="Legacy symbols",
        symbols=["XLK", "XLF", "XLK"],
    )

    resolved = symbol_repo.resolve_symbols(
        app_user_id=app_user_id,
        watchlist_ids=[watchlist.id],
    )

    assert resolved.symbols == ["XLK", "XLF"]
    assert resolved.source == "watchlist"

    with SessionLocal() as session:
        stored = session.execute(
            select(AppUserModel).where(AppUserModel.id == app_user_id)
        ).scalar_one()
        assert stored.email == "legacy@example.com"
