"""Internal workout generator models (not part of the public API contract)."""

from enum import Enum

from pydantic import BaseModel, Field

from app.models.training_response import Action, Intensity, RecommendedSession


class WorkoutPlanStatus(str, Enum):
    generated = "generated"
    no_workout = "no_workout"
    more_data_required = "more_data_required"


class MovementSlot(BaseModel):
    movement_pattern: str
    target_area: str | None = None
    sets: int | None = None
    rep_min: int | None = None
    rep_max: int | None = None
    work_seconds: int | None = None
    rest_seconds: int | None = None
    effort_target: str | None = None
    sequence: int
    notes: list[str] = Field(default_factory=list)


class WorkoutPlan(BaseModel):
    status: WorkoutPlanStatus
    action: Action
    session_type: RecommendedSession
    intensity: Intensity
    target_duration_minutes: int
    movement_slots: list[MovementSlot]
    generator_reason_codes: list[str] = Field(default_factory=list)
    generator_version: str
