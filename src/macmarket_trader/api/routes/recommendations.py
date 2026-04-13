"""Recommendation API route."""

from fastapi import APIRouter, Depends, HTTPException

from macmarket_trader.api.deps.auth import require_approved_user
from macmarket_trader.domain.enums import ApprovalStatus
from macmarket_trader.domain.schemas import RecommendationGenerateRequest, TradeRecommendation
from macmarket_trader.service import RecommendationService

router = APIRouter(prefix="/recommendations", tags=["recommendations"])
service = RecommendationService()


@router.post("/generate", response_model=TradeRecommendation)
def generate_recommendation(req: RecommendationGenerateRequest, _user=Depends(require_approved_user)) -> TradeRecommendation:
    approval_status = getattr(_user.approval_status, "value", _user.approval_status)
    user_is_approved = str(approval_status) == ApprovalStatus.APPROVED.value
    try:
        return service.generate(
            symbol=req.symbol,
            bars=req.bars,
            event_text=req.event_text,
            event=req.event,
            portfolio=req.portfolio,
            market_mode=req.market_mode,
            user_is_approved=user_is_approved,
            app_user_id=_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
