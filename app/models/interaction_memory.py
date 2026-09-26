"""Explicit presentation preferences, separate from sports-domain memory."""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


INTERACTION_MEMORY_VERSION = "interaction-memory-v1"
NonNegativeInt = Annotated[int, Field(strict=True, ge=0)]


class InteractionPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    explanation_length: Literal["short", "balanced", "detailed"] | None = None
    technical_depth: Literal["simple", "standard", "technical"] | None = None
    voice_preference: Literal["text", "either", "voice"] | None = None
    visual_preference: Literal["text", "balanced", "visual"] | None = None
    step_by_step_preference: Literal["summary", "adaptive", "step_by_step"] | None = None
    repetition_preference: Literal["minimal", "standard", "reinforced"] | None = None


class InteractionMemoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preferences: InteractionPreferences

    @field_validator("preferences", mode="before")
    @classmethod
    def require_canonical_preferences(cls, value):
        if not isinstance(value, InteractionPreferences):
            raise ValueError("preferences must be a canonical InteractionPreferences instance")
        return value


class InteractionMemorySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supported_preferences: NonNegativeInt
    specified_preferences: NonNegativeInt
    unspecified_preferences: NonNegativeInt
    has_any_preferences: Annotated[bool, Field(strict=True)]

    @model_validator(mode="after")
    def validate_inventory(self) -> Self:
        if self.supported_preferences != 6:
            raise ValueError("supported_preferences must equal 6")
        if self.specified_preferences > self.supported_preferences:
            raise ValueError("specified_preferences cannot exceed supported_preferences")
        if self.specified_preferences + self.unspecified_preferences != self.supported_preferences:
            raise ValueError("specified and unspecified counts must total supported_preferences")
        if self.has_any_preferences != (self.specified_preferences > 0):
            raise ValueError("has_any_preferences must match specified_preferences > 0")
        return self


class InteractionMemory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_version: Literal["interaction-memory-v1"]
    preferences: InteractionPreferences
    summary: InteractionMemorySummary
