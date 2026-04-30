from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError

from macmarket_trader.domain.models import (
    AppUserModel,
    UserSymbolUniverseModel,
    WatchlistModel,
    WatchlistSymbolModel,
)
from macmarket_trader.storage.db import build_engine, build_session_factory, init_db


def _alembic_config(database_url: str) -> Config:
    repo_root = Path(__file__).resolve().parents[1]
    config = Config(str(repo_root / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    config.set_main_option("script_location", str(repo_root / "alembic"))
    return config


def _prepare_pre_0008_schema(database_url: str) -> None:
    engine = build_engine(database_url)
    init_db(engine)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS watchlist_symbols"))
        conn.execute(text("DROP TABLE IF EXISTS user_symbol_universe"))
        conn.execute(
            text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)")
        )
        conn.execute(text("DELETE FROM alembic_version"))
        conn.execute(text("INSERT INTO alembic_version (version_num) VALUES ('20260429_0007')"))


def test_symbol_universe_schema_migration_upgrade_and_downgrade(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'symbol-universe-schema.db'}"
    config = _alembic_config(database_url)

    _prepare_pre_0008_schema(database_url)
    command.upgrade(config, "head")

    engine = build_engine(database_url)
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    assert {"user_symbol_universe", "watchlist_symbols"}.issubset(table_names)

    universe_columns = {column["name"] for column in inspector.get_columns("user_symbol_universe")}
    assert {
        "app_user_id",
        "symbol",
        "normalized_symbol",
        "display_name",
        "asset_type",
        "exchange",
        "provider_source",
        "provider_symbol",
        "notes",
        "active",
        "tags",
        "created_at",
        "updated_at",
    }.issubset(universe_columns)

    watchlist_symbol_columns = {
        column["name"] for column in inspector.get_columns("watchlist_symbols")
    }
    assert {
        "watchlist_id",
        "app_user_id",
        "user_symbol_id",
        "symbol",
        "normalized_symbol",
        "active",
        "sort_order",
        "notes",
        "added_at",
        "created_at",
        "updated_at",
    }.issubset(watchlist_symbol_columns)

    universe_indexes = {index["name"] for index in inspector.get_indexes("user_symbol_universe")}
    assert {
        "ix_user_symbol_universe_app_user_id",
        "ix_user_symbol_universe_normalized_symbol",
        "ix_user_symbol_universe_active",
        "ix_user_symbol_universe_user_active",
    }.issubset(universe_indexes)

    watchlist_symbol_indexes = {
        index["name"] for index in inspector.get_indexes("watchlist_symbols")
    }
    assert {
        "ix_watchlist_symbols_watchlist_id",
        "ix_watchlist_symbols_app_user_id",
        "ix_watchlist_symbols_user_symbol_id",
        "ix_watchlist_symbols_watchlist_active_sort",
    }.issubset(watchlist_symbol_indexes)

    universe_constraints = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("user_symbol_universe")
    }
    assert "uq_user_symbol_universe_user_symbol" in universe_constraints

    watchlist_symbol_constraints = {
        constraint["name"] for constraint in inspector.get_unique_constraints("watchlist_symbols")
    }
    assert "uq_watchlist_symbols_watchlist_symbol" in watchlist_symbol_constraints

    command.downgrade(config, "20260429_0007")

    downgraded_engine = build_engine(database_url)
    downgraded_tables = set(inspect(downgraded_engine).get_table_names())
    assert "user_symbol_universe" not in downgraded_tables
    assert "watchlist_symbols" not in downgraded_tables


def test_symbol_universe_models_support_manual_symbols_and_defaults(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'symbol-universe-models.db'}"
    engine = build_engine(database_url)
    init_db(engine)
    session_factory = build_session_factory(engine)

    with session_factory() as session:
        user = AppUserModel(
            external_auth_user_id="symbol-universe-user",
            email="symbol-universe@example.com",
            display_name="Symbol Universe User",
            approval_status="approved",
            app_role="user",
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        symbol = UserSymbolUniverseModel(
            app_user_id=user.id,
            symbol="brk.b",
            normalized_symbol="BRK.B",
            notes="Manual symbol without provider metadata",
            tags=["Core", "Watch Only"],
        )
        session.add(symbol)
        session.commit()
        session.refresh(symbol)

        watchlist = WatchlistModel(
            app_user_id=user.id,
            name="Manual universe",
            symbols=["BRK.B"],
        )
        session.add(watchlist)
        session.commit()
        session.refresh(watchlist)

        membership = WatchlistSymbolModel(
            watchlist_id=watchlist.id,
            app_user_id=user.id,
            user_symbol_id=None,
            symbol="BRK.B",
            normalized_symbol="BRK.B",
            sort_order=1,
        )
        session.add(membership)
        session.commit()
        session.refresh(membership)

        assert symbol.active is True
        assert symbol.provider_source is None
        assert symbol.provider_symbol is None
        assert symbol.asset_type is None
        assert symbol.tags == ["Core", "Watch Only"]
        assert membership.active is True
        assert membership.user_symbol_id is None
        assert membership.symbol == "BRK.B"

        stored_symbol = session.execute(
            select(UserSymbolUniverseModel).where(
                UserSymbolUniverseModel.app_user_id == user.id,
                UserSymbolUniverseModel.normalized_symbol == "BRK.B",
            )
        ).scalar_one()
        assert stored_symbol.id == symbol.id


def test_symbol_universe_unique_constraints(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'symbol-universe-unique.db'}"
    engine = build_engine(database_url)
    init_db(engine)
    session_factory = build_session_factory(engine)

    with session_factory() as session:
        user = AppUserModel(
            external_auth_user_id="unique-symbol-user",
            email="unique-symbol@example.com",
            display_name="Unique Symbol User",
            approval_status="approved",
            app_role="user",
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        session.add(
            UserSymbolUniverseModel(
                app_user_id=user.id,
                symbol="AAPL",
                normalized_symbol="AAPL",
            )
        )
        session.commit()

        session.add(
            UserSymbolUniverseModel(
                app_user_id=user.id,
                symbol="aapl",
                normalized_symbol="AAPL",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        watchlist = WatchlistModel(
            app_user_id=user.id,
            name="Duplicates",
            symbols=["AAPL"],
        )
        session.add(watchlist)
        session.commit()
        session.refresh(watchlist)

        now = datetime.now(timezone.utc)
        session.add(
            WatchlistSymbolModel(
                watchlist_id=watchlist.id,
                app_user_id=user.id,
                symbol="AAPL",
                normalized_symbol="AAPL",
                created_at=now,
                updated_at=now,
                added_at=now,
            )
        )
        session.commit()

        session.add(
            WatchlistSymbolModel(
                watchlist_id=watchlist.id,
                app_user_id=user.id,
                symbol="aapl",
                normalized_symbol="AAPL",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
