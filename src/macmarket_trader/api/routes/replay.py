"""Replay API route."""

from fastapi import APIRouter

from macmarket_trader.domain.schemas import ReplayRunRequest, ReplayRunResponse
from macmarket_trader.replay.engine import ReplayEngine
from macmarket_trader.service import RecommendationService

router = APIRouter(prefix="/replay", tags=["replay"])
replay_engine = ReplayEngine(service=RecommendationService())


@router.post("/run", response_model=ReplayRunResponse)
def run_replay(req: ReplayRunRequest) -> ReplayRunResponse:
    return replay_engine.run(req)
