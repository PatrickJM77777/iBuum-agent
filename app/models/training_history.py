"""Ordered factual history of canonical Session Outcome snapshots."""

from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.session_outcome import ExerciseOutcome, NonNegativeInt, SessionOutcome


TRAINING_HISTORY_VERSION = "training-history-v1"


class TrainingHistoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcomes: list[SessionOutcome]

    @field_validator("outcomes", mode="before")
    @classmethod
    def require_canonical_outcomes(cls, value):
        if not isinstance(value, list) or any(not isinstance(item, SessionOutcome) for item in value):
            raise ValueError("outcomes must be a list of canonical SessionOutcome objects")
        return value

    @model_validator(mode="after")
    def validate_unique_sessions(self) -> Self:
        identifiers = [outcome.session_id for outcome in self.outcomes]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("session_id must be unique across outcomes")
        return self


class TrainingHistorySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_sessions: NonNegativeInt
    completed_sessions: NonNegativeInt
    interrupted_sessions: NonNegativeInt
    total_exercises: NonNegativeInt
    completed_exercises: NonNegativeInt
    partial_exercises: NonNegativeInt
    skipped_exercises: NonNegativeInt
    not_started_exercises: NonNegativeInt
    completed_sets: NonNegativeInt
    skipped_sets: NonNegativeInt
    sessions_with_known_duration: NonNegativeInt
    known_duration_seconds: NonNegativeInt
    sessions_with_feedback: NonNegativeInt


class ExerciseHistoryOccurrence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: Annotated[str, Field(min_length=1, max_length=128)]
    session_completion_state: Literal["completed", "interrupted"]
    session_started_at: AwareDatetime | None = None
    session_ended_at: AwareDatetime | None = None
    source_action: Literal["train", "recovery"] | None = None
    session_type: Literal["upper_body", "lower_body", "full_body", "cardio", "mobility"] | None = None
    exercise: ExerciseOutcome


class ExerciseHistory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exercise_id: Annotated[str, Field(min_length=1, max_length=128)]
    occurrences: list[ExerciseHistoryOccurrence]


class TrainingHistory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    history_version: Literal["training-history-v1"] = TRAINING_HISTORY_VERSION
    sessions: list[SessionOutcome]
    exercise_history: list[ExerciseHistory]
    summary: TrainingHistorySummary
