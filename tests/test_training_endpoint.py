"""
Automated tests for iBuum Agent 0.1.

Run with:
    pytest -v

Organized in sections:
  1. Health / infrastructure
  2. Authentication & security
  3. Response contract shape
  4. Input validation (boundaries, enums, required fields)
  5. Rule engine behavior
  6. Rule engine invariants (properties that must always hold)

The API contract itself (endpoint paths, header name, env var name,
response field names) is NOT modified by this suite — these tests exist to
protect that contract going forward.
"""

import os

# The API key must be set BEFORE app.core.config is imported anywhere,
# since Settings() reads it at import time via get_settings().
os.environ.setdefault("IBUUM_API_KEY", "test-secret-key")

import pytest
from fastapi.testclient import TestClient

from app.main import app

API_KEY = os.environ["IBUUM_API_KEY"]
ENDPOINT = "/api/v1/training/recommendation"

client = TestClient(app)


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


def _headers(key: str | None = API_KEY) -> dict:
    return {"X-API-Key": key} if key else {}


def _post(payload: dict, key: str | None = API_KEY):
    return client.post(ENDPOINT, json=payload, headers=_headers(key))


# =========================================================================
# 1. HEALTH / INFRASTRUCTURE
# =========================================================================


def test_health_check_returns_200_and_ok_status():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "ibuum-agent"


def test_health_check_requires_no_authentication():
    # No X-API-Key header sent at all.
    response = client.get("/health")
    assert response.status_code == 200


def test_health_check_reports_agent_version():
    response = client.get("/health")
    assert response.json()["version"] == "0.1"


# =========================================================================
# 2. AUTHENTICATION & SECURITY
# =========================================================================


def test_missing_api_key_returns_401():
    response = client.post(ENDPOINT, json=_base_payload())
    assert response.status_code == 401


def test_wrong_api_key_returns_401():
    response = _post(_base_payload(), key="wrong-key")
    assert response.status_code == 401


def test_empty_string_api_key_returns_401():
    response = _post(_base_payload(), key="")
    assert response.status_code == 401


def test_valid_api_key_returns_200():
    response = _post(_base_payload())
    assert response.status_code == 200


def test_api_key_header_name_is_x_api_key():
    # Confirms the auth contract Base44 already integrates against.
    response = client.post(
        ENDPOINT, json=_base_payload(), headers={"X-API-Key": API_KEY}
    )
    assert response.status_code == 200


def test_401_response_does_not_leak_configured_key():
    response = _post(_base_payload(), key="wrong-key")
    assert API_KEY not in response.text


def test_invalid_key_with_malformed_body_still_returns_401_or_422_never_500():
    # Auth failures must never surface as a 500, regardless of body shape.
    response = client.post(
        ENDPOINT,
        json={"not": "a valid payload"},
        headers=_headers("wrong-key"),
    )
    assert response.status_code in (401, 422)


# =========================================================================
# 3. RESPONSE CONTRACT SHAPE
# =========================================================================


def test_response_contains_all_contract_fields():
    response = _post(_base_payload())
    body = response.json()
    expected_fields = {
        "action",
        "recommended_session",
        "intensity",
        "duration_minutes",
        "reason_codes",
        "needs_more_data",
        "agent_version",
    }
    assert expected_fields.issubset(body.keys())


def test_response_agent_version_is_0_1():
    response = _post(_base_payload())
    assert response.json()["agent_version"] == "0.1"


def test_response_reason_codes_is_a_list_of_strings():
    response = _post(_base_payload())
    reason_codes = response.json()["reason_codes"]
    assert isinstance(reason_codes, list)
    assert all(isinstance(code, str) for code in reason_codes)


def test_response_duration_minutes_is_non_negative_integer():
    response = _post(_base_payload())
    duration = response.json()["duration_minutes"]
    assert isinstance(duration, int)
    assert duration >= 0


# =========================================================================
# 4. INPUT VALIDATION
# =========================================================================


# Grouped as single tests with internal loops (rather than heavy
# pytest.mark.parametrize fan-out) so each still exercises every boundary
# case, but the suite doesn't balloon into hundreds of collected items for
# what is conceptually one check repeated across fields.


def test_out_of_range_values_are_rejected():
    out_of_range_cases = [
        ("age", 9),  # below minimum (10)
        ("age", 101),  # above maximum (100)
        ("height_cm", -5),  # not > 0
        ("weight_kg", -1),  # not > 0
        ("training_days_per_week", 0),  # below minimum (1)
        ("training_days_per_week", 8),  # above maximum (7)
        ("fatigue_level", 0),  # below minimum (1)
        ("fatigue_level", 6),  # above maximum (5)
        ("hours_since_last_session", -1),  # negative
    ]
    for field, value in out_of_range_cases:
        response = _post(_base_payload(**{field: value}))
        assert response.status_code == 422, f"{field}={value} should be rejected"


def test_boundary_values_are_accepted():
    boundary_cases = [
        ("age", 10),
        ("age", 100),
        ("training_days_per_week", 1),
        ("training_days_per_week", 7),
        ("fatigue_level", 1),
        ("fatigue_level", 5),
        ("hours_since_last_session", 0),
    ]
    for field, value in boundary_cases:
        response = _post(_base_payload(**{field: value}))
        assert response.status_code == 200, f"{field}={value} should be accepted"


def test_invalid_enum_values_are_rejected():
    invalid_enum_cases = [
        ("sex", "unspecified"),
        ("goal", "get_ripped"),
        ("training_level", "expert"),
        ("last_session_type", "arms_only"),
    ]
    for field, value in invalid_enum_cases:
        response = _post(_base_payload(**{field: value}))
        assert response.status_code == 422, f"{field}={value} should be rejected"


def test_missing_required_fields_are_rejected():
    required_fields = [
        "age", "sex", "height_cm", "weight_kg", "goal",
        "training_level", "training_days_per_week", "fatigue_level",
    ]
    for field in required_fields:
        payload = _base_payload()
        del payload[field]
        response = _post(payload)
        assert response.status_code == 422, f"missing {field} should be rejected"


def test_empty_request_body_is_rejected():
    response = client.post(ENDPOINT, json={}, headers=_headers())
    assert response.status_code == 422


def test_malformed_json_is_rejected():
    response = client.post(
        ENDPOINT,
        data="{not valid json",
        headers={**_headers(), "Content-Type": "application/json"},
    )
    assert response.status_code == 422


def test_last_session_type_and_hours_are_optional():
    payload = _base_payload()
    del payload["last_session_type"]
    del payload["hours_since_last_session"]
    response = _post(payload)
    assert response.status_code == 200


def test_user_id_rejects_email_like_values():
    response = _post(_base_payload(user_id="someone@example.com"))
    assert response.status_code == 422


def test_user_id_accepts_anonymous_identifier():
    response = _post(_base_payload(user_id="anon_8f3a1c"))
    assert response.status_code == 200


def test_invalid_cycle_phase_is_rejected():
    response = _post(
        _base_payload(
            sex="female",
            cycle_context={"phase": "not_a_real_phase", "discomfort": "mild"},
        )
    )
    assert response.status_code == 422


def test_invalid_cycle_discomfort_is_rejected():
    response = _post(
        _base_payload(
            sex="female",
            cycle_context={"phase": "luteal", "discomfort": "extreme"},
        )
    )
    assert response.status_code == 422


# =========================================================================
# 5. RULE ENGINE BEHAVIOR
# =========================================================================


def test_high_fatigue_returns_rest_action():
    response = _post(_base_payload(fatigue_level=5))
    body = response.json()
    assert body["action"] == "rest"
    assert "HIGH_FATIGUE" in body["reason_codes"]


def test_fatigue_level_4_reduces_intensity():
    response = _post(_base_payload(fatigue_level=4))
    body = response.json()
    assert body["intensity"] == "low"
    assert "MODERATE_FATIGUE" in body["reason_codes"]


def test_fatigue_level_3_is_tagged_without_forcing_rest():
    response = _post(_base_payload(fatigue_level=3))
    body = response.json()
    assert body["action"] != "rest"
    assert "MODERATE_FATIGUE" in body["reason_codes"]


def test_low_fatigue_is_tagged_low_fatigue():
    response = _post(_base_payload(fatigue_level=1))
    body = response.json()
    assert "LOW_FATIGUE" in body["reason_codes"]


def test_beginner_never_receives_high_intensity():
    response = _post(_base_payload(training_level="beginner", fatigue_level=1))
    body = response.json()
    assert body["intensity"] != "high"


def test_recent_lower_body_session_avoids_repeat_and_flags_reason():
    response = _post(
        _base_payload(last_session_type="lower_body", hours_since_last_session=10)
    )
    body = response.json()
    assert body["recommended_session"] != "lower_body"
    assert "RECENT_LOWER_BODY_SESSION" in body["reason_codes"]


def test_recent_upper_body_session_avoids_repeat_and_flags_reason():
    response = _post(
        _base_payload(last_session_type="upper_body", hours_since_last_session=5)
    )
    body = response.json()
    assert body["recommended_session"] != "upper_body"
    assert "RECENT_UPPER_BODY_SESSION" in body["reason_codes"]


def test_old_lower_body_session_does_not_trigger_conflict():
    # 30 hours ago is outside the 24h conflict window.
    response = _post(
        _base_payload(last_session_type="lower_body", hours_since_last_session=30)
    )
    body = response.json()
    assert "RECENT_LOWER_BODY_SESSION" not in body["reason_codes"]
    assert "RECOVERY_WINDOW_OK" in body["reason_codes"]


def test_missing_hours_with_known_last_session_flags_insufficient_data():
    payload = _base_payload(last_session_type="lower_body")
    del payload["hours_since_last_session"]
    response = _post(payload)
    body = response.json()
    assert body["needs_more_data"] is True
    assert "INSUFFICIENT_DATA" in body["reason_codes"]


def test_female_user_without_cycle_context_behaves_normally():
    response = _post(_base_payload(sex="female"))
    assert response.status_code == 200
    body = response.json()
    assert body["action"] in {"train", "recovery", "rest", "request_more_data"}


def test_cycle_context_is_optional():
    payload = _base_payload(sex="female")
    assert "cycle_context" not in payload
    response = _post(payload)
    assert response.status_code == 200


def test_high_menstrual_discomfort_triggers_recovery():
    response = _post(
        _base_payload(
            sex="female",
            cycle_context={"phase": "menstruation", "discomfort": "high"},
        )
    )
    body = response.json()
    assert "CYCLE_HIGH_DISCOMFORT" in body["reason_codes"]
    assert body["action"] == "recovery"
    assert body["intensity"] == "low"


def test_menstruation_with_low_discomfort_does_not_force_recovery():
    # Guards the explicit product rule: menstruation alone must NOT
    # automatically reduce training — only high discomfort does.
    response = _post(
        _base_payload(
            sex="female",
            fatigue_level=2,
            cycle_context={"phase": "menstruation", "discomfort": "none"},
        )
    )
    body = response.json()
    assert "CYCLE_HIGH_DISCOMFORT" not in body["reason_codes"]
    assert body["action"] != "recovery"


def test_non_menstruation_high_discomfort_does_not_trigger_cycle_rule():
    # Discomfort alone, outside menstruation, should not trigger rule 5.
    response = _post(
        _base_payload(
            sex="female",
            cycle_context={"phase": "luteal", "discomfort": "high"},
        )
    )
    body = response.json()
    assert "CYCLE_HIGH_DISCOMFORT" not in body["reason_codes"]


def test_male_user_can_still_send_no_cycle_context():
    response = _post(_base_payload(sex="male"))
    assert response.status_code == 200


# =========================================================================
# 6. RULE ENGINE INVARIANTS
# =========================================================================
#
# These protect properties that must hold no matter how the rules evolve,
# independent of any single scenario above.


REPRESENTATIVE_PAYLOADS = [
    _base_payload(),
    _base_payload(fatigue_level=5),
    _base_payload(fatigue_level=4),
    _base_payload(training_level="beginner", fatigue_level=1),
    _base_payload(last_session_type="lower_body", hours_since_last_session=5),
    _base_payload(last_session_type="upper_body", hours_since_last_session=5),
    _base_payload(
        sex="female",
        cycle_context={"phase": "menstruation", "discomfort": "high"},
    ),
    _base_payload(
        sex="female",
        cycle_context={"phase": "menstruation", "discomfort": "mild"},
    ),
]


def test_invariant_rest_action_never_pairs_with_active_intensity():
    """A `rest` response must never carry a train-level intensity."""
    for payload in REPRESENTATIVE_PAYLOADS:
        body = _post(payload).json()
        if body["action"] == "rest":
            assert body["intensity"] == "not_applicable"
            assert body["recommended_session"] == "rest"
            assert body["duration_minutes"] == 0


def test_invariant_train_action_never_has_not_applicable_intensity():
    """A `train` response must always specify a real intensity level."""
    for payload in REPRESENTATIVE_PAYLOADS:
        body = _post(payload).json()
        if body["action"] == "train":
            assert body["intensity"] in {"low", "moderate", "high"}


def test_invariant_response_always_matches_contract_shape():
    """Every representative scenario must still return the full contract."""
    expected_fields = {
        "action",
        "recommended_session",
        "intensity",
        "duration_minutes",
        "reason_codes",
        "needs_more_data",
        "agent_version",
    }
    for payload in REPRESENTATIVE_PAYLOADS:
        body = _post(payload).json()
        assert set(body.keys()) == expected_fields
        assert body["agent_version"] == "0.1"
