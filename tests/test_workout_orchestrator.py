"""Integration coverage uses the real engine, generator, selector and catalog."""

import os
from collections import Counter

os.environ.setdefault("IBUUM_API_KEY", "test-secret-key")

import pytest
from pydantic import ValidationError

from app.models.exercise import ExerciseEquipment, SuitableLocation
from app.models.exercise_selection import ExerciseSelectorContext, SelectionReasonCode
from app.models.training_request import TrainingRecommendationRequest
from app.models.training_response import Action, Intensity, ReasonCode
from app.models.workout_orchestration import WorkoutEnvironmentContext, WorkoutOrchestrationResult
from app.services import exercise_library, exercise_selector, training_engine, workout_generator
from app.services.workout_orchestrator import WORKOUT_ORCHESTRATOR_VERSION, WorkoutOrchestrator, orchestrate_workout


def request(**overrides):
    values = dict(age=30, sex="male", height_cm=178, weight_kg=80,
                  goal="strength", training_level="intermediate",
                  training_days_per_week=4, fatigue_level=1)
    return TrainingRecommendationRequest(**(values | overrides))


def gym():
    return WorkoutEnvironmentContext(available_equipment=frozenset(ExerciseEquipment),
                                     training_location=SuitableLocation.gym)


def check_pipeline(req, env):
    """Compare every upstream field and every selected/unresolved prescription."""
    recommendation = training_engine.evaluate(req)
    plan = workout_generator.generate_workout_plan(req, recommendation)
    context = ExerciseSelectorContext(
        training_level=req.training_level,
        available_equipment=env.available_equipment if env else None,
        training_location=env.training_location if env else None,
    )
    selected = exercise_selector.select_exercises(plan, context)
    result = orchestrate_workout(req, env)
    assert result.recommendation.model_dump() == recommendation.model_dump()
    assert result.selected_workout.source_plan.model_dump() == plan.model_dump()
    assert result.selected_workout.model_dump() == selected.model_dump()
    slots = result.selected_workout.selected_slots + result.selected_workout.unresolved_slots
    assert Counter(s.source_slot.model_dump_json() for s in slots) == Counter(
        s.model_dump_json() for s in plan.movement_slots)
    for slot in result.selected_workout.selected_slots:
        exercise = exercise_library.get_exercise_by_id(slot.exercise_id)
        assert exercise is not None
        assert exercise.movement_pattern == slot.source_slot.movement_pattern
        assert req.training_level in exercise.training_levels
        assert env.training_location in exercise.suitable_locations
        assert set(exercise.equipment) <= env.available_equipment
        assert slot.reason_codes
    return result


@pytest.mark.parametrize("last,hours,session", [
    (None, None, "full_body"), ("upper_body", 24, "lower_body"),
    ("lower_body", 48, "upper_body"), ("upper_body", 12, "lower_body"),
    ("lower_body", 12, "upper_body"),
])
def test_strength_bootstrap_and_rotation(last, hours, session):
    result = check_pipeline(request(last_session_type=last, hours_since_last_session=hours), gym())
    assert result.recommendation.action == "train"
    assert result.recommendation.recommended_session == session
    assert result.selected_workout.source_plan.session_type == session
    assert result.selected_workout.source_plan.status == "generated"
    assert result.selected_workout.selector_status == "complete"
    assert result.selected_workout.selected_slots
    if hours is not None and hours < 24:
        assert result.recommendation.intensity in (Intensity.low, Intensity.moderate)


@pytest.mark.parametrize("overrides", [
    dict(last_session_type="full_body", hours_since_last_session=12),
    dict(sex="female", cycle_context={"phase": "menstruation", "discomfort": "high"}),
])
def test_recovery_preserves_mobility_and_caps(overrides):
    result = check_pipeline(request(**overrides), gym())
    assert result.recommendation.action == "recovery"
    assert result.recommendation.recommended_session == "mobility"
    assert result.recommendation.intensity == "low"
    assert result.recommendation.duration_minutes <= 20
    assert result.selected_workout.source_plan.action == "recovery"
    assert result.selected_workout.selector_status == "complete"
    assert result.selected_workout.selected_slots
    assert all(s.source_slot.movement_pattern.startswith("mobility") or
               s.source_slot.movement_pattern == "breathing_core_control"
               for s in result.selected_workout.selected_slots)


@pytest.mark.parametrize("env", [None, gym()])
def test_high_fatigue_rest_never_gains_exercises(env):
    result = check_pipeline(request(fatigue_level=5), env)
    assert result.recommendation.action == "rest"
    assert result.selected_workout.source_plan.status == "no_workout"
    assert result.selected_workout.selector_status == "no_workout"
    assert result.selected_workout.source_plan.movement_slots == []
    assert result.selected_workout.selected_slots == []
    assert result.selected_workout.unresolved_slots == []


def test_unknown_recent_session_preserves_uncertainty():
    result = check_pipeline(request(last_session_type="unknown", hours_since_last_session=12), gym())
    assert result.recommendation.needs_more_data
    assert ReasonCode.INSUFFICIENT_DATA in result.recommendation.reason_codes
    assert ReasonCode.RECOVERY_WINDOW_OK not in result.recommendation.reason_codes
    assert ReasonCode.INSUFFICIENT_RECOVERY not in result.recommendation.reason_codes
    assert result.recommendation.intensity != "high"
    assert result.selected_workout.source_plan.status == "generated"
    assert result.selected_workout.selector_status == "complete"


def test_beginner_uses_request_level_and_intensity_ceiling():
    result = check_pipeline(request(training_level="beginner"), gym())
    assert result.recommendation.intensity != "high"
    assert result.selected_workout.selector_status == "complete"


def test_home_bodyweight_compatibility():
    env = WorkoutEnvironmentContext(training_location="home", available_equipment={"bodyweight"})
    result = check_pipeline(request(), env)
    assert result.selected_workout.selected_slots


@pytest.mark.parametrize("equipment", [frozenset(), frozenset({ExerciseEquipment.barbell})])
def test_unavailable_equipment_preserves_unresolved_slots(equipment):
    result = check_pipeline(request(), WorkoutEnvironmentContext(
        training_location="gym", available_equipment=equipment))
    assert result.recommendation.action == "train"
    assert result.selected_workout.selector_status == "incomplete"
    assert result.selected_workout.unresolved_slots
    assert all(s.reason_codes == [SelectionReasonCode.EQUIPMENT_NOT_AVAILABLE]
               for s in result.selected_workout.unresolved_slots)
    if not equipment:
        assert result.selected_workout.selected_slots == []


@pytest.mark.parametrize("env", [None, WorkoutEnvironmentContext(),
    WorkoutEnvironmentContext(training_location="gym"),
    WorkoutEnvironmentContext(available_equipment={"bodyweight"})])
def test_missing_environment_never_invents_context(env):
    result = check_pipeline(request(), env)
    assert result.recommendation.action == "train"
    assert result.selected_workout.source_plan.status == "generated"
    assert result.selected_workout.selector_status == "incomplete"
    assert result.selected_workout.selected_slots == []
    assert result.selected_workout.unresolved_slots
    assert all(s.reason_codes == [SelectionReasonCode.SELECTION_CONTEXT_INCOMPLETE]
               for s in result.selected_workout.unresolved_slots)


@pytest.mark.parametrize("goal,session", [("endurance", "cardio"), ("mobility", "mobility")])
def test_endurance_and_mobility(goal, session):
    result = check_pipeline(request(goal=goal), gym())
    assert result.recommendation.recommended_session == session
    assert result.selected_workout.selector_status == "complete"
    assert result.selected_workout.selected_slots


def test_provenance_versions_and_determinism():
    req, env = request(last_session_type="unknown", hours_since_last_session=12), gym()
    result = check_pipeline(req, env)
    assert result.orchestrator_version == WORKOUT_ORCHESTRATOR_VERSION
    assert result.recommendation.agent_version == training_engine.evaluate(req).agent_version
    assert result.selected_workout.source_plan.generator_version == workout_generator.WORKOUT_GENERATOR_VERSION
    assert result.selected_workout.selector_version == exercise_selector.EXERCISE_SELECTOR_VERSION
    assert result.selected_workout.source_plan.generator_reason_codes
    for _ in range(3):
        assert WorkoutOrchestrator().orchestrate(req, env).model_dump() == result.model_dump()
    assert set(WorkoutOrchestrationResult.model_fields) == {
        "recommendation", "selected_workout", "orchestrator_version"}


def test_environment_contract_and_single_source_of_truth():
    assert set(WorkoutEnvironmentContext.model_fields) == {"available_equipment", "training_location"}
    with pytest.raises(ValidationError):
        WorkoutEnvironmentContext(training_level="advanced")
    assert WorkoutEnvironmentContext().available_equipment is None
    assert WorkoutEnvironmentContext(available_equipment=set()).available_equipment == frozenset()


@pytest.mark.parametrize("overrides", [{}, {"fatigue_level": 5},
    {"last_session_type": "full_body", "hours_since_last_session": 12}])
def test_strict_call_chain_and_defensive_snapshots(monkeypatch, overrides):
    req, env = request(**overrides), gym()
    calls, upstream = [], {}
    evaluate = training_engine.TrainingEngine.evaluate
    generate = workout_generator.generate_workout_plan
    select = exercise_selector.select_exercises

    def engine_spy(self, received):
        assert received is req
        calls.append("engine")
        upstream["recommendation"] = evaluate(self, received)
        return upstream["recommendation"]

    def generator_spy(received, recommendation):
        assert received is req
        assert recommendation is upstream["recommendation"]
        calls.append("generator")
        upstream["plan"] = generate(received, recommendation)
        return upstream["plan"]

    def selector_spy(plan, context):
        assert plan is upstream["plan"]
        assert context.training_level == req.training_level
        assert context.available_equipment == env.available_equipment
        assert context.training_location == env.training_location
        calls.append("selector")
        upstream["selected"] = select(plan, context)
        return upstream["selected"]

    monkeypatch.setattr(training_engine.TrainingEngine, "evaluate", engine_spy)
    monkeypatch.setattr(workout_generator, "generate_workout_plan", generator_spy)
    monkeypatch.setattr(exercise_selector, "select_exercises", selector_spy)
    result = orchestrate_workout(req, env)
    assert calls == ["engine", "generator", "selector"]
    original_recommendation = upstream["recommendation"].model_dump()
    original_selected = upstream["selected"].model_dump()
    result.recommendation.reason_codes.clear()
    result.selected_workout.source_plan.generator_reason_codes.clear()
    result.selected_workout.selected_slots.clear()
    assert upstream["recommendation"].model_dump() == original_recommendation
    assert upstream["selected"].model_dump() == original_selected


def test_request_more_data_propagates_through_real_generator_and_selector(monkeypatch):
    # The current real engine does not emit this action; exercise its contract
    # boundary with a supplied decision, leaving generator/selector real.
    recommendation = training_engine.evaluate(request()).model_copy(update={
        "action": Action.request_more_data, "needs_more_data": True,
        "reason_codes": [ReasonCode.INSUFFICIENT_DATA]})
    monkeypatch.setattr(training_engine, "evaluate", lambda req: recommendation)
    result = orchestrate_workout(request(), gym())
    assert result.recommendation == recommendation
    assert result.selected_workout.source_plan.status == "more_data_required"
    assert result.selected_workout.selector_status == "more_data_required"
    assert result.selected_workout.selected_slots == []


@pytest.mark.parametrize("env", [gym(), None])
def test_mutating_results_leaves_inputs_catalog_and_other_results_untouched(env):
    req = request(sex="female", cycle_context={"phase": "follicular", "discomfort": "none"})
    before_request = req.model_dump()
    before_environment = env.model_dump() if env else None
    before_catalog = [e.model_dump() for e in exercise_library.list_exercises()]
    first = orchestrate_workout(req, env)
    previous = orchestrate_workout(req, env)
    snapshot = previous.model_dump()
    first.recommendation.reason_codes.clear()
    first.selected_workout.source_plan.movement_slots[0].notes.append("caller edit")
    slots = first.selected_workout.selected_slots + first.selected_workout.unresolved_slots
    slots[0].source_slot.sets = 999
    slots[0].reason_codes.clear()
    assert req.model_dump() == before_request
    assert (env.model_dump() if env else None) == before_environment
    assert [e.model_dump() for e in exercise_library.list_exercises()] == before_catalog
    assert previous.model_dump() == snapshot
    assert orchestrate_workout(req, env).model_dump() == snapshot


def test_public_api_remains_recommendation_only():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    paths = app.openapi()["paths"]
    assert set(paths) == {"/health", "/api/v1/training/recommendation"}
    assert client.get("/health").status_code == 200
    endpoint = "/api/v1/training/recommendation"
    payload = request().model_dump(mode="json")
    assert client.post(endpoint, json=payload).status_code == 401
    response = client.post(endpoint, json=payload, headers={"X-API-Key": os.environ["IBUUM_API_KEY"]})
    assert response.status_code == 200
    assert set(response.json()) == {"action", "recommended_session", "intensity", "duration_minutes",
                                    "reason_codes", "needs_more_data", "agent_version"}
    assert response.json() == training_engine.evaluate(request()).model_dump(mode="json")
