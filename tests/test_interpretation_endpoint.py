"""Real HTTP acceptance, shared-result identity, parity and public boundaries."""

import ast
from copy import deepcopy
import os
from pathlib import Path
import re
from unittest.mock import Mock

os.environ.setdefault("IBUUM_API_KEY", "test-secret-key")

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.routes import interpretation as route
from app.core.config import get_settings
from app.main import app
from app.models.exercise import ExerciseEquipment
from app.models.interpretation_api import (
    InterpretationApiPayload, InterpretationApiRequest, InterpretationApiResponse,
    InterpretationVersionsApiResponse,
)
from app.models.training_request import TrainingRecommendationRequest
from app.models.workout_orchestration import WorkoutEnvironmentContext
from app.services import exercise_library, training_engine, workout_orchestrator
from app.services.interpretation_api_mapper import to_interpretation_api_response
from app.services.interpretation_core import translate_reason
from app.services.kai_presenter import present_kai
from app.services.kaia_presenter import present_kaia
from app.services.workout_api_mapper import to_workout_api_response

ENDPOINT = "/api/v1/interpretation"
HEADERS = {"X-API-Key": os.environ["IBUUM_API_KEY"]}
GYM = {"training_location": "gym", "available_equipment": [e.value for e in ExerciseEquipment]}
EMPTY = {"training_location": "gym", "available_equipment": []}
PARTIAL = {"training_location": "gym", "available_equipment": ["barbell"]}
CYCLE = {"sex": "female", "cycle_context": {"phase": "menstruation", "discomfort": "none"}}
HIGH_CYCLE = {"sex": "female", "cycle_context": {"phase": "menstruation", "discomfort": "high"}}
RECENT = {"last_session_type": "full_body", "hours_since_last_session": 12}
UNKNOWN = {"last_session_type": "unknown", "hours_since_last_session": 12}
INTERPRETATION_KEYS = {
    "presenter", "tone", "action", "session", "intensity", "duration_minutes",
    "needs_more_data", "title", "summary", "reasons", "today_plan", "avatar_message",
    "missing_data_message", "environment_message", "cycle_insight", "reason_codes",
    "interpretation_version",
}
VERSION_KEYS = {"agent_version", "generator_version", "selector_version",
                "orchestrator_version", "interpretation_version"}
PROVENANCE = {"generator_reason_codes", "selected_reason_codes", "unresolved_reason_codes"}
CASES = [
    pytest.param({}, GYM, id="normal"),
    pytest.param(CYCLE, GYM, id="cycle"),
    pytest.param(HIGH_CYCLE, GYM, id="high-discomfort"),
    pytest.param({"fatigue_level": 5}, GYM, id="rest"),
    pytest.param(RECENT, GYM, id="recovery"),
    pytest.param(UNKNOWN, GYM, id="unknown-history"),
    pytest.param({"training_level": "beginner"}, GYM, id="beginner"),
    pytest.param({"goal": "endurance"}, GYM, id="endurance"),
    pytest.param({"goal": "mobility"}, GYM, id="mobility"),
    pytest.param({}, None, id="missing-environment"),
    pytest.param({}, EMPTY, id="empty-equipment"),
    pytest.param({}, PARTIAL, id="partial-equipment"),
    pytest.param({}, {"training_location": "home", "available_equipment": ["bodyweight"]}, id="home"),
]


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def payload(overrides=None, environment=GYM, presenter="kai"):
    return deepcopy({
        "presenter": presenter,
        "training": dict(age=30, sex="male", height_cm=178, weight_kg=80,
                         goal="strength", training_level="intermediate",
                         training_days_per_week=4, fatigue_level=1) | (overrides or {}),
        "environment": environment,
    })


def post(client, data):
    response = client.post(ENDPOINT, json=data, headers=HEADERS)
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"recommendation", "workout", "interpretation", "versions"}
    assert set(body["interpretation"]) == INTERPRETATION_KEYS
    assert set(body["versions"]) == VERSION_KEYS
    assert body["interpretation"]["interpretation_version"] == body["versions"]["interpretation_version"] == "interpretation-core-v1"
    rec, interpretation = body["recommendation"], body["interpretation"]
    for field in ("action", "intensity", "duration_minutes", "needs_more_data", "reason_codes"):
        assert interpretation[field] == rec[field]
    assert interpretation["session"] == rec["recommended_session"]
    return body


def direct_bundle(data):
    request = TrainingRecommendationRequest(**data["training"])
    environment = data.get("environment")
    env = WorkoutEnvironmentContext(**environment) if environment is not None else None
    return request, workout_orchestrator.orchestrate_workout(request, env), env


def wording(interpretation):
    return " ".join([interpretation["title"], interpretation["summary"],
                     *interpretation["reasons"], interpretation["today_plan"],
                     interpretation["avatar_message"], interpretation["cycle_insight"] or "",
                     interpretation["missing_data_message"] or "",
                     interpretation["environment_message"] or ""]).lower()


@pytest.mark.parametrize("presenter", ["kai", "kaia"])
@pytest.mark.parametrize("overrides,environment", CASES)
def test_workout_and_direct_interpretation_parity_and_determinism(client, overrides, environment, presenter):
    data = payload(overrides, environment, presenter)
    body = post(client, data)
    workout_response = client.post("/api/v1/workout", json={
        "training": data["training"], "environment": environment,
    }, headers=HEADERS)
    assert workout_response.status_code == 200
    workout = workout_response.json()
    assert set(workout) == {"recommendation", "workout", "versions"}
    assert body["recommendation"] == workout["recommendation"]
    assert body["workout"] == workout["workout"]
    args = direct_bundle(data)
    core = (present_kai if presenter == "kai" else present_kaia)(*args)
    # Independent projection: do not use the new mapper as the parity oracle.
    assert body["interpretation"] == core.model_dump(mode="json", exclude=PROVENANCE)
    assert body["versions"] == workout["versions"] | {"interpretation_version": core.interpretation_version}
    assert post(client, data) == body
    assert not re.search(r"diagn[oó]stic|hormon|lesion|fertilidad|tratamiento médico", wording(body["interpretation"]))


def test_normal_kai(client):
    body = post(client, payload())
    assert body["recommendation"]["action"] == "train"
    assert body["workout"]["plan_status"] == "generated"
    assert body["workout"]["selector_status"] == "complete"
    assert body["workout"]["exercises"]
    out = body["interpretation"]
    assert (out["presenter"], out["session"], out["intensity"], out["duration_minutes"]) == ("kai", "full_body", "high", 45)
    assert out["cycle_insight"] is None
    assert all(out[field] for field in ("title", "summary", "today_plan", "avatar_message"))


@pytest.mark.parametrize("phase", ["menstruation", "follicular", "ovulation", "luteal"])
def test_normal_kaia_phase_alone_safety_and_presenter_parity(client, phase):
    overrides = {"sex": "female", "cycle_context": {"phase": phase, "discomfort": "none"}}
    kaia = post(client, payload(overrides, presenter="kaia"))
    kai = post(client, payload(overrides))
    no_cycle = post(client, payload({"sex": "female"}, presenter="kaia"))
    for key in ("recommendation", "workout", "versions"):
        assert kaia[key] == kai[key] == no_cycle[key]
    assert no_cycle["interpretation"]["cycle_insight"] is None
    assert kai["interpretation"]["cycle_insight"] is None
    assert kaia["interpretation"]["cycle_insight"]
    assert "no tienes molestias" in kaia["interpretation"]["cycle_insight"]
    assert kaia["interpretation"]["action"] == "train"
    assert kaia["interpretation"]["intensity"] == "high"
    assert not re.search(r"reduc|recuperación|descans|capacidad", kaia["interpretation"]["cycle_insight"])
    assert {k: v for k, v in kaia["interpretation"].items() if k not in {"presenter", "cycle_insight"}} == {
        k: v for k, v in kai["interpretation"].items() if k not in {"presenter", "cycle_insight"}}


def test_high_cycle_discomfort_and_kai_cycle_context(client):
    kaia = post(client, payload(HIGH_CYCLE, presenter="kaia"))
    kai = post(client, payload(HIGH_CYCLE))
    assert kaia["recommendation"] == kai["recommendation"]
    assert kaia["workout"] == kai["workout"]
    out = kaia["interpretation"]
    assert (out["action"], out["session"], out["intensity"]) == ("recovery", "mobility", "low")
    assert "CYCLE_HIGH_DISCOMFORT" in out["reason_codes"]
    assert "Por las molestias reportadas, el motor ha indicado recuperación." in out["cycle_insight"]
    assert kai["interpretation"]["cycle_insight"] is None


def test_rest_has_no_substitute_workout(client):
    body = post(client, payload({"fatigue_level": 5}))
    work, out = body["workout"], body["interpretation"]
    assert work["plan_status"] == work["selector_status"] == "no_workout"
    assert work["exercises"] == work["unresolved_slots"] == []
    assert (out["action"], out["tone"], out["duration_minutes"]) == ("rest", "rest", 0)
    assert out["today_plan"] == "No hay una sesión activa programada para hoy."
    assert not re.search(r"movilidad|recuperación activa|alternativa|sustitut", wording(out))


def test_recent_session_recovery(client):
    out = post(client, payload(RECENT))["interpretation"]
    assert (out["action"], out["session"], out["intensity"]) == ("recovery", "mobility", "low")
    assert 0 < out["duration_minutes"] <= 20


def test_unknown_history_preserves_uncertainty(client):
    out = post(client, payload(UNKNOWN))["interpretation"]
    assert out["needs_more_data"] is True
    assert "INSUFFICIENT_DATA" in out["reason_codes"]
    assert out["missing_data_message"]
    for code in ("INSUFFICIENT_RECOVERY", "RECOVERY_WINDOW_OK"):
        assert code not in out["reason_codes"]
        assert translate_reason(code).lower() not in wording(out)


def test_beginner(client):
    body = post(client, payload({"training_level": "beginner"}))
    assert body["interpretation"]["intensity"] != "high"
    assert "BEGINNER_INTENSITY_LIMIT" in body["interpretation"]["reason_codes"]
    assert body["workout"]["exercises"]
    for slot in body["workout"]["exercises"]:
        assert "beginner" in exercise_library.get_exercise_by_id(slot["exercise_id"]).training_levels


@pytest.mark.parametrize("goal,session", [("endurance", "cardio"), ("mobility", "mobility")])
def test_goal(client, goal, session):
    assert post(client, payload({"goal": goal}))["interpretation"]["session"] == session


def test_missing_environment(client):
    data = payload()
    del data["environment"]
    body = post(client, data)
    assert body == post(client, payload(environment=None))
    assert body["recommendation"]["action"] == "train"
    assert body["workout"]["selector_status"] == "incomplete"
    assert body["workout"]["exercises"] == []
    assert body["workout"]["unresolved_slots"]
    assert "Falta indicar" in body["interpretation"]["environment_message"]


@pytest.mark.parametrize("location", ["gym", "home"])
def test_empty_equipment_is_known_and_does_not_imply_bodyweight(client, location):
    body = post(client, payload(environment={"training_location": location, "available_equipment": []}))
    assert body["workout"]["selector_status"] == "incomplete"
    assert body["workout"]["exercises"] == []
    assert body["workout"]["unresolved_slots"]
    assert all(s["reason_codes"] == ["EQUIPMENT_NOT_AVAILABLE"] for s in body["workout"]["unresolved_slots"])
    message = body["interpretation"]["environment_message"]
    assert "no dispones de equipamiento" in message
    assert "Falta indicar" not in message
    assert body != post(client, payload(environment=None))


def test_partial_equipment(client):
    body = post(client, payload(environment=PARTIAL))
    assert body["workout"]["selector_status"] == "incomplete"
    assert body["workout"]["exercises"] and body["workout"]["unresolved_slots"]
    assert "Parte de la sesión" in body["interpretation"]["environment_message"]
    for slot in body["workout"]["exercises"]:
        assert set(exercise_library.get_exercise_by_id(slot["exercise_id"]).equipment) <= {"barbell"}


@pytest.mark.parametrize("presenter", ["kai", "kaia"])
@pytest.mark.parametrize("environment", [None, {}, {"training_location": "gym"},
    {"training_location": "home"}, {"training_location": "gym", "available_equipment": None},
    {"available_equipment": ["barbell"]}, EMPTY, PARTIAL, GYM])
def test_one_orchestration_and_engine_execution_shared_identity_and_no_mutation(client, monkeypatch, presenter, environment):
    real_orchestrate = workout_orchestrator.orchestrate_workout
    real_presenter = present_kai if presenter == "kai" else present_kaia
    calls = []
    observed = {}

    def track_orchestrate(request, env):
        calls.append("orchestrate")
        observed["inputs"] = (request, env)
        observed["inputs_before"] = deepcopy((request, env))
        result = real_orchestrate(request, env)
        observed["result"] = result
        observed["before"] = result.model_dump(mode="json")
        return result

    def track_mapping(result):
        calls.append("workout_mapping")
        assert result is observed["result"]
        return to_workout_api_response(result)

    def track_presenter(request, result, env):
        calls.append("presenter")
        assert result is observed["result"]
        assert request is observed["inputs"][0] and env is observed["inputs"][1]
        return real_presenter(request, result, env)

    engine = Mock(wraps=training_engine.evaluate)
    monkeypatch.setattr(training_engine, "evaluate", engine)
    monkeypatch.setattr(workout_orchestrator, "orchestrate_workout", track_orchestrate)
    monkeypatch.setattr(route, "to_workout_api_response", track_mapping)
    monkeypatch.setattr(route, "present_" + presenter, track_presenter)
    post(client, payload(CYCLE, environment, presenter))
    assert calls == ["orchestrate", "workout_mapping", "presenter"]
    engine.assert_called_once()
    assert observed["result"].model_dump(mode="json") == observed["before"]
    assert observed["inputs"] == observed["inputs_before"]
    env = observed["inputs"][1]
    if environment is None:
        assert env is None
    else:
        equipment = environment.get("available_equipment")
        assert env.available_equipment == (None if equipment is None else frozenset(equipment))
        assert env.training_location == environment.get("training_location")


@pytest.mark.parametrize("key", [None, "", "wrong-key"])
def test_authentication_blocks_orchestration(client, monkeypatch, key):
    spy = Mock(side_effect=AssertionError("Authentication must stop the pipeline"))
    monkeypatch.setattr(workout_orchestrator, "orchestrate_workout", spy)
    response = client.post(ENDPOINT, json=payload({"user_id": "private-marker"}),
                           headers={} if key is None else {"X-API-Key": key})
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key."}
    assert HEADERS["X-API-Key"] not in response.text
    assert "private-marker" not in response.text and "IBUUM_API_KEY" not in response.text
    spy.assert_not_called()


@pytest.mark.parametrize("data", [
    {k: v for k, v in payload().items() if k != "presenter"},
    *[payload(presenter=p) for p in ("invalid", "Kai", "KAIA", "", None, 1)],
    payload({"goal": "invalid"}), payload({"training_level": "invalid"}),
    payload({"user_id": "name@example.com"}), payload({"age": 9}),
    payload({"fatigue_level": 6}), payload({"training_days_per_week": 8}),
    payload(environment={"available_equipment": ["invalid"]}),
    payload(environment={"training_location": "invalid"}),
    payload(environment={"training_level": "advanced"}),
    payload(environment={"extra": True}),
    payload(environment={"available_equipment": "bodyweight"}),
    payload() | {"extra": True}, payload() | {"training": None}, {}, [],
    *[payload() | {key: "override"} for key in ("versions", "action", "session", "intensity", "duration_minutes", "reason_codes")],
])
def test_request_validation(client, data):
    assert client.post(ENDPOINT, json=data, headers=HEADERS).status_code == 422


def test_malformed_json(client):
    assert client.post(ENDPOINT, content="{", headers=HEADERS | {"Content-Type": "application/json"}).status_code == 422


@pytest.mark.parametrize("method", ["get", "put", "patch", "delete", "head"])
def test_post_only(client, method):
    assert getattr(client, method)(ENDPOINT, headers=HEADERS).status_code == 405


def test_request_sequence_isolation(client):
    data = payload()
    before = deepcopy(data)
    catalog = [e.model_dump() for e in exercise_library.list_exercises()]
    normal = post(client, data)
    post(client, payload(CYCLE, presenter="kaia"))
    post(client, payload({"fatigue_level": 5}))
    assert post(client, data) == normal
    assert data == before
    assert [e.model_dump() for e in exercise_library.list_exercises()] == catalog


def test_mapper_defensive_values_and_version_sources():
    request, result, env = direct_bundle(payload(environment=PARTIAL))
    result.recommendation.agent_version = "agent-sentinel"
    result.selected_workout.source_plan.generator_version = "generator-sentinel"
    result.selected_workout.selector_version = "selector-sentinel"
    result.orchestrator_version = "orchestrator-sentinel"
    for slot in result.selected_workout.selected_slots + result.selected_workout.unresolved_slots:
        slot.source_slot.notes = ["preserved note"]
    core = present_kai(request, result, env)
    workout = to_workout_api_response(result)
    before = deepcopy((result, core, workout))
    public = to_interpretation_api_response(workout, core)
    assert public.versions.model_dump() == workout.versions.model_dump() | {"interpretation_version": core.interpretation_version}
    public.recommendation.reason_codes.clear()
    public.workout.generator_reason_codes.clear()
    public.interpretation.reasons.clear()
    public.interpretation.reason_codes.clear()
    for slot in public.workout.exercises + public.workout.unresolved_slots:
        slot.notes.clear()
    public.workout.exercises.clear()
    public.workout.unresolved_slots.clear()
    assert (result, core, workout) == before


def test_public_dtos_forbid_extra_fields(client):
    body = post(client, payload())
    for model, data in [(InterpretationApiRequest, payload()),
                        (InterpretationApiPayload, body["interpretation"]),
                        (InterpretationVersionsApiResponse, body["versions"]),
                        (InterpretationApiResponse, body)]:
        with pytest.raises(ValidationError):
            model.model_validate(data | {"internal": "forbidden"})


def test_openapi_public_boundary():
    schema = app.openapi()
    assert set(schema["paths"]) == {"/health", "/api/v1/training/recommendation", "/api/v1/workout", ENDPOINT}
    assert set(schema["paths"][ENDPOINT]) == {"post"}
    operation = schema["paths"][ENDPOINT]["post"]
    assert operation["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith("/InterpretationApiRequest")
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("/InterpretationApiResponse")
    assert any(p["name"] == "x-api-key" and p["in"] == "header" for p in operation["parameters"])
    schemas = schema["components"]["schemas"]
    assert not {"InterpretationResult", "WorkoutOrchestrationResult", "SelectedWorkoutPlan", "WorkoutPlan",
                "MovementSlot", "SelectedExerciseSlot", "ExerciseSelectorContext", "WorkoutEnvironmentContext"}.intersection(schemas)
    assert "source_plan" not in str(schema) and "source_slot" not in str(schema)
    assert not PROVENANCE.intersection(schemas["InterpretationApiPayload"]["properties"])
    assert set(schemas["InterpretationApiPayload"]["properties"]) == INTERPRETATION_KEYS
    assert set(schemas["InterpretationVersionsApiResponse"]["properties"]) == VERSION_KEYS
    assert schemas["InterpretationApiRequest"]["properties"]["training"]["$ref"].endswith("/TrainingRecommendationRequest")
    for name in ("InterpretationApiRequest", "InterpretationApiPayload", "InterpretationApiResponse",
                 "InterpretationVersionsApiResponse", "WorkoutEnvironmentApiRequest"):
        assert schemas[name]["additionalProperties"] is False


def test_new_adapter_imports_only_approved_boundaries():
    root = Path(__file__).resolve().parents[1]
    allowed = {"fastapi", "app.core.security", "app.models.interpretation_api", "app.models.interpretation",
               "app.models.workout_api", "app.services", "app.services.interpretation_api_mapper",
               "app.services.kai_presenter", "app.services.kaia_presenter", "app.services.workout_api_mapper"}
    for name in ("app/api/routes/interpretation.py", "app/services/interpretation_api_mapper.py"):
        tree = ast.parse((root / name).read_text(encoding="utf-8"))
        assert not any(isinstance(node, ast.Import) for node in ast.walk(tree))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.module in allowed
                if node.module == "app.services":
                    assert [alias.name for alias in node.names] == ["workout_orchestrator"]


def test_legacy_recommendation_and_health_unchanged(client):
    data = payload()["training"]
    response = client.post("/api/v1/training/recommendation", json=data, headers=HEADERS)
    assert response.status_code == 200
    assert response.json() == training_engine.evaluate(TrainingRecommendationRequest(**data)).model_dump(mode="json")
    settings = get_settings()
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": settings.service_name, "version": settings.agent_version}
