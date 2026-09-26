"""Explicit daily self-report and separate canonical recent-training facts."""

from datetime import date
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.weekly_training_state import WeeklyTrainingState


RECOVERY_DAILY_STATE_VERSION = "recovery-daily-state-v1"
NonNegativeInt = Annotated[int, Field(strict=True, ge=0)]
ReportedLevel = Annotated[int, Field(strict=True, ge=1, le=5)]
DiscomfortLevel = Literal["none", "mild", "moderate", "high"]


class DailyRecoverySignals(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sleep_quality: ReportedLevel | None = None
    sleep_duration_minutes: Annotated[int, Field(strict=True, ge=0, le=1440)] | None = None
    energy_level: ReportedLevel | None = None
    fatigue_level: ReportedLevel | None = None
    soreness_level: DiscomfortLevel | None = None
    discomfort_level: DiscomfortLevel | None = None


class DailyRecoveryStateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_week_state: WeeklyTrainingState
    reported_signals: DailyRecoverySignals

    @field_validator("current_week_state", mode="before")
    @classmethod
    def require_canonical_week(cls, value):
        if not isinstance(value, WeeklyTrainingState):
            raise ValueError("current_week_state must be a canonical WeeklyTrainingState instance")
        return value

    @field_validator("reported_signals", mode="before")
    @classmethod
    def require_canonical_signals(cls, value):
        if not isinstance(value, DailyRecoverySignals):
            raise ValueError("reported_signals must be a DailyRecoverySignals instance")
        return value


class DailyRecoveryFlags(BaseModel):
    model_config = ConfigDict(extra="forbid")

    low_sleep_quality: bool
    low_energy: bool
    high_fatigue: bool
    moderate_high_soreness: bool
    moderate_high_discomfort: bool


class DailyRecentTrainingContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_week_start: date
    source_week_end: date
    source_as_of_date: date
    total_sessions: NonNegativeInt
    completed_sessions: NonNegativeInt
    interrupted_sessions: NonNegativeInt
    unplanned_sessions: NonNegativeInt
    known_duration_seconds: NonNegativeInt
    due_remaining_planned_sessions: NonNegativeInt
    high_fatigue_sessions: NonNegativeInt
    latest_known_fatigue_after: ReportedLevel | None
    moderate_high_discomfort_sessions: NonNegativeInt
    latest_known_discomfort_after: DiscomfortLevel | None
    latest_known_session_rpe: Annotated[float, Field(strict=True, ge=1, le=10)] | None


class DailyRecoverySignalSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supported_signals: NonNegativeInt
    reported_signals: NonNegativeInt
    missing_signals: NonNegativeInt
    flagged_signals: NonNegativeInt

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if self.supported_signals != 6:
            raise ValueError("supported_signals must equal 6")
        if self.reported_signals + self.missing_signals != self.supported_signals:
            raise ValueError("reported_signals + missing_signals must equal supported_signals")
        if self.flagged_signals > self.reported_signals:
            raise ValueError("flagged_signals must not exceed reported_signals")
        return self


class DailyRecoveryState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recovery_version: Literal["recovery-daily-state-v1"] = RECOVERY_DAILY_STATE_VERSION
    source_week_state_version: Literal["weekly-training-state-v1"]
    state_date: date
    reported_signals: DailyRecoverySignals
    recent_training_context: DailyRecentTrainingContext
    flags: DailyRecoveryFlags
    signal_summary: DailyRecoverySignalSummary
