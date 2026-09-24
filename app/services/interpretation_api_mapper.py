"""Defensive public mapping of approved workout and interpretation values."""

from app.models.interpretation import InterpretationResult
from app.models.interpretation_api import (
    InterpretationApiPayload, InterpretationApiResponse,
    InterpretationVersionsApiResponse,
)
from app.models.workout_api import WorkoutApiResponse


def to_interpretation_api_response(
    workout: WorkoutApiResponse, interpretation: InterpretationResult,
) -> InterpretationApiResponse:
    return InterpretationApiResponse(
        recommendation=workout.recommendation.model_copy(deep=True),
        workout=workout.workout.model_copy(deep=True),
        interpretation=InterpretationApiPayload(
            presenter=interpretation.presenter.value,
            tone=interpretation.tone.value,
            action=interpretation.action,
            session=interpretation.session,
            intensity=interpretation.intensity,
            duration_minutes=interpretation.duration_minutes,
            needs_more_data=interpretation.needs_more_data,
            title=interpretation.title,
            summary=interpretation.summary,
            reasons=list(interpretation.reasons),
            today_plan=interpretation.today_plan,
            avatar_message=interpretation.avatar_message,
            missing_data_message=interpretation.missing_data_message,
            environment_message=interpretation.environment_message,
            cycle_insight=interpretation.cycle_insight,
            reason_codes=list(interpretation.reason_codes),
            interpretation_version=interpretation.interpretation_version,
        ),
        versions=InterpretationVersionsApiResponse(
            agent_version=workout.versions.agent_version,
            generator_version=workout.versions.generator_version,
            selector_version=workout.versions.selector_version,
            orchestrator_version=workout.versions.orchestrator_version,
            interpretation_version=interpretation.interpretation_version,
        ),
    )
