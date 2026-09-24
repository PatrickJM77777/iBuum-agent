"""Kaia entrypoint; cycle wording only, no separate training logic."""

from app.models.interpretation import InterpretationResult, Presenter
from app.models.training_request import TrainingRecommendationRequest
from app.models.workout_orchestration import WorkoutEnvironmentContext, WorkoutOrchestrationResult
from app.services.interpretation_core import interpret_workout


def present_kaia(request: TrainingRecommendationRequest, result: WorkoutOrchestrationResult,
                 environment: WorkoutEnvironmentContext | None = None) -> InterpretationResult:
    return interpret_workout(request, result, environment, presenter=Presenter.kaia)
