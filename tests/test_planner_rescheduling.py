"""Bounded rescheduling contract, policy and mutation-isolation tests."""

import ast
from datetime import date, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.models.planner_rescheduling import (
    PLANNER_RESCHEDULING_VERSION, PlannerReschedulingInput,
    PlannerReschedulingResult, RescheduleAppliedChange, ReschedulingSummary,
    SessionRescheduleRequest,
)
from app.models.progression import ProgressionDecision
from app.models.program_planner import (
    ProgramPlan, ProgramPlanSummary, ProgramPreviousWeekContext,
    ProgramProgressionSummary, ProgramSessionPlan,
)
from app.models.weekly_training_state import (
    WeeklyTrainingState, WeeklyPlannedSessionState, WeeklyPlanSummary,
    WeeklyWorkloadFacts, WeeklyRecoveryFacts, WeeklyAdherenceFacts,
)
from app.services.planner_rescheduling import reschedule_program

START = date(2026, 9, 30)


def day(offset):
    return START + timedelta(days=offset)


def counts(model, **overrides):
    return model(**{name: overrides.get(name, 0) for name in model.model_fields})


def inputs(requests=()):
    sessions = [ProgramSessionPlan(slot_id=name, scheduled_date=day(offset), session_type=kind)
                for name, offset, kind in [('due', 0, 'upper_body'),
                                           ('future', 5, 'cardio'), ('other', 6, 'mobility')]]
    plan = ProgramPlan(
        source_week_start=day(-7), source_week_end=day(-1),
        plan_week_start=START, plan_week_end=day(6), sessions=sessions,
        progression_decisions=[ProgressionDecision(
            exercise_id='squat', decision='DELOAD', reason_codes=['REPEATED_STRAIN'],
            occurrences_considered=3, latest_session_id='previous',
        )],
        previous_week_context=counts(
            ProgramPreviousWeekContext, source_week_start=day(-7),
            source_week_end=day(-1), source_as_of_date=day(-1), attendance_ratio=None,
            high_fatigue_sessions=2, moderate_high_discomfort_sessions=1,
        ),
        progression_summary=counts(ProgramProgressionSummary, total_decisions=1, deload_decisions=1),
        plan_summary=counts(ProgramPlanSummary, total_sessions=3,
                            upper_body_sessions=1, cardio_sessions=1, mobility_sessions=1),
    )
    week = WeeklyTrainingState(
        week_start=START, week_end=day(6), as_of_date=day(2),
        planned_sessions=[WeeklyPlannedSessionState(**s.model_dump(), status='remaining',
                                                   is_due=s.scheduled_date <= day(2)) for s in sessions],
        included_session_ids=[], unplanned_session_ids=[],
        plan_summary=counts(WeeklyPlanSummary, total_planned_sessions=3,
                            remaining_planned_sessions=3, due_remaining_planned_sessions=1,
                            future_remaining_planned_sessions=2),
        workload=counts(WeeklyWorkloadFacts),
        recovery=counts(WeeklyRecoveryFacts, latest_known_fatigue_after=None,
                        latest_known_discomfort_after=None, latest_known_session_rpe=None),
        adherence=counts(WeeklyAdherenceFacts, due_planned_sessions=1,
                         unresolved_due_sessions=1, attendance_ratio=0.0),
    )
    return dict(program_plan=plan, current_week_state=week, requests=list(requests))


def request(slot='due', target=3, reason='SCHEDULE_CHANGE'):
    return SessionRescheduleRequest(slot_id=slot, target_date=day(target), reason=reason)


def run(values):
    return reschedule_program(PlannerReschedulingInput(**values))


def test_empty_requests_versions_and_no_automatic_moves():
    values = inputs()
    result = run(values)
    assert result.rescheduler_version == PLANNER_RESCHEDULING_VERSION == 'planner-rescheduling-v1'
    assert result.source_planner_version == 'program-planner-v1'
    assert result.updated_plan == values['program_plan']
    assert result.updated_plan is not values['program_plan']
    assert result.changes == []
    assert result.summary.model_dump() == dict(total_sessions=3, requested_changes=0,
                                               rescheduled_sessions=0, unchanged_sessions=3)


@pytest.mark.parametrize('field', ['program_plan', 'current_week_state'])
def test_raw_canonical_dict_rejected(field):
    values = inputs()
    values[field] = values[field].model_dump()
    with pytest.raises(ValidationError, match='canonical'):
        run(values)


@pytest.mark.parametrize('case', ['start', 'end', 'missing', 'extra', 'date', 'type'])
def test_alignment_rejected_even_without_requests(case):
    values = inputs()
    week = values['current_week_state']
    if case == 'start':
        week.week_start = day(1)
    elif case == 'end':
        week.week_end = day(7)
    elif case == 'missing':
        week.planned_sessions.pop()
    elif case == 'extra':
        week.planned_sessions.append(week.planned_sessions[0].model_copy(update={'slot_id': 'extra'}))
    elif case == 'date':
        week.planned_sessions[0].scheduled_date = day(1)
    else:
        week.planned_sessions[0].session_type = 'lower_body'
    with pytest.raises(ValidationError):
        run(values)


def test_unknown_weekly_type_and_different_state_order_allowed():
    values = inputs([request()])
    values['current_week_state'].planned_sessions[0].session_type = None
    values['current_week_state'].planned_sessions.reverse()
    assert run(values).changes[0].session_type == 'upper_body'
    assert values['current_week_state'].planned_sessions[-1].session_type is None


@pytest.mark.parametrize('requests', [[request(), request(target=4)], [request('unknown')]])
def test_duplicate_or_unknown_requested_slot_rejected(requests):
    with pytest.raises(ValidationError):
        run(inputs(requests))


@pytest.mark.parametrize('status', ['completed', 'partial'])
def test_executed_slot_is_immutable(status):
    values = inputs([request()])
    values['current_week_state'].planned_sessions[0].status = status
    values['current_week_state'].planned_sessions[0].linked_session_id = 'executed'
    with pytest.raises(ValidationError, match='remaining'):
        run(values)
    values['requests'] = []
    assert run(values).updated_plan == values['program_plan']


@pytest.mark.parametrize('slot,target', [('due', -1), ('due', 7), ('due', 1), ('future', 5)])
def test_invalid_target_rejected(slot, target):
    with pytest.raises(ValidationError):
        run(inputs([request(slot, target)]))


@pytest.mark.parametrize('slot,target', [('due', 2), ('due', 6), ('future', 2), ('future', 6)])
def test_due_and_future_moves_earlier_later_and_inclusive_boundaries(slot, target):
    values = inputs([request(slot, target)])
    result = run(values)
    for before, after in zip(values['program_plan'].sessions, result.updated_plan.sessions):
        assert after.scheduled_date == (day(target) if before.slot_id == slot else before.scheduled_date)
    assert result.summary.model_dump() == dict(total_sessions=3, requested_changes=1,
                                               rescheduled_sessions=1, unchanged_sessions=2)
    assert result.plan_week_start == START
    assert result.plan_week_end == day(6)
    assert result.as_of_date == day(2)


def test_week_start_allowed_when_as_of_is_week_start():
    values = inputs([request('future', 0)])
    values['current_week_state'].as_of_date = START
    assert run(values).changes[0].new_scheduled_date == START


def test_shared_date_without_capacity_and_canonical_request_order():
    requests = [request('other', 3, 'AVAILABILITY_CHANGE'), request('future', 3),
                request('due', 3, 'UNRESOLVED_SESSION')]
    values = inputs(requests)
    result = run(values)
    values['requests'] = list(reversed(requests))
    assert run(values) == result
    assert [c.slot_id for c in result.changes] == ['due', 'future', 'other']
    assert [s.scheduled_date for s in result.updated_plan.sessions] == [day(3)] * 3
    for before, change in zip(values['program_plan'].sessions, result.changes):
        assert change.model_dump() == dict(
            slot_id=before.slot_id, original_scheduled_date=before.scheduled_date,
            new_scheduled_date=day(3), session_type=before.session_type,
            reason=next(r.reason for r in requests if r.slot_id == before.slot_id),
        )
    assert result.summary.model_dump() == dict(total_sessions=3, requested_changes=3,
                                               rescheduled_sessions=3, unchanged_sessions=0)


def test_preserves_every_program_field_except_requested_dates_and_is_deterministic():
    values = inputs([request()])
    before = values['program_plan'].model_dump()
    result = run(values)
    assert result == run(values)
    expected = values['program_plan'].model_dump()
    expected['sessions'][0]['scheduled_date'] = day(3)
    assert result.updated_plan.model_dump() == expected
    assert values['program_plan'].model_dump() == before


@pytest.mark.parametrize('code', ['PROGRESS', 'MAINTAIN', 'REDUCE', 'DELOAD', 'NEEDS_MORE_DATA'])
def test_recovery_and_progression_never_cause_moves(code):
    values = inputs()
    values['program_plan'].progression_decisions[0].decision = code
    values['current_week_state'].recovery.high_fatigue_sessions = 4
    values['current_week_state'].recovery.latest_known_fatigue_after = 5
    values['current_week_state'].recovery.moderate_high_discomfort_sessions = 4
    values['current_week_state'].recovery.latest_known_discomfort_after = 'high'
    result = run(values)
    assert result.updated_plan == values['program_plan']
    assert result.changes == []


def test_input_and_output_mutation_isolation():
    values = inputs([request()])
    data = PlannerReschedulingInput(**values)
    before = data.model_dump()
    result = reschedule_program(data)
    assert data.model_dump() == before
    assert values['requests'] == [request()]
    assert result.updated_plan.sessions is not data.program_plan.sessions
    assert result.updated_plan.previous_week_context is not data.program_plan.previous_week_context
    assert result.updated_plan.plan_summary is not data.program_plan.plan_summary
    assert result.updated_plan.progression_summary is not data.program_plan.progression_summary
    result.updated_plan.sessions[0].session_type = 'mobility'
    result.updated_plan.progression_decisions[0].reason_codes.clear()
    result.updated_plan.previous_week_context.high_fatigue_sessions = 99
    result.updated_plan.plan_summary.total_sessions = 99
    result.changes[0].new_scheduled_date = day(4)
    result.changes.clear()
    assert data.model_dump() == before
    assert reschedule_program(data).changes


@pytest.mark.parametrize('reason', ['SCHEDULE_CHANGE', 'AVAILABILITY_CHANGE', 'UNRESOLVED_SESSION'])
def test_exact_reasons_accepted(reason):
    assert run(inputs([request(reason=reason)])).changes[0].reason == reason


@pytest.mark.parametrize('reason', ['FAILURE', 'NONCOMPLIANT', 'fatigue', 'unknown', None])
def test_other_reasons_rejected(reason):
    with pytest.raises(ValidationError):
        request(reason=reason)


@pytest.mark.parametrize('slot_id', ['', 'x' * 129, 42])
def test_identifier_bounds(slot_id):
    with pytest.raises(ValidationError):
        request(slot=slot_id)


def test_exact_fields_extra_rejection_and_version_literals():
    values = inputs([request()])
    data = PlannerReschedulingInput(**values)
    result = reschedule_program(data)
    objects = [data, data.requests[0], result, result.changes[0], result.summary]
    expected_fields = [
        {'program_plan', 'current_week_state', 'requests'},
        {'slot_id', 'target_date', 'reason'},
        {'rescheduler_version', 'source_planner_version', 'plan_week_start', 'plan_week_end',
         'as_of_date', 'updated_plan', 'changes', 'summary'},
        {'slot_id', 'original_scheduled_date', 'new_scheduled_date', 'session_type', 'reason'},
        {'total_sessions', 'requested_changes', 'rescheduled_sessions', 'unchanged_sessions'},
    ]
    for obj, fields in zip(objects, expected_fields):
        assert set(type(obj).model_fields) == fields
        assert type(obj).model_config['extra'] == 'forbid'
        payload = dict(obj)
        with pytest.raises(ValidationError, match='extra_forbidden'):
            type(obj)(**payload, recommendation='move')
    for field in ['rescheduler_version', 'source_planner_version']:
        with pytest.raises(ValidationError):
            PlannerReschedulingResult(**{**dict(result), field: 'v2'})


@pytest.mark.parametrize('bad', [-1, True, False, 1.0, '1'])
def test_summary_counts_strict_nonnegative(bad):
    for field in ReschedulingSummary.model_fields:
        with pytest.raises(ValidationError):
            counts(ReschedulingSummary, **{field: bad})


def test_empty_program_supported():
    values = inputs()
    values['program_plan'].sessions.clear()
    values['current_week_state'].planned_sessions.clear()
    result = run(values)
    assert set(result.summary.model_dump().values()) == {0}


def test_pure_import_and_call_boundaries():
    root = Path(__file__).resolve().parents[1]
    allowed = {'datetime', 'typing', 'pydantic', 'app.models.program_planner',
               'app.models.weekly_training_state', 'app.models.planner_rescheduling'}
    forbidden = {'now', 'today', 'utcnow', 'timestamp', 'fromtimestamp', 'open',
                 'evaluate_progression', 'build_weekly_training_state', 'build_program_plan'}
    for relative in ['app/models/planner_rescheduling.py', 'app/services/planner_rescheduling.py']:
        tree = ast.parse((root / relative).read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.module in allowed
            if isinstance(node, ast.Import):
                assert all(alias.name in allowed for alias in node.names)
            if isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, 'attr', '')
                assert name not in forbidden
    # Exact file inventory/protected files are verified with Git at PR preparation.
