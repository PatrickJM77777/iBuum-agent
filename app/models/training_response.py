"""
Output model for POST /api/v1/training/recommendation.

The response is intentionally structured and machine-readable. Base44 is
responsible for turning this into natural-language advice for the end user.
"""

from enum import Enum

from pydantic import BaseModel


class Action(str, Enum):
    train = "train"
    recovery = "recovery"
    rest = "rest"
    request_more_data = "request_more_data"


class Intensity(str, Enum):
    low = "low"
    moderate = "moderate"
    high = "high"
    not_applicable = "not_applicable"


class RecommendedSession(str, Enum):
    upper_body = "upper_body"
    lower_body = "lower_body"
    full_body = "full_body"
    cardio = "cardio"
    mobility = "mobility"
    rest = "rest"
    not_applicable = "not_applicable"


class ReasonCode(str, Enum):
    """Centralized, machine-readable reason codes."""

    HIGH_FATIGUE = "HIGH_FATIGUE"
    MODERATE_FATIGUE = "MODERATE_FATIGUE"
    LOW_FATIGUE = "LOW_FATIGUE"
    INSUFFICIENT_RECOVERY = "INSUFFICIENT_RECOVERY"
    RECENT_LOWER_BODY_SESSION = "RECENT_LOWER_BODY_SESSION"
    RECENT_UPPER_BODY_SESSION = "RECENT_UPPER_BODY_SESSION"
    BEGINNER_INTENSITY_LIMIT = "BEGINNER_INTENSITY_LIMIT"
    CYCLE_CONTEXT_INCOMPLETE = "CYCLE_CONTEXT_INCOMPLETE"
    CYCLE_MODERATE_DISCOMFORT = "CYCLE_MODERATE_DISCOMFORT"
    CYCLE_HIGH_DISCOMFORT = "CYCLE_HIGH_DISCOMFORT"
    RECOVERY_WINDOW_OK = "RECOVERY_WINDOW_OK"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    LOW_WEEKLY_FREQUENCY = "LOW_WEEKLY_FREQUENCY"
    HIGH_WEEKLY_FREQUENCY = "HIGH_WEEKLY_FREQUENCY"


class TrainingRecommendationResponse(BaseModel):
    action: Action
    recommended_session: RecommendedSession
    intensity: Intensity
    duration_minutes: int
    reason_codes: list[ReasonCode]
    needs_more_data: bool
    agent_version: str
