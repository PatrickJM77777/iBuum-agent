"""Contracts for observed personal associations, without training decisions."""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.cycle_training_history import CyclePhase, CycleTrainingHistory
from app.models.session_outcome import NonNegativeInt


CYCLE_PATTERN_ANALYZER_VERSION = "cycle-pattern-analyzer-v1"
MIN_PHASE_METRIC_SAMPLES = 4
MIN_COMPARATOR_METRIC_SAMPLES = 8
RPE_MEAN_DIFFERENCE_THRESHOLD = 1.5
FATIGUE_MEAN_DIFFERENCE_THRESHOLD = 1.0
POST_DISCOMFORT_RATIO_DIFFERENCE_THRESHOLD = 0.30

KnownPhase = Literal["menstruation", "follicular", "ovulation", "luteal"]
SessionType = Literal["upper_body", "lower_body", "full_body", "cardio", "mobility"]
Metric = Literal["session_rpe", "fatigue_after", "post_session_discomfort"]
FiniteFloat = Annotated[float, Field(strict=True, allow_inf_nan=False)]
Ratio = Annotated[float, Field(strict=True, allow_inf_nan=False, ge=0, le=1)]
PHASES = ("menstruation", "follicular", "ovulation", "luteal", "unknown")
SESSION_TYPES = ("upper_body", "lower_body", "full_body", "cardio", "mobility")
METRICS = ("session_rpe", "fatigue_after", "post_session_discomfort")


class CyclePatternAnalyzerInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cycle_history: CycleTrainingHistory

    @field_validator("cycle_history", mode="before")
    @classmethod
    def require_canonical_history(cls, value):
        if not isinstance(value, CycleTrainingHistory):
            raise ValueError("cycle_history must be a canonical CycleTrainingHistory object")
        return value


class CyclePhaseEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phase: CyclePhase
    observed_sessions: NonNegativeInt
    completed_sessions: NonNegativeInt
    interrupted_sessions: NonNegativeInt
    sessions_with_known_rpe: NonNegativeInt
    mean_session_rpe: Annotated[float, Field(strict=True, allow_inf_nan=False, ge=1, le=10)] | None
    sessions_with_known_fatigue: NonNegativeInt
    mean_fatigue_after: Annotated[float, Field(strict=True, allow_inf_nan=False, ge=1, le=5)] | None
    sessions_with_known_post_discomfort: NonNegativeInt
    moderate_high_post_discomfort_sessions: NonNegativeInt
    moderate_high_post_discomfort_ratio: Ratio | None
    sessions_with_known_cycle_discomfort: NonNegativeInt
    moderate_high_cycle_discomfort_sessions: NonNegativeInt
    moderate_high_cycle_discomfort_ratio: Ratio | None


class CycleObservedPattern(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phase: KnownPhase
    session_type: SessionType
    metric: Metric
    direction: Literal["higher", "lower"]
    phase_sample_size: NonNegativeInt
    comparator_sample_size: NonNegativeInt
    phase_value: FiniteFloat
    comparator_value: FiniteFloat
    difference: FiniteFloat
    threshold: FiniteFloat


class CyclePatternAnalysisSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_sessions: NonNegativeInt
    sessions_with_cycle_context: NonNegativeInt
    sessions_without_cycle_context: NonNegativeInt
    known_phase_sessions: NonNegativeInt
    unknown_phase_sessions: NonNegativeInt
    sessions_eligible_for_pattern_analysis: NonNegativeInt
    detected_patterns: NonNegativeInt
    rpe_patterns: NonNegativeInt
    fatigue_patterns: NonNegativeInt
    post_session_discomfort_patterns: NonNegativeInt

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if self.total_sessions != self.sessions_with_cycle_context + self.sessions_without_cycle_context:
            raise ValueError("context counts must sum to total_sessions")
        if self.sessions_with_cycle_context != self.known_phase_sessions + self.unknown_phase_sessions:
            raise ValueError("phase counts must sum to sessions_with_cycle_context")
        if self.detected_patterns != self.rpe_patterns + self.fatigue_patterns + self.post_session_discomfort_patterns:
            raise ValueError("metric pattern counts must sum to detected_patterns")
        if self.sessions_eligible_for_pattern_analysis > self.known_phase_sessions:
            raise ValueError("eligible sessions cannot exceed known_phase_sessions")
        return self


class CyclePatternAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analyzer_version: Literal["cycle-pattern-analyzer-v1"] = CYCLE_PATTERN_ANALYZER_VERSION
    source_cycle_history_version: Literal["cycle-training-history-v1"]
    phase_evidence: list[CyclePhaseEvidence]
    patterns: list[CycleObservedPattern]
    summary: CyclePatternAnalysisSummary

    @field_validator("phase_evidence")
    @classmethod
    def require_canonical_phases(cls, value):
        if tuple(item.phase for item in value) != PHASES:
            raise ValueError("phase_evidence must contain exactly five phases in canonical order")
        return value
