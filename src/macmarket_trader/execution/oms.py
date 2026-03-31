"""In-memory order management state machine."""

from macmarket_trader.domain.enums import OrderStatus
from macmarket_trader.domain.schemas import FillRecord, OrderRecord


class OMS:
    """Tracks deterministic order states for paper execution."""

    def __init__(self) -> None:
        self.orders: dict[str, OrderRecord] = {}

    def submit(self, order: OrderRecord) -> OrderRecord:
        if order.status != OrderStatus.CREATED:
            msg = "Only created orders can be submitted"
            raise ValueError(msg)
        submitted = order.model_copy(update={"status": OrderStatus.SUBMITTED})
        self.orders[order.order_id] = submitted
        return submitted

    def partial_fill(self, order_id: str, price: float, filled_shares: int) -> tuple[OrderRecord, FillRecord]:
        order = self.orders[order_id]
        if order.status not in {OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED}:
            msg = "Order is not fillable"
            raise ValueError(msg)
        if filled_shares <= 0 or (order.filled_shares + filled_shares) >= order.shares:
            msg = "Partial fill size must be positive and less than remaining shares"
            raise ValueError(msg)

        cumulative = order.filled_shares + filled_shares
        partially_filled = order.model_copy(
            update={"status": OrderStatus.PARTIALLY_FILLED, "filled_shares": cumulative}
        )
        self.orders[order_id] = partially_filled
        fill = FillRecord(order_id=order_id, fill_price=price, filled_shares=filled_shares)
        return partially_filled, fill

    def final_fill(self, order_id: str, price: float) -> tuple[OrderRecord, FillRecord]:
        order = self.orders[order_id]
        if order.status not in {OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED}:
            msg = "Order is not fillable"
            raise ValueError(msg)

        remaining = order.shares - order.filled_shares
        if remaining <= 0:
            msg = "Order already fully filled"
            raise ValueError(msg)

        filled = order.model_copy(update={"status": OrderStatus.FILLED, "filled_shares": order.shares})
        self.orders[order_id] = filled
        fill = FillRecord(order_id=order_id, fill_price=price, filled_shares=remaining)
        return filled, fill

    def cancel(self, order_id: str) -> OrderRecord:
        order = self.orders[order_id]
        if order.status in {OrderStatus.FILLED, OrderStatus.CANCELLED}:
            msg = "Filled or cancelled orders cannot be cancelled"
            raise ValueError(msg)
        cancelled = order.model_copy(update={"status": OrderStatus.CANCELLED})
        self.orders[order_id] = cancelled
        return cancelled
