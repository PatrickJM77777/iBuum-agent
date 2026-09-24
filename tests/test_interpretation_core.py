"""Real-pipeline acceptance plus isolated explanation safety boundaries."""

from copy import deepcopy
import os
import re

import pytest
from pydantic import ValidationError

os.environ.setdefault("IBUUM_API_KEY", "test-secret-key")

from app.main import app
from app.models.exercise import ExerciseEquipment
from app.models.exercise_selection import SelectionReasonCode
from app.models.interpretation import InterpretationResult
from app.models.training_request import CyclePhase, TrainingRecommendationRequest
from app.models.training_response import ReasonCode
from app.models.workout_orchestration import WorkoutEnvironmentContext
from app.services import exercise_library
from app.services.interpretation_core import REASON_TRANSLATIONS, UNKNOWN_REASON, translate_reason
from app.services.kai_presenter import present_kai
from app.services.kaia_presenter import present_kaia
from app.services.workout_orchestrator import orchestrate_workout


def bundle(overrides=None, equipment=tuple(ExerciseEquipment), location="gym"):
    request = TrainingRecommendationRequest(**(dict(
        age=30, sex="male", height_cm=178, weight_kg=80, goal="strength",
        training_level="intermediate", training_days_per_week=4, fatigue_level=1,
    ) | (overrides or {})))
    environment = WorkoutEnvironmentContext(available_equipment=equipment, training_location=location)
    return request, orchestrate_workout(request, environment), environment


def text(output):
    return " ".join([output.title, output.summary, *output.reasons, output.today_plan,
                     output.avatar_message, output.missing_data_message or "",
                     output.environment_message or "", output.cycle_insight or ""]).lower()


SCENARIOS = [
    {}, {"fatigue_level": 5}, {"fatigue_level": 3}, {"fatigue_level": 4},
    {"last_session_type": "full_body", "hours_since_last_session": 12},
    {"last_session_type": "unknown", "hours_since_last_session": 12},
    {"training_level": "beginner"}, {"goal": "endurance"}, {"goal": "mobility"},
    {"training_days_per_week": 2}, {"training_days_per_week": 6},
    *[{"sex": "female", "cycle_context": {"phase": p.value, "discomfort": d}}
      for p in CyclePhase for d in ("none", "mild", "moderate", "high")],
    {"sex": "female", "cycle_context": {"phase": "menstruation"}},
]


@pytest.mark.parametrize("overrides", SCENARIOS)
def test_parity_determinism_immutability_and_safety(overrides):
    args = bundle(overrides)
    before = deepcopy(args)
    catalog = [e.model_dump() for e in exercise_library.list_exercises()]
    kai, kaia = present_kai(*args), present_kaia(*args)
    rec = args[1].recommendation
    assert kai.model_dump(exclude={"presenter", "cycle_insight"}) == kaia.model_dump(exclude={"presenter", "cycle_insight"})
    for output in (kai, kaia):
        assert (output.action, output.session, output.intensity, output.duration_minutes) == (
            rec.action, rec.recommended_session, rec.intensity, rec.duration_minutes)
        assert output.reason_codes == tuple(c.value for c in rec.reason_codes)
        assert output.needs_more_data == rec.needs_more_data
        assert output.title and output.summary and output.today_plan and output.reasons
        assert not re.search(r"diagn[oó]stic|hormon|lesion|microlesion|inflamad|tratamiento médico|fertilidad|no puedes entrenar", text(output))
        if "INSUFFICIENT_RECOVERY" not in output.reason_codes:
            assert translate_reason("INSUFFICIENT_RECOVERY").lower() not in text(output)
        if "RECOVERY_WINDOW_OK" not in output.reason_codes:
            assert translate_reason("RECOVERY_WINDOW_OK").lower() not in text(output)
    assert kai.cycle_insight is None
    for _ in range(3):
        assert present_kai(*args).model_dump_json() == kai.model_dump_json()
        assert present_kaia(*args).model_dump_json() == kaia.model_dump_json()
    assert args == before
    assert [e.model_dump() for e in exercise_library.list_exercises()] == catalog


@pytest.mark.parametrize("present", [present_kai, present_kaia])
def test_normal(present):
    output = present(*bundle())
    assert (output.tone, output.action, output.session, output.intensity, output.duration_minutes) == (
        "training", "train", "full_body", "high", 45)
    assert "45 minutos de cuerpo completo a intensidad alta" in output.today_plan
    assert output.cycle_insight is None


def test_rest_never_invents_active_work():
    output = present_kaia(*bundle({"fatigue_level": 5, "sex": "female",
        "cycle_context": {"phase": "menstruation", "discomfort": "high"}}))
    assert (output.tone, output.action, output.session, output.duration_minutes) == ("rest", "rest", "rest", 0)
    assert output.today_plan == "No hay una sesión activa programada para hoy."
    assert not re.search(r"movilidad|ejercicios|alternativa|recuperación", text(output))


def test_recovery():
    output = present_kai(*bundle({"last_session_type": "full_body", "hours_since_last_session": 12}))
    assert (output.tone, output.action, output.session, output.intensity) == ("recovery", "recovery", "mobility", "low")
    assert 0 < output.duration_minutes <= 20
    assert translate_reason("INSUFFICIENT_RECOVERY") in output.reasons


@pytest.mark.parametrize("overrides,session", [({"training_level": "beginner"}, "full_body"),
    ({"goal": "endurance"}, "cardio"), ({"goal": "mobility"}, "mobility")])
def test_level_and_goal(overrides, session):
    output = present_kai(*bundle(overrides))
    assert output.session == session
    if "training_level" in overrides:
        assert output.intensity != "high"
        assert not re.search(r"avanzad|agresiv|maxim|máxim", text(output))


@pytest.mark.parametrize("equipment,location,expected", [
    (None, None, "Falta indicar"), ([], "gym", "no dispones de equipamiento"),
    (["barbell"], "gym", "Parte de la sesión"),
    ([], None, "no dispones de equipamiento"),
])
def test_environment(equipment, location, expected):
    args = bundle(equipment=equipment, location=location)
    before = deepcopy(args)
    output = present_kai(*args)
    assert output.tone == "incomplete"
    assert expected in output.environment_message
    assert "bodyweight" not in text(output) and "peso corporal" not in text(output)
    if equipment == []:
        assert "qué equipamiento" not in output.environment_message
    if equipment == ["barbell"]:
        assert args[1].selected_workout.selected_slots and args[1].selected_workout.unresolved_slots
    assert args == before


def test_absent_environment():
    request, _, _ = bundle()
    output = present_kai(request, orchestrate_workout(request))
    assert "dónde entrenas" in output.environment_message
    assert "qué equipamiento" in output.environment_message


def test_unknown_history_is_uncertainty_not_recovery_evidence():
    output = present_kai(*bundle({"last_session_type": "unknown", "hours_since_last_session": 12}))
    assert output.needs_more_data and output.missing_data_message
    assert output.tone == "incomplete"
    assert "INSUFFICIENT_DATA" in output.reason_codes
    assert "recuperación" not in text(output)


@pytest.mark.parametrize("phase", list(CyclePhase))
@pytest.mark.parametrize("discomfort", ["none", "mild"])
def test_phase_alone_never_implies_reduction(phase, discomfort):
    base = present_kaia(*bundle({"sex": "female"}))
    output = present_kaia(*bundle({"sex": "female", "cycle_context": {
        "phase": phase, "discomfort": discomfort}}))
    assert output.model_dump(exclude={"cycle_insight"}) == base.model_dump(exclude={"cycle_insight"})
    assert output.cycle_insight
    assert not re.search(r"reduc|baja|limit|capacidad|adapt|impide|recuperación", output.cycle_insight)


@pytest.mark.parametrize("discomfort,action", [("moderate", "train"), ("high", "recovery")])
def test_reported_discomfort(discomfort, action):
    args = bundle({"sex": "female", "cycle_context": {"phase": "menstruation", "discomfort": discomfort}})
    output = present_kaia(*args)
    assert output.action == action
    assert "molestias" in output.cycle_insight
    assert "por la fase" not in output.cycle_insight.lower()
    if discomfort == "high":
        assert output.session == "mobility" and output.intensity == "low"
        assert output.duration_minutes == args[1].recommendation.duration_minutes
        assert "Por las molestias reportadas" in output.cycle_insight
    else:
        assert output.intensity == "moderate" and output.duration_minutes == 35


def test_omitted_discomfort_is_not_defaulted_to_reported_none():
    output = present_kaia(*bundle({"sex": "female", "cycle_context": {"phase": "menstruation"}}))
    assert output.needs_more_data and output.missing_data_message
    assert "No has indicado el nivel" in output.cycle_insight
    assert "no tienes molestias" not in output.cycle_insight


@pytest.mark.parametrize("code", list(ReasonCode) + list(SelectionReasonCode) + [
    "REST_DAY", "ENGINE_REQUESTED_MORE_DATA", "UNSUPPORTED_SESSION_TYPE",
    "INSUFFICIENT_GENERATOR_INPUT", "ENGINE_NEEDS_MORE_DATA",
])
def test_all_existing_reason_codes_have_explicit_translations(code):
    assert code in REASON_TRANSLATIONS
    assert translate_reason(code) != UNKNOWN_REASON


def test_unknown_reason_preserved_without_invented_meaning():
    request, result, env = bundle()
    # Simulate a future upstream enum without weakening the existing DTO.
    result.recommendation = result.recommendation.model_copy(update={"reason_codes": ["FUTURE_SIGNAL"]})
    result.selected_workout.source_plan.generator_reason_codes.append("FUTURE_GENERATOR")
    result.selected_workout.selected_slots[0].reason_codes.append("FUTURE_SELECTOR")
    output = present_kai(request, result, env)
    assert output.reason_codes == ("FUTURE_SIGNAL",)
    assert "FUTURE_GENERATOR" in output.generator_reason_codes
    assert "FUTURE_SELECTOR" in output.selected_reason_codes[0]
    assert UNKNOWN_REASON in output.reasons
    assert "FUTURE_SIGNAL" not in text(output)


def test_strict_frozen_result_and_no_shared_mutable_collections():
    args = bundle()
    output = present_kai(*args)
    with pytest.raises(ValidationError):
        output.title = "changed"
    with pytest.raises(ValidationError):
        InterpretationResult(**(output.model_dump() | {"unexpected": True}))
    with pytest.raises(ValidationError):
        InterpretationResult(**(output.model_dump() | {"duration_minutes": "45"}))
    with pytest.raises(ValidationError):
        InterpretationResult(**(output.model_dump() | {"interpretation_version": "v2"}))
    assert isinstance(output.reasons, tuple)
    args[1].recommendation.reason_codes.clear()
    args[1].selected_workout.selected_slots.clear()
    assert output.reason_codes and output.selected_reason_codes


def test_no_policy_execution_during_interpretation(monkeypatch):
    args = bundle()
    def forbidden(*args, **kwargs):
        raise AssertionError("Interpretation must only read the supplied result")
    for module, name in [("training_engine", "evaluate"), ("workout_generator", "generate_workout_plan"),
                         ("exercise_selector", "select_exercises"), ("workout_orchestrator", "orchestrate_workout")]:
        monkeypatch.setattr(f"app.services.{module}.{name}", forbidden)
    assert present_kai(*args).action == "train"
    assert present_kaia(*args).action == "train"


def test_openapi_unchanged():
    schema = app.openapi()
    assert set(schema["paths"]) == {"/health", "/api/v1/training/recommendation", "/api/v1/workout", "/api/v1/interpretation"}
    assert "InterpretationResult" not in schema["components"]["schemas"]


def test_approved_request_more_data_is_not_presented_as_active_training():
    from app.models.training_response import Action, Intensity, RecommendedSession
    from app.models.exercise_selection import ExerciseSelectionStatus

    request, result, env = bundle()
    result.recommendation = result.recommendation.model_copy(update={
        "action": Action.request_more_data, "recommended_session": RecommendedSession.not_applicable,
        "intensity": Intensity.not_applicable, "duration_minutes": 0,
        "needs_more_data": True, "reason_codes": [ReasonCode.INSUFFICIENT_DATA],
    })
    result.selected_workout.selector_status = ExerciseSelectionStatus.more_data_required
    output = present_kai(request, result, env)
    assert output.action == "request_more_data" and output.tone == "incomplete"
    assert output.missing_data_message
    assert "pendiente" in output.today_plan
    assert "minutos" not in output.today_plan
