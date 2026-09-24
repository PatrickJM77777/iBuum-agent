import inspect
import os
from collections import Counter

# Configure the test key before importing services that require settings.
os.environ.setdefault("IBUUM_API_KEY", "test-secret-key")

from app.models.exercise import (
    ExerciseDefinition,
    ExerciseEquipment,
    MovementPattern,
    SuitableLocation,
)
from app.models.training_request import TrainingLevel
from app.models.training_response import (
    Action,
    Intensity,
    ReasonCode,
    RecommendedSession,
    TrainingRecommendationResponse,
)
from app.services import exercise_library, training_engine
from app.services.workout_generator import (
    generate_workout_plan,
    get_supported_movement_patterns,
)
from tests.test_workout_generator import _recommendation, _request


def test_beginner_horizontal_push_bodyweight_options_include_gym():
    for exercise_id, levels in (
        ("push_up", (TrainingLevel.beginner, TrainingLevel.intermediate)),
        ("incline_push_up", (TrainingLevel.beginner,)),
    ):
        exercise = exercise_library.get_exercise_by_id(exercise_id)
        assert exercise.movement_pattern == MovementPattern.horizontal_push
        assert exercise.training_levels == levels
        assert exercise.equipment == (ExerciseEquipment.bodyweight,)
        assert exercise.suitable_locations == (
            SuitableLocation.home, SuitableLocation.gym, SuitableLocation.minimal_equipment,
        )


def test_catalog_loads_successfully():
    exercises = exercise_library.list_exercises()

    assert len(exercises) == 46
    assert all(isinstance(exercise, ExerciseDefinition) for exercise in exercises)


def test_all_exercise_ids_are_unique():
    exercises = exercise_library.list_exercises()
    ids = [exercise.id for exercise in exercises]

    assert len(ids) == len(set(ids))


def test_every_exercise_has_valid_movement_pattern_equipment_and_levels():
    for exercise in exercise_library.list_exercises():
        assert isinstance(exercise.movement_pattern, MovementPattern)
        assert exercise.equipment
        assert all(isinstance(item, ExerciseEquipment) for item in exercise.equipment)
        assert exercise.training_levels
        assert all(isinstance(level, TrainingLevel) for level in exercise.training_levels)


def test_get_exercise_by_id_returns_expected_entry():
    exercise = exercise_library.get_exercise_by_id("push_up")

    assert exercise is not None
    assert exercise.display_name == "Push-Up"
    assert exercise.movement_pattern == MovementPattern.horizontal_push


def test_unknown_exercise_id_returns_none():
    assert exercise_library.get_exercise_by_id("unknown_exercise") is None


def test_filter_by_movement_pattern_is_deterministic():
    first = exercise_library.list_exercises_by_movement_pattern(
        MovementPattern.horizontal_push
    )
    second = exercise_library.list_exercises_by_movement_pattern("horizontal_push")

    assert [exercise.id for exercise in first] == [
        "push_up",
        "incline_push_up",
        "dumbbell_bench_press",
        "barbell_bench_press",
    ]
    assert [exercise.id for exercise in first] == [exercise.id for exercise in second]


def test_filter_by_equipment_is_deterministic():
    exercises = exercise_library.list_exercises_by_equipment(
        ExerciseEquipment.bodyweight
    )

    assert exercises
    assert [exercise.id for exercise in exercises] == [
        exercise.id
        for exercise in exercise_library.list_exercises()
        if ExerciseEquipment.bodyweight in exercise.equipment
    ]


def test_filter_by_training_level_is_deterministic():
    exercises = exercise_library.list_exercises_by_training_level(TrainingLevel.beginner)

    assert exercises
    assert all(TrainingLevel.beginner in exercise.training_levels for exercise in exercises)
    assert [exercise.id for exercise in exercises] == [
        exercise.id
        for exercise in exercise_library.list_exercises()
        if TrainingLevel.beginner in exercise.training_levels
    ]


def test_filter_by_location_is_deterministic():
    exercises = exercise_library.list_exercises_by_location(
        SuitableLocation.minimal_equipment
    )

    assert exercises
    assert all(
        SuitableLocation.minimal_equipment in exercise.suitable_locations
        for exercise in exercises
    )
    assert [exercise.id for exercise in exercises] == [
        exercise.id
        for exercise in exercise_library.list_exercises()
        if SuitableLocation.minimal_equipment in exercise.suitable_locations
    ]


def test_every_workout_generator_movement_pattern_has_library_coverage():
    covered_patterns = {
        exercise.movement_pattern.value for exercise in exercise_library.list_exercises()
    }

    assert set(get_supported_movement_patterns()).issubset(covered_patterns)


def test_major_patterns_have_multiple_options_where_practical():
    counts = Counter(
        exercise.movement_pattern.value for exercise in exercise_library.list_exercises()
    )

    for pattern in (
        "horizontal_push",
        "horizontal_pull",
        "vertical_push",
        "vertical_pull",
        "squat_pattern",
        "hinge_pattern",
        "unilateral_lower",
        "core",
        "conditioning",
        "mobility",
    ):
        assert counts[pattern] >= 2


def test_bodyweight_minimal_equipment_and_gym_coverage_exist():
    bodyweight = exercise_library.list_exercises_by_equipment(ExerciseEquipment.bodyweight)
    minimal_equipment = exercise_library.list_exercises_by_location(
        SuitableLocation.minimal_equipment
    )
    gym = exercise_library.list_exercises_by_location(SuitableLocation.gym)

    assert bodyweight
    assert minimal_equipment
    assert gym


def test_beginner_options_exist_for_major_patterns():
    beginner_ids_by_pattern = {
        pattern: [
            exercise.id
            for exercise in exercise_library.list_exercises_by_movement_pattern(pattern)
            if TrainingLevel.beginner in exercise.training_levels
        ]
        for pattern in (
            "horizontal_push",
            "horizontal_pull",
            "vertical_push",
            "vertical_pull",
            "squat_pattern",
            "hinge_pattern",
            "unilateral_lower",
            "core",
            "conditioning",
            "mobility",
        )
    }

    assert all(beginner_ids_by_pattern.values())


def test_public_api_contract_is_unchanged():
    response = TrainingRecommendationResponse(
        action=Action.train,
        recommended_session=RecommendedSession.full_body,
        intensity=Intensity.moderate,
        duration_minutes=45,
        reason_codes=[ReasonCode.LOW_FATIGUE],
        needs_more_data=False,
        agent_version="0.1",
    )

    assert set(response.model_dump().keys()) == {
        "action",
        "recommended_session",
        "intensity",
        "duration_minutes",
        "reason_codes",
        "needs_more_data",
        "agent_version",
    }


def test_training_engine_and_workout_generator_behavior_remain_unchanged():
    request = _request(goal="general_fitness", training_level="beginner")
    first_engine = training_engine.evaluate(request)
    _ = exercise_library.list_exercises_by_movement_pattern("horizontal_push")
    second_engine = training_engine.evaluate(request)

    assert first_engine.model_dump() == second_engine.model_dump()

    first_plan = generate_workout_plan(request, _recommendation())
    _ = exercise_library.get_exercise_by_id("goblet_squat")
    second_plan = generate_workout_plan(request, _recommendation())

    assert first_plan.model_dump() == second_plan.model_dump()


def test_exercise_library_is_lookup_only_and_does_not_accept_user_profile_inputs():
    exercise_fields = set(ExerciseDefinition.model_fields)
    query_signatures = {
        name: inspect.signature(getattr(exercise_library, name))
        for name in (
            "get_exercise_by_id",
            "list_exercises",
            "list_exercises_by_movement_pattern",
            "list_exercises_by_equipment",
            "list_exercises_by_training_level",
            "list_exercises_by_location",
        )
    }

    assert {
        "sets",
        "rep_min",
        "rep_max",
        "work_seconds",
        "rest_seconds",
        "effort_target",
        "intensity",
        "duration_minutes",
        "goal",
        "user_id",
        "training_days_per_week",
        "fatigue_level",
    }.isdisjoint(exercise_fields)
    assert list(query_signatures["list_exercises"].parameters) == []
    assert list(query_signatures["get_exercise_by_id"].parameters) == ["exercise_id"]
    assert list(query_signatures["list_exercises_by_movement_pattern"].parameters) == [
        "movement_pattern"
    ]
    assert list(query_signatures["list_exercises_by_equipment"].parameters) == [
        "equipment"
    ]
    assert list(query_signatures["list_exercises_by_training_level"].parameters) == [
        "training_level"
    ]
    assert list(query_signatures["list_exercises_by_location"].parameters) == [
        "location"
    ]
