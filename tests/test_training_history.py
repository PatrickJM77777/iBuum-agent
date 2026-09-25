"""Training History contracts, factual preservation and domain boundaries."""

import ast
from copy import deepcopy
import inspect
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from app.models.session_outcome import SessionFeedback, SessionOutcome, SessionOutcomeInput
from app.models import training_history as models
from app.models.training_history import (
    ExerciseHistory, ExerciseHistoryOccurrence, TrainingHistory,
    TrainingHistoryInput, TrainingHistorySummary,
)
from app.services.session_outcome import build_session_outcome
from app.services import training_history as service
from app.services.training_history import build_training_history


SUMMARY_FIELDS = {
    "total_sessions", "completed_sessions", "interrupted_sessions",
    "total_exercises", "completed_exercises", "partial_exercises",
    "skipped_exercises", "not_started_exercises", "completed_sets", "skipped_sets",
    "sessions_with_known_duration", "known_duration_seconds", "sessions_with_feedback",
}


def exercise(exercise_id="squat", sequence=1, **fields):
    return dict(exercise_id=exercise_id, sequence=sequence,
                source_status="completed", sets=[]) | fields


def outcome(session_id="session-1", **fields):
    payload = dict(session_id=session_id, completion_state="completed", exercises=[]) | fields
    return build_session_outcome(SessionOutcomeInput(**payload))


def history(*outcomes):
    return build_training_history(TrainingHistoryInput(outcomes=list(outcomes)))


def test_empty_history_and_version():
    result = history()
    assert result.sessions == result.exercise_history == []
    assert result.summary.model_dump() == dict.fromkeys(SUMMARY_FIELDS, 0)
    assert result.history_version == models.TRAINING_HISTORY_VERSION == "training-history-v1"
    with pytest.raises(ValidationError):
        TrainingHistory(**(result.model_dump() | {"history_version": "v2"}))


@pytest.mark.parametrize("state", ["completed", "interrupted"])
def test_one_session_and_one_exercise(state):
    source = outcome(completion_state=state, exercises=[exercise()])
    result = history(source)
    assert result.sessions == [source]
    assert result.sessions[0].outcome_version == "session-outcome-v1"
    assert result.summary.total_sessions == 1
    assert result.summary.completed_sessions == int(state == "completed")
    assert result.summary.interrupted_sessions == int(state == "interrupted")
    assert len(result.exercise_history) == 1
    assert result.exercise_history[0].exercise_id == "squat"
    assert result.exercise_history[0].occurrences[0].session_completion_state == state


def test_mixed_summary_is_exact():
    entries = [exercise(source_status=status, sequence=i, sets=sets)
               for i, (status, sets) in enumerate([
                   ("completed", []),
                   ("in_progress", [dict(set_number=2, status="completed"),
                                    dict(set_number=1, status="skipped")]),
                   ("skipped", []), ("pending", []),
               ], 1)]
    sources = [outcome("a", exercises=entries),
               outcome("b", completion_state="interrupted", exercises=entries)]
    result = history(*sources)
    assert result.summary.model_dump() == dict(
        total_sessions=2, completed_sessions=1, interrupted_sessions=1,
        total_exercises=8, completed_exercises=2, partial_exercises=2,
        skipped_exercises=2, not_started_exercises=2, completed_sets=2, skipped_sets=2,
        sessions_with_known_duration=0, known_duration_seconds=0, sessions_with_feedback=0,
    )


def test_canonical_summary_and_status_are_authoritative():
    # Direct canonical output construction validates shape, not normalization.
    payload = outcome(exercises=[exercise(source_status="pending", planned_sets=1,
        sets=[dict(set_number=1, status="completed")])]).model_dump()
    payload["summary"] = dict(total_exercises=41, completed_exercises=11,
        partial_exercises=12, skipped_exercises=13, not_started_exercises=5,
        completed_sets=23, skipped_sets=24)
    source = SessionOutcome(**payload)
    result = history(source)
    for key, value in source.summary.model_dump().items():
        assert getattr(result.summary, key) == value
    assert result.exercise_history[0].occurrences[0].exercise.execution_status == "partial"
    assert result.sessions[0].model_dump() == source.model_dump()


def test_order_grouping_repetition_and_occurrence_context():
    sources = [
        outcome("z", started_at="2026-09-01T10:00:00Z", ended_at="2026-09-01T11:00:00Z",
                source_action="train", session_type="lower_body",
                exercises=[exercise("squat", 4), exercise("bench", 1), exercise("squat", 3)]),
        outcome("a", started_at="2026-01-01T10:00:00Z", ended_at="2026-01-01T11:00:00Z",
                completion_state="interrupted", source_action="recovery", session_type="mobility",
                exercises=[exercise("row", 2), exercise("squat", 1)]),
        outcome("m", exercises=[exercise("bench")]),
    ]
    result = history(*sources)
    assert [s.session_id for s in result.sessions] == ["z", "a", "m"]
    assert [g.exercise_id for g in result.exercise_history] == ["squat", "bench", "row"]
    assert [(o.session_id, o.exercise.sequence) for o in result.exercise_history[0].occurrences] == [
        ("z", 4), ("z", 3), ("a", 1)]
    assert [s.model_dump() for s in result.sessions] == [s.model_dump() for s in sources]
    for group in result.exercise_history:
        for entry in group.occurrences:
            source = next(s for s in sources if s.session_id == entry.session_id)
            assert entry.session_completion_state == source.completion_state
            assert entry.session_started_at == source.started_at
            assert entry.session_ended_at == source.ended_at
            assert entry.source_action == source.source_action
            assert entry.session_type == source.session_type
    assert result.exercise_history[1].occurrences[-1].session_started_at is None


def test_duration_and_feedback_presence_without_inference():
    sources = [outcome("unknown", started_at="2026-01-01T10:00:00Z",
                       ended_at="2026-01-01T11:00:00Z"),
               outcome("zero", actual_duration_seconds=0, feedback=SessionFeedback()),
               outcome("known", actual_duration_seconds=123, feedback={"fatigue_after": 2}),
               outcome("other", actual_duration_seconds=7)]
    result = history(*sources)
    assert result.summary.sessions_with_known_duration == 3
    assert result.summary.known_duration_seconds == 130
    assert result.summary.sessions_with_feedback == 2
    assert result.sessions[0].actual_duration_seconds is None
    assert result.sessions[0].feedback is None
    assert result.sessions[1].actual_duration_seconds == 0
    assert result.sessions[1].feedback == SessionFeedback()


def test_historical_metadata_sets_units_nulls_and_zeros_preserved():
    sources = []
    for identifier, name, pattern, load, unit, count in [
        ("old", "Goblet Squat", "squat", 50, "kg", 2),
        ("new", "Goblet Squat Updated", "updated", 110, "lb", 3),
    ]:
        sources.append(outcome(identifier, plan_id=identifier, exercises=[exercise(
            display_name=name, movement_pattern=pattern, planned_sets=count,
            planned_rep_min=8, planned_rep_max=12, planned_target_rir=2,
            planned_rest_seconds=90, source_status="in_progress", sets=[
                dict(set_number=4, status="completed", load_value=load, load_unit=unit,
                     reps=0, rir=0, actual_rest_seconds=0, duration_seconds=30,
                     distance_meters=12.5, recorded_at="2026-01-01T10:00:00+02:00"),
                dict(set_number=2, status="completed"),
                dict(set_number=1, status="skipped"),
            ])]))
    result = history(*sources)
    occurrences = result.exercise_history[0].occurrences
    for source, entry in zip(sources, occurrences):
        assert entry.exercise.model_dump() == source.exercises[0].model_dump()
        assert [s.set_number for s in entry.exercise.sets] == [4, 2, 1]
        first, unknown, skipped = entry.exercise.sets
        assert (first.reps, first.rir, first.actual_rest_seconds) == (0, 0, 0)
        assert all(v is None for k, v in unknown.model_dump().items()
                   if k not in {"set_number", "status"})
        assert skipped.reps is None
    assert [(o.exercise.sets[0].load_value, o.exercise.sets[0].load_unit)
            for o in occurrences] == [(50, "kg"), (110, "lb")]


@pytest.mark.parametrize("invalid", [None, {}, (), [None], ["session"],
    [SessionOutcomeInput(session_id="raw", completion_state="completed", exercises=[])],
    [dict(session_id="raw", completion_state="completed", exercises=[])],
    [outcome().model_dump()],
])
def test_only_canonical_objects_are_accepted(invalid):
    with pytest.raises(ValidationError):
        TrainingHistoryInput(outcomes=invalid)


def test_required_input_and_duplicate_session_ids():
    with pytest.raises(ValidationError):
        TrainingHistoryInput()
    first = outcome()
    with pytest.raises(ValidationError, match="session_id must be unique"):
        TrainingHistoryInput(outcomes=[first, first.model_copy(deep=True)])
    assert TrainingHistoryInput(outcomes=[first]).outcomes == [first]


@pytest.mark.parametrize("model", [TrainingHistoryInput, TrainingHistory,
    TrainingHistorySummary, ExerciseHistory, ExerciseHistoryOccurrence])
def test_every_new_model_forbids_unknown_fields(model):
    source = outcome(exercises=[exercise()])
    result = history(source)
    payloads = {
        TrainingHistoryInput: {"outcomes": [source]}, TrainingHistory: result.model_dump(),
        TrainingHistorySummary: result.summary.model_dump(),
        ExerciseHistory: result.exercise_history[0].model_dump(),
        ExerciseHistoryOccurrence: result.exercise_history[0].occurrences[0].model_dump(),
    }
    assert model.model_config["extra"] == "forbid"
    with pytest.raises(ValidationError):
        model(**(payloads[model] | {"unexpected": 1}))


@pytest.mark.parametrize("field", sorted(SUMMARY_FIELDS))
@pytest.mark.parametrize("invalid", [-1, True, 1.5, "1", None])
def test_summary_requires_strict_nonnegative_integers(field, invalid):
    with pytest.raises(ValidationError):
        TrainingHistorySummary(**(dict.fromkeys(SUMMARY_FIELDS, 0) | {field: invalid}))


@pytest.mark.parametrize("identifier", ["", "x" * 129])
def test_exercise_group_identifier_bounds(identifier):
    with pytest.raises(ValidationError):
        ExerciseHistory(exercise_id=identifier, occurrences=[])


def test_exact_new_contracts_exclude_analysis_identity_and_prose():
    assert set(TrainingHistoryInput.model_fields) == {"outcomes"}
    assert set(TrainingHistory.model_fields) == {"history_version", "sessions", "exercise_history", "summary"}
    assert set(TrainingHistorySummary.model_fields) == SUMMARY_FIELDS
    assert set(ExerciseHistory.model_fields) == {"exercise_id", "occurrences"}
    assert set(ExerciseHistoryOccurrence.model_fields) == {
        "session_id", "session_completion_state", "session_started_at", "session_ended_at",
        "source_action", "session_type", "exercise",
    }


def mutable_ids(value):
    if isinstance(value, BaseModel):
        return {id(value)}.union(*(mutable_ids(getattr(value, field)) for field in type(value).model_fields))
    if isinstance(value, list):
        return {id(value)}.union(*(mutable_ids(item) for item in value))
    return set()


def test_determinism_no_mutation_and_no_nested_aliasing():
    source = outcome(feedback={"fatigue_after": 2}, exercises=[exercise(sets=[
        dict(set_number=1, status="completed", reps=0)])])
    data = TrainingHistoryInput(outcomes=[source])
    before = deepcopy(data)
    result = build_training_history(data)
    for _ in range(3):
        assert build_training_history(data).model_dump_json() == result.model_dump_json()
    assert data == before
    assert mutable_ids(result).isdisjoint(mutable_ids(data))
    occurrence = result.exercise_history[0].occurrences[0]
    assert mutable_ids(occurrence.exercise).isdisjoint(mutable_ids(result.sessions[0]))
    result.sessions[0].exercises[0].sets[0].reps = 99
    result.sessions[0].feedback.fatigue_after = 5
    result.sessions[0].summary.completed_sets = 99
    result.sessions[0].exercises.clear()
    occurrence.exercise.display_name = "Changed"
    occurrence.exercise.sets.clear()
    result.sessions.clear()
    assert data == before
    assert source == before.outcomes[0]


def test_modules_are_pure_and_not_wired_into_routes():
    allowed = {"typing", "pydantic", "app.models.session_outcome", "app.models.training_history"}
    for module in (models, service):
        tree = ast.parse(inspect.getsource(module))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(alias.name in allowed for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                assert node.module in allowed
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {"open", "eval", "exec", "__import__", "sorted", "build_session_outcome"}
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in {"now", "utcnow", "today", "random", "sort"}
    root = Path(__file__).resolve().parents[1]
    for path in [root / "app/main.py", *(root / "app/api").rglob("*.py")]:
        assert "training_history" not in path.read_text(encoding="utf-8")
