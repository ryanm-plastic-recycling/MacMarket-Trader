import pytest

from macmarket_trader.domain.enums import Direction, OrderStatus
from macmarket_trader.domain.schemas import OrderRecord
from macmarket_trader.execution.oms import OMS


def _order() -> OrderRecord:
    return OrderRecord(
        recommendation_id="rec_1",
        symbol="MSFT",
        side=Direction.LONG,
        shares=10,
        limit_price=100,
    )


def test_oms_legal_state_transitions() -> None:
    oms = OMS()
    submitted = oms.submit(_order())
    assert submitted.status == OrderStatus.SUBMITTED

    partial, first_fill = oms.partial_fill(submitted.order_id, price=100, filled_shares=4)
    assert partial.status == OrderStatus.PARTIALLY_FILLED
    assert first_fill.filled_shares == 4

    filled, second_fill = oms.final_fill(submitted.order_id, price=100)
    assert filled.status == OrderStatus.FILLED
    assert second_fill.filled_shares == 6


def test_oms_illegal_transitions_raise() -> None:
    oms = OMS()
    submitted = oms.submit(_order())
    filled, _ = oms.final_fill(submitted.order_id, price=100)
    with pytest.raises(ValueError, match="cannot be cancelled"):
        oms.cancel(filled.order_id)

    with pytest.raises(ValueError, match="not fillable"):
        oms.final_fill(filled.order_id, price=100)
