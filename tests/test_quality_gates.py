from datetime import date, timedelta

from macmarket_trader.domain.schemas import Bar, PortfolioSnapshot
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
            rel_volume=1.1,
        )
        for i in range(25)
    ]


def test_low_quality_recommendation_returns_no_trade(monkeypatch) -> None:
    monkeypatch.setattr('macmarket_trader.service.settings.min_expected_rr', 10.0)
    service = RecommendationService(persist_audit=False)

    rec = service.generate(
        symbol='AAPL',
        bars=_bars(),
        event_text='earnings beat',
        event=None,
        portfolio=PortfolioSnapshot(),
    )

    assert rec.approved is False
    assert rec.outcome == 'no_trade'
    assert rec.rejection_reason is not None
    assert 'Expected RR' in rec.rejection_reason
