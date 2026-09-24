"""Stable public Workout API V1 contracts, independent of pipeline models."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.models.exercise import ExerciseEquipment, SuitableLocation
from app.models.training_request import TrainingRecommendationRequest
from app.models.training_response import (
    Action, Intensity, RecommendedSession, TrainingRecommendationResponse,
)


class WorkoutEnvironmentApiRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    available_equipment: list[ExerciseEquipment] | None = None
    training_location: SuitableLocation | None = None


class WorkoutApiRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    training: TrainingRecommendationRequest
    environment: WorkoutEnvironmentApiRequest | None = None


class WorkoutSlotApiResponse(BaseModel):
    """Flat public prescription shared by selected and unresolved work."""

    sequence: int
    movement_pattern: str
    target_area: str | None
    sets: int | None
    rep_min: int | None
    rep_max: int | None
    work_seconds: int | None
    rest_seconds: int | None
    effort_target: str | None
    notes: list[str]


class WorkoutExerciseApiResponse(WorkoutSlotApiResponse):
    exercise_id: str
    display_name: str
    selection_reason_codes: list[str]


class WorkoutUnresolvedSlotApiResponse(WorkoutSlotApiResponse):
    reason_codes: list[str]


class WorkoutApiPayload(BaseModel):
    plan_status: Literal["generated", "no_workout", "more_data_required"]
    selector_status: Literal["complete", "incomplete", "no_workout", "more_data_required"]
    action: Action
    session_type: RecommendedSession
    intensity: Intensity
    duration_minutes: int
    exercises: list[WorkoutExerciseApiResponse]
    unresolved_slots: list[WorkoutUnresolvedSlotApiResponse]
    generator_reason_codes: list[str]


class WorkoutVersionsApiResponse(BaseModel):
    agent_version: str
    generator_version: str
    selector_version: str
    orchestrator_version: str


class WorkoutApiResponse(BaseModel):
    recommendation: TrainingRecommendationResponse
    workout: WorkoutApiPayload
    versions: WorkoutVersionsApiResponse
