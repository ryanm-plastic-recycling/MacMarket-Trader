"""Paper broker adapter backed by OMS."""

from macmarket_trader.domain.schemas import FillRecord, OrderIntent, OrderRecord
from macmarket_trader.execution.oms import OMS


class PaperBroker:
    """Creates and fills paper orders at deterministic reference prices."""

    def __init__(self, oms: OMS | None = None) -> None:
        self.oms = oms or OMS()

    def execute(self, intent: OrderIntent) -> tuple[OrderRecord, FillRecord]:
        record = OrderRecord(**intent.model_dump())
        submitted = self.oms.submit(record)
        return self.oms.final_fill(submitted.order_id, submitted.limit_price)
