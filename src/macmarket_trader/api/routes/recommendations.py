"""Recommendation API route."""

from fastapi import APIRouter, Depends

from macmarket_trader.api.deps.auth import require_approved_user
from macmarket_trader.domain.schemas import RecommendationGenerateRequest, TradeRecommendation
from macmarket_trader.service import RecommendationService

router = APIRouter(prefix="/recommendations", tags=["recommendations"])
service = RecommendationService()


@router.post("/generate", response_model=TradeRecommendation)
def generate_recommendation(req: RecommendationGenerateRequest, _user=Depends(require_approved_user)) -> TradeRecommendation:
    return service.generate(
        symbol=req.symbol,
        bars=req.bars,
        event_text=req.event_text,
        event=req.event,
        portfolio=req.portfolio,
    )
