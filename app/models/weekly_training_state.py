"""Explicit weekly scope and factual internal aggregate contracts."""

from datetime import date, timedelta
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.session_outcome import NonNegativeInt
from app.models.training_history import TrainingHistory


WEEKLY_TRAINING_STATE_VERSION = "weekly-training-state-v1"
Identifier = Annotated[str, Field(min_length=1, max_length=128)]
SessionType = Literal["upper_body", "lower_body", "full_body", "cardio", "mobility"]


class WeeklyPlannedSessionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot_id: Identifier
    scheduled_date: date
    session_type: SessionType | None = None
    linked_session_id: Identifier | None = None


class WeeklyTrainingStateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    history: TrainingHistory
    week_start: date
    as_of_date: date
    planned_sessions: list[WeeklyPlannedSessionInput]
    included_session_ids: list[str]

    @field_validator("history", mode="before")
    @classmethod
    def require_canonical_history(cls, value):
        if not isinstance(value, TrainingHistory):
            raise ValueError("history must be a canonical TrainingHistory instance")
        return value

    @model_validator(mode="after")
    def validate_weekly_scope(self) -> Self:
        try:
            week_end = self.week_start + timedelta(days=6)
        except OverflowError as error:
            raise ValueError("week_start must allow a seven-day window") from error
        if not self.week_start <= self.as_of_date <= week_end:
            raise ValueError("as_of_date must fall inside the week")
        slot_ids = [slot.slot_id for slot in self.planned_sessions]
        if len(slot_ids) != len(set(slot_ids)):
            raise ValueError("slot_id must be unique")
        included = set(self.included_session_ids)
        if len(included) != len(self.included_session_ids):
            raise ValueError("included_session_ids must be unique")
        known = {session.session_id for session in self.history.sessions}
        if not included <= known:
            raise ValueError("every included_session_id must exist in history.sessions")
        linked = set()
        for slot in self.planned_sessions:
            if not self.week_start <= slot.scheduled_date <= week_end:
                raise ValueError("scheduled_date must fall inside the week")
            if slot.linked_session_id is None:
                continue
            if slot.linked_session_id not in known:
                raise ValueError("linked_session_id must exist in history.sessions")
            if slot.linked_session_id not in included:
                raise ValueError("linked_session_id must appear in included_session_ids")
            if slot.linked_session_id in linked:
                raise ValueError("one session may link to at most one planned slot")
            linked.add(slot.linked_session_id)
        return self


class WeeklyPlannedSessionState(WeeklyPlannedSessionInput):
    model_config = ConfigDict(extra="forbid")

    status: Literal["completed", "partial", "remaining"]
    is_due: bool


class WeeklyPlanSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_planned_sessions: NonNegativeInt
    completed_planned_sessions: NonNegativeInt
    partial_planned_sessions: NonNegativeInt
    remaining_planned_sessions: NonNegativeInt
    due_remaining_planned_sessions: NonNegativeInt
    future_remaining_planned_sessions: NonNegativeInt


class WeeklyWorkloadFacts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_sessions: NonNegativeInt
    completed_sessions: NonNegativeInt
    interrupted_sessions: NonNegativeInt
    unplanned_sessions: NonNegativeInt
    total_exercises: NonNegativeInt
    completed_exercises: NonNegativeInt
    partial_exercises: NonNegativeInt
    skipped_exercises: NonNegativeInt
    not_started_exercises: NonNegativeInt
    completed_sets: NonNegativeInt
    skipped_sets: NonNegativeInt
    sessions_with_known_duration: NonNegativeInt
    known_duration_seconds: NonNegativeInt


class WeeklyRecoveryFacts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sessions_with_feedback: NonNegativeInt
    sessions_with_known_fatigue: NonNegativeInt
    high_fatigue_sessions: NonNegativeInt
    latest_known_fatigue_after: Annotated[int, Field(strict=True, ge=1, le=5)] | None
    sessions_with_known_discomfort: NonNegativeInt
    moderate_high_discomfort_sessions: NonNegativeInt
    latest_known_discomfort_after: Literal["none", "mild", "moderate", "high"] | None
    sessions_with_known_session_rpe: NonNegativeInt
    latest_known_session_rpe: Annotated[float, Field(strict=True, ge=1, le=10)] | None


class WeeklyAdherenceFacts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    due_planned_sessions: NonNegativeInt
    completed_due_sessions: NonNegativeInt
    partial_due_sessions: NonNegativeInt
    unresolved_due_sessions: NonNegativeInt
    attendance_ratio: Annotated[float, Field(strict=True, ge=0, le=1)] | None


class WeeklyTrainingState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state_version: Literal["weekly-training-state-v1"] = WEEKLY_TRAINING_STATE_VERSION
    week_start: date
    week_end: date
    as_of_date: date
    planned_sessions: list[WeeklyPlannedSessionState]
    included_session_ids: list[str]
    unplanned_session_ids: list[str]
    plan_summary: WeeklyPlanSummary
    workload: WeeklyWorkloadFacts
    recovery: WeeklyRecoveryFacts
    adherence: WeeklyAdherenceFacts
