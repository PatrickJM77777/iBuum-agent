"""Exercise Selector V1: stable compatibility filtering, internal only."""

from app.models.exercise import MovementPattern
from app.models.exercise_selection import (
    ExerciseSelectionStatus,
    ExerciseSelectorContext,
    SelectedExerciseSlot,
    SelectedWorkoutPlan,
    SelectionReasonCode as Reason,
    UnresolvedExerciseSlot,
)
from app.models.workout import WorkoutPlan, WorkoutPlanStatus
from app.services.exercise_library import list_exercises_by_movement_pattern

EXERCISE_SELECTOR_VERSION = "exercise-selector-v1"


def select_exercises(
    plan: WorkoutPlan, context: ExerciseSelectorContext | None = None
) -> SelectedWorkoutPlan:
    """Preserve prescriptions; never relax compatibility to fill a slot.

    Input list order is authoritative (sequence values are preserved, not sorted).
    Reasons identify the first filter that exhausted candidates. Previously unused
    IDs are preferred, then the first remaining entry in library order is chosen.
    """
    result = SelectedWorkoutPlan(
        source_plan=plan.model_copy(deep=True),
        selector_status=ExerciseSelectionStatus.complete,
        selector_version=EXERCISE_SELECTOR_VERSION,
    )
    if plan.status != WorkoutPlanStatus.generated:
        result.selector_status = ExerciseSelectionStatus(plan.status.value)
        # Retain even unexpected slots on a blocked upstream plan explicitly.
        result.unresolved_slots = [
            UnresolvedExerciseSlot(
                source_slot=slot.model_copy(deep=True),
                reason_codes=[Reason.UPSTREAM_SELECTION_BLOCKED],
            )
            for slot in plan.movement_slots
        ]
        return result

    context = context or ExerciseSelectorContext()
    used_ids: set[str] = set()
    for slot in plan.movement_slots:
        failure = None
        candidates = []
        try:
            pattern = MovementPattern(slot.movement_pattern)
        except ValueError:
            failure = Reason.INVALID_MOVEMENT_PATTERN
        else:
            if (
                context.training_level is None
                or context.training_location is None
                or context.available_equipment is None
            ):
                failure = Reason.SELECTION_CONTEXT_INCOMPLETE
            else:
                candidates = list_exercises_by_movement_pattern(pattern)
                if not candidates:
                    failure = Reason.NO_COMPATIBLE_EXERCISE
                else:
                    candidates = [e for e in candidates if context.training_level in e.training_levels]
                    if not candidates:
                        failure = Reason.TRAINING_LEVEL_NOT_COMPATIBLE
                    else:
                        candidates = [e for e in candidates if context.training_location in e.suitable_locations]
                        if not candidates:
                            failure = Reason.LOCATION_NOT_COMPATIBLE
                        else:
                            candidates = [e for e in candidates if set(e.equipment) <= context.available_equipment]
                            if not candidates:
                                failure = Reason.EQUIPMENT_NOT_AVAILABLE

        if failure is not None:
            result.unresolved_slots.append(UnresolvedExerciseSlot(
                source_slot=slot.model_copy(deep=True), reason_codes=[failure]
            ))
            continue

        unused = [e for e in candidates if e.id not in used_ids]
        reasons = [Reason.STABLE_CATALOG_ORDER]
        if not unused:
            reasons.append(Reason.REUSED_AFTER_ALTERNATIVES_EXHAUSTED)
        elif len(unused) != len(candidates):
            reasons.append(Reason.DUPLICATE_AVOIDED)
        chosen = (unused or candidates)[0]
        used_ids.add(chosen.id)
        result.selected_slots.append(SelectedExerciseSlot(
            source_slot=slot.model_copy(deep=True),
            exercise_id=chosen.id,
            display_name=chosen.display_name,
            reason_codes=reasons,
        ))

    if result.unresolved_slots:
        result.selector_status = ExerciseSelectionStatus.incomplete
    return result
