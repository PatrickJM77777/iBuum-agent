"""Immutable internal presentation contract; not an HTTP DTO."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.models.training_response import Action, Intensity, RecommendedSession


class Presenter(str, Enum):
    kai = "kai"
    kaia = "kaia"


class InterpretationTone(str, Enum):
    training = "training"
    recovery = "recovery"
    rest = "rest"
    incomplete = "incomplete"


class InterpretationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    presenter: Presenter
    tone: InterpretationTone
    action: Action
    session: RecommendedSession
    intensity: Intensity
    duration_minutes: int
    needs_more_data: bool
    title: str
    summary: str
    reasons: tuple[str, ...]
    today_plan: str
    avatar_message: str
    missing_data_message: str | None
    environment_message: str | None
    cycle_insight: str | None
    reason_codes: tuple[str, ...]
    generator_reason_codes: tuple[str, ...]
    selected_reason_codes: tuple[tuple[str, ...], ...]
    unresolved_reason_codes: tuple[tuple[str, ...], ...]
    interpretation_version: Literal["interpretation-core-v1"] = "interpretation-core-v1"
