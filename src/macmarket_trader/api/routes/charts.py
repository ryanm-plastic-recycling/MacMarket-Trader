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


def _bar_metadata(bars: list[Bar], *, source: str, timeframe: str, fallback_mode: bool) -> dict[str, object]:
    first = bars[0] if bars else None
    last = bars[-1] if bars else None
    return {
        "provider": source,
        "timeframe": timeframe,
        "fallback_mode": fallback_mode,
        "session_policy": first.session_policy if first else None,
        "source_session_policy": first.source_session_policy if first else None,
        "source_timeframe": first.source_timeframe if first else None,
        "output_timeframe": timeframe.upper(),
        "filtered_extended_hours_count": 0 if first and first.session_policy == "regular_hours" else None,
        "rth_bucket_count": len(bars) if first and first.session_policy == "regular_hours" else None,
        "first_bar_timestamp": first.timestamp.isoformat() if first and first.timestamp else None,
        "last_bar_timestamp": last.timestamp.isoformat() if last and last.timestamp else None,
    }


def _resolve_bars(symbol: str, timeframe: str, request_bars: list[Bar]) -> tuple[list[Bar], str, bool, dict[str, object]]:
    if request_bars:
        return request_bars, "request_bars", False, _bar_metadata(
            request_bars,
            source="request_bars",
            timeframe=timeframe,
            fallback_mode=False,
        )

    _limit_by_tf = {"1H": 400, "4H": 200, "1D": 120}
    limit = _limit_by_tf.get(timeframe.upper(), 120)

    provider_bars, provider_source, provider_fallback = market_data_service.historical_bars(
        symbol=symbol,
        timeframe=timeframe,
        limit=limit,
    )
    if provider_bars:
        provider_metadata = getattr(market_data_service, "last_historical_metadata", None)
        return provider_bars, provider_source, provider_fallback, dict(provider_metadata or _bar_metadata(
            provider_bars,
            source=provider_source,
            timeframe=timeframe,
            fallback_mode=provider_fallback,
        ))

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
            {},
        )

    bars, source, fallback = market_data_service.historical_bars(symbol=symbol, timeframe=timeframe, limit=limit)
    provider_metadata = getattr(market_data_service, "last_historical_metadata", None)
    return bars, source, fallback, dict(provider_metadata or _bar_metadata(
        bars,
        source=source,
        timeframe=timeframe,
        fallback_mode=fallback,
    ))


@router.post("/haco", response_model=HacoChartPayload)
def get_haco_chart(req: HacoChartRequest, _user=Depends(require_approved_user)) -> HacoChartPayload:
    bars, data_source, fallback_mode, metadata = _resolve_bars(req.symbol, req.timeframe, req.bars)
    return service.build_payload(
        symbol=req.symbol,
        timeframe=req.timeframe,
        bars=bars,
        include_heikin_ashi=req.include_heikin_ashi,
        data_source=data_source,
        fallback_mode=fallback_mode,
        metadata=metadata,
    )
