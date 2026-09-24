"""Internal exercise library models."""

from enum import Enum
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.training_request import TrainingLevel


class MovementPattern(str, Enum):
    horizontal_push = "horizontal_push"
    horizontal_pull = "horizontal_pull"
    vertical_push = "vertical_push"
    vertical_pull = "vertical_pull"
    squat_pattern = "squat_pattern"
    hinge_pattern = "hinge_pattern"
    unilateral_lower = "unilateral_lower"
    posterior_chain = "posterior_chain"
    core = "core"
    conditioning = "conditioning"
    mobility = "mobility"
    mobility_spine = "mobility_spine"
    mobility_hips = "mobility_hips"
    mobility_shoulders = "mobility_shoulders"
    mobility_ankles = "mobility_ankles"
    breathing_core_control = "breathing_core_control"


class ExerciseEquipment(str, Enum):
    bodyweight = "bodyweight"
    dumbbell = "dumbbell"
    barbell = "barbell"
    kettlebell = "kettlebell"
    resistance_band = "resistance_band"
    cable = "cable"
    machine = "machine"


class Laterality(str, Enum):
    unilateral = "unilateral"
    bilateral = "bilateral"


class BodyPosition(str, Enum):
    standing = "standing"
    seated = "seated"
    floor = "floor"
    supine = "supine"
    prone = "prone"
    kneeling = "kneeling"
    supported = "supported"


class DemandLevel(str, Enum):
    low = "low"
    moderate = "moderate"
    high = "high"


class SuitableLocation(str, Enum):
    home = "home"
    gym = "gym"
    minimal_equipment = "minimal_equipment"


class ExerciseDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(..., min_length=1)
    display_name: str = Field(..., min_length=1)
    movement_pattern: MovementPattern
    primary_regions: tuple[str, ...] = Field(..., min_length=1)
    secondary_regions: tuple[str, ...] = ()
    equipment: tuple[ExerciseEquipment, ...] = Field(..., min_length=1)
    training_levels: tuple[TrainingLevel, ...] = Field(..., min_length=1)
    laterality: Laterality
    body_position: BodyPosition
    impact_level: DemandLevel
    balance_demand: DemandLevel
    coordination_demand: DemandLevel
    suitable_locations: tuple[SuitableLocation, ...] = Field(..., min_length=1)

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)*", value):
            raise ValueError("exercise ids must be lowercase snake_case.")
        return value
