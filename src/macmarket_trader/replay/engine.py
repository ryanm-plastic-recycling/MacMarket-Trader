"""Replay engine using same recommendation pipeline as live API."""

from macmarket_trader.domain.schemas import PortfolioSnapshot, ReplayRunRequest, ReplayRunResponse
from macmarket_trader.execution.paper_broker import PaperBroker
from macmarket_trader.portfolio.engine import PortfolioEngine
from macmarket_trader.service import RecommendationService


class ReplayEngine:
    """Runs deterministic sequence replay with paper execution."""

    def __init__(self, service: RecommendationService, broker: PaperBroker | None = None) -> None:
        self.service = service
        self.broker = broker or PaperBroker()
        self.portfolio_engine = PortfolioEngine()

    def run(self, req: ReplayRunRequest) -> ReplayRunResponse:
        recs = []
        orders = []
        fills = []
        approved = 0
        portfolio_state = req.portfolio or PortfolioSnapshot()

        for text in req.event_texts:
            rec = self.service.generate(
                symbol=req.symbol,
                bars=req.bars,
                event_text=text,
                event=None,
                portfolio=portfolio_state,
            )
            recs.append(rec)
            if rec.approved:
                approved += 1
                intent = self.service.to_order_intent(rec)
                order, fill = self.broker.execute(intent)
                self.service.persist_order(order, notes="replay_fill")
                orders.append(order)
                fills.append(fill)
                portfolio_state = self.portfolio_engine.apply_fill(
                    portfolio=portfolio_state,
                    risk_dollars=rec.sizing.risk_dollars,
                    position_notional=fill.fill_price * fill.filled_shares,
                )

        summary = {
            "recommendation_count": float(len(recs)),
            "approved_count": float(approved),
            "fill_count": float(len(fills)),
            "final_heat": portfolio_state.current_heat,
            "final_open_notional": portfolio_state.open_positions_notional,
        }
        return ReplayRunResponse(
            recommendations=recs,
            orders=orders,
            fills=fills,
            final_portfolio=portfolio_state,
            summary_metrics=summary,
        )
