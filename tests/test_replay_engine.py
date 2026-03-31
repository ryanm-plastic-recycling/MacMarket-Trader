from datetime import date, timedelta

from macmarket_trader.domain.schemas import Bar, PortfolioSnapshot, ReplayRunRequest
from macmarket_trader.replay.engine import ReplayEngine
from macmarket_trader.service import RecommendationService


def _bars() -> list[Bar]:
    base = date(2026, 1, 1)
    return [
        Bar(
            date=base + timedelta(days=i),
            open=100 + i,
            high=101 + i,
            low=99 + i,
            close=100.5 + i,
            volume=1_000_000 + i * 10_000,
            rel_volume=1.3,
        )
        for i in range(25)
    ]


def test_replay_updates_portfolio_state_across_sequence() -> None:
    engine = ReplayEngine(service=RecommendationService(persist_audit=False))
    response = engine.run(
        ReplayRunRequest(
            symbol="AAPL",
            event_texts=["earnings beat", "follow-through upgrade"],
            bars=_bars(),
            portfolio=PortfolioSnapshot(current_heat=0.0, open_positions_notional=0.0),
        )
    )

    assert response.summary_metrics.approved_count >= 1
    assert response.final_portfolio.current_heat > 0.0
    assert response.final_portfolio.open_positions_notional > 0.0


def test_replay_later_steps_see_updated_state() -> None:
    engine = ReplayEngine(service=RecommendationService(persist_audit=False))
    response = engine.run(
        ReplayRunRequest(
            symbol="AAPL",
            event_texts=["earnings beat", "second positive event"],
            bars=_bars(),
            portfolio=PortfolioSnapshot(current_heat=0.0, equity=100_000),
        )
    )

    assert response.recommendations[0].constraints.checks[-1].details != response.recommendations[1].constraints.checks[-1].details
    assert response.summary_metrics.ending_heat > 0
