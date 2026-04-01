"""Protected chart routes."""

from fastapi import APIRouter, Depends

from macmarket_trader.api.deps.auth import require_approved_user
from macmarket_trader.charts.haco_service import HacoChartService
from macmarket_trader.domain.schemas import HacoChartPayload, HacoChartRequest

router = APIRouter(prefix="/charts", tags=["charts"])
service = HacoChartService()


@router.post("/haco", response_model=HacoChartPayload)
def get_haco_chart(req: HacoChartRequest, _user=Depends(require_approved_user)) -> HacoChartPayload:
    return service.build_payload(
        symbol=req.symbol,
        timeframe=req.timeframe,
        bars=req.bars,
        include_heikin_ashi=req.include_heikin_ashi,
    )
