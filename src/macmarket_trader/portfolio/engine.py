"""Portfolio helper engine for deterministic updates."""

from macmarket_trader.domain.schemas import PortfolioSnapshot


class PortfolioEngine:
    """Provides simple portfolio state transitions."""

    def apply_fill(
        self,
        portfolio: PortfolioSnapshot,
        risk_dollars: float,
        position_notional: float,
    ) -> PortfolioSnapshot:
        heat_increment = risk_dollars / max(portfolio.equity, 1.0)
        return portfolio.model_copy(
            update={
                "current_heat": portfolio.current_heat + heat_increment,
                "open_positions_notional": portfolio.open_positions_notional + position_notional,
            }
        )
