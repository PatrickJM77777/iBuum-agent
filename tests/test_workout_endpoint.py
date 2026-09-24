"""Public contract, real-pipeline parity, authentication and boundary regression."""

import os
from unittest.mock import Mock

os.environ.setdefault("IBUUM_API_KEY", "test-secret-key")

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.exercise import ExerciseEquipment
from app.models.training_request import TrainingRecommendationRequest
from app.models.training_response import Action, ReasonCode
from app.models.workout_orchestration import WorkoutEnvironmentContext
from app.services import exercise_library, training_engine, workout_orchestrator
from app.services.workout_api_mapper import to_workout_api_response

ENDPOINT = "/api/v1/workout"
HEADERS = {"X-API-Key": os.environ["IBUUM_API_KEY"]}
client = TestClient(app)
GYM = {"training_location": "gym", "available_equipment": [e.value for e in ExerciseEquipment]}
EMPTY = {"training_location": "gym", "available_equipment": []}
PARTIAL = {"training_location": "gym", "available_equipment": ["barbell"]}
HOME = {"training_location": "home", "available_equipment": ["bodyweight"]}


def payload(overrides=None, environment=GYM):
    training = dict(age=30, sex="male", height_cm=178, weight_kg=80,
                    goal="strength", training_level="intermediate",
                    training_days_per_week=4, fatigue_level=1)
    return {"training": training | (overrides or {}), "environment": environment}


def post(data):
    response = client.post(ENDPOINT, json=data, headers=HEADERS)
    assert response.status_code == 200, response.text
    return response.json()


CASES = [
    ({}, GYM), ({"fatigue_level": 5}, GYM),
    ({"last_session_type": "full_body", "hours_since_last_session": 12}, GYM),
    ({}, None), ({}, EMPTY), ({}, PARTIAL), ({}, HOME),
    ({"goal": "endurance"}, GYM), ({"goal": "mobility"}, GYM),
    ({"sex": "female", "cycle_context": {"phase": "menstruation", "discomfort": "high"}}, GYM),
    ({"training_level": "beginner"}, GYM),
]


@pytest.mark.parametrize("overrides,environment", CASES)
def test_exact_independent_mapping_and_determinism(overrides, environment):
    data = payload(overrides, environment)
    req = TrainingRecommendationRequest(**data["training"])
    env = WorkoutEnvironmentContext(**environment) if environment is not None else None
    direct = workout_orchestrator.orchestrate_workout(req, env)
    selected = direct.selected_workout
    plan = selected.source_plan
    # Independent oracle uses the complete internal slot dump, not the API mapper.
    expected = {
        "recommendation": direct.recommendation.model_dump(mode="json"),
        "workout": {
            "plan_status": plan.status.value,
            "selector_status": selected.selector_status.value,
            "action": plan.action.value, "session_type": plan.session_type.value,
            "intensity": plan.intensity.value,
            "duration_minutes": plan.target_duration_minutes,
            "exercises": [s.source_slot.model_dump(mode="json") | {
                "exercise_id": s.exercise_id, "display_name": s.display_name,
                "selection_reason_codes": [r.value for r in s.reason_codes],
            } for s in selected.selected_slots],
            "unresolved_slots": [s.source_slot.model_dump(mode="json") | {
                "reason_codes": [r.value for r in s.reason_codes],
            } for s in selected.unresolved_slots],
            "generator_reason_codes": plan.generator_reason_codes,
        },
        "versions": {
            "agent_version": direct.recommendation.agent_version,
            "generator_version": plan.generator_version,
            "selector_version": selected.selector_version,
            "orchestrator_version": direct.orchestrator_version,
        },
    }
    assert post(data) == expected
    assert post(data) == post(data)


@pytest.mark.parametrize("key", [None, "", "wrong-key"])
def test_authentication_rejection_does_not_leak(key, monkeypatch):
    spy = Mock()
    monkeypatch.setattr(workout_orchestrator, "orchestrate_workout", spy)
    data = payload({"user_id": "private-marker"})
    response = client.post(ENDPOINT, json=data,
                           headers={} if key is None else {"X-API-Key": key})
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key."}
    assert HEADERS["X-API-Key"] not in response.text
    assert "private-marker" not in response.text
    spy.assert_not_called()


@pytest.mark.parametrize("method", ["get", "put", "patch", "delete", "head"])
def test_post_only(method):
    assert getattr(client, method)(ENDPOINT, headers=HEADERS).status_code == 405


@pytest.mark.parametrize("environment", [None, {}, {"training_location": "gym"},
    {"available_equipment": ["bodyweight"]}, EMPTY, GYM])
def test_environment_mapping_and_exactly_one_call(environment, monkeypatch):
    real = workout_orchestrator.orchestrate_workout
    spy = Mock(wraps=real)
    monkeypatch.setattr(workout_orchestrator, "orchestrate_workout", spy)
    post(payload(environment=environment))
    spy.assert_called_once()
    req, env = spy.call_args.args
    assert req.training_level == "intermediate"
    if environment is None:
        assert env is None
    else:
        equipment = environment.get("available_equipment")
        assert env.available_equipment == (None if equipment is None else frozenset(equipment))
        assert env.training_location == environment.get("training_location")


def test_absent_environment_is_unknown():
    data = payload()
    del data["environment"]
    assert post(data) == post(payload(environment=None))


@pytest.mark.parametrize("bad", [
    {"available_equipment": ["invalid"]}, {"training_location": "invalid"},
    {"training_level": "advanced"}, {"extra": True}, {"available_equipment": "bodyweight"},
])
def test_invalid_environment(bad):
    assert client.post(ENDPOINT, json=payload(environment=bad), headers=HEADERS).status_code == 422


@pytest.mark.parametrize("data", [{}, {"training": None}, [],
    payload() | {"extra": True}, payload({"age": 9}), payload({"goal": "invalid"}),
    payload({"training_level": "invalid"}), payload({"training_days_per_week": 8}),
    payload({"weight_kg": 0}), payload({"user_id": "name@example.com"})])
def test_invalid_request(data):
    assert client.post(ENDPOINT, json=data, headers=HEADERS).status_code == 422


def test_malformed_json():
    response = client.post(ENDPOINT, content="{", headers=HEADERS | {"Content-Type": "application/json"})
    assert response.status_code == 422


def test_complete_workout():
    body = post(payload())
    workout = body["workout"]
    assert workout["plan_status"] == "generated"
    assert workout["selector_status"] == "complete"
    assert workout["exercises"]
    assert workout["unresolved_slots"] == []


def test_rest():
    body = post(payload({"fatigue_level": 5}))
    assert body["recommendation"]["action"] == "rest"
    assert body["workout"]["plan_status"] == "no_workout"
    assert body["workout"]["selector_status"] == "no_workout"
    assert body["workout"]["exercises"] == body["workout"]["unresolved_slots"] == []


@pytest.mark.parametrize("overrides", [
    {"last_session_type": "full_body", "hours_since_last_session": 12},
    {"sex": "female", "cycle_context": {"phase": "menstruation", "discomfort": "high"}},
])
def test_recovery(overrides):
    body = post(payload(overrides))
    workout = body["workout"]
    assert body["recommendation"]["action"] == workout["action"] == "recovery"
    assert workout["session_type"] == "mobility"
    assert workout["intensity"] == "low"
    assert workout["duration_minutes"] <= 20
    assert workout["exercises"]
    assert all(e["movement_pattern"].startswith("mobility") or
               e["movement_pattern"] == "breathing_core_control" for e in workout["exercises"])


@pytest.mark.parametrize("environment,reason", [
    (None, "SELECTION_CONTEXT_INCOMPLETE"), (EMPTY, "EQUIPMENT_NOT_AVAILABLE"),
    ({"training_location": "home", "available_equipment": []}, "EQUIPMENT_NOT_AVAILABLE"),
])
def test_unknown_and_empty_are_distinct(environment, reason):
    body = post(payload(environment=environment))
    workout = body["workout"]
    assert body["recommendation"]["action"] == workout["action"] == "train"
    assert workout["plan_status"] == "generated"
    assert workout["selector_status"] == "incomplete"
    assert workout["exercises"] == []
    assert workout["unresolved_slots"]
    assert all(s["reason_codes"] == [reason] for s in workout["unresolved_slots"])


@pytest.mark.parametrize("environment", [PARTIAL, HOME])
def test_partial_and_bodyweight_preserve_constraints(environment):
    workout = post(payload(environment=environment))["workout"]
    assert workout["exercises"]
    if environment == PARTIAL:
        assert workout["selector_status"] == "incomplete"
        assert workout["unresolved_slots"]
    for slot in workout["exercises"]:
        exercise = exercise_library.get_exercise_by_id(slot["exercise_id"])
        assert set(exercise.equipment) <= set(environment["available_equipment"])
        assert environment["training_location"] in exercise.suitable_locations


def test_beginner():
    body = post(payload({"training_level": "beginner"}))
    assert body["recommendation"]["intensity"] != "high"
    assert body["workout"]["exercises"]
    for slot in body["workout"]["exercises"]:
        assert "beginner" in exercise_library.get_exercise_by_id(slot["exercise_id"]).training_levels


@pytest.mark.parametrize("goal,session", [("endurance", "cardio"), ("mobility", "mobility")])
def test_goal(goal, session):
    body = post(payload({"goal": goal}))
    assert body["recommendation"]["recommended_session"] == body["workout"]["session_type"] == session


@pytest.mark.parametrize("phase", ["menstruation", "follicular", "ovulation", "luteal"])
def test_phase_alone_does_not_penalize(phase):
    assert post(payload({"sex": "female"})) == post(payload({
        "sex": "female", "cycle_context": {"phase": phase, "discomfort": "none"}}))


def test_more_data_domain_result(monkeypatch):
    req = TrainingRecommendationRequest(**payload()["training"])
    decision = training_engine.evaluate(req).model_copy(update={
        "action": Action.request_more_data, "needs_more_data": True,
        "reason_codes": [ReasonCode.INSUFFICIENT_DATA]})
    monkeypatch.setattr(training_engine, "evaluate", lambda request: decision)
    body = post(payload())
    assert body["recommendation"] == decision.model_dump(mode="json")
    assert body["workout"]["plan_status"] == "more_data_required"
    assert body["workout"]["selector_status"] == "more_data_required"
    assert body["workout"]["exercises"] == body["workout"]["unresolved_slots"] == []


def test_mapper_preserves_nondefault_notes_and_versions_without_mutation():
    req = TrainingRecommendationRequest(**payload()["training"])
    result = workout_orchestrator.orchestrate_workout(req, WorkoutEnvironmentContext(**PARTIAL))
    selected = result.selected_workout
    for slot in selected.selected_slots + selected.unresolved_slots:
        slot.source_slot.notes = ["first", "second"]
        slot.source_slot.effort_target = "synthetic effort"
    result.recommendation.agent_version = "agent-sentinel"
    selected.source_plan.generator_version = "generator-sentinel"
    selected.selector_version = "selector-sentinel"
    result.orchestrator_version = "orchestrator-sentinel"
    before = result.model_dump(mode="json")
    public = to_workout_api_response(result)
    for slot in public.workout.exercises + public.workout.unresolved_slots:
        assert slot.notes == ["first", "second"]
        assert slot.effort_target == "synthetic effort"
        slot.notes.clear()
    assert public.versions.model_dump() == {
        "agent_version": "agent-sentinel", "generator_version": "generator-sentinel",
        "selector_version": "selector-sentinel", "orchestrator_version": "orchestrator-sentinel"}
    public.recommendation.reason_codes.clear()
    public.workout.generator_reason_codes.clear()
    assert result.model_dump(mode="json") == before


def test_existing_endpoints_are_unchanged(monkeypatch):
    spy = Mock(side_effect=AssertionError("recommendation must not orchestrate"))
    monkeypatch.setattr(workout_orchestrator, "orchestrate_workout", spy)
    assert client.get("/health").status_code == 200
    data = payload()["training"]
    response = client.post("/api/v1/training/recommendation", json=data, headers=HEADERS)
    assert response.status_code == 200
    assert set(response.json()) == {"action", "recommended_session", "intensity",
        "duration_minutes", "reason_codes", "needs_more_data", "agent_version"}
    assert response.json() == training_engine.evaluate(TrainingRecommendationRequest(**data)).model_dump(mode="json")
    spy.assert_not_called()


def test_openapi_public_boundary():
    schema = app.openapi()
    assert set(schema["paths"]) == {"/health", "/api/v1/training/recommendation", ENDPOINT}
    assert set(schema["paths"][ENDPOINT]) == {"post"}
    operation = schema["paths"][ENDPOINT]["post"]
    assert operation["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith("/WorkoutApiRequest")
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("/WorkoutApiResponse")
    forbidden = {"WorkoutOrchestrationResult", "WorkoutEnvironmentContext", "SelectedWorkoutPlan",
                 "ExerciseSelectorContext", "WorkoutPlan", "MovementSlot", "SelectedExerciseSlot"}
    assert not forbidden.intersection(schema["components"]["schemas"])
    assert "source_slot" not in str(schema)
    assert "source_plan" not in str(schema)
    for name in ("WorkoutApiRequest", "WorkoutEnvironmentApiRequest"):
        assert schema["components"]["schemas"][name]["additionalProperties"] is False
