"""Focused progression policy, canonical contracts and purity checks."""

import ast
from copy import deepcopy
import inspect
from typing import get_args

import pytest
from pydantic import ValidationError

from app.models import progression as models
from app.models.progression import ProgressionDecision, ProgressionInput, ProgressionReasonCode as R
from app.models.session_outcome import SessionOutcomeInput
from app.models.training_history import ExerciseHistory, TrainingHistoryInput
from app.services import progression_engine as service
from app.services.progression_engine import evaluate_progression
from app.services.session_outcome import build_session_outcome
from app.services.training_history import build_training_history


def entry(reps=8, **fields):
    return dict(set_number=1, status="completed", reps=reps) | fields


def exercise(sets=None, **fields):
    return dict(sequence=1, exercise_id="squat", source_status="completed",
                sets=[entry()] if sets is None else sets) | fields


def session(identifier, exercises=None, **fields):
    return build_session_outcome(SessionOutcomeInput(**(dict(
        session_id=identifier, completion_state="completed",
        exercises=[exercise()] if exercises is None else exercises,
    ) | fields)))


def history(*sessions):
    return build_training_history(TrainingHistoryInput(outcomes=list(sessions)))


def evaluate(source, exercise_id="squat"):
    return evaluate_progression(ProgressionInput(history=source, exercise_id=exercise_id))


def pair(before=None, after=None, feedback=None):
    return history(session("previous", [before or exercise()]),
                   session("latest", [after or exercise()], feedback=feedback))


def test_absent_empty_and_single_occurrence():
    for source in [history(), history(session("other", [exercise(exercise_id="other")]))]:
        result = evaluate(source)
        assert result.decision == "NEEDS_MORE_DATA"
        assert result.reason_codes == [R.EXERCISE_NOT_IN_HISTORY]
        assert result.occurrences_considered == 0
        assert result.latest_session_id is None
    source = history()
    source.exercise_history.append(ExerciseHistory(exercise_id="squat", occurrences=[]))
    assert evaluate(source).reason_codes == [R.INSUFFICIENT_HISTORY]
    result = evaluate(history(session("one", feedback=dict(fatigue_after=5, discomfort_after="high"))))
    assert result.decision == "NEEDS_MORE_DATA"
    assert result.reason_codes == [R.INSUFFICIENT_HISTORY]
    assert result.occurrences_considered == 1
    assert result.latest_session_id == "one"


@pytest.mark.parametrize("before,after,feedback,decision,reasons", [
    (exercise(), exercise([entry(9)]), None, "PROGRESS", [R.PERFORMANCE_IMPROVED]),
    (exercise([entry(None, load_value=50, load_unit="kg")]),
     exercise([entry(None, load_value=55, load_unit="kg")]), None, "PROGRESS", [R.PERFORMANCE_IMPROVED]),
    (exercise(), exercise([entry(9)]), dict(fatigue_after=4), "MAINTAIN", [R.NO_STRONG_CHANGE_SIGNAL]),
    (exercise(), exercise([entry(9)]), dict(discomfort_after="moderate"), "MAINTAIN", [R.NO_STRONG_CHANGE_SIGNAL]),
    (exercise(), exercise([entry(9)]), dict(discomfort_after="high"), "MAINTAIN", [R.NO_STRONG_CHANGE_SIGNAL]),
    (exercise(), exercise([entry(9)], source_status="in_progress"), None, "MAINTAIN", [R.NO_STRONG_CHANGE_SIGNAL]),
    (exercise(source_status="in_progress"), exercise([entry(9)]), None, "MAINTAIN", [R.NO_STRONG_CHANGE_SIGNAL]),
    (exercise(), exercise([entry(9, rir=1)]), None, "MAINTAIN", [R.NO_STRONG_CHANGE_SIGNAL]),
    (exercise(), exercise(), None, "MAINTAIN", [R.PERFORMANCE_STABLE]),
    (exercise([entry(8, load_value=50, load_unit="kg")]),
     exercise([entry(9, load_value=45, load_unit="kg")]), None, "MAINTAIN", [R.PERFORMANCE_MIXED]),
    (exercise(), exercise([entry(7)]), None, "MAINTAIN", [R.NO_STRONG_CHANGE_SIGNAL]),
    (exercise(), exercise(), dict(fatigue_after=5), "MAINTAIN", [R.PERFORMANCE_STABLE]),
    (exercise(), exercise(source_status="in_progress"), None, "MAINTAIN", [R.PERFORMANCE_STABLE]),
    (exercise(), exercise([entry(7)]), dict(fatigue_after=4), "REDUCE", [R.LATEST_HIGH_FATIGUE, R.PERFORMANCE_REGRESSED]),
    (exercise(), exercise([entry(rir=0)], source_status="in_progress"), None, "REDUCE", [R.LATEST_EXECUTION_INCOMPLETE, R.LATEST_HIGH_EFFORT]),
    (exercise(), exercise(), dict(fatigue_after=4, discomfort_after="moderate"), "REDUCE", [R.LATEST_HIGH_FATIGUE, R.LATEST_MODERATE_HIGH_DISCOMFORT]),
    (exercise([entry(None)]), exercise([entry(None)]), None, "NEEDS_MORE_DATA", [R.INSUFFICIENT_COMPARABLE_PERFORMANCE]),
    (exercise([entry(None)]), exercise([entry(None)]), dict(fatigue_after=5, discomfort_after="high"), "REDUCE", [R.LATEST_HIGH_FATIGUE, R.LATEST_MODERATE_HIGH_DISCOMFORT]),
])
def test_policy(before, after, feedback, decision, reasons):
    result = evaluate(pair(before, after, feedback))
    assert result.decision == decision
    assert result.reason_codes == reasons
    assert result.occurrences_considered == 2
    assert result.latest_session_id == "latest"


@pytest.mark.parametrize("reps,decision", [(None, "NEEDS_MORE_DATA"), (9, "PROGRESS")])
def test_units_never_convert_but_reps_remain_comparable(reps, decision):
    source = pair(exercise([entry(None if reps is None else 8, load_value=50, load_unit="kg")]),
                  exercise([entry(reps, load_value=110.231, load_unit="lb")]))
    assert evaluate(source).decision == decision


@pytest.mark.parametrize("feedback", [None, {}, dict(fatigue_after=None, discomfort_after=None),
                                      dict(fatigue_after=3, discomfort_after="mild")])
def test_unknown_recovery_and_rir_remain_unknown(feedback):
    source = pair(after=exercise([entry(9, rir=None)], planned_target_rir=0), feedback=feedback)
    snapshot = deepcopy(source)
    assert evaluate(source).decision == "PROGRESS"
    assert source == snapshot
    assert source.exercise_history[0].occurrences[-1].exercise.sets[0].rir is None


@pytest.mark.parametrize("rir,decision", [(0, "MAINTAIN"), (1, "MAINTAIN"), (1.01, "PROGRESS")])
def test_effort_threshold(rir, decision):
    assert evaluate(pair(after=exercise([entry(9, rir=rir)]))).decision == decision


def test_effort_uses_mean_of_only_known_completed_sets():
    latest = exercise([entry(9, rir=0), entry(None, set_number=2, rir=3),
                       entry(None, set_number=3), entry(None, set_number=4, status="skipped")])
    assert evaluate(pair(after=latest)).decision == "PROGRESS"


@pytest.mark.parametrize("strain,issues,decision", [(True, True, "DELOAD"),
                                                     (True, False, "MAINTAIN"),
                                                     (False, True, "MAINTAIN")])
def test_deload_requires_both_repeated_evidence_families(strain, issues, decision):
    source = history(*(session(str(i), [exercise(source_status="in_progress" if issues else "completed")],
                              feedback=dict(fatigue_after=4) if strain else None) for i in range(3)))
    result = evaluate(source)
    assert result.decision == decision
    if decision == "DELOAD":
        assert result.reason_codes == [R.REPEATED_STRAIN, R.REPEATED_EXECUTION_OR_EFFORT_ISSUES]
    assert result.occurrences_considered == 3


def test_deload_effort_issues_and_discomfort_in_two_unique_sessions():
    source = history(session("first", [exercise([entry(rir=0)], sequence=2),
                                       exercise([entry(rir=1)], sequence=1)],
                             feedback=dict(discomfort_after="moderate")),
                     session("last", feedback=dict(fatigue_after=4)))
    assert evaluate(source).decision == "DELOAD"


def test_repeated_same_session_does_not_double_count_strain():
    source = history(session("first"), session("last", [
        exercise(source_status="in_progress", sequence=2),
        exercise(source_status="in_progress", sequence=1),
    ], feedback=dict(fatigue_after=5, discomfort_after="high")))
    assert evaluate(source).decision == "REDUCE"
    only_one = history(session("only", [exercise([entry(rir=0)], sequence=i) for i in range(1, 4)],
                               feedback=dict(fatigue_after=5)))
    assert evaluate(only_one).decision == "REDUCE"


def test_only_last_three_and_only_immediately_previous_comparison():
    source = history(session("old", [exercise(source_status="in_progress")], feedback=dict(fatigue_after=5)),
                     session("a", [exercise([entry(100)], source_status="in_progress")], feedback=dict(fatigue_after=5)),
                     session("b", [exercise([entry(8)])]), session("c", [exercise([entry(9)])]))
    result = evaluate(source)
    assert result.decision == "PROGRESS"
    assert result.occurrences_considered == 3


def test_timestamps_do_not_reorder_and_repeat_is_deterministic_without_mutation():
    source = history(session("z", [exercise([entry(8)])], started_at="2026-09-25T00:00:00Z"),
                     session("a", [exercise([entry(9)])], started_at="2026-01-01T00:00:00Z"))
    snapshot = deepcopy(source)
    result = evaluate(source)
    assert result.decision == "PROGRESS"
    assert result.latest_session_id == "a"
    assert evaluate(source).model_dump() == result.model_dump()
    assert source == snapshot


def test_plans_and_other_metrics_are_not_actual_performance():
    source = pair(exercise([entry(None, duration_seconds=10)], planned_rep_min=5, planned_rep_max=5),
                  exercise([entry(None, duration_seconds=20)], planned_rep_min=10, planned_rep_max=10,
                           planned_sets=5, planned_target_rir=0))
    assert evaluate(source).reason_codes == [R.INSUFFICIENT_COMPARABLE_PERFORMANCE]


def test_skipped_and_unmatched_sets_ignored_and_set_numbers_match():
    before = exercise([entry(100, set_number=3), entry(8, set_number=2),
                       entry(None, status="skipped", set_number=1)])
    after = exercise([entry(100, set_number=1), entry(9, set_number=2),
                      entry(None, status="skipped", set_number=3), entry(0, set_number=4)])
    assert evaluate(pair(before, after)).decision == "PROGRESS"
    assert evaluate(pair(exercise([entry(8, set_number=1)]),
                         exercise([entry(9, set_number=2)]))).decision == "NEEDS_MORE_DATA"


@pytest.mark.parametrize("status", ["pending", "skipped"])
def test_no_started_or_skipped_execution_is_negative(status):
    source = pair(after=exercise([], source_status=status), feedback=dict(fatigue_after=4))
    assert evaluate(source).reason_codes == [R.LATEST_EXECUTION_INCOMPLETE, R.LATEST_HIGH_FATIGUE]


def test_exact_model_contracts_and_enums():
    assert set(ProgressionInput.model_fields) == {"history", "exercise_id"}
    assert set(ProgressionDecision.model_fields) == {
        "engine_version", "exercise_id", "decision", "reason_codes", "occurrences_considered", "latest_session_id"}
    assert set(get_args(ProgressionDecision.model_fields["decision"].annotation)) == {
        "PROGRESS", "MAINTAIN", "REDUCE", "DELOAD", "NEEDS_MORE_DATA"}
    assert {item.value for item in R} == set('''EXERCISE_NOT_IN_HISTORY INSUFFICIENT_HISTORY
        INSUFFICIENT_COMPARABLE_PERFORMANCE PERFORMANCE_IMPROVED PERFORMANCE_STABLE PERFORMANCE_MIXED
        PERFORMANCE_REGRESSED LATEST_EXECUTION_INCOMPLETE LATEST_HIGH_FATIGUE
        LATEST_MODERATE_HIGH_DISCOMFORT LATEST_HIGH_EFFORT REPEATED_STRAIN
        REPEATED_EXECUTION_OR_EFFORT_ISSUES NO_STRONG_CHANGE_SIGNAL'''.split())
    assert evaluate(history()).engine_version == models.PROGRESSION_ENGINE_VERSION == "progression-engine-v1"
    for model, payload in [(ProgressionInput, dict(history=history(), exercise_id="squat")),
                           (ProgressionDecision, evaluate(history()).model_dump())]:
        assert model.model_config["extra"] == "forbid"
        with pytest.raises(ValidationError):
            model(**(payload | {"persona": "Kai"}))


@pytest.mark.parametrize("value", [{}, [], history().model_dump()])
def test_only_actual_canonical_history_accepted(value):
    with pytest.raises(ValidationError):
        ProgressionInput(history=value, exercise_id="squat")


@pytest.mark.parametrize("value", ["", "x" * 129, 1, None])
def test_exercise_id_validation(value):
    with pytest.raises(ValidationError):
        ProgressionInput(history=history(), exercise_id=value)


@pytest.mark.parametrize("field,value", [("occurrences_considered", True), ("occurrences_considered", "2"),
                                         ("occurrences_considered", 2.0), ("occurrences_considered", -1),
                                         ("engine_version", "v2"), ("decision", "OTHER"),
                                         ("reason_codes", ["OTHER"])])
def test_output_validation(field, value):
    with pytest.raises(ValidationError):
        ProgressionDecision(**(evaluate(history()).model_dump() | {field: value}))


def test_pure_import_boundaries_and_no_routes():
    allowed = {"enum", "typing", "pydantic", "app.models.training_history",
               "app.models.session_outcome", "app.models.progression"}
    for module in [models, service]:
        tree = ast.parse(inspect.getsource(module))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.module in allowed
            if isinstance(node, ast.Import):
                assert all(alias.name in allowed for alias in node.names)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {"open", "eval", "exec", "__import__", "APIRouter", "FastAPI"}
