"""Explicit within-week date changes to an approved canonical program."""

from datetime import date
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.models.program_planner import Identifier, NonNegativeInt, ProgramPlan, SessionType
from app.models.weekly_training_state import WeeklyTrainingState


PLANNER_RESCHEDULING_VERSION = "planner-rescheduling-v1"
RescheduleReason = Literal[
    "SCHEDULE_CHANGE", "AVAILABILITY_CHANGE", "UNRESOLVED_SESSION"
]


class SessionRescheduleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot_id: Identifier
    target_date: date
    reason: RescheduleReason


class PlannerReschedulingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    program_plan: ProgramPlan
    current_week_state: WeeklyTrainingState
    requests: list[SessionRescheduleRequest]

    @field_validator("program_plan", mode="before")
    @classmethod
    def require_canonical_plan(cls, value):
        if not isinstance(value, ProgramPlan):
            raise ValueError("program_plan must be a canonical ProgramPlan instance")
        return value

    @field_validator("current_week_state", mode="before")
    @classmethod
    def require_canonical_state(cls, value):
        if not isinstance(value, WeeklyTrainingState):
            raise ValueError("current_week_state must be a canonical WeeklyTrainingState instance")
        return value

    @model_validator(mode="after")
    def validate_rescheduling_scope(self) -> Self:
        plan, week = self.program_plan, self.current_week_state
        if (plan.plan_week_start, plan.plan_week_end) != (week.week_start, week.week_end):
            raise ValueError("plan and current state must represent the same week")
        slots = {slot.slot_id: slot for slot in plan.sessions}
        states = {slot.slot_id: slot for slot in week.planned_sessions}
        if len(slots) != len(plan.sessions) or len(states) != len(week.planned_sessions):
            raise ValueError("canonical slot IDs must be unique")
        if slots.keys() != states.keys():
            raise ValueError("plan and current state must have exactly matching slot IDs")
        for slot_id, slot in slots.items():
            state = states[slot_id]
            if state.scheduled_date != slot.scheduled_date:
                raise ValueError("matching slots must have the same scheduled_date")
            if state.session_type is not None and state.session_type != slot.session_type:
                raise ValueError("known session_type must match the program")
        requested_ids = [request.slot_id for request in self.requests]
        if len(requested_ids) != len(set(requested_ids)):
            raise ValueError("requested slot_id values must be unique")
        for request in self.requests:
            if request.slot_id not in slots:
                raise ValueError("requested slot_id must exist in the program")
            if states[request.slot_id].status != "remaining":
                raise ValueError("only remaining sessions may be rescheduled")
            if not plan.plan_week_start <= request.target_date <= plan.plan_week_end:
                raise ValueError("target_date must be inside the program week")
            if request.target_date < week.as_of_date:
                raise ValueError("target_date must not precede as_of_date")
            if request.target_date == slots[request.slot_id].scheduled_date:
                raise ValueError("target_date must differ from scheduled_date")
        return self


class RescheduleAppliedChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot_id: Identifier
    original_scheduled_date: date
    new_scheduled_date: date
    session_type: SessionType
    reason: RescheduleReason


class ReschedulingSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_sessions: NonNegativeInt
    requested_changes: NonNegativeInt
    rescheduled_sessions: NonNegativeInt
    unchanged_sessions: NonNegativeInt


class PlannerReschedulingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rescheduler_version: Literal["planner-rescheduling-v1"] = PLANNER_RESCHEDULING_VERSION
    source_planner_version: Literal["program-planner-v1"]
    plan_week_start: date
    plan_week_end: date
    as_of_date: date
    updated_plan: ProgramPlan
    changes: list[RescheduleAppliedChange]
    summary: ReschedulingSummary
