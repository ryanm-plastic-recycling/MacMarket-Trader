"""Recommendation API route."""

from fastapi import APIRouter

from macmarket_trader.domain.schemas import RecommendationGenerateRequest, TradeRecommendation
from macmarket_trader.service import RecommendationService

router = APIRouter(prefix="/recommendations", tags=["recommendations"])
service = RecommendationService()


@router.post("/generate", response_model=TradeRecommendation)
def generate_recommendation(req: RecommendationGenerateRequest) -> TradeRecommendation:
    return service.generate(
        symbol=req.symbol,
        bars=req.bars,
        event_text=req.event_text,
        event=req.event,
        portfolio=req.portfolio,
    )
