import inspect
from dataclasses import asdict, fields

from app.models.training_request import TrainingRecommendationRequest
from app.models.training_response import ReasonCode
from app.services.cycle_context import NormalizedCycleContext, normalize_cycle_context


def _request(**overrides) -> TrainingRecommendationRequest:
    payload = {
        "age": 30,
        "sex": "female",
        "height_cm": 168.0,
        "weight_kg": 62.0,
        "goal": "general_fitness",
        "training_level": "intermediate",
        "training_days_per_week": 4,
        "fatigue_level": 2,
        "last_session_type": "unknown",
        "hours_since_last_session": 48,
    }
    payload.update(overrides)
    return TrainingRecommendationRequest(**payload)


def _normalize(**overrides):
    return normalize_cycle_context(_request(**overrides))


def test_cycle_context_normalization_is_empty_when_absent():
    normalized = _normalize()
    assert normalized.available is False
    assert normalized.reason_codes == ()
    assert normalized.requires_more_data is False


def test_cycle_context_missing_discomfort_is_marked_incomplete():
    normalized = _normalize(cycle_context={"phase": "menstruation"})
    assert normalized.available is True
    assert normalized.phase.value == "menstruation"
    assert normalized.discomfort is None
    assert normalized.is_complete is False
    assert normalized.requires_more_data is True
    assert normalized.reason_codes == (ReasonCode.CYCLE_CONTEXT_INCOMPLETE,)


def test_cycle_context_moderate_discomfort_is_a_conservative_signal():
    normalized = _normalize(cycle_context={"phase": "menstruation", "discomfort": "moderate"})
    assert normalized.phase.value == "menstruation"
    assert normalized.discomfort.value == "moderate"
    assert normalized.reason_codes == (ReasonCode.CYCLE_MODERATE_DISCOMFORT,)


def test_cycle_context_high_discomfort_is_normalized_without_deciding_training():
    normalized = _normalize(cycle_context={"phase": "luteal", "discomfort": "high"})
    assert normalized.phase.value == "luteal"
    assert normalized.discomfort.value == "high"
    assert normalized.reason_codes == (ReasonCode.CYCLE_HIGH_DISCOMFORT,)


def test_cycle_context_module_exposes_no_decision_bearing_fields():
    field_names = {field.name for field in fields(NormalizedCycleContext)}
    assert "action" not in field_names
    assert "recommended_session" not in field_names
    assert "intensity_ceiling" not in field_names
    assert "duration_ceiling" not in field_names


def test_cycle_context_normalization_is_deterministic():
    first = _normalize(cycle_context={"phase": "menstruation", "discomfort": "moderate"})
    second = _normalize(cycle_context={"phase": "menstruation", "discomfort": "moderate"})
    assert first == second


def test_cycle_context_output_is_minimal_and_privacy_safe():
    normalized = _normalize(cycle_context={"phase": "menstruation", "discomfort": "mild"})
    assert set(asdict(normalized).keys()) == {
        "available",
        "phase",
        "discomfort",
        "is_complete",
        "requires_more_data",
        "reason_codes",
    }


def test_cycle_context_module_does_not_import_logging_or_store_payloads():
    source = inspect.getsource(inspect.getmodule(normalize_cycle_context))
    assert "import logging" not in source
    assert "logger =" not in source
