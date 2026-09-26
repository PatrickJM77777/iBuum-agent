"""Caller-supplied external activity facts, separate from canonical execution."""

from datetime import date
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


EXTERNAL_ACTIVITY_HISTORY_VERSION = "external-activity-history-v1"
NonNegativeInt = Annotated[int, Field(strict=True, ge=0)]


class ExternalActivityFeedback(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activity_rpe: Annotated[float, Field(strict=True, ge=1, le=10, allow_inf_nan=False)] | None = None
    fatigue_after: Annotated[int, Field(strict=True, ge=1, le=5)] | None = None
    discomfort_after: Literal["none", "mild", "moderate", "high"] | None = None


class ExternalActivityRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activity_id: Annotated[str, Field(strict=True, min_length=1, max_length=128)]
    activity_type: Literal[
        "strength_training", "functional_training", "calisthenics", "cardio_fitness",
        "running", "walking", "cycling", "swimming", "football", "basketball",
        "volleyball", "tennis", "padel", "yoga", "pilates", "dance", "hiking",
        "climbing", "rowing", "combat_sport", "mobility_training", "team_sport", "other",
    ]
    custom_activity_name: Annotated[str, Field(strict=True, min_length=1, max_length=80)] | None = None
    activity_date: date
    completion_state: Literal["completed", "partial"] | None = None
    actual_duration_minutes: Annotated[int, Field(strict=True, ge=1, le=1440)] | None = None
    distance_meters: Annotated[float, Field(strict=True, gt=0, allow_inf_nan=False)] | None = None
    feedback: ExternalActivityFeedback | None = None

    @model_validator(mode="after")
    def validate_custom_name(self) -> Self:
        name = self.custom_activity_name
        if self.activity_type == "other":
            if name is None or not name.strip() or name != name.strip():
                raise ValueError("other requires a nonblank custom name without surrounding whitespace")
        elif name is not None:
            raise ValueError("known activities cannot have a custom_activity_name")
        return self


class ExternalActivityHistoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    records: list[ExternalActivityRecord]

    @field_validator("records", mode="before")
    @classmethod
    def require_canonical_records(cls, value):
        if not isinstance(value, list) or any(
            not isinstance(record, ExternalActivityRecord) for record in value
        ):
            raise ValueError("records must be a list of canonical ExternalActivityRecord instances")
        return value

    @field_validator("records")
    @classmethod
    def validate_identity_and_order(cls, records):
        identifiers = [record.activity_id for record in records]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("activity_id must be unique within history")
        if any(current.activity_date < previous.activity_date
               for previous, current in zip(records, records[1:])):
            raise ValueError("activity_date must be non-decreasing; records are never sorted")
        return records


class ExternalActivityHistorySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_records: NonNegativeInt
    known_activity_records: NonNegativeInt
    custom_activity_records: NonNegativeInt
    completed_records: NonNegativeInt
    partial_records: NonNegativeInt
    records_without_completion_state: NonNegativeInt
    records_with_known_duration: NonNegativeInt
    records_with_known_distance: NonNegativeInt
    records_with_feedback: NonNegativeInt
    has_any_records: Annotated[bool, Field(strict=True)]

    @model_validator(mode="after")
    def validate_inventory(self) -> Self:
        if self.known_activity_records + self.custom_activity_records != self.total_records:
            raise ValueError("known and custom counts must sum to total_records")
        if (self.completed_records + self.partial_records + self.records_without_completion_state
                != self.total_records):
            raise ValueError("completion counts must sum to total_records")
        if any(count > self.total_records for count in (
            self.records_with_known_duration, self.records_with_known_distance,
            self.records_with_feedback,
        )):
            raise ValueError("optional-field counts cannot exceed total_records")
        if self.has_any_records != (self.total_records > 0):
            raise ValueError("has_any_records must match total_records > 0")
        return self


class ExternalActivityHistory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    history_version: Literal["external-activity-history-v1"]
    records: list[ExternalActivityRecord]
    summary: ExternalActivityHistorySummary
