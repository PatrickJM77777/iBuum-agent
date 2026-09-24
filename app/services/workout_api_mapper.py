"""Pure boundary transformations; no training or exercise selection decisions."""

from app.models.workout import MovementSlot
from app.models.workout_api import (
    WorkoutApiPayload, WorkoutApiResponse, WorkoutEnvironmentApiRequest,
    WorkoutExerciseApiResponse, WorkoutUnresolvedSlotApiResponse,
    WorkoutVersionsApiResponse,
)
from app.models.workout_orchestration import (
    WorkoutEnvironmentContext, WorkoutOrchestrationResult,
)


def to_internal_environment(
    environment: WorkoutEnvironmentApiRequest | None,
) -> WorkoutEnvironmentContext | None:
    if environment is None:
        return None
    return WorkoutEnvironmentContext(
        available_equipment=(None if environment.available_equipment is None
                             else frozenset(environment.available_equipment)),
        training_location=environment.training_location,
    )


def _prescription(slot: MovementSlot) -> dict:
    return dict(
        sequence=slot.sequence, movement_pattern=slot.movement_pattern,
        target_area=slot.target_area, sets=slot.sets,
        rep_min=slot.rep_min, rep_max=slot.rep_max,
        work_seconds=slot.work_seconds, rest_seconds=slot.rest_seconds,
        effort_target=slot.effort_target, notes=list(slot.notes),
    )


def to_workout_api_response(result: WorkoutOrchestrationResult) -> WorkoutApiResponse:
    selected = result.selected_workout
    plan = selected.source_plan
    return WorkoutApiResponse(
        recommendation=result.recommendation.model_copy(deep=True),
        workout=WorkoutApiPayload(
            plan_status=plan.status.value,
            selector_status=selected.selector_status.value,
            action=plan.action, session_type=plan.session_type,
            intensity=plan.intensity, duration_minutes=plan.target_duration_minutes,
            exercises=[WorkoutExerciseApiResponse(
                **_prescription(slot.source_slot), exercise_id=slot.exercise_id,
                display_name=slot.display_name,
                selection_reason_codes=[reason.value for reason in slot.reason_codes],
            ) for slot in selected.selected_slots],
            unresolved_slots=[WorkoutUnresolvedSlotApiResponse(
                **_prescription(slot.source_slot),
                reason_codes=[reason.value for reason in slot.reason_codes],
            ) for slot in selected.unresolved_slots],
            generator_reason_codes=list(plan.generator_reason_codes),
        ),
        versions=WorkoutVersionsApiResponse(
            agent_version=result.recommendation.agent_version,
            generator_version=plan.generator_version,
            selector_version=selected.selector_version,
            orchestrator_version=result.orchestrator_version,
        ),
    )
