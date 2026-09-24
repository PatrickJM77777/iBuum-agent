"""Deterministic internal composition of the approved training pipeline."""

from app.models.exercise_selection import ExerciseSelectorContext
from app.models.training_request import TrainingRecommendationRequest
from app.models.workout_orchestration import (
    WorkoutEnvironmentContext,
    WorkoutOrchestrationResult,
)
from app.services import exercise_selector, training_engine, workout_generator

WORKOUT_ORCHESTRATOR_VERSION = "workout-orchestrator-v1"


class WorkoutOrchestrator:
    """Coordinate existing services without changing their decisions."""

    def orchestrate(
        self,
        request: TrainingRecommendationRequest,
        environment: WorkoutEnvironmentContext | None = None,
    ) -> WorkoutOrchestrationResult:
        environment = environment if environment is not None else WorkoutEnvironmentContext()
        recommendation = training_engine.evaluate(request)
        plan = workout_generator.generate_workout_plan(request, recommendation)
        context = ExerciseSelectorContext(
            training_level=request.training_level,
            available_equipment=environment.available_equipment,
            training_location=environment.training_location,
        )
        selected = exercise_selector.select_exercises(plan, context)
        return WorkoutOrchestrationResult(
            recommendation=recommendation.model_copy(deep=True),
            selected_workout=selected.model_copy(deep=True),
            orchestrator_version=WORKOUT_ORCHESTRATOR_VERSION,
        )


def orchestrate_workout(
    request: TrainingRecommendationRequest,
    environment: WorkoutEnvironmentContext | None = None,
) -> WorkoutOrchestrationResult:
    """Run the same engine, generator, selector chain for every request."""
    return WorkoutOrchestrator().orchestrate(request, environment)
