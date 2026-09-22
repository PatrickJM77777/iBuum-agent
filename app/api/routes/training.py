"""
POST /api/v1/training/recommendation

This route contains NO business logic. It only:
  1. validates input (via the Pydantic request model),
  2. authenticates (via the verify_api_key dependency),
  3. calls the rules engine,
  4. returns the structured result.
"""

from fastapi import APIRouter, Depends

from app.core.security import verify_api_key
from app.models.training_request import TrainingRecommendationRequest
from app.models.training_response import TrainingRecommendationResponse
from app.services import training_rules

router = APIRouter(prefix="/api/v1/training", tags=["training"])


@router.post(
    "/recommendation",
    response_model=TrainingRecommendationResponse,
    dependencies=[Depends(verify_api_key)],
)
async def get_training_recommendation(
    payload: TrainingRecommendationRequest,
) -> TrainingRecommendationResponse:
    """Return a deterministic training recommendation for the given context."""
    return training_rules.evaluate(payload)
