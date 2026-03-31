"""Deterministic risk sizing and validation engine."""

from math import floor

from macmarket_trader.domain.schemas import (
    ConstraintCheck,
    ConstraintReport,
    PortfolioSnapshot,
    TradeSetup,
)


class RiskEngine:
    """Calculates deterministic position sizing and constraints."""

    version = "risk-v2"

    def size_position(
        self,
        setup: TradeSetup,
        risk_dollars: float,
        portfolio: PortfolioSnapshot,
        max_portfolio_heat: float,
        max_position_notional: float,
        explicit_share_cap: int | None = None,
    ) -> tuple[int, float, bool, str | None, ConstraintReport]:
        entry = (setup.entry_zone_low + setup.entry_zone_high) / 2
        stop_distance = abs(entry - setup.invalidation_price)

        checks: list[ConstraintCheck] = []
        if stop_distance <= 0:
            checks.append(ConstraintCheck(name="stop_distance", passed=False, details="Stop distance <= 0"))
            report = ConstraintReport(
                checks=checks,
                risk_based_share_cap=0,
                notional_share_cap=0,
                explicit_share_cap=explicit_share_cap,
                final_share_count=0,
            )
            return 0, stop_distance, False, "Invalid stop distance", report

        risk_cap = floor(risk_dollars / stop_distance)
        checks.append(
            ConstraintCheck(
                name="risk_budget",
                passed=risk_cap > 0,
                details=f"risk_cap={risk_cap} shares",
            )
        )

        notional_cap = floor((max_position_notional * max(portfolio.equity, 1.0)) / max(entry, 0.01))
        checks.append(
            ConstraintCheck(
                name="position_notional_cap",
                passed=notional_cap > 0,
                details=f"notional_cap={notional_cap} shares",
            )
        )

        caps = [risk_cap, notional_cap]
        if explicit_share_cap is not None:
            caps.append(explicit_share_cap)

        shares = min(caps)

        realized_risk_dollars = shares * stop_distance
        projected_heat = portfolio.current_heat + (realized_risk_dollars / max(portfolio.equity, 1.0))
        heat_ok = projected_heat <= max_portfolio_heat
        checks.append(
            ConstraintCheck(
                name="portfolio_heat",
                passed=heat_ok,
                details=f"projected_heat={projected_heat:.4f}, limit={max_portfolio_heat:.4f}",
            )
        )

        rejection_reason: str | None = None
        approved = True
        if shares < 1:
            approved = False
            rejection_reason = "Final allowed share count below 1"
        elif not heat_ok:
            approved = False
            rejection_reason = "Portfolio heat limit exceeded"

        report = ConstraintReport(
            checks=checks,
            risk_based_share_cap=risk_cap,
            notional_share_cap=notional_cap,
            explicit_share_cap=explicit_share_cap,
            final_share_count=max(shares, 0),
        )
        return max(shares, 0), stop_distance, approved, rejection_reason, report
