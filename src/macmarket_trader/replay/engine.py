"""Replay engine using same recommendation pipeline as live API."""

from macmarket_trader.domain.schemas import ReplayRunRequest, ReplayRunResponse
from macmarket_trader.execution.paper_broker import PaperBroker
from macmarket_trader.service import RecommendationService


class ReplayEngine:
    """Runs deterministic sequence replay with paper execution."""

    def __init__(self, service: RecommendationService, broker: PaperBroker | None = None) -> None:
        self.service = service
        self.broker = broker or PaperBroker()

    def run(self, req: ReplayRunRequest) -> ReplayRunResponse:
        recs = []
        orders = []
        fills = []
        approved = 0
        for text in req.event_texts:
            rec = self.service.generate(
                symbol=req.symbol,
                bars=req.bars,
                event_text=text,
                event=None,
                portfolio=req.portfolio,
            )
            recs.append(rec)
            if rec.approved:
                approved += 1
                intent = self.service.to_order_intent(rec)
                order, fill = self.broker.execute(intent)
                orders.append(order)
                fills.append(fill)

        summary = {
            "recommendation_count": float(len(recs)),
            "approved_count": float(approved),
            "fill_count": float(len(fills)),
        }
        return ReplayRunResponse(
            recommendations=recs,
            orders=orders,
            fills=fills,
            summary_metrics=summary,
        )
