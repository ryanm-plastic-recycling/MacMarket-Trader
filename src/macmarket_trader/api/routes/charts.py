"""Protected chart routes."""

from fastapi import APIRouter, Depends

from macmarket_trader.api.deps.auth import require_approved_user
from macmarket_trader.charts.haco_service import HacoChartService
from macmarket_trader.data.providers.registry import build_market_data_service
from macmarket_trader.domain.schemas import Bar, HacoChartPayload, HacoChartRequest
from macmarket_trader.storage.db import SessionLocal
from macmarket_trader.storage.repositories import DailyBarRepository

router = APIRouter(prefix="/charts", tags=["charts"])
service = HacoChartService()
bar_repo = DailyBarRepository(SessionLocal)
market_data_service = build_market_data_service()


def _resolve_bars(symbol: str, timeframe: str, request_bars: list[Bar]) -> tuple[list[Bar], str, bool]:
    if request_bars:
        return request_bars, "request_bars", False

    _limit_by_tf = {"1H": 400, "4H": 200, "1D": 120}
    limit = _limit_by_tf.get(timeframe.upper(), 120)

    provider_bars, provider_source, provider_fallback = market_data_service.historical_bars(
        symbol=symbol,
        timeframe=timeframe,
        limit=limit,
    )
    if provider_bars:
        return provider_bars, provider_source, provider_fallback

    persisted = bar_repo.list_for_symbol(symbol=symbol) if timeframe.upper() == "1D" else []
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

    return market_data_service.historical_bars(symbol=symbol, timeframe=timeframe, limit=limit)


@router.post("/haco", response_model=HacoChartPayload)
def get_haco_chart(req: HacoChartRequest, _user=Depends(require_approved_user)) -> HacoChartPayload:
    bars, data_source, fallback_mode = _resolve_bars(req.symbol, req.timeframe, req.bars)
    return service.build_payload(
        symbol=req.symbol,
        timeframe=req.timeframe,
        bars=bars,
        include_heikin_ashi=req.include_heikin_ashi,
        data_source=data_source,
        fallback_mode=fallback_mode,
    )
