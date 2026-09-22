"""
Deterministic training rules engine.

This module contains ALL business logic for iBuum Agent 0.1. The API route
layer must stay free of business rules and only call `evaluate()`.

The rules are intentionally simple and conservative. They do not make
medical decisions and do not assume menstruation automatically reduces
training capacity — cycle data only modifies the outcome when it is
explicitly relevant (high discomfort).
"""

from app.core.config import get_settings
from app.models.training_request import (
    CycleDiscomfort,
    CyclePhase,
    SessionType,
    TrainingLevel,
    TrainingRecommendationRequest,
)
from app.models.training_response import (
    Action,
    Intensity,
    ReasonCode,
    RecommendedSession,
    TrainingRecommendationResponse,
)

DEFAULT_DURATION_MINUTES = 45
REDUCED_DURATION_MINUTES = 30
RECOVERY_DURATION_MINUTES = 20

# Intensity ranking used to "cap" intensity without ever raising it.
_INTENSITY_ORDER = [Intensity.low, Intensity.moderate, Intensity.high]


def _cap_intensity(intensity: Intensity, max_intensity: Intensity) -> Intensity:
    """Return the lower of the two intensities (never allow an increase)."""
    if _INTENSITY_ORDER.index(intensity) > _INTENSITY_ORDER.index(max_intensity):
        return max_intensity
    return intensity


def _default_session(last_session_type: SessionType | None) -> RecommendedSession:
    """
    Pick a sensible baseline session by lightly rotating away from the
    muscle group trained most recently. This is a simple heuristic, not an
    intelligent coaching system.
    """
    if last_session_type == SessionType.upper_body:
        return RecommendedSession.lower_body
    if last_session_type == SessionType.lower_body:
        return RecommendedSession.upper_body
    return RecommendedSession.full_body


def evaluate(
    request: TrainingRecommendationRequest,
) -> TrainingRecommendationResponse:
    """Apply the deterministic rules and return a structured recommendation."""

    reason_codes: list[ReasonCode] = []
    agent_version = get_settings().agent_version

    action = Action.train
    recommended_session = _default_session(request.last_session_type)
    intensity = Intensity.moderate
    duration_minutes = DEFAULT_DURATION_MINUTES
    needs_more_data = False

    # --- RULE 1: fatigue_level >= 5 -> recovery/rest -----------------------
    if request.fatigue_level >= 5:
        reason_codes.append(ReasonCode.HIGH_FATIGUE)
        return TrainingRecommendationResponse(
            action=Action.rest,
            recommended_session=RecommendedSession.rest,
            intensity=Intensity.not_applicable,
            duration_minutes=0,
            reason_codes=reason_codes,
            needs_more_data=False,
            agent_version=agent_version,
        )

    # --- RULE 2: fatigue_level == 4 -> reduce intensity ---------------------
    if request.fatigue_level == 4:
        intensity = _cap_intensity(intensity, Intensity.low)
        duration_minutes = REDUCED_DURATION_MINUTES
        reason_codes.append(ReasonCode.MODERATE_FATIGUE)
    elif request.fatigue_level == 3:
        reason_codes.append(ReasonCode.MODERATE_FATIGUE)
    else:
        reason_codes.append(ReasonCode.LOW_FATIGUE)

    # --- RULE 3: avoid repeating a demanding session too soon --------------
    recent_conflict = False
    if (
        request.last_session_type == SessionType.lower_body
        and request.hours_since_last_session is not None
        and request.hours_since_last_session < 24
    ):
        recent_conflict = True
        reason_codes.append(ReasonCode.RECENT_LOWER_BODY_SESSION)
        if recommended_session == RecommendedSession.lower_body:
            recommended_session = RecommendedSession.upper_body

    if (
        request.last_session_type == SessionType.upper_body
        and request.hours_since_last_session is not None
        and request.hours_since_last_session < 24
    ):
        recent_conflict = True
        reason_codes.append(ReasonCode.RECENT_UPPER_BODY_SESSION)
        if recommended_session == RecommendedSession.upper_body:
            recommended_session = RecommendedSession.lower_body

    if request.hours_since_last_session is None and request.last_session_type in (
        SessionType.upper_body,
        SessionType.lower_body,
    ):
        # We know a demanding session happened, but not when, so we cannot
        # confidently confirm the recovery window. Stay conservative.
        needs_more_data = True
        reason_codes.append(ReasonCode.INSUFFICIENT_DATA)
    elif not recent_conflict:
        reason_codes.append(ReasonCode.RECOVERY_WINDOW_OK)

    # --- RULE 4: beginners never get "high" intensity -----------------------
    if request.training_level == TrainingLevel.beginner:
        capped = _cap_intensity(intensity, Intensity.moderate)
        if capped != intensity:
            reason_codes.append(ReasonCode.BEGINNER_INTENSITY_LIMIT)
        intensity = capped

    # --- RULE 5: high menstrual discomfort may reduce intensity ------------
    cycle = request.cycle_context
    if (
        cycle is not None
        and cycle.phase == CyclePhase.menstruation
        and cycle.discomfort == CycleDiscomfort.high
    ):
        reason_codes.append(ReasonCode.CYCLE_HIGH_DISCOMFORT)
        action = Action.recovery
        recommended_session = RecommendedSession.mobility
        intensity = Intensity.low
        duration_minutes = min(duration_minutes, RECOVERY_DURATION_MINUTES)

    return TrainingRecommendationResponse(
        action=action,
        recommended_session=recommended_session,
        intensity=intensity,
        duration_minutes=duration_minutes,
        reason_codes=reason_codes,
        needs_more_data=needs_more_data,
        agent_version=agent_version,
    )
