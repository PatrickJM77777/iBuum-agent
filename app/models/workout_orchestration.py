"""Internal orchestration inputs and provenance; not public API models."""

from pydantic import BaseModel, ConfigDict

from app.models.exercise import ExerciseEquipment, SuitableLocation
from app.models.exercise_selection import SelectedWorkoutPlan
from app.models.training_response import TrainingRecommendationResponse


class WorkoutEnvironmentContext(BaseModel):
    """Unknown equipment is None; empty means none; bodyweight is explicit."""

    model_config = ConfigDict(extra="forbid")

    available_equipment: frozenset[ExerciseEquipment] | None = None
    training_location: SuitableLocation | None = None


class WorkoutOrchestrationResult(BaseModel):
    recommendation: TrainingRecommendationResponse
    selected_workout: SelectedWorkoutPlan
    orchestrator_version: str
