from __future__ import annotations

from datetime import date

import pytest

from macmarket_trader.domain.models import AppUserModel
from macmarket_trader.domain.schemas import OptionPaperLegInput, OptionPaperStructureInput
from macmarket_trader.options.paper_contracts import OptionPaperContractError, prepare_option_paper_structure
from macmarket_trader.storage.db import build_engine, build_session_factory, init_db
from macmarket_trader.storage.repositories import OptionPaperRepository


def _build_session_factory(tmp_path, name: str):
    engine = build_engine(f"sqlite:///{tmp_path / name}")
    init_db(engine)
    return build_session_factory(engine)


def _seed_user(session_factory, *, external_id: str, email: str) -> int:
    with session_factory() as session:
        user = AppUserModel(
            external_auth_user_id=external_id,
            email=email,
            display_name=email.split("@", 1)[0],
            approval_status="approved",
            app_role="user",
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user.id


def _vertical_call_debit() -> OptionPaperStructureInput:
    return OptionPaperStructureInput(
        structure_type="vertical_debit_spread",
        underlying_symbol="aapl",
        legs=[
            OptionPaperLegInput(
                action="buy",
                right="call",
                strike=205.0,
                expiration=date(2026, 5, 15),
                premium=4.2,
                label="long call",
            ),
            OptionPaperLegInput(
                action="sell",
                right="call",
                strike=215.0,
                expiration=date(2026, 5, 15),
                premium=1.6,
                label="short call",
            ),
        ],
        notes="paper contract test",
    )


def _iron_condor() -> OptionPaperStructureInput:
    return OptionPaperStructureInput(
        structure_type="iron_condor",
        underlying_symbol="msft",
        legs=[
            OptionPaperLegInput(
                action="buy",
                right="put",
                strike=390.0,
                expiration=date(2026, 6, 19),
                premium=1.1,
                label="long put wing",
            ),
            OptionPaperLegInput(
                action="sell",
                right="put",
                strike=395.0,
                expiration=date(2026, 6, 19),
                premium=2.9,
                label="short put",
            ),
            OptionPaperLegInput(
                action="sell",
                right="call",
                strike=405.0,
                expiration=date(2026, 6, 19),
                premium=2.8,
                label="short call",
            ),
            OptionPaperLegInput(
                action="buy",
                right="call",
                strike=410.0,
                expiration=date(2026, 6, 19),
                premium=1.0,
                label="long call wing",
            ),
        ],
    )


def test_prepare_option_paper_structure_derives_metrics_and_expiration() -> None:
    prepared = prepare_option_paper_structure(_vertical_call_debit())

    assert prepared.underlying_symbol == "AAPL"
    assert prepared.expiration == date(2026, 5, 15)
    assert prepared.net_debit == 2.6
    assert prepared.net_credit is None
    assert prepared.max_profit == 740.0
    assert prepared.max_loss == 260.0
    assert prepared.breakevens == (207.6,)
    assert len(prepared.legs) == 2


def test_create_option_paper_order_round_trip_with_legs(tmp_path) -> None:
    session_factory = _build_session_factory(tmp_path, "options-order.db")
    repo = OptionPaperRepository(session_factory)
    user_id = _seed_user(
        session_factory,
        external_id="options-order-user",
        email="options-order@example.com",
    )

    order = repo.create_order(app_user_id=user_id, structure=_vertical_call_debit())
    fetched = repo.get_order(order_id=order.id, app_user_id=user_id)

    assert order.execution_enabled is False
    assert order.status == "created"
    assert order.underlying_symbol == "AAPL"
    assert order.net_debit == 2.6
    assert order.notes == "paper contract test"
    assert len(order.legs) == 2
    assert order.legs[0].quantity == 1
    assert order.legs[0].multiplier == 100
    assert order.legs[0].leg_status == "created"
    assert fetched is not None
    assert fetched.id == order.id
    assert [leg.label for leg in fetched.legs] == ["long call", "short call"]


def test_create_position_and_trade_records_query_correctly(tmp_path) -> None:
    session_factory = _build_session_factory(tmp_path, "options-position-trade.db")
    repo = OptionPaperRepository(session_factory)
    user_id = _seed_user(
        session_factory,
        external_id="options-position-user",
        email="options-position@example.com",
    )
    other_user_id = _seed_user(
        session_factory,
        external_id="options-position-other",
        email="options-position-other@example.com",
    )

    source_order = repo.create_order(app_user_id=user_id, structure=_vertical_call_debit())
    open_position = repo.create_position(
        app_user_id=user_id,
        structure=_vertical_call_debit(),
        source_order_id=source_order.id,
    )
    repo.create_position(
        app_user_id=user_id,
        structure=_vertical_call_debit(),
        status="closed",
    )
    repo.create_position(app_user_id=other_user_id, structure=_iron_condor())

    positions = repo.list_open_positions(app_user_id=user_id)
    fetched_position = repo.get_position(position_id=open_position.id, app_user_id=user_id)
    missing_for_other_user = repo.get_position(position_id=open_position.id, app_user_id=other_user_id)

    assert len(positions) == 1
    assert positions[0].id == open_position.id
    assert positions[0].source_order_id == source_order.id
    assert len(positions[0].legs) == 2
    assert positions[0].legs[0].entry_premium == 4.2
    assert fetched_position is not None
    assert fetched_position.underlying_symbol == "AAPL"
    assert missing_for_other_user is None

    trade = repo.create_trade(
        app_user_id=user_id,
        structure=_vertical_call_debit(),
        position_id=open_position.id,
        gross_pnl=125.0,
        total_commissions=0.0,
        net_pnl=125.0,
        settlement_mode="manual_close",
    )
    trades = repo.list_trades(app_user_id=user_id)

    assert trade.position_id == open_position.id
    assert trade.gross_pnl == 125.0
    assert trade.total_commissions == 0.0
    assert trade.legs[0].entry_premium == 4.2
    assert trade.legs[0].exit_premium is None
    assert len(trades) == 1
    assert trades[0].id == trade.id
    assert len(trades[0].legs) == 2


def test_repository_contracts_block_naked_short_and_bad_expiration(tmp_path) -> None:
    session_factory = _build_session_factory(tmp_path, "options-invalid.db")
    repo = OptionPaperRepository(session_factory)
    user_id = _seed_user(
        session_factory,
        external_id="options-invalid-user",
        email="options-invalid@example.com",
    )

    naked_short = OptionPaperStructureInput(
        structure_type="long_call",
        underlying_symbol="spy",
        legs=[
            OptionPaperLegInput(
                action="sell",
                right="call",
                strike=500.0,
                expiration=date(2026, 5, 15),
                premium=4.5,
            )
        ],
    )
    mismatched_expiration = OptionPaperStructureInput(
        structure_type="vertical_debit_spread",
        underlying_symbol="qqq",
        legs=[
            OptionPaperLegInput(
                action="buy",
                right="call",
                strike=450.0,
                expiration=date(2026, 5, 15),
                premium=5.0,
            ),
            OptionPaperLegInput(
                action="sell",
                right="call",
                strike=460.0,
                expiration=date(2026, 5, 22),
                premium=2.0,
            ),
        ],
    )

    with pytest.raises(OptionPaperContractError, match="naked_short_option_not_supported"):
        repo.create_order(app_user_id=user_id, structure=naked_short)

    with pytest.raises(OptionPaperContractError, match="multi_expiration_structures_not_supported"):
        repo.create_position(app_user_id=user_id, structure=mismatched_expiration)
