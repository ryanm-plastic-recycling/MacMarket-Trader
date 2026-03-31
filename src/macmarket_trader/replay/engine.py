"""Replay engine using same recommendation pipeline as live API."""

from macmarket_trader.domain.schemas import PortfolioSnapshot, ReplayRunRequest, ReplayRunResponse, ReplaySummaryMetrics
from macmarket_trader.execution.paper_broker import PaperBroker
from macmarket_trader.portfolio.engine import PortfolioEngine
from macmarket_trader.service import RecommendationService
from macmarket_trader.storage.db import SessionLocal
from macmarket_trader.storage.repositories import ReplayRepository


class ReplayEngine:
    """Runs deterministic sequence replay with paper execution."""

    def __init__(
        self,
        service: RecommendationService,
        broker: PaperBroker | None = None,
        replay_repository: ReplayRepository | None = None,
    ) -> None:
        self.service = service
        self.broker = broker or PaperBroker()
        self.portfolio_engine = PortfolioEngine()
        self.replay_repository = replay_repository or ReplayRepository(SessionLocal)

    def run(self, req: ReplayRunRequest) -> ReplayRunResponse:
        recs = []
        orders = []
        fills = []
        approved = 0
        portfolio_state = req.portfolio or PortfolioSnapshot()

        for idx, text in enumerate(req.event_texts):
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
                self.service.persist_fill(fill)
                orders.append(order)
                fills.append(fill)
                portfolio_state = self.portfolio_engine.apply_fill(
                    portfolio=portfolio_state,
                    risk_dollars=rec.sizing.shares * rec.sizing.stop_distance,
                    position_notional=fill.fill_price * fill.filled_shares,
                )

            if self.service.persist_audit:
                run_id = -1
                if idx == len(req.event_texts) - 1:
                    run = self.replay_repository.create_run(
                        symbol=req.symbol,
                        recommendation_count=len(recs),
                        approved_count=approved,
                        fill_count=len(fills),
                        ending_heat=portfolio_state.current_heat,
                        ending_open_notional=portfolio_state.open_positions_notional,
                    )
                    run_id = run.id
                if run_id > 0:
                    for step_index, step_rec in enumerate(recs):
                        self.replay_repository.create_step(
                            replay_run_id=run_id,
                            step_index=step_index,
                            recommendation_id=step_rec.recommendation_id,
                            approved=step_rec.approved,
                            snapshot=portfolio_state,
                        )

        summary = ReplaySummaryMetrics(
            recommendation_count=float(len(recs)),
            approved_count=float(approved),
            fill_count=float(len(fills)),
            ending_heat=portfolio_state.current_heat,
            ending_open_notional=portfolio_state.open_positions_notional,
        )
        return ReplayRunResponse(
            recommendations=recs,
            orders=orders,
            fills=fills,
            final_portfolio=portfolio_state,
            summary_metrics=summary,
        )
