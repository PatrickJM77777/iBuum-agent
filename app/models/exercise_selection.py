"""Internal selection results; deliberately separate from the public API."""

from enum import Enum

from pydantic import BaseModel, Field

from app.models.exercise import ExerciseEquipment, SuitableLocation
from app.models.training_request import TrainingLevel
from app.models.workout import MovementSlot, WorkoutPlan


class ExerciseSelectorContext(BaseModel):
    """None means unknown; an empty equipment set means nothing is available.

    Bodyweight must be explicitly included, just like every other equipment type.
    """

    training_level: TrainingLevel | None = None
    available_equipment: frozenset[ExerciseEquipment] | None = None
    training_location: SuitableLocation | None = None


class ExerciseSelectionStatus(str, Enum):
    complete = "complete"
    incomplete = "incomplete"
    no_workout = "no_workout"
    more_data_required = "more_data_required"


class SelectionReasonCode(str, Enum):
    STABLE_CATALOG_ORDER = "STABLE_CATALOG_ORDER"
    DUPLICATE_AVOIDED = "DUPLICATE_AVOIDED"
    REUSED_AFTER_ALTERNATIVES_EXHAUSTED = "REUSED_AFTER_ALTERNATIVES_EXHAUSTED"
    SELECTION_CONTEXT_INCOMPLETE = "SELECTION_CONTEXT_INCOMPLETE"
    INVALID_MOVEMENT_PATTERN = "INVALID_MOVEMENT_PATTERN"
    NO_COMPATIBLE_EXERCISE = "NO_COMPATIBLE_EXERCISE"
    TRAINING_LEVEL_NOT_COMPATIBLE = "TRAINING_LEVEL_NOT_COMPATIBLE"
    LOCATION_NOT_COMPATIBLE = "LOCATION_NOT_COMPATIBLE"
    EQUIPMENT_NOT_AVAILABLE = "EQUIPMENT_NOT_AVAILABLE"
    UPSTREAM_SELECTION_BLOCKED = "UPSTREAM_SELECTION_BLOCKED"


class SelectedExerciseSlot(BaseModel):
    source_slot: MovementSlot
    exercise_id: str
    display_name: str
    reason_codes: list[SelectionReasonCode]


class UnresolvedExerciseSlot(BaseModel):
    source_slot: MovementSlot
    reason_codes: list[SelectionReasonCode]


class SelectedWorkoutPlan(BaseModel):
    # Snapshot retains all upstream metadata without duplicating its schema.
    source_plan: WorkoutPlan
    selector_status: ExerciseSelectionStatus
    selected_slots: list[SelectedExerciseSlot] = Field(default_factory=list)
    unresolved_slots: list[UnresolvedExerciseSlot] = Field(default_factory=list)
    selector_version: str
