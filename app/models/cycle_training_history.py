"""Minimal session-linked cycle facts, without analysis or training policy."""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.session_outcome import NonNegativeInt, SessionOutcome
from app.models.training_history import TrainingHistory


CYCLE_TRAINING_HISTORY_VERSION = "cycle-training-history-v1"
CyclePhase = Literal["menstruation", "follicular", "ovulation", "luteal", "unknown"]
CycleDiscomfort = Literal["none", "mild", "moderate", "high"]


class CycleTrainingObservationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: Annotated[str, Field(min_length=1, max_length=128)]
    phase: CyclePhase
    discomfort: CycleDiscomfort | None = None


class CycleTrainingHistoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    training_history: TrainingHistory
    cycle_observations: list[CycleTrainingObservationInput]

    @field_validator("training_history", mode="before")
    @classmethod
    def require_canonical_history(cls, value):
        if not isinstance(value, TrainingHistory):
            raise ValueError("training_history must be a canonical TrainingHistory object")
        return value

    @field_validator("cycle_observations", mode="before")
    @classmethod
    def require_canonical_observations(cls, value):
        if not isinstance(value, list) or any(
            not isinstance(item, CycleTrainingObservationInput) for item in value
        ):
            raise ValueError("cycle_observations must be a list of canonical observation objects")
        return value

    @model_validator(mode="after")
    def validate_linkage(self) -> Self:
        identifiers = [item.session_id for item in self.cycle_observations]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("session_id must be unique across cycle_observations")
        session_ids = {session.session_id for session in self.training_history.sessions}
        if not set(identifiers) <= session_ids:
            raise ValueError("every observation must reference a training_history session")
        return self


class CycleTrainingContextSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phase: CyclePhase
    discomfort: CycleDiscomfort | None = None


class CycleTrainingSessionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session: SessionOutcome
    cycle_context: CycleTrainingContextSnapshot | None


class CycleTrainingHistorySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_sessions: NonNegativeInt
    sessions_with_cycle_context: NonNegativeInt
    sessions_without_cycle_context: NonNegativeInt
    menstruation_sessions: NonNegativeInt
    follicular_sessions: NonNegativeInt
    ovulation_sessions: NonNegativeInt
    luteal_sessions: NonNegativeInt
    unknown_phase_sessions: NonNegativeInt
    sessions_with_known_cycle_discomfort: NonNegativeInt
    cycle_discomfort_none_sessions: NonNegativeInt
    cycle_discomfort_mild_sessions: NonNegativeInt
    cycle_discomfort_moderate_sessions: NonNegativeInt
    cycle_discomfort_high_sessions: NonNegativeInt

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if self.total_sessions != self.sessions_with_cycle_context + self.sessions_without_cycle_context:
            raise ValueError("context counts must sum to total_sessions")
        if self.sessions_with_cycle_context != (
            self.menstruation_sessions + self.follicular_sessions + self.ovulation_sessions
            + self.luteal_sessions + self.unknown_phase_sessions
        ):
            raise ValueError("phase counts must sum to sessions_with_cycle_context")
        if self.sessions_with_known_cycle_discomfort != (
            self.cycle_discomfort_none_sessions + self.cycle_discomfort_mild_sessions
            + self.cycle_discomfort_moderate_sessions + self.cycle_discomfort_high_sessions
        ):
            raise ValueError("discomfort counts must sum to sessions_with_known_cycle_discomfort")
        if self.sessions_with_known_cycle_discomfort > self.sessions_with_cycle_context:
            raise ValueError("known discomfort cannot exceed sessions_with_cycle_context")
        return self


class CycleTrainingHistory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cycle_history_version: Literal["cycle-training-history-v1"] = CYCLE_TRAINING_HISTORY_VERSION
    source_training_history_version: Literal["training-history-v1"]
    sessions: list[CycleTrainingSessionRecord]
    summary: CycleTrainingHistorySummary
