"""Bounded direction-only progression contracts."""

from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.training_history import TrainingHistory


PROGRESSION_ENGINE_VERSION = "progression-engine-v1"


class ProgressionReasonCode(str, Enum):
    EXERCISE_NOT_IN_HISTORY = "EXERCISE_NOT_IN_HISTORY"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    INSUFFICIENT_COMPARABLE_PERFORMANCE = "INSUFFICIENT_COMPARABLE_PERFORMANCE"
    PERFORMANCE_IMPROVED = "PERFORMANCE_IMPROVED"
    PERFORMANCE_STABLE = "PERFORMANCE_STABLE"
    PERFORMANCE_MIXED = "PERFORMANCE_MIXED"
    PERFORMANCE_REGRESSED = "PERFORMANCE_REGRESSED"
    LATEST_EXECUTION_INCOMPLETE = "LATEST_EXECUTION_INCOMPLETE"
    LATEST_HIGH_FATIGUE = "LATEST_HIGH_FATIGUE"
    LATEST_MODERATE_HIGH_DISCOMFORT = "LATEST_MODERATE_HIGH_DISCOMFORT"
    LATEST_HIGH_EFFORT = "LATEST_HIGH_EFFORT"
    REPEATED_STRAIN = "REPEATED_STRAIN"
    REPEATED_EXECUTION_OR_EFFORT_ISSUES = "REPEATED_EXECUTION_OR_EFFORT_ISSUES"
    NO_STRONG_CHANGE_SIGNAL = "NO_STRONG_CHANGE_SIGNAL"


class ProgressionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    history: TrainingHistory
    exercise_id: Annotated[str, Field(min_length=1, max_length=128)]

    @field_validator("history", mode="before")
    @classmethod
    def require_canonical_history(cls, value):
        if not isinstance(value, TrainingHistory):
            raise ValueError("history must be a canonical TrainingHistory instance")
        return value


class ProgressionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    engine_version: Literal["progression-engine-v1"] = PROGRESSION_ENGINE_VERSION
    exercise_id: str
    decision: Literal["PROGRESS", "MAINTAIN", "REDUCE", "DELOAD", "NEEDS_MORE_DATA"]
    reason_codes: list[ProgressionReasonCode]
    occurrences_considered: Annotated[int, Field(strict=True, ge=0)]
    latest_session_id: str | None
