"""Explicit one-week program structure and authoritative context contracts."""

from datetime import date, timedelta
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.progression import ProgressionDecision
from app.models.weekly_training_state import WeeklyTrainingState


PROGRAM_PLANNER_VERSION = "program-planner-v1"
Identifier = Annotated[str, Field(min_length=1, max_length=128)]
NonNegativeInt = Annotated[int, Field(strict=True, ge=0)]
SessionType = Literal["upper_body", "lower_body", "full_body", "cardio", "mobility"]


class ProgramSessionTemplateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot_id: Identifier
    day_offset: Annotated[int, Field(strict=True, ge=0, le=6)]
    session_type: SessionType


class ProgramPlannerInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    previous_week_state: WeeklyTrainingState
    progression_decisions: list[ProgressionDecision]
    plan_week_start: date
    session_templates: list[ProgramSessionTemplateInput]

    @field_validator("previous_week_state", mode="before")
    @classmethod
    def require_canonical_week(cls, value):
        if not isinstance(value, WeeklyTrainingState):
            raise ValueError("previous_week_state must be a canonical WeeklyTrainingState instance")
        return value

    @field_validator("progression_decisions", mode="before")
    @classmethod
    def require_canonical_decisions(cls, value):
        if not isinstance(value, list) or any(
            not isinstance(item, ProgressionDecision) for item in value
        ):
            raise ValueError("progression_decisions must contain canonical ProgressionDecision instances")
        return value

    @model_validator(mode="after")
    def validate_program_scope(self) -> Self:
        try:
            next_week_start = self.previous_week_state.week_end + timedelta(days=1)
            self.plan_week_start + timedelta(days=6)
        except OverflowError as error:
            raise ValueError("dates must allow a contiguous seven-day program week") from error
        if self.plan_week_start != next_week_start:
            raise ValueError("plan_week_start must equal previous week_end + 1 day")
        exercise_ids = [item.exercise_id for item in self.progression_decisions]
        if len(exercise_ids) != len(set(exercise_ids)):
            raise ValueError("progression exercise_id must be unique")
        slot_ids = [item.slot_id for item in self.session_templates]
        if len(slot_ids) != len(set(slot_ids)):
            raise ValueError("slot_id must be unique")
        return self


class ProgramSessionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot_id: Identifier
    scheduled_date: date
    session_type: SessionType


class ProgramProgressionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_decisions: NonNegativeInt
    progress_decisions: NonNegativeInt
    maintain_decisions: NonNegativeInt
    reduce_decisions: NonNegativeInt
    deload_decisions: NonNegativeInt
    needs_more_data_decisions: NonNegativeInt


class ProgramPreviousWeekContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_week_start: date
    source_week_end: date
    source_as_of_date: date
    planned_sessions: NonNegativeInt
    completed_planned_sessions: NonNegativeInt
    partial_planned_sessions: NonNegativeInt
    remaining_planned_sessions: NonNegativeInt
    due_remaining_planned_sessions: NonNegativeInt
    unplanned_sessions: NonNegativeInt
    attendance_ratio: Annotated[float, Field(strict=True, ge=0, le=1)] | None
    high_fatigue_sessions: NonNegativeInt
    moderate_high_discomfort_sessions: NonNegativeInt


class ProgramPlanSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_sessions: NonNegativeInt
    upper_body_sessions: NonNegativeInt
    lower_body_sessions: NonNegativeInt
    full_body_sessions: NonNegativeInt
    cardio_sessions: NonNegativeInt
    mobility_sessions: NonNegativeInt


class ProgramPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    planner_version: Literal["program-planner-v1"] = PROGRAM_PLANNER_VERSION
    source_week_start: date
    source_week_end: date
    plan_week_start: date
    plan_week_end: date
    sessions: list[ProgramSessionPlan]
    progression_decisions: list[ProgressionDecision]
    previous_week_context: ProgramPreviousWeekContext
    progression_summary: ProgramProgressionSummary
    plan_summary: ProgramPlanSummary
