"""Bounded weekly facts, explicit scope, isolation and architecture contracts."""

import ast
from copy import deepcopy
from datetime import date, timedelta
import inspect

import pytest
from pydantic import ValidationError

from app.models.session_outcome import SessionOutcome, SessionOutcomeInput
from app.models.training_history import TrainingHistoryInput
from app.models import weekly_training_state as models
from app.services.session_outcome import build_session_outcome
from app.services.training_history import build_training_history
from app.services import weekly_training_state as service


START = date(2026, 9, 23)  # Wednesday is a valid caller-selected anchor.
SUMMARY = dict(total_exercises=17, completed_exercises=5, partial_exercises=4,
               skipped_exercises=3, not_started_exercises=5, completed_sets=13, skipped_sets=7)


def outcome(session_id="a", **fields):
    return build_session_outcome(SessionOutcomeInput(**(
        dict(session_id=session_id, completion_state="completed", exercises=[]) | fields)))


def slot(slot_id="slot", day=0, linked=None, **fields):
    return models.WeeklyPlannedSessionInput(**dict(
        slot_id=slot_id, scheduled_date=START + timedelta(days=day),
        linked_session_id=linked) | fields)


def data(sessions=(), planned=(), included=None, **fields):
    return models.WeeklyTrainingStateInput(**(dict(
        history=build_training_history(TrainingHistoryInput(outcomes=list(sessions))),
        week_start=START, as_of_date=START + timedelta(days=2),
        planned_sessions=list(planned),
        included_session_ids=([s.session_id for s in sessions] if included is None else included),
    ) | fields))


def build(*args, **kwargs):
    return service.build_weekly_training_state(data(*args, **kwargs))


def test_empty_week_version_and_seven_dates():
    result = build()
    assert result.week_start.weekday() == 2
    assert result.week_end == START + timedelta(days=6)
    assert result.state_version == models.WEEKLY_TRAINING_STATE_VERSION == "weekly-training-state-v1"
    assert result.planned_sessions == result.included_session_ids == result.unplanned_session_ids == []
    assert set(result.plan_summary.model_dump().values()) == {0}
    assert set(result.workload.model_dump().values()) == {0}
    assert result.recovery.model_dump() == dict(
        sessions_with_feedback=0, sessions_with_known_fatigue=0, high_fatigue_sessions=0,
        latest_known_fatigue_after=None, sessions_with_known_discomfort=0,
        moderate_high_discomfort_sessions=0, latest_known_discomfort_after=None,
        sessions_with_known_session_rpe=0, latest_known_session_rpe=None)
    assert result.adherence.attendance_ratio is None
    with pytest.raises(ValidationError):
        models.WeeklyTrainingState(**(result.model_dump() | {"state_version": "v2"}))


def test_empty_plan_and_empty_scope_are_distinct():
    actual = outcome()
    unplanned = build([actual])
    assert unplanned.workload.total_sessions == unplanned.workload.unplanned_sessions == 1
    assert unplanned.unplanned_session_ids == ["a"]
    assert unplanned.adherence.attendance_ratio is None
    excluded = build([actual], [slot()], included=[])
    assert excluded.workload.total_sessions == 0
    assert excluded.planned_sessions[0].status == "remaining"
    assert excluded.adherence.attendance_ratio == 0.0


@pytest.mark.parametrize("offset", [-1, 7])
def test_dates_outside_week_rejected(offset):
    with pytest.raises(ValidationError, match="as_of_date"):
        data(as_of_date=START + timedelta(days=offset))
    with pytest.raises(ValidationError, match="scheduled_date"):
        data(planned=[slot(day=offset)])


@pytest.mark.parametrize("offset", [0, 6])
def test_week_boundary_dates_are_inclusive(offset):
    result = build(planned=[slot(day=offset)], as_of_date=START + timedelta(days=offset))
    assert result.planned_sessions[0].is_due


@pytest.mark.parametrize("planned,included,message", [
    ([slot(), slot()], [], "slot_id must be unique"),
    ([], ["a", "a"], "included_session_ids must be unique"),
    ([], ["unknown"], "included_session_id must exist"),
    ([slot(linked="unknown")], ["a"], "linked_session_id must exist"),
    ([slot(linked="a")], [], "linked_session_id must appear"),
    ([slot("one", linked="a"), slot("two", linked="a")], ["a"], "at most one"),
])
def test_explicit_scope_validation(planned, included, message):
    with pytest.raises(ValidationError, match=message):
        data([outcome()], planned, included, )


@pytest.mark.parametrize("raw", [{}, [], "history"])
def test_history_requires_canonical_instance(raw):
    with pytest.raises(ValidationError, match="canonical TrainingHistory"):
        data(history=raw)
    with pytest.raises(ValidationError, match="canonical TrainingHistory"):
        data(history=data().history.model_dump())


@pytest.mark.parametrize("field,value", [
    ("slot_id", ""), ("slot_id", "x" * 129),
    ("linked_session_id", ""), ("linked_session_id", "x" * 129),
    ("session_type", "unknown"),
])
def test_slot_field_validation(field, value):
    with pytest.raises(ValidationError):
        models.WeeklyPlannedSessionInput(**(dict(slot_id="s", scheduled_date=START) | {field: value}))


def test_mixed_plan_states_due_boundary_and_adherence():
    result = build(
        [outcome("done"), outcome("partial", completion_state="interrupted"),
         outcome("early"), outcome("extra")],
        [slot("future", 3), slot("done", 0, "done", session_type="cardio"),
         slot("partial", 1, "partial"), slot("due", 2), slot("early", 6, "early")],
    )
    assert [s.slot_id for s in result.planned_sessions] == ["future", "done", "partial", "due", "early"]
    assert [s.status for s in result.planned_sessions] == ["remaining", "completed", "partial", "remaining", "completed"]
    assert [s.is_due for s in result.planned_sessions] == [False, True, True, True, False]
    assert result.planned_sessions[1].session_type == "cardio"
    assert result.plan_summary.model_dump() == dict(
        total_planned_sessions=5, completed_planned_sessions=2, partial_planned_sessions=1,
        remaining_planned_sessions=2, due_remaining_planned_sessions=1,
        future_remaining_planned_sessions=1)
    assert result.adherence.model_dump() == dict(
        due_planned_sessions=3, completed_due_sessions=1, partial_due_sessions=1,
        unresolved_due_sessions=1, attendance_ratio=2 / 3)
    assert result.unplanned_session_ids == ["extra"]


@pytest.mark.parametrize("completion", ["completed", "interrupted"])
def test_full_attendance_includes_partial(completion):
    result = build([outcome(completion_state=completion)], [slot(linked="a")])
    assert result.adherence.attendance_ratio == 1.0


def test_future_completed_and_remaining_slots_have_no_due_denominator():
    result = build([outcome()], [slot("early", 3, "a"), slot("later", 6)])
    assert result.adherence.due_planned_sessions == 0
    assert result.adherence.attendance_ratio is None


def test_canonical_order_controls_scope_unplanned_and_latest_known_values():
    sessions = [
        outcome("z", started_at="2035-01-01T00:00:00Z", feedback=dict(
            fatigue_after=5, discomfort_after="high", session_rpe=9)),
        outcome("excluded", feedback=dict(fatigue_after=5, discomfort_after="high", session_rpe=10)),
        outcome("b", started_at="2000-01-01T00:00:00Z", feedback=dict(
            fatigue_after=1, discomfort_after="none", session_rpe=2)),
        outcome("a", feedback={}),
    ]
    result = build(sessions, [slot(linked="b")], included=["a", "b", "z"])
    assert result.included_session_ids == ["z", "b", "a"]
    assert result.unplanned_session_ids == ["z", "a"]
    assert result.recovery.latest_known_fatigue_after == 1
    assert result.recovery.latest_known_discomfort_after == "none"
    assert result.recovery.latest_known_session_rpe == 2
    assert result.recovery.sessions_with_feedback == 3
    assert result.recovery.high_fatigue_sessions == 1
    assert result == build(sessions, [slot(linked="b")], included=["z", "a", "b"])


def test_workload_sums_canonical_summaries_and_explicit_durations_only():
    # A valid direct output can contain authoritative summary values independent
    # of its exercise list. Weekly aggregation must not normalize them again.
    canonical = SessionOutcome(**(outcome().model_dump() | {"summary": SUMMARY}))
    sessions = [canonical, outcome("zero", actual_duration_seconds=0),
                outcome("timed", actual_duration_seconds=37, completion_state="interrupted"),
                outcome("also-timed", actual_duration_seconds=5),
                outcome("timestamps", started_at="2026-09-23T00:00:00Z",
                        ended_at="2026-09-23T01:00:00Z"),
                outcome("excluded", actual_duration_seconds=999)]
    result = build(sessions, included=[s.session_id for s in sessions[:-1]])
    assert result.workload.model_dump() == SUMMARY | dict(
        total_sessions=5, completed_sessions=4, interrupted_sessions=1, unplanned_sessions=5,
        sessions_with_known_duration=3, known_duration_seconds=42)


def test_feedback_counts_thresholds_and_independent_latest_known_values():
    sessions = [outcome("absent"), outcome("null", feedback={}),
                outcome("low", feedback=dict(fatigue_after=3, discomfort_after="none", session_rpe=1)),
                outcome("high", feedback=dict(fatigue_after=4, discomfort_after="moderate", session_rpe=10)),
                outcome("higher", feedback=dict(fatigue_after=5, discomfort_after="high")),
                outcome("mild", feedback=dict(discomfort_after="mild")),
                outcome("trailing-null", feedback={})]
    result = build(sessions)
    assert result.recovery.model_dump() == dict(
        sessions_with_feedback=6, sessions_with_known_fatigue=3, high_fatigue_sessions=2,
        latest_known_fatigue_after=5, sessions_with_known_discomfort=4,
        moderate_high_discomfort_sessions=2, latest_known_discomfort_after="mild",
        sessions_with_known_session_rpe=2, latest_known_session_rpe=10.0)
    only_null = build([outcome(feedback={})]).recovery.model_dump()
    assert only_null == build().recovery.model_dump() | {"sessions_with_feedback": 1}


def test_repeatability_nonmutation_and_detached_output_lists():
    source = data([outcome("a", feedback=dict(fatigue_after=4)), outcome("b")],
                  [slot(linked="a")], included=["b", "a"])
    before = deepcopy(source.model_dump())
    result = service.build_weekly_training_state(source)
    assert result == service.build_weekly_training_state(source)
    assert source.model_dump() == before
    assert result.planned_sessions is not source.planned_sessions
    assert result.planned_sessions[0] is not source.planned_sessions[0]
    assert result.included_session_ids is not source.included_session_ids
    assert result.unplanned_session_ids is not result.included_session_ids
    result.planned_sessions[0].slot_id = "changed"
    result.planned_sessions.clear()
    result.included_session_ids.clear()
    result.unplanned_session_ids.append("changed")
    result.recovery.latest_known_fatigue_after = 1
    result.workload.total_sessions = 100
    assert source.model_dump() == before


def model_examples():
    source = data(planned=[slot()])
    result = service.build_weekly_training_state(source)
    return [source, source.planned_sessions[0], result, result.planned_sessions[0],
            result.plan_summary, result.workload, result.recovery, result.adherence]


def test_all_eight_models_forbid_extra_fields():
    for example in model_examples():
        payload = example.model_dump() | {"recommendation": "unexpected"}
        if isinstance(example, models.WeeklyTrainingStateInput):
            payload["history"] = example.history
        with pytest.raises(ValidationError, match="extra_forbidden"):
            type(example)(**payload)


@pytest.mark.parametrize("invalid", [True, "1", 1.0, -1])
def test_every_count_is_a_strict_nonnegative_integer(invalid):
    result = build()
    for aggregate in [result.plan_summary, result.workload, result.recovery, result.adherence]:
        for name, value in aggregate.model_dump().items():
            if type(value) is int:
                with pytest.raises(ValidationError):
                    type(aggregate)(**(aggregate.model_dump() | {name: invalid}))


@pytest.mark.parametrize("invalid", [-0.01, 1.01, float("nan"), float("inf"), True, "0.5"])
def test_attendance_ratio_bounds(invalid):
    with pytest.raises(ValidationError):
        models.WeeklyAdherenceFacts(**(build().adherence.model_dump() | {"attendance_ratio": invalid}))


def test_exact_fields_exclude_scores_recommendations_and_prose():
    expected = {
        models.WeeklyPlannedSessionInput: "slot_id scheduled_date session_type linked_session_id",
        models.WeeklyTrainingStateInput: "history week_start as_of_date planned_sessions included_session_ids",
        models.WeeklyPlannedSessionState: "slot_id scheduled_date session_type linked_session_id status is_due",
        models.WeeklyTrainingState: "state_version week_start week_end as_of_date planned_sessions included_session_ids unplanned_session_ids plan_summary workload recovery adherence",
        models.WeeklyPlanSummary: "total_planned_sessions completed_planned_sessions partial_planned_sessions remaining_planned_sessions due_remaining_planned_sessions future_remaining_planned_sessions",
        models.WeeklyWorkloadFacts: "total_sessions completed_sessions interrupted_sessions unplanned_sessions total_exercises completed_exercises partial_exercises skipped_exercises not_started_exercises completed_sets skipped_sets sessions_with_known_duration known_duration_seconds",
        models.WeeklyRecoveryFacts: "sessions_with_feedback sessions_with_known_fatigue high_fatigue_sessions latest_known_fatigue_after sessions_with_known_discomfort moderate_high_discomfort_sessions latest_known_discomfort_after sessions_with_known_session_rpe latest_known_session_rpe",
        models.WeeklyAdherenceFacts: "due_planned_sessions completed_due_sessions partial_due_sessions unresolved_due_sessions attendance_ratio",
    }
    for model, names in expected.items():
        assert set(model.model_fields) == set(names.split())


def test_pure_import_and_function_boundaries():
    allowed = {"datetime", "typing", "pydantic", "app.models.session_outcome",
               "app.models.training_history", "app.models.weekly_training_state"}
    for module in [models, service]:
        tree = ast.parse(inspect.getsource(module))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.module in allowed
            if isinstance(node, ast.Import):
                assert all(alias.name in allowed for alias in node.names)
            if isinstance(node, ast.Attribute):
                assert node.attr not in {"now", "today", "utcnow", "started_at", "ended_at"}
    functions = [node.name for node in ast.parse(inspect.getsource(service)).body
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    assert functions == ["build_weekly_training_state"]
