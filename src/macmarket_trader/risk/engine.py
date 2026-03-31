"""Deterministic risk sizing and validation engine."""

from math import floor

from macmarket_trader.domain.schemas import PortfolioSnapshot, TradeSetup


class RiskEngine:
    """Calculates deterministic position sizing and constraints."""

    version = "risk-v1"

    def size_position(
        self,
        setup: TradeSetup,
        risk_dollars: float,
        portfolio: PortfolioSnapshot,
        max_portfolio_heat: float,
        max_position_notional: float,
    ) -> tuple[int, float, bool, str | None]:
        entry = (setup.entry_zone_low + setup.entry_zone_high) / 2
        stop_distance = abs(entry - setup.invalidation_price)
        if stop_distance <= 0:
            return 0, stop_distance, False, "Invalid stop distance"

        shares = floor(risk_dollars / stop_distance)
        if shares <= 0:
            return 0, stop_distance, False, "Risk budget too small for stop distance"

        position_notional = shares * entry
        if portfolio.current_heat + (risk_dollars / max(portfolio.equity, 1.0)) > max_portfolio_heat:
            return 0, stop_distance, False, "Portfolio heat limit exceeded"

        if position_notional / max(portfolio.equity, 1.0) > max_position_notional:
            return 0, stop_distance, False, "Max position notional exceeded"

        return shares, stop_distance, True, None
