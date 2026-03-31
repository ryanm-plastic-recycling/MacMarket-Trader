from macmarket_trader.domain.enums import Direction, OrderStatus
from macmarket_trader.domain.schemas import OrderRecord
from macmarket_trader.execution.oms import OMS


def test_oms_state_transitions() -> None:
    oms = OMS()
    order = OrderRecord(
        recommendation_id="rec_1",
        symbol="MSFT",
        side=Direction.LONG,
        shares=10,
        limit_price=100,
    )
    submitted = oms.submit(order)
    assert submitted.status == OrderStatus.SUBMITTED
    filled, fill = oms.fill(submitted.order_id, price=100)
    assert filled.status == OrderStatus.FILLED
    assert fill.filled_shares == 10
