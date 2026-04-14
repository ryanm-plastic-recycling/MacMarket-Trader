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

    def run(
        self,
        req: ReplayRunRequest,
        *,
        app_user_id: int | None = None,
        source_recommendation_id: str | None = None,
        source_strategy: str | None = None,
        source_market_mode: str | None = None,
        source_market_data_source: str | None = None,
        source_fallback_mode: bool | None = None,
    ) -> ReplayRunResponse:
        recs = []
        orders = []
        fills = []
        approved = 0
        step_snapshots: list[tuple[PortfolioSnapshot, PortfolioSnapshot]] = []
        portfolio_state = req.portfolio or PortfolioSnapshot()

        for text in req.event_texts:
            pre_step_snapshot = portfolio_state.model_copy(deep=True)
            rec = self.service.generate(
                symbol=req.symbol,
                bars=req.bars,
                event_text=text,
                event=None,
                portfolio=portfolio_state,
                market_mode=req.market_mode,
                app_user_id=app_user_id,
            )
            recs.append(rec)
            if rec.approved:
                approved += 1
                intent = self.service.to_order_intent(rec)
                order, fill = self.broker.execute(intent)
                self.service.persist_order(order, notes="replay_fill", app_user_id=app_user_id)
                self.service.persist_fill(fill)
                orders.append(order)
                fills.append(fill)
                portfolio_state = self.portfolio_engine.apply_fill(
                    portfolio=portfolio_state,
                    risk_dollars=rec.sizing.shares * rec.sizing.stop_distance,
                    position_notional=fill.fill_price * fill.filled_shares,
                )

            post_step_snapshot = portfolio_state.model_copy(deep=True)
            step_snapshots.append((pre_step_snapshot, post_step_snapshot))

        if self.service.persist_audit:
            run = self.replay_repository.create_run(
                symbol=req.symbol,
                recommendation_id=recs[0].recommendation_id if recs else None,
                source_recommendation_id=source_recommendation_id,
                source_strategy=source_strategy,
                source_market_mode=source_market_mode,
                source_market_data_source=source_market_data_source,
                source_fallback_mode=source_fallback_mode,
                recommendation_count=len(recs),
                approved_count=approved,
                fill_count=len(fills),
                ending_heat=portfolio_state.current_heat,
                ending_open_notional=portfolio_state.open_positions_notional,
                app_user_id=app_user_id,
            )
            for step_index, (step_rec, snapshots) in enumerate(zip(recs, step_snapshots, strict=True)):
                pre_snapshot, post_snapshot = snapshots
                self.replay_repository.create_step(
                    replay_run_id=run.id,
                    step_index=step_index,
                    recommendation_id=step_rec.recommendation_id,
                    approved=step_rec.approved,
                    pre_step_snapshot=pre_snapshot,
                    post_step_snapshot=post_snapshot,
                )

        summary = ReplaySummaryMetrics(
            recommendation_count=float(len(recs)),
            approved_count=float(approved),
            fill_count=float(len(fills)),
            ending_heat=portfolio_state.current_heat,
            ending_open_notional=portfolio_state.open_positions_notional,
        )
        return ReplayRunResponse(
            market_mode=req.market_mode,
            recommendations=recs,
            orders=orders,
            fills=fills,
            final_portfolio=portfolio_state,
            summary_metrics=summary,
        )
