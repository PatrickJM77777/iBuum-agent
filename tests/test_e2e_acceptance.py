"""Network-independent acceptance of the real public HTTP/backend pipeline.

Only rejected authentication uses a mock, to prove orchestration cannot execute.
The parity oracle deliberately does not call the production API mapper.
"""

from collections import Counter
from copy import deepcopy
import json
import os
from unittest.mock import Mock

os.environ.setdefault("IBUUM_API_KEY", "test-secret-key")

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.training_request import Goal, TrainingRecommendationRequest
from app.models.workout_orchestration import WorkoutEnvironmentContext
from app.services import exercise_library, training_engine, workout_orchestrator

ENDPOINT = "/api/v1/workout"
HEADERS = {"X-API-Key": os.environ["IBUUM_API_KEY"]}
GYM = {"training_location": "gym", "available_equipment": [
    "bodyweight", "dumbbell", "barbell", "kettlebell", "resistance_band", "cable", "machine",
]}
PARTIAL = {"training_location": "gym", "available_equipment": ["barbell"]}
HOME = {"training_location": "home", "available_equipment": ["bodyweight"]}
RECENT_FULL = {"last_session_type": "full_body", "hours_since_last_session": 12}
HIGH_CYCLE = {"sex": "female", "cycle_context": {"phase": "menstruation", "discomfort": "high"}}
RECOMMENDATION_KEYS = {
    "action", "recommended_session", "intensity", "duration_minutes",
    "reason_codes", "needs_more_data", "agent_version",
}
WORKOUT_KEYS = {
    "plan_status", "selector_status", "action", "session_type", "intensity",
    "duration_minutes", "exercises", "unresolved_slots", "generator_reason_codes",
}
VERSION_KEYS = {"agent_version", "generator_version", "selector_version", "orchestrator_version"}
SLOT_KEYS = {
    "sequence", "movement_pattern", "target_area", "sets", "rep_min", "rep_max",
    "work_seconds", "rest_seconds", "effort_target", "notes",
}


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def payload(overrides=None, environment=GYM):
    data = {"training": dict(
        age=30, sex="male", height_cm=178, weight_kg=80, goal="strength",
        training_level="intermediate", training_days_per_week=4, fatigue_level=1,
    ) | deepcopy(overrides or {})}
    if environment is not None:
        data["environment"] = deepcopy(environment)
    return data


def assert_no_internal_wrappers(value):
    if isinstance(value, dict):
        assert not {"source_plan", "source_slot"}.intersection(value)
        for child in value.values():
            assert_no_internal_wrappers(child)
    elif isinstance(value, list):
        for child in value:
            assert_no_internal_wrappers(child)


def post(client, data):
    response = client.post(ENDPOINT, json=data, headers=HEADERS)
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"recommendation", "workout", "versions"}
    rec, work = body["recommendation"], body["workout"]
    assert set(rec) == RECOMMENDATION_KEYS
    assert set(work) == WORKOUT_KEYS
    assert set(body["versions"]) == VERSION_KEYS
    assert all(isinstance(v, str) and v for v in body["versions"].values())
    assert rec["agent_version"] == body["versions"]["agent_version"]
    assert_no_internal_wrappers(body)
    for field in ("action", "intensity", "duration_minutes"):
        assert rec[field] == work[field]
    assert rec["recommended_session"] == work["session_type"]
    for slot in work["exercises"]:
        assert set(slot) == SLOT_KEYS | {"exercise_id", "display_name", "selection_reason_codes"}
        exercise = exercise_library.get_exercise_by_id(slot["exercise_id"])
        assert exercise is not None
        assert slot["display_name"] == exercise.display_name
        assert slot["movement_pattern"] == exercise.movement_pattern
        assert data["training"]["training_level"] in exercise.training_levels
        env = data["environment"]
        assert env["training_location"] in exercise.suitable_locations
        assert set(exercise.equipment) <= set(env["available_equipment"])
    for slot in work["unresolved_slots"]:
        assert set(slot) == SLOT_KEYS | {"reason_codes"}
        assert slot["reason_codes"]
    if work["selector_status"] == "complete":
        assert work["unresolved_slots"] == []
    if work["selector_status"] == "incomplete":
        assert work["unresolved_slots"]
    if rec["action"] == "rest":
        assert work["plan_status"] == work["selector_status"] == "no_workout"
        assert work["duration_minutes"] == 0
        assert work["exercises"] == work["unresolved_slots"] == []
    if rec["action"] == "recovery":
        assert work["session_type"] == "mobility"
        assert work["intensity"] == "low"
        assert 0 < work["duration_minutes"] <= 20
        for slot in work["exercises"] + work["unresolved_slots"]:
            assert slot["movement_pattern"].startswith("mobility") or slot["movement_pattern"] == "breathing_core_control"
            assert slot["rep_min"] is None and slot["rep_max"] is None
            assert 0 < slot["sets"] <= 2
            assert 0 < slot["work_seconds"] <= 45
            assert slot["effort_target"] == "RPE 3-4"
    if data["training"]["training_level"] == "beginner":
        assert rec["intensity"] != "high"
    return body


# A-P, with both explicit-empty locations and all known phase-only contexts.
CASES = [
    ("A-normal", {}, GYM), ("B-rest", {"fatigue_level": 5}, GYM),
    ("C-recovery", RECENT_FULL, GYM), ("D-missing", {}, None),
    ("E-empty", {}, {"training_location": "gym", "available_equipment": []}),
    ("F-partial", {}, PARTIAL), ("G-home", {}, HOME),
    ("H-home-empty", {}, {"training_location": "home", "available_equipment": []}),
    ("I-beginner", {"training_level": "beginner"}, GYM),
    ("J-endurance", {"goal": "endurance"}, GYM),
    ("K-mobility", {"goal": "mobility"}, GYM),
    *[(f"L-{phase}", {"sex": "female", "cycle_context": {"phase": phase, "discomfort": "none"}}, GYM)
      for phase in ("menstruation", "follicular", "ovulation", "luteal")],
    ("M-high-discomfort", HIGH_CYCLE, GYM),
    ("N-upper", {"last_session_type": "upper_body", "hours_since_last_session": 12}, GYM),
    ("O-lower", {"last_session_type": "lower_body", "hours_since_last_session": 12}, GYM),
    ("P-unknown", {"last_session_type": "unknown", "hours_since_last_session": 12}, GYM),
]


def direct_result(data):
    environment = data.get("environment")
    return workout_orchestrator.orchestrate_workout(
        TrainingRecommendationRequest(**data["training"]),
        WorkoutEnvironmentContext(**environment) if environment is not None else None,
    )


def assert_parity_and_slot_accounting(body, direct):
    selected = direct.selected_workout
    plan = selected.source_plan
    assert body["recommendation"] == direct.recommendation.model_dump(mode="json")
    assert body["versions"] == {
        "agent_version": direct.recommendation.agent_version,
        "generator_version": plan.generator_version,
        "selector_version": selected.selector_version,
        "orchestrator_version": direct.orchestrator_version,
    }
    assert body["workout"] == {
        "plan_status": plan.status.value, "selector_status": selected.selector_status.value,
        "action": plan.action.value, "session_type": plan.session_type.value,
        "intensity": plan.intensity.value, "duration_minutes": plan.target_duration_minutes,
        "generator_reason_codes": list(plan.generator_reason_codes),
        "exercises": [slot.source_slot.model_dump(mode="json") | {
            "exercise_id": slot.exercise_id, "display_name": slot.display_name,
            "selection_reason_codes": [reason.value for reason in slot.reason_codes],
        } for slot in selected.selected_slots],
        "unresolved_slots": [slot.source_slot.model_dump(mode="json") | {
            "reason_codes": [reason.value for reason in slot.reason_codes],
        } for slot in selected.unresolved_slots],
    }
    slots = body["workout"]["exercises"] + body["workout"]["unresolved_slots"]
    # Multisets detect lost, duplicated, or altered prescriptions, even at equal counts.
    assert Counter(json.dumps({k: s[k] for k in SLOT_KEYS}, sort_keys=True) for s in slots) == Counter(
        json.dumps(s.model_dump(mode="json"), sort_keys=True) for s in plan.movement_slots
    )
    assert len({s["sequence"] for s in slots}) == len(slots)
    if plan.status == "generated":
        assert slots


@pytest.mark.parametrize("case,overrides,environment", CASES, ids=[c[0] for c in CASES])
def test_canonical_acceptance(client, case, overrides, environment):
    data = payload(overrides, environment)
    body = post(client, data)
    rec, work = body["recommendation"], body["workout"]
    assert_parity_and_slot_accounting(body, direct_result(data))
    if case == "B-rest":
        assert rec["action"] == "rest"
    else:
        assert work["plan_status"] == "generated"
    if case in ("C-recovery", "M-high-discomfort"):
        assert rec["action"] == "recovery"
    if case in ("A-normal", "C-recovery", "M-high-discomfort"):
        assert work["selector_status"] == "complete"
        assert work["exercises"]
    if case in ("A-normal", "D-missing", "E-empty", "F-partial", "G-home", "H-home-empty"):
        assert rec["action"] == "train"
    if case in ("D-missing", "E-empty", "H-home-empty"):
        assert work["selector_status"] == "incomplete"
        assert work["exercises"] == []
        reason = "SELECTION_CONTEXT_INCOMPLETE" if case == "D-missing" else "EQUIPMENT_NOT_AVAILABLE"
        assert all(s["reason_codes"] == [reason] for s in work["unresolved_slots"])
    if case in ("F-partial", "G-home", "I-beginner"):
        assert work["exercises"]
    if case == "F-partial":
        assert work["selector_status"] == "incomplete"
        assert all(s["reason_codes"] == ["EQUIPMENT_NOT_AVAILABLE"] for s in work["unresolved_slots"])
    if case in ("J-endurance", "K-mobility"):
        assert rec["recommended_session"] == ("cardio" if case == "J-endurance" else "mobility")
    if case.startswith("L-"):
        assert body == post(client, payload({"sex": "female"}))
    if case in ("N-upper", "O-lower"):
        assert rec["action"] == "train"
        assert rec["recommended_session"] == ("lower_body" if case == "N-upper" else "upper_body")
        assert rec["intensity"] != "high"
        assert "INSUFFICIENT_RECOVERY" in rec["reason_codes"]
    if case == "P-unknown":
        assert rec["needs_more_data"] is True
        assert "INSUFFICIENT_DATA" in rec["reason_codes"]
        assert not {"RECOVERY_WINDOW_OK", "INSUFFICIENT_RECOVERY"}.intersection(rec["reason_codes"])
        assert rec["recommended_session"] == "mobility"
        assert rec["intensity"] != "high"


@pytest.mark.parametrize("goal", [g.value for g in Goal])
@pytest.mark.parametrize("safety,action", [({"fatigue_level": 5}, "rest"), (RECENT_FULL, "recovery"), (HIGH_CYCLE, "recovery")],
                         ids=["fatigue", "recent-full-body", "cycle-discomfort"])
def test_safety_precedes_every_goal(client, goal, safety, action):
    body = post(client, payload({"goal": goal} | safety))
    assert body["recommendation"]["action"] == action


@pytest.mark.parametrize("overrides,environment", [({}, GYM), ({"fatigue_level": 5}, GYM),
    (RECENT_FULL, GYM), ({}, None), ({}, PARTIAL)],
    ids=["normal", "rest", "recovery", "missing", "partial"])
def test_repeated_http_json_is_identical(client, overrides, environment):
    data = payload(overrides, environment)
    first = post(client, data)
    for _ in range(3):
        assert post(client, data) == first


def test_requests_and_catalog_remain_isolated(client):
    before = [e.model_dump(mode="json") for e in exercise_library.list_exercises()]
    normal = payload()
    original = deepcopy(normal)
    first = post(client, normal)
    post(client, payload({"fatigue_level": 5}))
    post(client, payload(RECENT_FULL))
    post(client, payload(environment=None))
    post(client, payload(environment=PARTIAL))
    assert post(client, normal) == first
    assert normal == original
    assert [e.model_dump(mode="json") for e in exercise_library.list_exercises()] == before


@pytest.mark.parametrize("key", [None, "", "incorrect-acceptance-key"], ids=["missing", "empty", "wrong"])
def test_authentication_blocks_pipeline_safely(client, monkeypatch, key):
    blocked = Mock(side_effect=AssertionError("Authentication must block orchestration"))
    monkeypatch.setattr(workout_orchestrator, "orchestrate_workout", blocked)
    response = client.post(ENDPOINT, json=payload({"user_id": "private-acceptance-marker"}),
                           headers={} if key is None else {"X-API-Key": key})
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key."}
    assert HEADERS["X-API-Key"] not in response.text
    assert "private-acceptance-marker" not in response.text
    assert "Traceback" not in response.text
    blocked.assert_not_called()


@pytest.mark.parametrize("data", [
    payload({"goal": "invalid"}), payload({"training_level": "invalid"}),
    payload({"training_days_per_week": 0}), payload({"training_days_per_week": 8}),
    payload({"fatigue_level": 0}), payload({"fatigue_level": 6}),
    payload(environment={"available_equipment": ["invalid"]}),
    payload(environment={"training_location": "invalid"}),
    payload(environment=GYM | {"training_level": "advanced"}),
    payload() | {"unexpected": True}, payload({"user_id": "person@example.com"}),
], ids=["goal", "level", "days-below", "days-above", "fatigue-below", "fatigue-above",
        "equipment", "location", "environment-level", "top-level-extra", "email-id"])
def test_invalid_requests_are_422(client, data):
    assert client.post(ENDPOINT, json=data, headers=HEADERS).status_code == 422


def test_malformed_json_is_422(client):
    response = client.post(ENDPOINT, content="{", headers=HEADERS | {"Content-Type": "application/json"})
    assert response.status_code == 422


def test_openapi_exposes_only_public_contracts(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert set(schema["paths"]) == {"/health", "/api/v1/training/recommendation", ENDPOINT}
    assert set(schema["paths"][ENDPOINT]) == {"post"}
    operation = schema["paths"][ENDPOINT]["post"]
    assert operation["requestBody"]["content"]["application/json"]["schema"] == {"$ref": "#/components/schemas/WorkoutApiRequest"}
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {"$ref": "#/components/schemas/WorkoutApiResponse"}
    forbidden = {"WorkoutOrchestrationResult", "WorkoutEnvironmentContext", "SelectedWorkoutPlan",
                 "ExerciseSelectorContext", "WorkoutPlan", "MovementSlot", "SelectedExerciseSlot"}
    assert not forbidden.intersection(schema["components"]["schemas"])
    assert "source_slot" not in json.dumps(schema)
    assert "source_plan" not in json.dumps(schema)


@pytest.mark.parametrize("overrides", [{}, {"fatigue_level": 5}, RECENT_FULL,
    {"goal": "endurance"}, HIGH_CYCLE], ids=["normal", "rest", "recovery", "endurance", "cycle"])
def test_legacy_recommendation_is_unchanged(client, overrides):
    data = payload(overrides)
    response = client.post("/api/v1/training/recommendation", json=data["training"], headers=HEADERS)
    assert response.status_code == 200
    expected = response.json()
    assert set(expected) == RECOMMENDATION_KEYS
    assert expected == training_engine.evaluate(TrainingRecommendationRequest(**data["training"])).model_dump(mode="json")
    assert post(client, data)["recommendation"] == expected
    assert client.post("/api/v1/training/recommendation", json=data["training"], headers=HEADERS).json() == expected


def test_health_remains_available(client):
    assert client.get("/health").status_code == 200
