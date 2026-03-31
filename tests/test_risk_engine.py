from macmarket_trader.domain.enums import Direction, SetupType
from macmarket_trader.domain.schemas import PortfolioSnapshot, TradeSetup
from macmarket_trader.risk.engine import RiskEngine


def test_risk_engine_rejects_invalid_stop_distance() -> None:
    setup = TradeSetup(
        setup_type=SetupType.EVENT_CONTINUATION,
        direction=Direction.LONG,
        entry_zone_low=100,
        entry_zone_high=100,
        trigger_text="t",
        invalidation_price=100,
        invalidation_reason="x",
        target_1=102,
        target_2=104,
        trailing_rule_text="trail",
        time_stop_days=2,
    )
    shares, _, approved, reason = RiskEngine().size_position(
        setup=setup,
        risk_dollars=1000,
        portfolio=PortfolioSnapshot(),
        max_portfolio_heat=0.1,
        max_position_notional=0.5,
    )
    assert shares == 0
    assert not approved
    assert reason == "Invalid stop distance"
