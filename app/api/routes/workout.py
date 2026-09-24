"""Authenticated public adapter for the internal workout pipeline."""

from fastapi import APIRouter, Depends

from app.core.security import verify_api_key
from app.models.workout_api import WorkoutApiRequest, WorkoutApiResponse
from app.services import workout_orchestrator
from app.services.workout_api_mapper import to_internal_environment, to_workout_api_response

router = APIRouter(prefix="/api/v1", tags=["workout"])


@router.post(
    "/workout", response_model=WorkoutApiResponse,
    dependencies=[Depends(verify_api_key)],
)
async def get_workout(payload: WorkoutApiRequest) -> WorkoutApiResponse:
    environment = to_internal_environment(payload.environment)
    result = workout_orchestrator.orchestrate_workout(payload.training, environment)
    return to_workout_api_response(result)
