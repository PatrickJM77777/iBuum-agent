"""Current explicitly declared activities, independent of training decisions."""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SPORT_ACTIVITY_PROFILE_VERSION = "sport-activity-profile-v1"
NonNegativeInt = Annotated[int, Field(strict=True, ge=0)]


class SportActivityEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activity_type: Literal[
        "strength_training", "functional_training", "calisthenics", "cardio_fitness",
        "running", "walking", "cycling", "swimming", "football", "basketball",
        "volleyball", "tennis", "padel", "yoga", "pilates", "dance", "hiking",
        "climbing", "rowing", "combat_sport", "mobility_training", "team_sport", "other",
    ]
    custom_activity_name: Annotated[str, Field(strict=True, min_length=1, max_length=80)] | None = None
    days_per_week: Annotated[int, Field(strict=True, ge=1, le=7)] | None = None
    experience_level: Literal["beginner", "intermediate", "advanced"] | None = None
    typical_duration_minutes: Annotated[int, Field(strict=True, ge=1, le=720)] | None = None
    practice_environment: Literal[
        "home", "gym", "outdoors", "pool", "court_or_field", "studio",
        "sports_facility", "mixed", "other",
    ] | None = None

    @model_validator(mode="after")
    def validate_custom_name(self) -> Self:
        name = self.custom_activity_name
        if self.activity_type == "other":
            if name is None or not name.strip() or name != name.strip():
                raise ValueError("other requires a nonblank custom name without surrounding whitespace")
        elif name is not None:
            raise ValueError("known activities cannot have a custom_activity_name")
        return self


class SportActivityProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activities: list[SportActivityEntry]

    @field_validator("activities", mode="before")
    @classmethod
    def require_canonical_entries(cls, value):
        if not isinstance(value, list) or any(
            not isinstance(entry, SportActivityEntry) for entry in value
        ):
            raise ValueError("activities must be a list of canonical SportActivityEntry instances")
        return value

    @field_validator("activities")
    @classmethod
    def reject_duplicates(cls, activities):
        identities = set()
        for entry in activities:
            identity = (entry.activity_type, entry.custom_activity_name.casefold()
                        if entry.activity_type == "other" else None)
            if identity in identities:
                raise ValueError("duplicate activity identity")
            identities.add(identity)
        return activities


class SportActivityProfileSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_activities: NonNegativeInt
    known_activities: NonNegativeInt
    custom_activities: NonNegativeInt
    activities_with_days_per_week: NonNegativeInt
    activities_with_experience_level: NonNegativeInt
    activities_with_typical_duration: NonNegativeInt
    activities_with_practice_environment: NonNegativeInt
    has_any_activities: Annotated[bool, Field(strict=True)]

    @model_validator(mode="after")
    def validate_inventory(self) -> Self:
        if self.known_activities + self.custom_activities != self.total_activities:
            raise ValueError("known and custom counts must sum to total_activities")
        if any(count > self.total_activities for count in (
            self.activities_with_days_per_week, self.activities_with_experience_level,
            self.activities_with_typical_duration, self.activities_with_practice_environment,
        )):
            raise ValueError("optional-field counts cannot exceed total_activities")
        if self.has_any_activities != (self.total_activities > 0):
            raise ValueError("has_any_activities must match total_activities > 0")
        return self


class SportActivityProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_version: Literal["sport-activity-profile-v1"]
    activities: list[SportActivityEntry]
    summary: SportActivityProfileSummary
