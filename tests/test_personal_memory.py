"""Bounded snapshot contracts, source consistency and mutation isolation."""

import ast
from datetime import date
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from app.models import personal_memory as m
from app.models.cycle_pattern_analyzer import CyclePatternAnalyzerInput
from app.models.cycle_training_history import CycleTrainingHistoryInput, CycleTrainingObservationInput
from app.models.daily_recovery_state import DailyRecoverySignals, DailyRecoveryStateInput
from app.models.progression import ProgressionDecision
from app.models.session_outcome import SessionOutcomeInput
from app.models.training_history import TrainingHistoryInput
from app.models.weekly_training_state import WeeklyTrainingStateInput, WeeklyPlannedSessionInput
from app.services.cycle_pattern_analyzer import analyze_cycle_patterns
from app.services.cycle_training_history import build_cycle_training_history
from app.services.daily_recovery_state import build_daily_recovery_state
from app.services.personal_memory import build_personal_memory as build
from app.services.session_outcome import build_session_outcome
from app.services.training_history import build_training_history
from app.services.weekly_training_state import build_weekly_training_state


SOURCE_FIELDS = set('training_history progression_decisions weekly_training_states '
                    'daily_recovery_states cycle_training_history cycle_pattern_analysis'.split())
COUNT_FIELDS = set('total_training_sessions exercise_histories progression_decisions '
                   'weekly_state_snapshots daily_recovery_snapshots cycle_training_sessions cycle_patterns'.split())
BOOL_FIELDS = {'has_cycle_training_history', 'has_cycle_pattern_analysis'}


def inputs(**changes):
    return dict(training_history=build_training_history(TrainingHistoryInput(outcomes=[])),
                progression_decisions=[], weekly_training_states=[], daily_recovery_states=[]) | changes


def decision(exercise_id='squat', value='MAINTAIN'):
    return ProgressionDecision(exercise_id=exercise_id, decision=value,
                               reason_codes=['PERFORMANCE_STABLE', 'NO_STRONG_CHANGE_SIGNAL'],
                               occurrences_considered=3, latest_session_id='s0')


def weekly(history, start=1, as_of=2, included=()):
    return build_weekly_training_state(WeeklyTrainingStateInput(
        history=history, week_start=date(2026, 4, start), as_of_date=date(2026, 4, as_of),
        included_session_ids=list(included), planned_sessions=[WeeklyPlannedSessionInput(
            slot_id='slot', scheduled_date=date(2026, 4, start),
            linked_session_id=included[0] if included else None,
        )],
    ))


def daily(state):
    return build_daily_recovery_state(DailyRecoveryStateInput(
        current_week_state=state, reported_signals=DailyRecoverySignals(
            sleep_quality=2, fatigue_level=1, energy_level=4, soreness_level='mild',
        ),
    ))


@pytest.fixture
def sources():
    outcomes = [build_session_outcome(SessionOutcomeInput(
        session_id=f's{i}', completion_state='completed', session_type='lower_body',
        feedback=dict(session_rpe=9.0 if i < 4 else 5.0, fatigue_after=4, discomfort_after='none'),
        exercises=[dict(sequence=1, exercise_id='squat', source_status='completed',
                        sets=[dict(set_number=1, status='completed', reps=8)])],
    )) for i in range(12)]
    history = build_training_history(TrainingHistoryInput(outcomes=outcomes))
    cycle = build_cycle_training_history(CycleTrainingHistoryInput(
        training_history=history, cycle_observations=[CycleTrainingObservationInput(
            session_id=f's{i}', phase='luteal' if i < 4 else 'follicular', discomfort='high',
        ) for i in range(12)],
    ))
    states = [weekly(history, 1, 2, ['s0']), weekly(history, 1, 5, ['s0', 's1']),
              weekly(history, 8, 8, ['s2'])]
    return dict(training_history=history, progression_decisions=[decision('z'), decision('a', 'REDUCE')],
                weekly_training_states=states, daily_recovery_states=[daily(states[0]), daily(states[2])],
                cycle_training_history=cycle,
                cycle_pattern_analysis=analyze_cycle_patterns(CyclePatternAnalyzerInput(cycle_history=cycle)))


def test_empty_and_required_history():
    result = build(m.PersonalMemoryInput(**inputs()))
    assert result.summary.model_dump() == dict.fromkeys(COUNT_FIELDS, 0) | dict.fromkeys(BOOL_FIELDS, False)
    assert result.cycle_training_history is result.cycle_pattern_analysis is None
    for field in ('progression_decisions', 'weekly_training_states', 'daily_recovery_states'):
        assert getattr(result, field) == []
    for payload in ({k: v for k, v in inputs().items() if k != 'training_history'},
                    inputs(training_history=None)):
        with pytest.raises(ValidationError):
            m.PersonalMemoryInput(**payload)


@pytest.mark.parametrize('field', sorted(SOURCE_FIELDS))
def test_reject_raw_nested_dictionaries(sources, field):
    value = sources[field]
    sources[field] = [value[0].model_dump()] if isinstance(value, list) else value.model_dump()
    for validate in (m.PersonalMemoryInput.model_validate, build):
        with pytest.raises(ValidationError, match='canonical'):
            validate(sources)


@pytest.mark.parametrize('field', ['progression_decisions', 'weekly_training_states', 'daily_recovery_states'])
@pytest.mark.parametrize('bad', [None, {}, (), [None]])
def test_require_canonical_lists(field, bad):
    with pytest.raises(ValidationError):
        m.PersonalMemoryInput(**inputs(**{field: bad}))


@pytest.mark.parametrize('value', ['PROGRESS', 'MAINTAIN', 'REDUCE', 'DELOAD', 'NEEDS_MORE_DATA'])
def test_progression_values_and_snapshot_order(value):
    decisions = [decision('z', value), decision('a')]
    result = build(m.PersonalMemoryInput(**inputs(progression_decisions=decisions)))
    assert [item.model_dump() for item in result.progression_decisions] == [item.model_dump() for item in decisions]
    with pytest.raises(ValidationError, match='exercise_id must be unique'):
        m.PersonalMemoryInput(**inputs(progression_decisions=[decisions[0], decisions[0].model_copy(deep=True)]))


@pytest.mark.parametrize('indices', [(0,), (0, 1), (0, 1, 2)])
def test_weekly_chronology_and_history_superset(sources, indices):
    states = [sources['weekly_training_states'][i] for i in indices]
    result = build(m.PersonalMemoryInput(**inputs(training_history=sources['training_history'],
                                                weekly_training_states=states)))
    assert [state.model_dump() for state in result.weekly_training_states] == [state.model_dump() for state in states]
    assert len(result.training_history.sessions) > len(states[-1].included_session_ids)


@pytest.mark.parametrize('indices', [(0, 0), (1, 0), (0, 2, 1)])
def test_reject_weekly_duplicate_reversed_nonmonotonic(sources, indices):
    sources['weekly_training_states'] = [sources['weekly_training_states'][i] for i in indices]
    with pytest.raises(ValidationError, match='strictly ascending'):
        m.PersonalMemoryInput(**sources)


@pytest.mark.parametrize('field', ['included_session_ids', 'unplanned_session_ids', 'linked_session_id'])
def test_weekly_references_must_exist(sources, field):
    payload = sources['weekly_training_states'][0].model_dump()
    if field == 'linked_session_id':
        payload['planned_sessions'][0][field] = 'missing'
    else:
        payload[field] = ['missing']
    sources['weekly_training_states'] = [m.WeeklyTrainingState(**payload)]
    with pytest.raises(ValidationError, match='weekly session references'):
        m.PersonalMemoryInput(**sources)


@pytest.mark.parametrize('indices', [(0,), (0, 1)])
def test_recovery_independent_snapshots_allow_missing_dates(sources, indices):
    states = [sources['daily_recovery_states'][i] for i in indices]
    result = build(m.PersonalMemoryInput(**inputs(daily_recovery_states=states)))
    assert [state.model_dump() for state in result.daily_recovery_states] == [state.model_dump() for state in states]
    assert result.weekly_training_states == []
    assert len(result.daily_recovery_states) == len(indices)


@pytest.mark.parametrize('indices', [(0, 0), (1, 0), (0, 1, 0)])
def test_reject_recovery_duplicate_reversed_nonmonotonic(sources, indices):
    sources['daily_recovery_states'] = [sources['daily_recovery_states'][i] for i in indices]
    with pytest.raises(ValidationError, match='strictly ascending state_date'):
        m.PersonalMemoryInput(**sources)


@pytest.mark.parametrize('mismatch', ['count', 'id', 'order', 'facts'])
def test_cycle_history_must_match_every_session(sources, mismatch):
    payload = sources['cycle_training_history'].model_dump()
    if mismatch == 'count':
        payload['sessions'].pop()
    elif mismatch == 'id':
        payload['sessions'][0]['session']['session_id'] = 'other'
    elif mismatch == 'order':
        payload['sessions'].reverse()
    else:
        payload['sessions'][0]['session']['feedback']['session_rpe'] = 1.0
    sources['cycle_training_history'] = m.CycleTrainingHistory(**payload)
    with pytest.raises(ValidationError, match='cycle_training_history session'):
        m.PersonalMemoryInput(**sources)


def test_analysis_requires_cycle_history(sources):
    sources['cycle_training_history'] = None
    with pytest.raises(ValidationError, match='requires cycle_training_history'):
        m.PersonalMemoryInput(**sources)


@pytest.mark.parametrize('field', ['total_sessions', 'sessions_with_cycle_context',
                                 'sessions_without_cycle_context', 'unknown_phase_sessions', 'known_phase_sessions'])
def test_analysis_inventory_guards_individually(sources, field):
    # Isolate each cross-source guard; deliberately bypass upstream count invariants.
    sources['cycle_pattern_analysis'].summary = sources['cycle_pattern_analysis'].summary.model_copy(
        update={field: getattr(sources['cycle_pattern_analysis'].summary, field) + 1})
    with pytest.raises(ValidationError, match=field):
        m.PersonalMemoryInput(**sources)


def test_analysis_version_guard(sources):
    # Future/invalid version used solely to exercise the cross-source check.
    sources['cycle_pattern_analysis'].source_cycle_history_version = 'future'
    with pytest.raises(ValidationError, match='source cycle version'):
        m.PersonalMemoryInput(**sources)


@pytest.mark.parametrize('cycle,analysis', [(False, False), (True, False), (True, True)])
def test_exact_facts_summary_versions_and_determinism(sources, cycle, analysis):
    if not cycle:
        sources['cycle_training_history'] = None
    if not analysis:
        sources['cycle_pattern_analysis'] = None
    data = m.PersonalMemoryInput(**sources)
    before = data.model_dump()
    result = build(data)
    assert data.model_dump() == before
    assert result.model_dump() == build(data).model_dump()
    assert result.memory_version == m.PERSONAL_MEMORY_VERSION == 'personal-memory-v1'
    assert result.source_training_history_version == 'training-history-v1'
    for field in SOURCE_FIELDS:
        assert getattr(result, field) == getattr(data, field)
    assert result.summary.model_dump() == dict(
        total_training_sessions=12, exercise_histories=1, progression_decisions=2,
        weekly_state_snapshots=3, daily_recovery_snapshots=2, has_cycle_training_history=cycle,
        cycle_training_sessions=12 if cycle else 0, has_cycle_pattern_analysis=analysis,
        cycle_patterns=data.cycle_pattern_analysis.summary.detected_patterns if analysis else 0,
    )
    if analysis:
        assert result.cycle_pattern_analysis.patterns


def assert_detached(left, right):
    if isinstance(left, BaseModel):
        assert left is not right
        for field in type(left).model_fields:
            assert_detached(getattr(left, field), getattr(right, field))
    elif isinstance(left, list):
        assert left is not right
        for a, b in zip(left, right, strict=True):
            assert_detached(a, b)
    else:
        assert left == right


def test_deep_isolation_including_nested_lists_and_patterns(sources):
    data = m.PersonalMemoryInput(**sources)
    before = data.model_dump()
    result = build(data)
    for field in SOURCE_FIELDS:
        assert_detached(getattr(result, field), getattr(data, field))
    result.training_history.sessions[0].exercises[0].sets[0].reps = 99
    result.training_history.exercise_history[0].occurrences[0].exercise.sets.clear()
    result.progression_decisions[0].reason_codes.clear()
    result.weekly_training_states[0].adherence.attendance_ratio = 0.0
    result.weekly_training_states[0].recovery.high_fatigue_sessions = 99
    result.daily_recovery_states[0].reported_signals.energy_level = 1
    result.daily_recovery_states[0].flags.low_energy = True
    result.daily_recovery_states[0].recent_training_context.total_sessions = 99
    result.cycle_training_history.sessions[0].session.feedback.fatigue_after = 1
    result.cycle_training_history.sessions[0].cycle_context.phase = 'unknown'
    result.cycle_pattern_analysis.patterns[0].difference = 0.0
    result.cycle_pattern_analysis.phase_evidence.clear()
    result.progression_decisions.clear()
    result.weekly_training_states.clear()
    result.daily_recovery_states.clear()
    assert data.model_dump() == before
    assert build(data).model_dump() != result.model_dump()


def test_exact_model_fields_and_extra_forbid(sources):
    result = build(m.PersonalMemoryInput(**sources))
    assert set(m.PersonalMemoryInput.model_fields) == SOURCE_FIELDS
    assert set(m.PersonalMemory.model_fields) == SOURCE_FIELDS | {
        'memory_version', 'source_training_history_version', 'summary'}
    assert set(m.PersonalMemorySummary.model_fields) == COUNT_FIELDS | BOOL_FIELDS
    for cls, values in [(m.PersonalMemoryInput, sources),
                        (m.PersonalMemory, {field: getattr(result, field) for field in type(result).model_fields}),
                        (m.PersonalMemorySummary, result.summary.model_dump())]:
        assert cls.model_config['extra'] == 'forbid'
        with pytest.raises(ValidationError, match='Extra inputs'):
            cls(**values, inferred_profile='none')


@pytest.mark.parametrize('field', sorted(COUNT_FIELDS))
@pytest.mark.parametrize('bad', [-1, True, 1.0, '1'])
def test_strict_nonnegative_summary_counts(field, bad):
    values = dict.fromkeys(COUNT_FIELDS, 0) | dict.fromkeys(BOOL_FIELDS, True)
    with pytest.raises(ValidationError):
        m.PersonalMemorySummary(**(values | {field: bad}))


@pytest.mark.parametrize('field', sorted(BOOL_FIELDS))
@pytest.mark.parametrize('bad', [0, 1, 'true', None])
def test_strict_summary_booleans(field, bad):
    values = dict.fromkeys(COUNT_FIELDS, 0) | dict.fromkeys(BOOL_FIELDS, True)
    with pytest.raises(ValidationError):
        m.PersonalMemorySummary(**(values | {field: bad}))


@pytest.mark.parametrize('changes', [dict(cycle_training_sessions=1), dict(cycle_patterns=1),
                                   dict(has_cycle_pattern_analysis=True)])
def test_summary_presence_invariants(changes):
    values = dict.fromkeys(COUNT_FIELDS, 0) | dict.fromkeys(BOOL_FIELDS, False)
    with pytest.raises(ValidationError):
        m.PersonalMemorySummary(**(values | changes))


@pytest.mark.parametrize('field', ['memory_version', 'source_training_history_version'])
def test_output_version_literals(field):
    result = build(m.PersonalMemoryInput(**inputs()))
    values = {name: getattr(result, name) for name in type(result).model_fields}
    with pytest.raises(ValidationError):
        m.PersonalMemory(**(values | {field: 'future'}))


def test_no_upstream_recalculation(monkeypatch, sources):
    import importlib

    def forbidden(*args, **kwargs):
        pytest.fail('Personal Memory must not call an upstream engine')

    for module, function in [('training_history', 'build_training_history'),
                             ('progression_engine', 'evaluate_progression'),
                             ('weekly_training_state', 'build_weekly_training_state'),
                             ('daily_recovery_state', 'build_daily_recovery_state'),
                             ('cycle_training_history', 'build_cycle_training_history'),
                             ('cycle_pattern_analyzer', 'analyze_cycle_patterns')]:
        monkeypatch.setattr(importlib.import_module(f'app.services.{module}'), function, forbidden)
    assert build(m.PersonalMemoryInput(**sources)).summary.total_training_sessions == 12


def test_architecture_import_and_call_boundaries():
    root = Path(__file__).resolve().parents[1]
    allowed = {'typing', 'pydantic', 'app.models.personal_memory', 'app.models.training_history',
               'app.models.progression', 'app.models.weekly_training_state', 'app.models.daily_recovery_state',
               'app.models.cycle_training_history', 'app.models.cycle_pattern_analyzer'}
    forbidden = {'now', 'today', 'utcnow', 'open', 'write_text', 'write_bytes', 'eval', 'exec',
                 'build_training_history', 'evaluate_progression', 'build_weekly_training_state',
                 'build_daily_recovery_state', 'build_cycle_training_history', 'analyze_cycle_patterns'}
    for path in ['app/models/personal_memory.py', 'app/services/personal_memory.py']:
        tree = ast.parse((root / path).read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(alias.name in allowed for alias in node.names)
            if isinstance(node, ast.ImportFrom):
                assert node.module in allowed
            if isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, 'attr', '')
                assert name not in forbidden
