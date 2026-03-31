from macmarket_trader.domain.enums import Direction, SetupType
from macmarket_trader.domain.schemas import PortfolioSnapshot, TradeSetup
from macmarket_trader.risk.engine import RiskEngine


def _setup() -> TradeSetup:
    return TradeSetup(
        setup_type=SetupType.EVENT_CONTINUATION,
        direction=Direction.LONG,
        entry_zone_low=100,
        entry_zone_high=100,
        trigger_text="t",
        invalidation_price=95,
        invalidation_reason="x",
        target_1=108,
        target_2=112,
        trailing_rule_text="trail",
        time_stop_days=2,
    )


def test_risk_engine_sizes_risk_limited() -> None:
    shares, _, approved, reason, report = RiskEngine().size_position(
        setup=_setup(),
        risk_dollars=500,
        portfolio=PortfolioSnapshot(equity=100_000),
        max_portfolio_heat=0.2,
        max_position_notional=0.5,
    )
    assert shares == 100
    assert approved
    assert reason is None
    assert report.risk_based_share_cap == 100


def test_risk_engine_sizes_notional_limited() -> None:
    shares, _, approved, _, report = RiskEngine().size_position(
        setup=_setup(),
        risk_dollars=5_000,
        portfolio=PortfolioSnapshot(equity=100_000),
        max_portfolio_heat=0.2,
        max_position_notional=0.03,
    )
    assert approved
    assert shares == 30
    assert report.notional_share_cap == 30


def test_risk_engine_rejects_zero_share() -> None:
    shares, _, approved, reason, _ = RiskEngine().size_position(
        setup=_setup(),
        risk_dollars=1,
        portfolio=PortfolioSnapshot(),
        max_portfolio_heat=0.2,
        max_position_notional=0.2,
    )
    assert shares == 0
    assert not approved
    assert reason == "Final allowed share count below 1"


def test_risk_engine_rejects_portfolio_heat() -> None:
    shares, _, approved, reason, _ = RiskEngine().size_position(
        setup=_setup(),
        risk_dollars=1_000,
        portfolio=PortfolioSnapshot(equity=100_000, current_heat=0.059),
        max_portfolio_heat=0.06,
        max_position_notional=0.2,
    )
    assert shares > 0
    assert not approved
    assert reason == "Portfolio heat limit exceeded"


def test_risk_engine_downsizes_instead_of_rejecting_when_notional_cap_tighter() -> None:
    shares, _, approved, reason, report = RiskEngine().size_position(
        setup=_setup(),
        risk_dollars=10_000,
        portfolio=PortfolioSnapshot(equity=100_000),
        max_portfolio_heat=0.2,
        max_position_notional=0.01,
    )
    assert approved
    assert reason is None
    assert shares == 10
    assert report.risk_based_share_cap > report.notional_share_cap
