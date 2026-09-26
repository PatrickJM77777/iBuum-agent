"""Canonical sports-domain snapshots, without inferred personal conclusions."""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.cycle_pattern_analyzer import CyclePatternAnalysis
from app.models.cycle_training_history import CycleTrainingHistory
from app.models.daily_recovery_state import DailyRecoveryState
from app.models.progression import ProgressionDecision
from app.models.training_history import TrainingHistory
from app.models.weekly_training_state import WeeklyTrainingState


PERSONAL_MEMORY_VERSION = "personal-memory-v1"
NonNegativeInt = Annotated[int, Field(strict=True, ge=0)]


class PersonalMemoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    training_history: TrainingHistory
    progression_decisions: list[ProgressionDecision]
    weekly_training_states: list[WeeklyTrainingState]
    daily_recovery_states: list[DailyRecoveryState]
    cycle_training_history: CycleTrainingHistory | None = None
    cycle_pattern_analysis: CyclePatternAnalysis | None = None

    @field_validator("training_history", "cycle_training_history", "cycle_pattern_analysis", mode="before")
    @classmethod
    def require_canonical_source(cls, value, info):
        expected = {
            "training_history": TrainingHistory,
            "cycle_training_history": CycleTrainingHistory,
            "cycle_pattern_analysis": CyclePatternAnalysis,
        }[info.field_name]
        if value is None and info.field_name != "training_history":
            return value
        if not isinstance(value, expected):
            raise ValueError(f"{info.field_name} must be a canonical {expected.__name__} instance")
        return value

    @field_validator("progression_decisions", "weekly_training_states", "daily_recovery_states", mode="before")
    @classmethod
    def require_canonical_list(cls, value, info):
        expected = {
            "progression_decisions": ProgressionDecision,
            "weekly_training_states": WeeklyTrainingState,
            "daily_recovery_states": DailyRecoveryState,
        }[info.field_name]
        if not isinstance(value, list) or any(not isinstance(item, expected) for item in value):
            raise ValueError(f"{info.field_name} must be a list of canonical {expected.__name__} instances")
        return value

    @model_validator(mode="after")
    def validate_source_consistency(self) -> Self:
        identifiers = [item.exercise_id for item in self.progression_decisions]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("progression_decisions exercise_id must be unique")
        weeks = [(item.week_start, item.as_of_date) for item in self.weekly_training_states]
        if any(previous >= current for previous, current in zip(weeks, weeks[1:])):
            raise ValueError("weekly_training_states must have unique strictly ascending (week_start, as_of_date)")
        session_ids = {item.session_id for item in self.training_history.sessions}
        for state in self.weekly_training_states:
            references = set(state.included_session_ids) | set(state.unplanned_session_ids)
            references.update(slot.linked_session_id for slot in state.planned_sessions
                              if slot.linked_session_id is not None)
            if not references <= session_ids:
                raise ValueError("weekly session references must exist in training_history.sessions")
        dates = [item.state_date for item in self.daily_recovery_states]
        if any(previous >= current for previous, current in zip(dates, dates[1:])):
            raise ValueError("daily_recovery_states must have unique strictly ascending state_date")
        cycle = self.cycle_training_history
        if cycle is not None:
            sessions = self.training_history.sessions
            if len(cycle.sessions) != len(sessions):
                raise ValueError("cycle_training_history session count must match training_history")
            for record, session in zip(cycle.sessions, sessions):
                if (record.session.session_id != session.session_id
                        or record.session.model_dump() != session.model_dump()):
                    raise ValueError("cycle_training_history sessions must exactly match training_history in order")
        analysis = self.cycle_pattern_analysis
        if analysis is not None:
            if cycle is None:
                raise ValueError("cycle_pattern_analysis requires cycle_training_history")
            if analysis.source_cycle_history_version != cycle.cycle_history_version:
                raise ValueError("cycle_pattern_analysis source cycle version must match")
            for field in ("total_sessions", "sessions_with_cycle_context",
                          "sessions_without_cycle_context", "unknown_phase_sessions"):
                if getattr(analysis.summary, field) != getattr(cycle.summary, field):
                    raise ValueError(f"cycle_pattern_analysis {field} inventory must match cycle history")
            known = (cycle.summary.menstruation_sessions + cycle.summary.follicular_sessions
                     + cycle.summary.ovulation_sessions + cycle.summary.luteal_sessions)
            if analysis.summary.known_phase_sessions != known:
                raise ValueError("cycle_pattern_analysis known_phase_sessions inventory must match cycle history")
        return self


class PersonalMemorySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_training_sessions: NonNegativeInt
    exercise_histories: NonNegativeInt
    progression_decisions: NonNegativeInt
    weekly_state_snapshots: NonNegativeInt
    daily_recovery_snapshots: NonNegativeInt
    has_cycle_training_history: Annotated[bool, Field(strict=True)]
    cycle_training_sessions: NonNegativeInt
    has_cycle_pattern_analysis: Annotated[bool, Field(strict=True)]
    cycle_patterns: NonNegativeInt

    @model_validator(mode="after")
    def validate_inventory(self) -> Self:
        if not self.has_cycle_training_history and self.cycle_training_sessions != 0:
            raise ValueError("absent cycle history requires zero cycle_training_sessions")
        if not self.has_cycle_pattern_analysis and self.cycle_patterns != 0:
            raise ValueError("absent cycle analysis requires zero cycle_patterns")
        if self.has_cycle_pattern_analysis and not self.has_cycle_training_history:
            raise ValueError("cycle analysis requires cycle history")
        return self


class PersonalMemory(PersonalMemoryInput):
    model_config = ConfigDict(extra="forbid")

    memory_version: Literal["personal-memory-v1"] = PERSONAL_MEMORY_VERSION
    source_training_history_version: Literal["training-history-v1"]
    cycle_training_history: CycleTrainingHistory | None
    cycle_pattern_analysis: CyclePatternAnalysis | None
    summary: PersonalMemorySummary
