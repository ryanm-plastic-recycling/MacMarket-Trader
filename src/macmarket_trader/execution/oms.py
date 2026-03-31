"""In-memory order management state machine."""

from macmarket_trader.domain.enums import OrderStatus
from macmarket_trader.domain.schemas import FillRecord, OrderRecord


class OMS:
    """Tracks deterministic order states for paper execution."""

    def __init__(self) -> None:
        self.orders: dict[str, OrderRecord] = {}

    def submit(self, order: OrderRecord) -> OrderRecord:
        submitted = order.model_copy(update={"status": OrderStatus.SUBMITTED})
        self.orders[order.order_id] = submitted
        return submitted

    def fill(self, order_id: str, price: float) -> tuple[OrderRecord, FillRecord]:
        order = self.orders[order_id]
        filled = order.model_copy(update={"status": OrderStatus.FILLED})
        self.orders[order_id] = filled
        fill = FillRecord(order_id=order_id, fill_price=price, filled_shares=order.shares)
        return filled, fill
