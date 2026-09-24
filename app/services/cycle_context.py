from dataclasses import dataclass

from app.models.training_request import (
    CycleDiscomfort,
    CyclePhase,
    TrainingRecommendationRequest,
)
from app.models.training_response import ReasonCode


@dataclass(frozen=True)
class NormalizedCycleContext:
    available: bool = False
    phase: CyclePhase | None = None
    discomfort: CycleDiscomfort | None = None
    is_complete: bool = False
    requires_more_data: bool = False
    reason_codes: tuple[ReasonCode, ...] = ()


def _reason_codes_for_discomfort(
    discomfort: CycleDiscomfort,
) -> tuple[ReasonCode, ...]:
    if discomfort == CycleDiscomfort.moderate:
        return (ReasonCode.CYCLE_MODERATE_DISCOMFORT,)
    if discomfort == CycleDiscomfort.high:
        return (ReasonCode.CYCLE_HIGH_DISCOMFORT,)
    return ()


def normalize_cycle_context(request: TrainingRecommendationRequest) -> NormalizedCycleContext:
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
        reason_codes=_reason_codes_for_discomfort(cycle.discomfort),
    )

    return normalized
