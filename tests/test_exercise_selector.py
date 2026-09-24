import ast
import inspect
from pathlib import Path

import pytest

from app.models.exercise import ExerciseEquipment, MovementPattern, SuitableLocation
from app.models.exercise_selection import (
    ExerciseSelectionStatus as Status,
    ExerciseSelectorContext,
    SelectionReasonCode as Reason,
)
from app.models.training_request import TrainingLevel, TrainingRecommendationRequest
from app.models.training_response import TrainingRecommendationResponse
from app.models.workout import MovementSlot, WorkoutPlan, WorkoutPlanStatus
from app.services import exercise_selector
from app.services.exercise_library import (
    get_exercise_by_id,
    list_exercises,
    list_exercises_by_movement_pattern,
)
from app.services.exercise_selector import select_exercises
from app.services.workout_generator import generate_workout_plan


def context(**overrides):
    values = dict(training_level="beginner", training_location="gym",
                  available_equipment=list(ExerciseEquipment))
    values.update(overrides)
    return ExerciseSelectorContext(**values)


def plan(*patterns):
    return WorkoutPlan(
        status="generated", action="train", session_type="full_body",
        intensity="moderate", target_duration_minutes=45,
        generator_version="workout-generator-v1", generator_reason_codes=["SOURCE"],
        movement_slots=[MovementSlot(
            movement_pattern=p, target_area="original", sequence=10-i,
            sets=3, rep_min=8, rep_max=12, work_seconds=40, rest_seconds=75,
            effort_target="RPE 6-7", notes=["Keep this note"],
        ) for i, p in enumerate(patterns)],
    )


def generated(session, level="intermediate", action="train"):
    request = TrainingRecommendationRequest(
        age=30, sex="male", height_cm=178, weight_kg=80, goal="general_fitness",
        training_level=level, training_days_per_week=4, fatigue_level=2,
    )
    recommendation = TrainingRecommendationResponse(
        action=action, recommended_session=session, intensity="moderate",
        duration_minutes=45, reason_codes=[], needs_more_data=False, agent_version="0.1",
    )
    return generate_workout_plan(request, recommendation)


@pytest.mark.parametrize("pattern", list(MovementPattern))
@pytest.mark.parametrize("level", list(TrainingLevel))
def test_patterns_and_levels_select_first_compatible_catalog_entry(pattern, level):
    result = select_exercises(plan(pattern.value), context(training_level=level))
    expected = [e for e in list_exercises_by_movement_pattern(pattern)
                if level in e.training_levels and SuitableLocation.gym in e.suitable_locations]
    if not expected:
        assert result.selector_status == Status.incomplete
        assert not result.selected_slots
        assert result.unresolved_slots[0].reason_codes == [Reason.LOCATION_NOT_COMPATIBLE]
        return
    assert result.selector_status == Status.complete
    assert result.selected_slots[0].exercise_id == expected[0].id
    assert get_exercise_by_id(result.selected_slots[0].exercise_id).movement_pattern == pattern


@pytest.mark.parametrize("session", ["upper_body", "lower_body", "full_body", "cardio", "mobility"])
def test_real_generator_workouts_resolve_without_changing_prescriptions(session):
    source = generated(session)
    before = source.model_dump()
    result = select_exercises(source, context(training_level="intermediate"))
    assert result.selector_status == Status.complete
    assert not result.unresolved_slots
    assert len(result.selected_slots) == len(source.movement_slots)
    assert [s.source_slot.model_dump() for s in result.selected_slots] == before["movement_slots"]
    assert result.source_plan.model_dump() == before
    assert source.model_dump() == before


@pytest.mark.parametrize("location", list(SuitableLocation))
@pytest.mark.parametrize("equipment", [[], [ExerciseEquipment.bodyweight], [ExerciseEquipment.dumbbell]])
def test_equipment_and_location_are_never_relaxed(location, equipment):
    source = plan(*(p.value for p in MovementPattern))
    result = select_exercises(source, context(training_location=location, available_equipment=equipment))
    assert len(result.selected_slots) + len(result.unresolved_slots) == len(source.movement_slots)
    for selected in result.selected_slots:
        exercise = get_exercise_by_id(selected.exercise_id)
        assert set(exercise.equipment) <= set(equipment)
        assert location in exercise.suitable_locations
        assert TrainingLevel.beginner in exercise.training_levels
    for unresolved in result.unresolved_slots:
        assert not [e for e in list_exercises_by_movement_pattern(unresolved.source_slot.movement_pattern)
                    if TrainingLevel.beginner in e.training_levels and location in e.suitable_locations
                    and set(e.equipment) <= set(equipment)]


def test_duplicate_avoidance_then_explicit_reuse_in_catalog_order():
    candidates = [e for e in list_exercises_by_movement_pattern("horizontal_push")
                  if TrainingLevel.beginner in e.training_levels and SuitableLocation.home in e.suitable_locations]
    result = select_exercises(plan(*(["horizontal_push"] * (len(candidates)+1))), context(training_location="home"))
    assert [s.exercise_id for s in result.selected_slots] == [e.id for e in candidates] + [candidates[0].id]
    assert Reason.DUPLICATE_AVOIDED in result.selected_slots[1].reason_codes
    assert Reason.REUSED_AFTER_ALTERNATIVES_EXHAUSTED in result.selected_slots[-1].reason_codes


def test_determinism_including_unresolved_slots_and_reasons():
    source = plan("horizontal_push", "horizontal_push", "vertical_pull", "unknown")
    ctx = context(available_equipment=["bodyweight"], training_location="home")
    assert select_exercises(source, ctx).model_dump_json() == select_exercises(source, ctx).model_dump_json()


@pytest.mark.parametrize("missing", ["training_level", "training_location", "available_equipment"])
def test_missing_context_fields_are_explicit(missing):
    result = select_exercises(plan("core"), context(**{missing: None}))
    assert result.selector_status == Status.incomplete
    assert not result.selected_slots
    assert result.unresolved_slots[0].reason_codes == [Reason.SELECTION_CONTEXT_INCOMPLETE]


def test_absent_context_is_explicit():
    result = select_exercises(plan("core"))
    assert result.unresolved_slots[0].reason_codes == [Reason.SELECTION_CONTEXT_INCOMPLETE]


def test_empty_equipment_does_not_imply_bodyweight():
    result = select_exercises(plan("core"), context(available_equipment=[]))
    assert result.selector_status == Status.incomplete
    assert result.source_plan.status == "generated"
    assert not result.selected_slots
    assert result.unresolved_slots[0].reason_codes == [Reason.EQUIPMENT_NOT_AVAILABLE]


def test_unknown_pattern_is_retained_without_fallback():
    source = plan("unknown", "core")
    result = select_exercises(source, context())
    assert result.selector_status == Status.incomplete
    assert result.unresolved_slots[0].source_slot == source.movement_slots[0]
    assert result.unresolved_slots[0].reason_codes == [Reason.INVALID_MOVEMENT_PATTERN]
    assert len(result.selected_slots) == 1


@pytest.mark.parametrize("stage,reason", [
    ("empty", Reason.NO_COMPATIBLE_EXERCISE),
    ("level", Reason.TRAINING_LEVEL_NOT_COMPATIBLE),
    ("location", Reason.LOCATION_NOT_COMPATIBLE),
    ("equipment", Reason.EQUIPMENT_NOT_AVAILABLE),
])
def test_first_exhausted_filter_is_reported(monkeypatch, stage, reason):
    exercise = list_exercises_by_movement_pattern("horizontal_push")[0].model_copy(
        update={"suitable_locations": (SuitableLocation.gym,)}
    )
    changes = {
        "level": {"training_levels": (TrainingLevel.advanced,)},
        "location": {"suitable_locations": (SuitableLocation.home,)},
        "equipment": {"equipment": (ExerciseEquipment.barbell, ExerciseEquipment.dumbbell)},
    }
    candidates = [] if stage == "empty" else [exercise.model_copy(update=changes[stage])]
    monkeypatch.setattr(exercise_selector, "list_exercises_by_movement_pattern", lambda _: candidates)
    result = select_exercises(plan("horizontal_push"), context(available_equipment=["bodyweight", "barbell"]))
    assert not result.selected_slots
    assert result.unresolved_slots[0].reason_codes == [reason]


@pytest.mark.parametrize("status", ["no_workout", "more_data_required"])
@pytest.mark.parametrize("patterns", [(), ("core",)])
def test_upstream_blocked_status_never_queries_library(monkeypatch, status, patterns):
    source = plan(*patterns)
    source.status = WorkoutPlanStatus(status)
    def forbidden(_):
        pytest.fail("Blocked plans must not query the library")
    monkeypatch.setattr(exercise_selector, "list_exercises_by_movement_pattern", forbidden)
    result = select_exercises(source)
    assert result.selector_status.value == status
    assert result.source_plan == source
    assert not result.selected_slots
    assert len(result.unresolved_slots) == len(patterns)


def test_real_rest_and_more_data_generator_outputs():
    for action, session, status in [("rest", "rest", Status.no_workout),
                                    ("request_more_data", "full_body", Status.more_data_required)]:
        source = generated(session, action=action)
        result = select_exercises(source)
        assert result.selector_status == status
        assert result.source_plan == source
        assert not result.selected_slots


def test_beginner_horizontal_push_with_compatible_home_context():
    result = select_exercises(plan("horizontal_push"), context(
        training_location="home", available_equipment=["bodyweight"]
    ))
    assert result.selector_status == Status.complete
    exercise = get_exercise_by_id(result.selected_slots[0].exercise_id)
    assert exercise.movement_pattern == MovementPattern.horizontal_push
    assert TrainingLevel.beginner in exercise.training_levels


def test_beginner_horizontal_push_resolves_in_gym_with_bodyweight():
    result = select_exercises(plan("horizontal_push"), context(
        training_level="beginner", training_location="gym",
        available_equipment=["bodyweight"],
    ))
    assert result.selector_status == Status.complete
    assert not result.unresolved_slots
    assert len(result.selected_slots) == 1
    exercise = get_exercise_by_id(result.selected_slots[0].exercise_id)
    assert exercise.movement_pattern == MovementPattern.horizontal_push
    assert TrainingLevel.beginner in exercise.training_levels
    assert SuitableLocation.gym in exercise.suitable_locations
    assert set(exercise.equipment) <= {ExerciseEquipment.bodyweight}


@pytest.mark.parametrize("session", ["upper_body", "full_body"])
def test_real_beginner_gym_workout_with_horizontal_push_is_complete(session):
    source = generated(session, level="beginner")
    before = source.model_dump()
    assert any(s.movement_pattern == "horizontal_push" for s in source.movement_slots)
    result = select_exercises(source, context(
        training_level="beginner", training_location="gym",
        available_equipment=list(ExerciseEquipment),
    ))
    assert result.selector_status == Status.complete
    assert not result.unresolved_slots
    assert len(result.selected_slots) == len(source.movement_slots)
    assert [s.source_slot.model_dump() for s in result.selected_slots] == before["movement_slots"]
    assert source.model_dump() == result.source_plan.model_dump() == before
    for selected in result.selected_slots:
        exercise = get_exercise_by_id(selected.exercise_id)
        assert exercise.movement_pattern.value == selected.source_slot.movement_pattern
        assert TrainingLevel.beginner in exercise.training_levels
        assert SuitableLocation.gym in exercise.suitable_locations


def test_recovery_preserves_requested_mobility_patterns():
    source = generated("mobility", action="recovery")
    result = select_exercises(source, context(available_equipment=["bodyweight"]))
    assert result.selector_status == Status.complete
    assert result.source_plan.action == "recovery"
    for selected, original in zip(result.selected_slots, source.movement_slots, strict=True):
        assert get_exercise_by_id(selected.exercise_id).movement_pattern.value == original.movement_pattern
        assert selected.source_slot == original


def test_result_mutation_cannot_modify_upstream_or_catalog():
    source = plan("core")
    before = source.model_dump()
    catalog_before = [e.model_dump() for e in list_exercises()]
    result = select_exercises(source, context())
    result.source_plan.movement_slots[0].notes.append("changed")
    result.selected_slots[0].source_slot.sets = 999
    result.selected_slots[0].source_slot.notes.append("changed")
    assert source.model_dump() == before
    assert [e.model_dump() for e in list_exercises()] == catalog_before


def test_selector_architecture_has_only_compatibility_dependencies():
    tree = ast.parse(inspect.getsource(exercise_selector))
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert imports == {
        "app.models.exercise", "app.models.exercise_selection", "app.models.workout",
        "app.services.exercise_library",
    }
    assert not any(isinstance(node, ast.Import) for node in ast.walk(tree))
    # No embedded definitions, prescription construction, clocks, randomness,
    # medical services, I/O, or API decorators can enter the service unnoticed.
    calls = {node.func.id for node in ast.walk(tree)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert calls <= {
        "SelectedWorkoutPlan", "ExerciseSelectionStatus", "UnresolvedExerciseSlot",
        "ExerciseSelectorContext", "set", "MovementPattern",
        "list_exercises_by_movement_pattern", "len", "SelectedExerciseSlot",
    }
    assert not any(isinstance(node, ast.FunctionDef) and node.decorator_list for node in ast.walk(tree))


def test_public_api_does_not_import_selector_or_expose_context():
    from app.models.training_response import TrainingRecommendationResponse
    assert set(TrainingRecommendationResponse.model_fields) == {
        "action", "recommended_session", "intensity", "duration_minutes", "reason_codes",
        "needs_more_data", "agent_version",
    }
    assert {"available_equipment", "training_location"}.isdisjoint(TrainingRecommendationRequest.model_fields)
    root = Path(__file__).resolve().parents[1] / "app"
    for path in root.rglob("*.py"):
        # The internal orchestrator is the only approved selector consumer.
        if path.relative_to(root).as_posix() in {
            "services/exercise_selector.py", "models/exercise_selection.py",
            "services/workout_orchestrator.py", "models/workout_orchestration.py",
        }:
            continue
        assert "exercise_selector" not in path.read_text(encoding="utf-8")
        assert "exercise_selection" not in path.read_text(encoding="utf-8")
        # API adapter and interpretation may consume approved orchestration
        # contracts, never selection directly.
        if path.relative_to(root).as_posix() in {
            "api/routes/workout.py", "services/workout_api_mapper.py",
            "services/interpretation_core.py", "services/kai_presenter.py",
            "services/kaia_presenter.py",
        }:
            continue
        assert "workout_orchestrator" not in path.read_text(encoding="utf-8")
        assert "workout_orchestration" not in path.read_text(encoding="utf-8")
