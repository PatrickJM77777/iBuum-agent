"""Bounded contract, context, isolation and architecture tests for Program Planner."""

import ast
from datetime import date, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.models.progression import ProgressionDecision, ProgressionReasonCode
from app.models.program_planner import (
    PROGRAM_PLANNER_VERSION, ProgramPlannerInput, ProgramPlan,
    ProgramPlanSummary, ProgramPreviousWeekContext, ProgramProgressionSummary,
    ProgramSessionPlan, ProgramSessionTemplateInput,
)
from app.models.weekly_training_state import (
    WeeklyTrainingState, WeeklyPlanSummary, WeeklyWorkloadFacts,
    WeeklyRecoveryFacts, WeeklyAdherenceFacts,
)
from app.services.program_planner import build_program_plan


TYPES = ['upper_body', 'lower_body', 'full_body', 'cardio', 'mobility']
DECISIONS = ['PROGRESS', 'MAINTAIN', 'REDUCE', 'DELOAD', 'NEEDS_MORE_DATA']


def week(*, end=date(2026, 9, 29), attendance=None, fatigue=0, discomfort=0):
    # Canonical aggregate fixtures: the planner must trust supplied facts.
    return WeeklyTrainingState(
        week_start=end - timedelta(days=6), week_end=end,
        as_of_date=end - timedelta(days=2), planned_sessions=[],
        included_session_ids=[], unplanned_session_ids=[],
        plan_summary=WeeklyPlanSummary(
            total_planned_sessions=10, completed_planned_sessions=2,
            partial_planned_sessions=3, remaining_planned_sessions=5,
            due_remaining_planned_sessions=4, future_remaining_planned_sessions=1,
        ),
        workload=WeeklyWorkloadFacts(**{
            name: 7 if name == 'unplanned_sessions' else 0
            for name in WeeklyWorkloadFacts.model_fields
        }),
        recovery=WeeklyRecoveryFacts(**{
            name: None if name.startswith('latest_') else
            fatigue if name == 'high_fatigue_sessions' else
            discomfort if name == 'moderate_high_discomfort_sessions' else 0
            for name in WeeklyRecoveryFacts.model_fields
        }),
        adherence=WeeklyAdherenceFacts(
            due_planned_sessions=9, completed_due_sessions=2,
            partial_due_sessions=3, unresolved_due_sessions=4,
            attendance_ratio=attendance,
        ),
    )


def decision(code='PROGRESS', exercise_id='squat'):
    return ProgressionDecision(
        exercise_id=exercise_id, decision=code,
        reason_codes=[ProgressionReasonCode.PERFORMANCE_IMPROVED],
        occurrences_considered=3, latest_session_id='latest-session',
    )


def slot(slot_id='slot', offset=0, session_type='upper_body'):
    return ProgramSessionTemplateInput(
        slot_id=slot_id, day_offset=offset, session_type=session_type,
    )


def planner_input(**changes):
    values = dict(previous_week_state=week(), progression_decisions=[],
                  plan_week_start=date(2026, 9, 30), session_templates=[])
    values.update(changes)
    return ProgramPlannerInput(**values)


def test_empty_inputs_version_week_window_and_non_monday():
    data = planner_input()
    plan = build_program_plan(data)
    assert plan.planner_version == PROGRAM_PLANNER_VERSION == 'program-planner-v1'
    assert plan.plan_week_end == plan.plan_week_start + timedelta(days=6)
    assert plan.plan_week_start.weekday() != 0
    assert plan.sessions == plan.progression_decisions == []
    assert set(plan.plan_summary.model_dump().values()) == {0}
    assert set(plan.progression_summary.model_dump().values()) == {0}
    assert data.previous_week_state.as_of_date < data.previous_week_state.week_end


@pytest.mark.parametrize('start', [date(2026, 10, 1), date(2026, 9, 29), date(2026, 9, 24)])
def test_noncontiguous_weeks_rejected(start):
    with pytest.raises(ValidationError, match='week_end'):
        planner_input(plan_week_start=start)


@pytest.mark.parametrize('end,start', [
    (date.max, date.max),
    (date(9999, 12, 25), date(9999, 12, 26)),
])
def test_date_overflow_is_validation_error(end, start):
    with pytest.raises(ValidationError, match='seven-day'):
        planner_input(previous_week_state=week(end=end), plan_week_start=start)


def test_last_representable_week_allowed():
    plan = build_program_plan(planner_input(
        previous_week_state=week(end=date(9999, 12, 24)),
        plan_week_start=date(9999, 12, 25), session_templates=[slot(offset=6)],
    ))
    assert plan.plan_week_end == plan.sessions[0].scheduled_date == date.max


@pytest.mark.parametrize('changes', [
    {'previous_week_state': week().model_dump()},
    {'progression_decisions': [decision().model_dump()]},
    {'progression_decisions': [decision(), decision('REDUCE')]},
    {'session_templates': [slot(), slot(offset=6)]},
])
def test_canonical_objects_and_unique_identifiers(changes):
    with pytest.raises(ValidationError):
        planner_input(**changes)


@pytest.mark.parametrize('offset', [-1, 7, True, False, 1.0, '1'])
def test_strict_bounded_day_offset(offset):
    with pytest.raises(ValidationError):
        slot(offset=offset)


@pytest.mark.parametrize('identifier', ['', 'x' * 129])
def test_slot_identifier_bounds(identifier):
    with pytest.raises(ValidationError):
        slot(slot_id=identifier)


def test_unknown_session_type_rejected():
    with pytest.raises(ValidationError):
        slot(session_type='rest')


def test_dates_same_day_order_and_all_type_counts():
    templates = [slot(str(i), offset, kind) for i, (offset, kind) in enumerate(zip(
        [6, 0, 3, 0, 2, 6], TYPES + ['upper_body'],
    ))]
    data = planner_input(session_templates=templates)
    plan = build_program_plan(data)
    assert [s.slot_id for s in plan.sessions] == [s.slot_id for s in templates]
    assert [s.session_type for s in plan.sessions] == TYPES + ['upper_body']
    assert [s.scheduled_date for s in plan.sessions] == [
        data.plan_week_start + timedelta(days=s.day_offset) for s in templates
    ]
    assert plan.sessions[1].scheduled_date == plan.sessions[3].scheduled_date
    assert plan.sessions[0].scheduled_date > plan.sessions[1].scheduled_date
    assert plan.plan_summary.model_dump() == dict(
        total_sessions=6, upper_body_sessions=2, lower_body_sessions=1,
        full_body_sessions=1, cardio_sessions=1, mobility_sessions=1,
    )


@pytest.mark.parametrize('codes', [[code] for code in DECISIONS] + [DECISIONS + ['REDUCE']])
def test_progression_categories_counted_without_reinterpretation(codes):
    decisions = [decision(code, str(i)) for i, code in enumerate(codes)]
    plan = build_program_plan(planner_input(progression_decisions=decisions))
    assert plan.progression_decisions == decisions
    assert plan.progression_summary.model_dump() == {
        'total_decisions': len(codes),
        **{code.lower() + '_decisions': codes.count(code) for code in DECISIONS},
    }
    for original, copied in zip(decisions, plan.progression_decisions):
        assert copied.model_dump() == original.model_dump()
        assert copied is not original
        assert copied.reason_codes is not original.reason_codes
        assert copied.occurrences_considered == 3
        assert copied.latest_session_id == 'latest-session'


@pytest.mark.parametrize('attendance', [None, 0.0, 0.625])
def test_previous_context_copied_factually(attendance):
    source = week(attendance=attendance, fatigue=3, discomfort=2)
    plan = build_program_plan(planner_input(previous_week_state=source))
    assert plan.source_week_start == source.week_start
    assert plan.source_week_end == source.week_end
    assert plan.previous_week_context.model_dump() == dict(
        source_week_start=source.week_start, source_week_end=source.week_end,
        source_as_of_date=source.as_of_date, planned_sessions=10,
        completed_planned_sessions=2, partial_planned_sessions=3,
        remaining_planned_sessions=5, due_remaining_planned_sessions=4,
        unplanned_sessions=7, attendance_ratio=attendance,
        high_fatigue_sessions=3, moderate_high_discomfort_sessions=2,
    )


@pytest.mark.parametrize('context,codes', [
    ({'attendance': 0.0}, []), ({'fatigue': 9}, []),
    ({'discomfort': 8}, []), ({}, ['REDUCE']), ({}, ['DELOAD']),
    ({}, ['NEEDS_MORE_DATA']), ({}, ['PROGRESS']),
])
def test_context_never_adapts_or_carries_unresolved_sessions(context, codes):
    templates = [slot('last', 6, 'cardio'), slot('first', 0, 'mobility')]
    data = planner_input(
        previous_week_state=week(**context), session_templates=templates,
        progression_decisions=[decision(code) for code in codes],
    )
    plan = build_program_plan(data)
    assert [(s.slot_id, s.session_type, s.scheduled_date) for s in plan.sessions] == [
        (s.slot_id, s.session_type, data.plan_week_start + timedelta(days=s.day_offset))
        for s in templates
    ]
    assert plan.plan_summary.total_sessions == 2


def test_determinism_nonmutation_and_output_isolation():
    templates, decisions, previous = [slot()], [decision()], week()
    data = planner_input(session_templates=templates, progression_decisions=decisions,
                         previous_week_state=previous)
    before = data.model_dump()
    plan = build_program_plan(data)
    assert plan == build_program_plan(data)
    assert data.model_dump() == before
    assert plan.sessions is not data.session_templates
    assert plan.progression_decisions is not data.progression_decisions
    plan.sessions[0].slot_id = 'edited'
    plan.sessions.clear()
    plan.progression_decisions[0].reason_codes.clear()
    plan.progression_decisions[0].exercise_id = 'edited'
    plan.progression_decisions.clear()
    plan.previous_week_context.planned_sessions = 999
    assert data.model_dump() == before
    assert templates[0].slot_id == 'slot'
    assert decisions[0].reason_codes == [ProgressionReasonCode.PERFORMANCE_IMPROVED]
    assert previous.plan_summary.total_planned_sessions == 10


def examples():
    data = planner_input(session_templates=[slot()])
    plan = build_program_plan(data)
    return [data.session_templates[0], data, plan.sessions[0],
            plan.progression_summary, plan.previous_week_context, plan.plan_summary, plan]


@pytest.mark.parametrize('example', examples(), ids=lambda x: type(x).__name__)
def test_all_new_models_forbid_extra_fields(example):
    values = {name: getattr(example, name) for name in type(example).model_fields}
    with pytest.raises(ValidationError, match='extra_forbidden'):
        type(example)(**values, unexpected='not allowed')


@pytest.mark.parametrize('bad', [-1, True, 1.0, '1'])
def test_summary_and_context_counts_are_strict_nonnegative(bad):
    plan = build_program_plan(planner_input())
    for example in [plan.plan_summary, plan.progression_summary, plan.previous_week_context]:
        for name, value in example.model_dump().items():
            if type(value) is int:
                with pytest.raises(ValidationError):
                    type(example)(**(example.model_dump() | {name: bad}))


def test_exact_contract_fields():
    contracts = {
        ProgramSessionTemplateInput: 'slot_id day_offset session_type',
        ProgramPlannerInput: 'previous_week_state progression_decisions plan_week_start session_templates',
        ProgramSessionPlan: 'slot_id scheduled_date session_type',
        ProgramProgressionSummary: 'total_decisions progress_decisions maintain_decisions reduce_decisions deload_decisions needs_more_data_decisions',
        ProgramPreviousWeekContext: 'source_week_start source_week_end source_as_of_date planned_sessions completed_planned_sessions partial_planned_sessions remaining_planned_sessions due_remaining_planned_sessions unplanned_sessions attendance_ratio high_fatigue_sessions moderate_high_discomfort_sessions',
        ProgramPlanSummary: 'total_sessions upper_body_sessions lower_body_sessions full_body_sessions cardio_sessions mobility_sessions',
        ProgramPlan: 'planner_version source_week_start source_week_end plan_week_start plan_week_end sessions progression_decisions previous_week_context progression_summary plan_summary',
    }
    for model, fields in contracts.items():
        assert set(model.model_fields) == set(fields.split())


def test_pure_dependency_boundary_and_no_clock_timestamps_or_routes():
    root = Path(__file__).resolve().parents[1]
    allowed = {'datetime', 'typing', 'pydantic', 'app.models.progression',
               'app.models.weekly_training_state', 'app.models.program_planner'}
    forbidden = {'evaluate_progression', 'build_weekly_training_state',
                 'now', 'today', 'utcnow', 'timestamp', 'started_at', 'ended_at',
                 'APIRouter', 'FastAPI', 'router'}
    for relative in ['app/models/program_planner.py', 'app/services/program_planner.py']:
        tree = ast.parse((root / relative).read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.module in allowed
                if node.module == 'datetime':
                    assert {item.name for item in node.names} <= {'date', 'timedelta'}
                if node.module == 'app.models.progression':
                    assert {item.name for item in node.names} == {'ProgressionDecision'}
                if node.module == 'app.models.weekly_training_state':
                    assert {item.name for item in node.names} == {'WeeklyTrainingState'}
            elif isinstance(node, ast.Import):
                assert all(item.name in allowed for item in node.names)
            elif isinstance(node, ast.Name):
                assert node.id not in forbidden
            elif isinstance(node, ast.Attribute):
                assert node.attr not in forbidden
