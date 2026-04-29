from __future__ import annotations

from datetime import date
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from macmarket_trader.domain.models import (
    AppUserModel,
    PaperOptionOrderLegModel,
    PaperOptionOrderModel,
    PaperOptionPositionLegModel,
    PaperOptionPositionModel,
    PaperOptionTradeLegModel,
    PaperOptionTradeModel,
)
from macmarket_trader.storage.db import build_engine, build_session_factory, init_db


def _alembic_config(database_url: str) -> Config:
    repo_root = Path(__file__).resolve().parents[1]
    config = Config(str(repo_root / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    config.set_main_option("script_location", str(repo_root / "alembic"))
    return config


def _prepare_pre_0007_schema(database_url: str) -> None:
    engine = build_engine(database_url)
    init_db(engine)
    with engine.begin() as conn:
        for table_name in (
            "paper_option_trade_legs",
            "paper_option_trades",
            "paper_option_position_legs",
            "paper_option_positions",
            "paper_option_order_legs",
            "paper_option_orders",
        ):
            conn.execute(text(f"DROP TABLE IF EXISTS {table_name}"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)"))
        conn.execute(text("DELETE FROM alembic_version"))
        conn.execute(text("INSERT INTO alembic_version (version_num) VALUES ('20260429_0006')"))


def test_options_paper_schema_migration_upgrade_and_downgrade(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'options-schema.db'}"
    config = _alembic_config(database_url)

    _prepare_pre_0007_schema(database_url)
    command.upgrade(config, "head")

    engine = build_engine(database_url)
    inspector = inspect(engine)
    expected_tables = {
        "paper_option_orders",
        "paper_option_order_legs",
        "paper_option_positions",
        "paper_option_position_legs",
        "paper_option_trades",
        "paper_option_trade_legs",
    }
    assert expected_tables.issubset(set(inspector.get_table_names()))

    order_columns = {column["name"] for column in inspector.get_columns("paper_option_orders")}
    assert {"execution_enabled", "breakevens", "created_at"}.issubset(order_columns)

    order_leg_columns = {column["name"] for column in inspector.get_columns("paper_option_order_legs")}
    assert {"option_order_id", "multiplier", "leg_status"}.issubset(order_leg_columns)

    trade_columns = {column["name"] for column in inspector.get_columns("paper_option_trades")}
    assert {"position_id", "total_commissions", "settlement_mode"}.issubset(trade_columns)

    order_indexes = {index["name"] for index in inspector.get_indexes("paper_option_orders")}
    assert {
        "ix_paper_option_orders_app_user_id",
        "ix_paper_option_orders_underlying_symbol",
        "ix_paper_option_orders_status",
    }.issubset(order_indexes)

    command.downgrade(config, "20260429_0006")

    downgraded_engine = build_engine(database_url)
    downgraded_inspector = inspect(downgraded_engine)
    assert "paper_option_orders" not in downgraded_inspector.get_table_names()
    assert "paper_option_positions" not in downgraded_inspector.get_table_names()


def test_options_paper_models_support_defaults_and_leg_rows(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'options-models.db'}"
    engine = build_engine(database_url)
    init_db(engine)
    session_factory = build_session_factory(engine)

    with session_factory() as session:
        user = AppUserModel(
            external_auth_user_id="options-schema-user",
            email="options-schema@example.com",
            display_name="Options Schema User",
            approval_status="approved",
            app_role="user",
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        order = PaperOptionOrderModel(
            app_user_id=user.id,
            underlying_symbol="AAPL",
            structure_type="vertical_debit_spread",
            expiration=date(2026, 5, 15),
            net_debit=2.5,
            max_profit=250.0,
            max_loss=250.0,
            breakevens=[202.5],
        )
        session.add(order)
        session.commit()
        session.refresh(order)

        order_leg = PaperOptionOrderLegModel(
            option_order_id=order.id,
            action="buy",
            right="call",
            strike=200.0,
            expiration=date(2026, 5, 15),
            premium=4.2,
        )
        session.add(order_leg)

        position = PaperOptionPositionModel(
            app_user_id=user.id,
            underlying_symbol="AAPL",
            structure_type="vertical_debit_spread",
            expiration=date(2026, 5, 15),
            opening_net_debit=2.5,
            max_profit=250.0,
            max_loss=250.0,
            breakevens=[202.5],
            source_order_id=order.id,
        )
        session.add(position)
        session.commit()
        session.refresh(position)

        position_leg = PaperOptionPositionLegModel(
            position_id=position.id,
            action="buy",
            right="call",
            strike=200.0,
            expiration=date(2026, 5, 15),
            entry_premium=4.2,
        )
        session.add(position_leg)

        trade = PaperOptionTradeModel(
            app_user_id=user.id,
            position_id=position.id,
            structure_type="vertical_debit_spread",
            underlying_symbol="AAPL",
            expiration=date(2026, 5, 15),
            gross_pnl=125.0,
            total_commissions=0.0,
            net_pnl=125.0,
            settlement_mode="manual_close",
        )
        session.add(trade)
        session.commit()
        session.refresh(trade)

        trade_leg = PaperOptionTradeLegModel(
            trade_id=trade.id,
            action="buy",
            right="call",
            strike=200.0,
            expiration=date(2026, 5, 15),
            entry_premium=4.2,
            exit_premium=5.45,
            leg_gross_pnl=125.0,
            leg_commission=0.0,
            leg_net_pnl=125.0,
        )
        session.add(trade_leg)
        session.commit()
        session.refresh(order_leg)
        session.refresh(position_leg)
        session.refresh(trade_leg)

        assert order.execution_enabled is False
        assert order.notes == ""
        assert order.breakevens == [202.5]
        assert order_leg.quantity == 1
        assert order_leg.multiplier == 100
        assert order_leg.leg_status == "created"
        assert position.status == "open"
        assert position.source_order_id == order.id
        assert position_leg.quantity == 1
        assert position_leg.multiplier == 100
        assert position_leg.status == "open"
        assert trade.notes == ""
        assert trade.position_id == position.id
        assert trade_leg.quantity == 1
        assert trade_leg.multiplier == 100
