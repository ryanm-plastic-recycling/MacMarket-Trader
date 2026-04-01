"""Protected chart routes."""

from datetime import date, timedelta

from fastapi import APIRouter, Depends

from macmarket_trader.api.deps.auth import require_approved_user
from macmarket_trader.charts.haco_service import HacoChartService
from macmarket_trader.domain.schemas import Bar, HacoChartPayload, HacoChartRequest
from macmarket_trader.storage.db import SessionLocal
from macmarket_trader.storage.repositories import DailyBarRepository

router = APIRouter(prefix="/charts", tags=["charts"])
service = HacoChartService()
bar_repo = DailyBarRepository(SessionLocal)


def _deterministic_fallback_bars(symbol: str, count: int = 120) -> list[Bar]:
    del symbol
    base = date(2025, 1, 1)
    bars: list[Bar] = []
    for idx in range(count):
        t = base + timedelta(days=idx)
        price = 100 + idx * 0.25
        bars.append(
            Bar(
                date=t,
                open=price,
                high=price + 1.2,
                low=price - 1.0,
                close=price + 0.35,
                volume=1_000_000 + idx * 5000,
                rel_volume=1.0,
            )
        )
    return bars


def _resolve_bars(symbol: str, request_bars: list[Bar]) -> tuple[list[Bar], str, bool]:
    if request_bars:
        return request_bars, "request_bars", False

    persisted = bar_repo.list_for_symbol(symbol=symbol)
    if persisted:
        return (
            [
                Bar(
                    date=model.bar_date.date(),
                    open=model.open,
                    high=model.high,
                    low=model.low,
                    close=model.close,
                    volume=model.volume,
                    rel_volume=None,
                )
                for model in persisted
            ],
            "daily_bars",
            False,
        )

    return _deterministic_fallback_bars(symbol), "deterministic_fallback", True


@router.post("/haco", response_model=HacoChartPayload)
def get_haco_chart(req: HacoChartRequest, _user=Depends(require_approved_user)) -> HacoChartPayload:
    bars, data_source, fallback_mode = _resolve_bars(req.symbol, req.bars)
    return service.build_payload(
        symbol=req.symbol,
        timeframe=req.timeframe,
        bars=bars,
        include_heikin_ashi=req.include_heikin_ashi,
        data_source=data_source,
        fallback_mode=fallback_mode,
    )
