"""Session facts, terminal semantics, validation and architectural boundaries."""

import ast
from copy import deepcopy
from datetime import datetime, timezone
import inspect
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.models import session_outcome as models
from app.models.session_outcome import (
    ExerciseExecutionInput, ExerciseOutcome, SessionFeedback, SessionOutcome,
    SessionOutcomeInput, SessionOutcomeSummary, SetExecutionInput,
)
from app.services import session_outcome as service
from app.services.session_outcome import build_session_outcome


def exercise(status="completed", sets=None, **fields):
    return dict(sequence=1, exercise_id="squat", source_status=status,
                sets=[] if sets is None else sets, **fields)


def session(exercises=None, **fields):
    return dict(session_id="session-1", completion_state="completed",
                exercises=[] if exercises is None else exercises) | fields


def build(**fields):
    return build_session_outcome(SessionOutcomeInput(**session(**fields)))


@pytest.mark.parametrize("terminal", ["completed", "interrupted"])
@pytest.mark.parametrize("source,logs,expected", [
    ("completed", [], "completed"),
    ("completed", ["completed", "skipped"], "completed"),
    ("in_progress", [], "partial"),
    ("in_progress", ["completed"], "partial"),
    ("skipped", [], "skipped"),
    ("skipped", ["skipped"], "skipped"),
    ("skipped", ["completed", "skipped"], "partial"),
    ("pending", ["completed"], "partial"),
    ("pending", [], "not_started"),
    ("pending", ["skipped"], "not_started"),
])
def test_explicit_states_independent_of_terminal_state(terminal, source, logs, expected):
    sets = [dict(set_number=i, status=s) for i, s in enumerate(logs, 1)]
    result = build(completion_state=terminal, exercises=[exercise(source, sets)])
    assert result.completion_state == terminal
    actual = result.exercises[0]
    assert actual.source_status == source
    assert actual.execution_status == expected
    assert actual.completed_sets == logs.count("completed")
    assert actual.skipped_sets == logs.count("skipped")


@pytest.mark.parametrize("source", ["pending", "in_progress", "skipped"])
@pytest.mark.parametrize("count", [1, 2])
def test_set_count_never_auto_completes(source, count):
    sets = [dict(set_number=i, status="completed") for i in range(1, count + 1)]
    result = build(exercises=[exercise(source, sets, planned_sets=1)])
    assert result.exercises[0].execution_status == "partial"


def test_normal_session_preserves_all_facts_and_is_deterministic_without_mutation():
    metrics = dict(set_number=2, status="completed", reps=8, load_value=42.5,
                   load_unit="lb", duration_seconds=60, distance_meters=25.5,
                   rir=2.5, actual_rest_seconds=90,
                   recorded_at=datetime(2026, 1, 1, 12, tzinfo=timezone.utc))
    data = SessionOutcomeInput(**session(
        exercises=[exercise(sets=[metrics, dict(set_number=1, status="completed")],
                            display_name="Squat", movement_pattern="squat",
                            planned_sets=3, planned_rep_min=10, planned_rep_max=12,
                            planned_target_rir=3, planned_rest_seconds=120)],
        plan_id="plan-1", source_action="train", session_type="lower_body",
        started_at="2026-01-01T12:00:00+00:00", ended_at="2026-01-01T13:00:00+00:00",
        actual_duration_seconds=1234,
        feedback=dict(session_rpe=7.5, fatigue_after=3, discomfort_after="none"),
    ))
    before = deepcopy(data)
    result = build_session_outcome(data)
    assert result.outcome_version == models.SESSION_OUTCOME_VERSION == "session-outcome-v1"
    assert result.model_dump(exclude={"outcome_version", "exercises", "summary"}) == data.model_dump(exclude={"exercises"})
    assert result.exercises[0].model_dump(exclude={"execution_status", "completed_sets", "skipped_sets"}) == data.exercises[0].model_dump()
    assert result.exercises[0].sets[0].model_dump() == metrics
    assert result.exercises[0].sets[1].reps is None  # planned range never becomes actual
    assert result.summary.model_dump() == dict(total_exercises=1, completed_exercises=1,
        partial_exercises=0, skipped_exercises=0, not_started_exercises=0,
        completed_sets=2, skipped_sets=0)
    for _ in range(3):
        assert build_session_outcome(data).model_dump_json() == result.model_dump_json()
    assert data == before
    result.exercises[0].sets[0].reps = 99
    result.feedback.fatigue_after = 5
    assert data == before  # no nested mutable aliases either


def test_order_and_exact_mixed_summary():
    entries = [exercise("pending"), exercise("completed"), exercise("skipped"),
               exercise("in_progress", [dict(set_number=4, status="completed"),
                                         dict(set_number=2, status="skipped")])]
    for sequence, entry in zip([4, 1, 3, 2], entries):
        entry["sequence"] = sequence
    result = build(exercises=entries)
    assert [e.sequence for e in result.exercises] == [4, 1, 3, 2]
    assert [s.set_number for s in result.exercises[-1].sets] == [4, 2]
    assert result.summary.model_dump() == dict(total_exercises=4, completed_exercises=1,
        partial_exercises=1, skipped_exercises=1, not_started_exercises=1,
        completed_sets=1, skipped_sets=1)


@pytest.mark.parametrize("terminal", ["completed", "interrupted"])
def test_empty_session_and_unknown_facts(terminal):
    result = build(completion_state=terminal)
    assert result.completion_state == terminal
    assert result.exercises == []
    assert all(value == 0 for value in result.summary.model_dump().values())
    for key in ("feedback", "actual_duration_seconds", "plan_id", "source_action",
                "session_type", "started_at", "ended_at"):
        assert getattr(result, key) is None


def test_zero_and_null_are_distinct_and_feedback_is_not_inferred():
    result = build(actual_duration_seconds=0, exercises=[exercise(sets=[
        dict(set_number=1, status="completed", reps=0, rir=0, actual_rest_seconds=0),
        dict(set_number=2, status="completed")], planned_rep_min=0, planned_rep_max=0,
        planned_target_rir=0, planned_rest_seconds=0)])
    assert result.actual_duration_seconds == 0
    assert result.feedback is None
    first, second = result.exercises[0].sets
    assert (first.reps, first.rir, first.actual_rest_seconds) == (0, 0, 0)
    assert all(value is None for key, value in second.model_dump().items()
               if key not in {"set_number", "status"})
    reported = build(feedback={"discomfort_after": "none"}).feedback
    assert reported.discomfort_after == "none"
    assert reported.session_rpe is reported.fatigue_after is None
    assert build(feedback={}).feedback.discomfort_after is None


def test_duration_not_derived_and_offsets_compared_as_instants():
    result = build(started_at="2026-01-01T13:00:00+02:00", ended_at="2026-01-01T12:00:00Z")
    assert result.actual_duration_seconds is None
    assert build(started_at="2026-01-01T12:00:00Z", ended_at="2026-01-01T12:00:00Z").actual_duration_seconds is None


@pytest.mark.parametrize("model,payload", [
    (SessionOutcomeInput, session()), (SessionFeedback, {}),
    (ExerciseExecutionInput, exercise()),
    (SetExecutionInput, dict(set_number=1, status="completed")),
    (ExerciseOutcome, exercise() | dict(execution_status="completed", completed_sets=0, skipped_sets=0)),
    (SessionOutcomeSummary, dict.fromkeys(SessionOutcomeSummary.model_fields, 0)),
    (SessionOutcome, build().model_dump()),
])
def test_all_models_reject_unknown_fields(model, payload):
    with pytest.raises(ValidationError):
        model(**(payload | {"unexpected": 1}))
    assert model.model_config["extra"] == "forbid"


@pytest.mark.parametrize("fields", [
    {"exercises": [exercise(), exercise()]},
    {"session_id": ""}, {"session_id": "x" * 129}, {"plan_id": "x" * 129},
    {"source_action": "rest"}, {"source_action": "request_more_data"},
    {"session_type": "unknown"}, {"completion_state": "pending"},
    {"actual_duration_seconds": -1}, {"actual_duration_seconds": 1.5},
    {"started_at": "2026-01-01T12:00:00"}, {"ended_at": datetime(2026, 1, 1)},
    {"started_at": "2026-01-01T12:00:00Z", "ended_at": "2026-01-01T11:59:59Z"},
])
def test_invalid_sessions(fields):
    with pytest.raises(ValidationError):
        SessionOutcomeInput(**(session() | fields))


@pytest.mark.parametrize("fields", [
    {"sequence": 0}, {"exercise_id": ""}, {"exercise_id": "x" * 129},
    {"display_name": "x" * 161}, {"movement_pattern": "x" * 81},
    {"planned_sets": 0}, {"planned_rep_min": 1}, {"planned_rep_max": 1},
    {"planned_rep_min": 2, "planned_rep_max": 1},
    {"planned_rep_min": -1, "planned_rep_max": 1},
    {"planned_target_rir": 11}, {"planned_rest_seconds": -1},
    {"source_status": "partial"},
    {"sets": [dict(set_number=1, status="completed"), dict(set_number=1, status="skipped")]},
])
def test_invalid_exercises(fields):
    with pytest.raises(ValidationError):
        ExerciseExecutionInput(**(exercise() | fields))


@pytest.mark.parametrize("fields", [
    {"set_number": 0}, {"reps": -1}, {"reps": True}, {"reps": 1.5},
    {"load_value": 20}, {"load_unit": "kg"},
    {"load_value": 0, "load_unit": "kg"}, {"load_value": 1001, "load_unit": "kg"},
    {"load_value": 20, "load_unit": "stone"},
    {"duration_seconds": 0}, {"duration_seconds": 36001},
    {"distance_meters": 0}, {"distance_meters": float("inf")},
    {"distance_meters": float("nan")}, {"rir": -1}, {"rir": 11},
    {"actual_rest_seconds": -1}, {"recorded_at": "2026-01-01T12:00:00"},
    {"status": "pending"},
])
def test_invalid_sets(fields):
    with pytest.raises(ValidationError):
        SetExecutionInput(**(dict(set_number=1, status="completed") | fields))


@pytest.mark.parametrize("metrics", [
    {"reps": 0}, {"load_value": 1, "load_unit": "kg"}, {"load_unit": "lb"},
    {"duration_seconds": 1}, {"distance_meters": 1}, {"rir": 0}, {"actual_rest_seconds": 0},
])
def test_skipped_set_rejects_each_performance_metric(metrics):
    with pytest.raises(ValidationError):
        SetExecutionInput(set_number=1, status="skipped", **metrics)


def test_skipped_timestamp_and_numeric_upper_bounds():
    assert SetExecutionInput(set_number=1, status="skipped", recorded_at="2026-01-01T12:00:00Z").recorded_at is not None
    entry = SetExecutionInput(set_number=1, status="completed", load_value=1000,
                              load_unit="kg", duration_seconds=36000, rir=10)
    assert (entry.load_value, entry.duration_seconds, entry.rir) == (1000, 36000, 10)


@pytest.mark.parametrize("fields", [
    {"session_rpe": 0}, {"session_rpe": 11}, {"session_rpe": float("nan")},
    {"fatigue_after": 0}, {"fatigue_after": 6}, {"fatigue_after": 1.5},
    {"discomfort_after": "severe"},
])
def test_invalid_feedback(fields):
    with pytest.raises(ValidationError):
        SessionFeedback(**fields)


@pytest.mark.parametrize("model,payload,required", [
    (SessionOutcomeInput, session(), ["session_id", "completion_state", "exercises"]),
    (ExerciseExecutionInput, exercise(), ["sequence", "exercise_id", "source_status", "sets"]),
    (SetExecutionInput, dict(set_number=1, status="completed"), ["set_number", "status"]),
])
def test_required_fields(model, payload, required):
    for field in required:
        with pytest.raises(ValidationError):
            model(**{key: value for key, value in payload.items() if key != field})


def test_exact_output_contract_has_no_scores_identity_or_recommendations():
    assert set(SessionOutcome.model_fields) == {
        "outcome_version", "session_id", "plan_id", "source_action", "session_type",
        "completion_state", "started_at", "ended_at", "actual_duration_seconds",
        "feedback", "exercises", "summary",
    }
    assert set(ExerciseOutcome.model_fields) == {
        "sequence", "exercise_id", "display_name", "movement_pattern", "planned_sets",
        "planned_rep_min", "planned_rep_max", "planned_target_rir", "planned_rest_seconds",
        "source_status", "sets", "execution_status", "completed_sets", "skipped_sets",
    }
    assert set(SessionOutcomeSummary.model_fields) == {
        "total_exercises", "completed_exercises", "partial_exercises", "skipped_exercises",
        "not_started_exercises", "completed_sets", "skipped_sets",
    }
    assert set(SessionFeedback.model_fields) == {"session_rpe", "fatigue_after", "discomfort_after"}
    with pytest.raises(ValidationError):
        SessionOutcome(**(build().model_dump() | {"outcome_version": "v2"}))


def test_pure_modules_have_no_external_or_engine_dependencies():
    allowed = {"typing", "pydantic", "app.models.session_outcome"}
    for module in (models, service):
        tree = ast.parse(inspect.getsource(module))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(alias.name in allowed for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                assert node.module in allowed
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {"open", "eval", "exec", "__import__"}
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in {"now", "utcnow", "today", "random"}
    root = Path(__file__).resolve().parents[1]
    for path in [root / "app/main.py", *(root / "app/api").rglob("*.py")]:
        assert "session_outcome" not in path.read_text(encoding="utf-8")
