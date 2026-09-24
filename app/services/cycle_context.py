from dataclasses import dataclass

from app.models.training_request import (
    CycleDiscomfort,
    CyclePhase,
    TrainingRecommendationRequest,
)
from app.models.training_response import Action, Intensity, ReasonCode, RecommendedSession


@dataclass(frozen=True)
class NormalizedCycleContext:
    available: bool = False
    phase: CyclePhase | None = None
    discomfort: CycleDiscomfort | None = None
    is_complete: bool = False
    requires_more_data: bool = False
    action: Action | None = None
    recommended_session: RecommendedSession | None = None
    intensity_ceiling: Intensity | None = None
    duration_ceiling: int | None = None
    reason_codes: tuple[ReasonCode, ...] = ()


def normalize_cycle_context(
    request: TrainingRecommendationRequest,
    *,
    moderate_duration_cap: int,
    recovery_duration_cap: int,
) -> NormalizedCycleContext:
    """
    Normalize optional cycle inputs into deterministic internal context.

    This module does not make the final training decision. It only converts
    optional request data into structured signals for the Training Rules
    pipeline to consume.
    """

    cycle = request.cycle_context
    if cycle is None:
        return NormalizedCycleContext()

    discomfort_was_provided = "discomfort" in cycle.model_fields_set
    if not discomfort_was_provided:
        return NormalizedCycleContext(
            available=True,
            phase=cycle.phase,
            is_complete=False,
            requires_more_data=True,
            reason_codes=(ReasonCode.CYCLE_CONTEXT_INCOMPLETE,),
        )

    normalized = NormalizedCycleContext(
        available=True,
        phase=cycle.phase,
        discomfort=cycle.discomfort,
        is_complete=True,
    )

    if cycle.discomfort == CycleDiscomfort.high:
        return NormalizedCycleContext(
            available=True,
            phase=cycle.phase,
            discomfort=cycle.discomfort,
            is_complete=True,
            action=Action.recovery,
            recommended_session=RecommendedSession.mobility,
            intensity_ceiling=Intensity.low,
            duration_ceiling=recovery_duration_cap,
            reason_codes=(ReasonCode.CYCLE_HIGH_DISCOMFORT,),
        )

    if cycle.discomfort == CycleDiscomfort.moderate:
        return NormalizedCycleContext(
            available=True,
            phase=cycle.phase,
            discomfort=cycle.discomfort,
            is_complete=True,
            intensity_ceiling=Intensity.moderate,
            duration_ceiling=moderate_duration_cap,
            reason_codes=(ReasonCode.CYCLE_MODERATE_DISCOMFORT,),
        )

    return normalized
