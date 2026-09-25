"""Narrow backend contract lock for the future Base44 bridge; no external calls."""

import os
from typing import get_args

os.environ.setdefault("IBUUM_API_KEY", "test-secret-key")

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.models.interpretation_api import InterpretationApiRequest
from app.models.training_request import TrainingRecommendationRequest
from app.models.workout_api import WorkoutEnvironmentApiRequest


ENDPOINT = "/api/v1/interpretation"
INTERPRETATION_FIELDS = {
    "presenter", "tone", "action", "session", "intensity", "duration_minutes",
    "needs_more_data", "title", "summary", "reasons", "today_plan",
    "avatar_message", "missing_data_message", "environment_message",
    "cycle_insight", "reason_codes", "interpretation_version",
}
VERSION_FIELDS = {
    "agent_version", "generator_version", "selector_version",
    "orchestrator_version", "interpretation_version",
}


def request_data():
    return {
        "presenter": "kai",
        "training": {
            "age": 30, "sex": "male", "height_cm": 178, "weight_kg": 80,
            "goal": "strength", "training_level": "intermediate",
            "training_days_per_week": 4, "fatigue_level": 1,
        },
    }


def test_public_routes_and_interpretation_operation():
    paths = app.openapi()["paths"]
    assert set(paths) == {
        "/health", "/api/v1/training/recommendation", "/api/v1/workout", ENDPOINT,
    }
    assert set(paths[ENDPOINT]) == {"post"}
    operation = paths[ENDPOINT]["post"]
    assert operation["requestBody"]["required"] is True
    assert operation["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/InterpretationApiRequest",
    }
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/InterpretationApiResponse",
    }
    # FastAPI represents this dependency as a lowercase header parameter,
    # not an OpenAPI security scheme. HTTP header names are case-insensitive.
    assert any(p["in"] == "header" and p["name"].lower() == "x-api-key"
               for p in operation["parameters"])


def test_request_properties_and_existing_model_reuse():
    schema = app.openapi()["components"]["schemas"]["InterpretationApiRequest"]
    assert set(schema["properties"]) == {"presenter", "training", "environment"}
    assert set(schema["required"]) == {"presenter", "training"}
    assert schema["properties"]["presenter"]["enum"] == ["kai", "kaia"]
    assert schema["properties"]["training"] == {
        "$ref": "#/components/schemas/TrainingRecommendationRequest",
    }
    assert schema["properties"]["environment"]["anyOf"] == [
        {"$ref": "#/components/schemas/WorkoutEnvironmentApiRequest"}, {"type": "null"},
    ]
    fields = InterpretationApiRequest.model_fields
    assert fields["training"].annotation is TrainingRecommendationRequest
    assert set(get_args(fields["environment"].annotation)) == {
        WorkoutEnvironmentApiRequest, type(None),
    }


@pytest.mark.parametrize("presenter", ["kai", "kaia"])
def test_explicit_presenters_accepted(presenter):
    assert InterpretationApiRequest.model_validate(
        request_data() | {"presenter": presenter}
    ).presenter == presenter


@pytest.mark.parametrize("presenter", ["Kai", "KAIA", "other", "", None, 1])
def test_other_presenters_rejected(presenter):
    with pytest.raises(ValidationError):
        InterpretationApiRequest.model_validate(request_data() | {"presenter": presenter})


def test_missing_presenter_rejected():
    data = request_data()
    del data["presenter"]
    with pytest.raises(ValidationError):
        InterpretationApiRequest.model_validate(data)


def test_public_response_properties_and_internal_boundary():
    schema = app.openapi()
    schemas = schema["components"]["schemas"]
    response = schemas["InterpretationApiResponse"]
    public_models = {
        "recommendation": "TrainingRecommendationResponse",
        "workout": "WorkoutApiPayload",
        "interpretation": "InterpretationApiPayload",
        "versions": "InterpretationVersionsApiResponse",
    }
    assert set(response["properties"]) == set(response["required"]) == set(public_models)
    for field, model in public_models.items():
        assert response["properties"][field] == {"$ref": f"#/components/schemas/{model}"}
    for model, expected in (
        ("InterpretationApiPayload", INTERPRETATION_FIELDS),
        ("InterpretationVersionsApiResponse", VERSION_FIELDS),
    ):
        assert set(schemas[model]["properties"]) == expected
        assert set(schemas[model]["required"]) == expected
        assert schemas[model]["additionalProperties"] is False
    assert not {
        "InterpretationResult", "WorkoutOrchestrationResult", "SelectedWorkoutPlan",
        "WorkoutPlan", "MovementSlot", "SelectedExerciseSlot", "ExerciseSelectorContext",
        "WorkoutEnvironmentContext",
    }.intersection(schemas)
    assert "source_plan" not in str(schema)
    assert "source_slot" not in str(schema)


def test_request_and_environment_reject_extra_fields():
    schemas = app.openapi()["components"]["schemas"]
    for model in ("InterpretationApiRequest", "WorkoutEnvironmentApiRequest"):
        assert schemas[model]["additionalProperties"] is False
    with pytest.raises(ValidationError):
        InterpretationApiRequest.model_validate(request_data() | {"action": "rest"})
    with pytest.raises(ValidationError):
        InterpretationApiRequest.model_validate(
            request_data() | {"environment": {"training_level": "advanced"}}
        )


def test_environment_unknown_null_and_empty_are_not_collapsed():
    omitted = InterpretationApiRequest.model_validate(request_data())
    null = InterpretationApiRequest.model_validate(request_data() | {"environment": None})
    assert omitted.environment is null.environment is None
    for environment in ({}, {"available_equipment": None}, {"training_location": "home"}):
        parsed = InterpretationApiRequest.model_validate(request_data() | {"environment": environment})
        assert parsed.environment is not None
        assert parsed.environment.available_equipment is None
    empty = InterpretationApiRequest.model_validate(
        request_data() | {"environment": {"available_equipment": []}}
    )
    assert empty.environment.available_equipment == []


@pytest.mark.parametrize("headers", [{}, {"X-API-Key": ""}, {"X-API-Key": "contract-invalid-key"}])
def test_runtime_authentication_required(headers):
    with TestClient(app) as client:
        response = client.post(ENDPOINT, json=request_data(), headers=headers)
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key."}
