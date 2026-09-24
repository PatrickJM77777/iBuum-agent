"""Authenticated adapter combining one approved workout with its explanation."""

from fastapi import APIRouter, Depends

from app.core.security import verify_api_key
from app.models.interpretation_api import InterpretationApiRequest, InterpretationApiResponse
from app.services import workout_orchestrator
from app.services.interpretation_api_mapper import to_interpretation_api_response
from app.services.kai_presenter import present_kai
from app.services.kaia_presenter import present_kaia
from app.services.workout_api_mapper import to_internal_environment, to_workout_api_response

router = APIRouter(prefix="/api/v1", tags=["interpretation"])


@router.post(
    "/interpretation", response_model=InterpretationApiResponse,
    dependencies=[Depends(verify_api_key)],
)
async def get_interpretation(payload: InterpretationApiRequest) -> InterpretationApiResponse:
    environment = to_internal_environment(payload.environment)
    result = workout_orchestrator.orchestrate_workout(payload.training, environment)
    workout = to_workout_api_response(result)
    presenter = present_kai if payload.presenter == "kai" else present_kaia
    interpretation = presenter(payload.training, result, environment)
    return to_interpretation_api_response(workout, interpretation)
