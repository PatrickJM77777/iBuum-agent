"""Explicit public Interpretation API V1 contracts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.models.training_request import TrainingRecommendationRequest
from app.models.training_response import (
    Action, Intensity, RecommendedSession, TrainingRecommendationResponse,
)
from app.models.workout_api import WorkoutApiPayload, WorkoutEnvironmentApiRequest


class InterpretationApiRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    presenter: Literal["kai", "kaia"]
    training: TrainingRecommendationRequest
    environment: WorkoutEnvironmentApiRequest | None = None


class InterpretationApiPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    presenter: Literal["kai", "kaia"]
    tone: Literal["training", "recovery", "rest", "incomplete"]
    action: Action
    session: RecommendedSession
    intensity: Intensity
    duration_minutes: int
    needs_more_data: bool
    title: str
    summary: str
    reasons: list[str]
    today_plan: str
    avatar_message: str
    missing_data_message: str | None
    environment_message: str | None
    cycle_insight: str | None
    reason_codes: list[str]
    interpretation_version: Literal["interpretation-core-v1"]


class InterpretationVersionsApiResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_version: str
    generator_version: str
    selector_version: str
    orchestrator_version: str
    interpretation_version: Literal["interpretation-core-v1"]


class InterpretationApiResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation: TrainingRecommendationResponse
    workout: WorkoutApiPayload
    interpretation: InterpretationApiPayload
    versions: InterpretationVersionsApiResponse
