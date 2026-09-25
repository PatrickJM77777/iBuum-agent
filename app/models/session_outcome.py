"""Validated execution facts, independent of prescriptions and persistence."""

from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


SESSION_OUTCOME_VERSION = "session-outcome-v1"
NonNegativeInt = Annotated[int, Field(ge=0, strict=True)]
PositiveInt = Annotated[int, Field(ge=1, strict=True)]
Effort = Annotated[float, Field(ge=0, le=10, strict=True, allow_inf_nan=False)]


class SessionFeedback(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_rpe: Annotated[float, Field(ge=1, le=10, strict=True)] | None = None
    fatigue_after: Annotated[int, Field(ge=1, le=5, strict=True)] | None = None
    discomfort_after: Literal["none", "mild", "moderate", "high"] | None = None


class SetExecutionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    set_number: PositiveInt
    status: Literal["completed", "skipped"]
    reps: NonNegativeInt | None = None
    load_value: Annotated[float, Field(gt=0, le=1000, strict=True)] | None = None
    load_unit: Literal["kg", "lb"] | None = None
    duration_seconds: Annotated[int, Field(gt=0, le=36000, strict=True)] | None = None
    distance_meters: Annotated[float, Field(gt=0, strict=True, allow_inf_nan=False)] | None = None
    rir: Effort | None = None
    actual_rest_seconds: NonNegativeInt | None = None
    recorded_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_performance(self) -> Self:
        if (self.load_value is None) != (self.load_unit is None):
            raise ValueError("load_value and load_unit must be supplied together")
        metrics = (self.reps, self.load_value, self.load_unit, self.duration_seconds,
                   self.distance_meters, self.rir, self.actual_rest_seconds)
        if self.status == "skipped" and any(value is not None for value in metrics):
            raise ValueError("skipped sets cannot contain performance metrics")
        return self


class ExerciseExecutionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence: PositiveInt
    exercise_id: Annotated[str, Field(min_length=1, max_length=128)]
    source_status: Literal["pending", "in_progress", "completed", "skipped"]
    sets: list[SetExecutionInput]
    display_name: Annotated[str, Field(max_length=160)] | None = None
    movement_pattern: Annotated[str, Field(max_length=80)] | None = None
    planned_sets: PositiveInt | None = None
    planned_rep_min: NonNegativeInt | None = None
    planned_rep_max: NonNegativeInt | None = None
    planned_target_rir: Effort | None = None
    planned_rest_seconds: NonNegativeInt | None = None

    @model_validator(mode="after")
    def validate_plan_and_sets(self) -> Self:
        if (self.planned_rep_min is None) != (self.planned_rep_max is None):
            raise ValueError("planned rep bounds must be supplied together")
        if self.planned_rep_min is not None and self.planned_rep_min > self.planned_rep_max:
            raise ValueError("planned_rep_min must not exceed planned_rep_max")
        numbers = [entry.set_number for entry in self.sets]
        if len(numbers) != len(set(numbers)):
            raise ValueError("set_number must be unique within an exercise")
        return self


class SessionOutcomeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: Annotated[str, Field(min_length=1, max_length=128)]
    completion_state: Literal["completed", "interrupted"]
    exercises: list[ExerciseExecutionInput]
    plan_id: Annotated[str, Field(max_length=128)] | None = None
    source_action: Literal["train", "recovery"] | None = None
    session_type: Literal["upper_body", "lower_body", "full_body", "cardio", "mobility"] | None = None
    started_at: AwareDatetime | None = None
    ended_at: AwareDatetime | None = None
    actual_duration_seconds: NonNegativeInt | None = None
    feedback: SessionFeedback | None = None

    @model_validator(mode="after")
    def validate_session(self) -> Self:
        if self.started_at is not None and self.ended_at is not None:
            if self.ended_at < self.started_at:
                raise ValueError("ended_at must not precede started_at")
        sequences = [exercise.sequence for exercise in self.exercises]
        if len(sequences) != len(set(sequences)):
            raise ValueError("exercise sequence must be unique within a session")
        return self


class ExerciseOutcome(ExerciseExecutionInput):
    model_config = ConfigDict(extra="forbid")

    execution_status: Literal["completed", "partial", "skipped", "not_started"]
    completed_sets: NonNegativeInt
    skipped_sets: NonNegativeInt


class SessionOutcomeSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_exercises: NonNegativeInt
    completed_exercises: NonNegativeInt
    partial_exercises: NonNegativeInt
    skipped_exercises: NonNegativeInt
    not_started_exercises: NonNegativeInt
    completed_sets: NonNegativeInt
    skipped_sets: NonNegativeInt


class SessionOutcome(SessionOutcomeInput):
    model_config = ConfigDict(extra="forbid")

    outcome_version: Literal["session-outcome-v1"] = SESSION_OUTCOME_VERSION
    exercises: list[ExerciseOutcome]
    summary: SessionOutcomeSummary
