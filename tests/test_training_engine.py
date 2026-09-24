import os

import pytest

# Configure the test key before importing the application and its settings.
os.environ.setdefault("IBUUM_API_KEY", "test-secret-key")

from fastapi.testclient import TestClient

from app.main import app
from app.models.training_request import CycleDiscomfort, TrainingRecommendationRequest
from app.models.training_response import (
    Action,
    Intensity,
    ReasonCode,
    RecommendedSession,
    TrainingRecommendationResponse,
)
from app.services.cycle_context import NormalizedCycleContext
from app.services import training_rules
from app.services.training_engine import TrainingEngine

client = TestClient(app)
engine = TrainingEngine()


def _base_payload(**overrides) -> dict:
    payload = {
        "age": 30,
        "sex": "male",
        "height_cm": 178.0,
        "weight_kg": 80.0,
        "goal": "general_fitness",
        "training_level": "intermediate",
        "training_days_per_week": 4,
        "fatigue_level": 2,
        "last_session_type": "unknown",
        "hours_since_last_session": 48,
    }
    payload.update(overrides)
    return payload


def _request(**overrides) -> TrainingRecommendationRequest:
    return TrainingRecommendationRequest(**_base_payload(**overrides))


def test_engine_orchestrates_normal_training_request():
    result = engine.evaluate(_request())
    assert result.action == Action.train


def test_engine_preserves_fatigue_priority():
    result = engine.evaluate(_request(goal="strength", fatigue_level=5))
    assert result.action == Action.rest


def test_engine_preserves_recovery_priority():
    result = engine.evaluate(
        _request(
            sex="female",
            goal="strength",
            fatigue_level=1,
            cycle_context={"phase": "menstruation", "discomfort": "high"},
        )
    )
    assert result.action == Action.recovery
    assert result.intensity != Intensity.high


def test_engine_preserves_beginner_ceiling():
    result = engine.evaluate(
        _request(training_level="beginner", goal="strength", fatigue_level=1)
    )
    assert result.intensity == Intensity.moderate


def test_engine_intermediate_high_intensity_conditions():
    result = engine.evaluate(
        _request(
            training_level="intermediate",
            goal="strength",
            fatigue_level=1,
            last_session_type="unknown",
        )
    )
    assert result.intensity == Intensity.high


def test_cycle_phase_alone_does_not_reduce_training():
    baseline = engine.evaluate(_request(sex="female"))
    cycle_none = engine.evaluate(
        _request(sex="female", cycle_context={"phase": "menstruation", "discomfort": "none"})
    )
    assert cycle_none == baseline


def test_high_cycle_discomfort_can_constrain_training():
    result = engine.evaluate(
        _request(sex="female", cycle_context={"phase": "menstruation", "discomfort": "high"})
    )
    assert result.action == Action.recovery


def test_rules_engine_retains_cycle_decision_ownership(monkeypatch):
    def fake_normalize(_request):
        return NormalizedCycleContext(
            available=True,
            phase=None,
            discomfort=None,
            is_complete=True,
            requires_more_data=False,
            reason_codes=(ReasonCode.CYCLE_HIGH_DISCOMFORT,),
        )

    monkeypatch.setattr(training_rules, "normalize_cycle_context", fake_normalize)
    result = engine.evaluate(_request(sex="female"))
    assert result.action == Action.train


def test_rules_engine_interprets_normalized_cycle_signals(monkeypatch):
    def fake_normalize(_request):
        return NormalizedCycleContext(
            available=True,
            phase=None,
            discomfort=CycleDiscomfort.high,
            is_complete=True,
            requires_more_data=False,
            reason_codes=(ReasonCode.CYCLE_HIGH_DISCOMFORT,),
        )

    monkeypatch.setattr(training_rules, "normalize_cycle_context", fake_normalize)
    result = engine.evaluate(_request(sex="female", goal="strength", fatigue_level=1))
    assert result.action == Action.recovery
    assert result.recommended_session == RecommendedSession.mobility
    assert result.intensity == Intensity.low


def test_missing_recovery_time_uses_uncertainty():
    payload = _base_payload(last_session_type="lower_body")
    del payload["hours_since_last_session"]
    result = engine.evaluate(TrainingRecommendationRequest(**payload))
    assert result.needs_more_data is True
    assert ReasonCode.INSUFFICIENT_DATA in result.reason_codes
    assert ReasonCode.INSUFFICIENT_RECOVERY not in result.reason_codes


def test_goal_cannot_override_fatigue_ceiling():
    result = engine.evaluate(
        _request(goal="muscle_gain", fatigue_level=3, training_level="advanced")
    )
    assert result.intensity == Intensity.moderate


def test_weekly_frequency_affects_session_not_universal_full_body():
    low = engine.evaluate(_request(goal="strength", training_days_per_week=2))
    high = engine.evaluate(_request(goal="strength", training_days_per_week=6, last_session_type="upper_body"))
    assert low.recommended_session == RecommendedSession.full_body
    assert high.recommended_session != RecommendedSession.full_body


def test_final_invariants_handle_contradictory_state():
    state = training_rules._State(action=Action.rest, intensity_ceiling=Intensity.high)
    state.reason_codes = [ReasonCode.INSUFFICIENT_RECOVERY]
    finalized = training_rules._finalize(state, Intensity.high, "0.1")
    assert finalized.action == Action.rest
    assert finalized.intensity == Intensity.not_applicable


def test_reason_codes_machine_readable():
    result = engine.evaluate(_request())
    assert all(isinstance(code, ReasonCode) for code in result.reason_codes)


def test_needs_more_data_behavior():
    payload = _base_payload(last_session_type="upper_body")
    del payload["hours_since_last_session"]
    result = engine.evaluate(TrainingRecommendationRequest(**payload))
    assert result.needs_more_data is True


def test_public_response_contract_unchanged():
    keys = set(engine.evaluate(_request()).model_dump().keys())
    assert keys == {
        "action",
        "recommended_session",
        "intensity",
        "duration_minutes",
        "reason_codes",
        "needs_more_data",
        "agent_version",
    }


def test_route_to_engine_integration(monkeypatch):
    from app.api.routes import training as training_route

    def fake_evaluate(_payload):
        return TrainingRecommendationResponse(
            action=Action.recovery,
            recommended_session=RecommendedSession.mobility,
            intensity=Intensity.low,
            duration_minutes=20,
            reason_codes=[ReasonCode.CYCLE_HIGH_DISCOMFORT],
            needs_more_data=False,
            agent_version="0.1",
        )

    monkeypatch.setattr(training_route.training_engine, "evaluate", fake_evaluate)
    response = client.post(
        "/api/v1/training/recommendation",
        json=_base_payload(),
        headers={"X-API-Key": os.environ["IBUUM_API_KEY"]},
    )
    assert response.status_code == 200
    assert response.json()["action"] == "recovery"


@pytest.mark.parametrize("goal", ["general_fitness", "fat_loss", "muscle_gain", "strength"])
@pytest.mark.parametrize("days", range(1, 8))
def test_v11_frequency_rotation_and_bootstrap(goal, days):
    for last, hours in [(None, None), ("unknown", None), ("unknown", 24),
                        ("cardio", 2), ("mobility", 2), ("rest", 2),
                        ("upper_body", 24), ("lower_body", 24), ("full_body", 24)]:
        result = engine.evaluate(_request(goal=goal, training_days_per_week=days,
                                         last_session_type=last, hours_since_last_session=hours))
        expected = "full_body"
        if days >= 4:
            expected = {"upper_body": "lower_body", "lower_body": "upper_body",
                        "full_body": "upper_body"}.get(last, "full_body")
        assert result.action == Action.train
        assert result.recommended_session == expected
        assert ReasonCode.INSUFFICIENT_RECOVERY not in result.reason_codes
        if last in (None, "unknown"):
            assert ReasonCode.RECOVERY_WINDOW_OK not in result.reason_codes
        else:
            assert ReasonCode.RECOVERY_WINDOW_OK in result.reason_codes


@pytest.mark.parametrize("goal", ["general_fitness", "fat_loss", "muscle_gain", "strength", "endurance", "mobility"])
@pytest.mark.parametrize("hours", [0, 23])
def test_v11_recent_full_body_requires_recovery(goal, hours):
    result = engine.evaluate(_request(goal=goal, fatigue_level=1, last_session_type="full_body",
                                     hours_since_last_session=hours))
    assert result.action == Action.recovery
    assert result.recommended_session == RecommendedSession.mobility
    assert result.intensity == Intensity.low
    assert result.duration_minutes <= 20
    assert ReasonCode.INSUFFICIENT_RECOVERY in result.reason_codes
    assert ReasonCode.RECOVERY_WINDOW_OK not in result.reason_codes
    assert not result.needs_more_data


@pytest.mark.parametrize("last", [None, "unknown", "full_body"])
def test_v11_uncertain_recent_or_untimed_full_body_session(last):
    result = engine.evaluate(_request(goal="strength", fatigue_level=1,
                                     last_session_type=last,
                                     hours_since_last_session=None if last == "full_body" else 23))
    assert result.recommended_session == RecommendedSession.mobility
    assert result.needs_more_data
    assert result.intensity == Intensity.moderate
    assert ReasonCode.INSUFFICIENT_DATA in result.reason_codes
    assert ReasonCode.INSUFFICIENT_RECOVERY not in result.reason_codes
    assert ReasonCode.RECOVERY_WINDOW_OK not in result.reason_codes


@pytest.mark.parametrize("days", [1, 3, 4, 7])
@pytest.mark.parametrize("last,expected", [("upper_body", "lower_body"), ("lower_body", "upper_body")])
def test_v11_recent_split_conflict_preserved(days, last, expected):
    result = engine.evaluate(_request(goal="strength", training_days_per_week=days,
                                     last_session_type=last, hours_since_last_session=23))
    assert result.action == Action.train
    assert result.recommended_session == expected
    assert result.intensity == Intensity.moderate
    assert ReasonCode.INSUFFICIENT_RECOVERY in result.reason_codes


@pytest.mark.parametrize("last,hours", [("full_body", 23), ("unknown", 23), (None, None)])
def test_v11_safety_priority_preserved(last, hours):
    context = dict(goal="strength", last_session_type=last, hours_since_last_session=hours)
    rest = engine.evaluate(_request(**context, fatigue_level=5))
    assert rest.action == Action.rest
    assert rest.intensity == Intensity.not_applicable
    cycle = engine.evaluate(_request(**context, sex="female",
                                    cycle_context={"phase": "follicular", "discomfort": "high"}))
    assert cycle.action == Action.recovery
    assert cycle.intensity == Intensity.low
    assert ReasonCode.CYCLE_HIGH_DISCOMFORT in cycle.reason_codes
    assert ReasonCode.INSUFFICIENT_RECOVERY not in cycle.reason_codes
    beginner = engine.evaluate(_request(**context, training_level="beginner"))
    assert beginner.intensity != Intensity.high
