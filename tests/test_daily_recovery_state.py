"""Bounded daily context contracts, signal semantics and pure engine boundaries."""

import ast
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.models.daily_recovery_state import (
    RECOVERY_DAILY_STATE_VERSION, DailyRecoverySignals, DailyRecoveryStateInput,
    DailyRecoveryFlags, DailyRecentTrainingContext, DailyRecoverySignalSummary,
    DailyRecoveryState,
)
from app.models.weekly_training_state import (
    WeeklyTrainingState, WeeklyPlanSummary, WeeklyWorkloadFacts,
    WeeklyRecoveryFacts, WeeklyAdherenceFacts,
)
from app.services.daily_recovery_state import build_daily_recovery_state


def week():
    # Deliberately independent aggregate facts: never reconstruct from ID lists.
    return WeeklyTrainingState(
        week_start=date(2020, 2, 25), week_end=date(2020, 3, 2),
        as_of_date=date(2020, 2, 29), planned_sessions=[],
        included_session_ids=[], unplanned_session_ids=[],
        plan_summary=WeeklyPlanSummary(
            total_planned_sessions=9, completed_planned_sessions=2,
            partial_planned_sessions=1, remaining_planned_sessions=6,
            due_remaining_planned_sessions=4, future_remaining_planned_sessions=2,
        ),
        workload=WeeklyWorkloadFacts(**{
            name: value for value, name in enumerate(WeeklyWorkloadFacts.model_fields, 1)
        }),
        recovery=WeeklyRecoveryFacts(
            sessions_with_feedback=8, sessions_with_known_fatigue=7,
            high_fatigue_sessions=3, latest_known_fatigue_after=5,
            sessions_with_known_discomfort=6, moderate_high_discomfort_sessions=2,
            latest_known_discomfort_after='high', sessions_with_known_session_rpe=4,
            latest_known_session_rpe=8.5,
        ),
        adherence=WeeklyAdherenceFacts(
            due_planned_sessions=7, completed_due_sessions=2,
            partial_due_sessions=1, unresolved_due_sessions=4, attendance_ratio=None,
        ),
    )


def data(**signals):
    return DailyRecoveryStateInput(
        current_week_state=week(), reported_signals=DailyRecoverySignals(**signals),
    )


def test_canonical_input_and_all_unknown():
    source = data()
    assert isinstance(source.current_week_state, WeeklyTrainingState)
    assert isinstance(source.reported_signals, DailyRecoverySignals)
    result = build_daily_recovery_state(source)
    assert set(result.reported_signals.model_dump().values()) == {None}
    assert not any(result.flags.model_dump().values())
    assert result.signal_summary.model_dump() == dict(
        supported_signals=6, reported_signals=0, missing_signals=6, flagged_signals=0,
    )


@pytest.mark.parametrize('field', ['current_week_state', 'reported_signals'])
def test_raw_nested_dictionaries_rejected_at_input_and_builder(field):
    source = data()
    values = dict(current_week_state=source.current_week_state,
                  reported_signals=source.reported_signals)
    values[field] = values[field].model_dump()
    with pytest.raises(ValidationError):
        DailyRecoveryStateInput(**values)
    with pytest.raises(ValidationError):
        build_daily_recovery_state(values)


@pytest.mark.parametrize('field', ['sleep_quality', 'energy_level', 'fatigue_level'])
def test_strict_reported_scales(field):
    for value in (1, 5, None):
        assert getattr(DailyRecoverySignals(**{field: value}), field) == value
    for value in (0, 6, True, 2.0, '2'):
        with pytest.raises(ValidationError):
            DailyRecoverySignals(**{field: value})


def test_strict_sleep_duration():
    for value in (0, 1440, None):
        assert DailyRecoverySignals(sleep_duration_minutes=value).sleep_duration_minutes == value
    for value in (-1, 1441, True, 60.0, '60'):
        with pytest.raises(ValidationError):
            DailyRecoverySignals(sleep_duration_minutes=value)


@pytest.mark.parametrize('field', ['soreness_level', 'discomfort_level'])
def test_categories(field):
    for value in ('none', 'mild', 'moderate', 'high', None):
        assert getattr(DailyRecoverySignals(**{field: value}), field) == value
    with pytest.raises(ValidationError):
        DailyRecoverySignals(**{field: 'unknown'})


@pytest.mark.parametrize('field,flag,cases', [
    ('sleep_quality', 'low_sleep_quality', [(1, True), (2, True), (3, False), (5, False), (None, False)]),
    ('energy_level', 'low_energy', [(1, True), (2, True), (3, False), (5, False), (None, False)]),
    ('fatigue_level', 'high_fatigue', [(1, False), (3, False), (4, True), (5, True), (None, False)]),
    ('soreness_level', 'moderate_high_soreness', [('none', False), ('mild', False), ('moderate', True), ('high', True), (None, False)]),
    ('discomfort_level', 'moderate_high_discomfort', [('none', False), ('mild', False), ('moderate', True), ('high', True), (None, False)]),
])
def test_exact_daily_flags(field, flag, cases):
    for value, expected in cases:
        result = build_daily_recovery_state(data(**{field: value}))
        assert result.flags.model_dump() == {
            name: expected if name == flag else False for name in DailyRecoveryFlags.model_fields
        }
        assert result.signal_summary.flagged_signals == int(expected)


@pytest.mark.parametrize('duration', [0, 1, 1440])
def test_duration_is_reported_without_flag(duration):
    result = build_daily_recovery_state(data(sleep_duration_minutes=duration))
    assert not any(result.flags.model_dump().values())
    assert result.signal_summary.reported_signals == 1
    assert result.signal_summary.missing_signals == 5


def test_exact_recent_facts_and_versions():
    source = data()
    result = build_daily_recovery_state(source)
    assert result.recovery_version == RECOVERY_DAILY_STATE_VERSION == 'recovery-daily-state-v1'
    assert result.source_week_state_version == source.current_week_state.state_version
    assert result.state_date == date(2020, 2, 29)
    assert result.recent_training_context.model_dump() == dict(
        source_week_start=date(2020, 2, 25), source_week_end=date(2020, 3, 2),
        source_as_of_date=date(2020, 2, 29), total_sessions=1, completed_sessions=2,
        interrupted_sessions=3, unplanned_sessions=4, known_duration_seconds=13,
        due_remaining_planned_sessions=4, high_fatigue_sessions=3,
        latest_known_fatigue_after=5, moderate_high_discomfort_sessions=2,
        latest_known_discomfort_after='high', latest_known_session_rpe=8.5,
    )


def test_daily_and_weekly_conflicting_facts_remain_distinct():
    result = build_daily_recovery_state(data(fatigue_level=1, discomfort_level='none'))
    assert result.reported_signals.fatigue_level == 1
    assert result.recent_training_context.latest_known_fatigue_after == 5
    assert result.reported_signals.discomfort_level == 'none'
    assert result.recent_training_context.latest_known_discomfort_after == 'high'
    assert not result.flags.high_fatigue
    assert not result.flags.moderate_high_discomfort
    source = data(fatigue_level=5, discomfort_level='high')
    source.current_week_state.recovery.high_fatigue_sessions = 0
    source.current_week_state.recovery.moderate_high_discomfort_sessions = 0
    source.current_week_state.recovery.latest_known_fatigue_after = None
    source.current_week_state.recovery.latest_known_discomfort_after = None
    source.current_week_state.recovery.latest_known_session_rpe = None
    result = build_daily_recovery_state(source)
    assert result.flags.high_fatigue and result.flags.moderate_high_discomfort
    assert result.recent_training_context.high_fatigue_sessions == 0
    assert result.recent_training_context.moderate_high_discomfort_sessions == 0
    assert result.recent_training_context.latest_known_fatigue_after is None
    assert result.recent_training_context.latest_known_discomfort_after is None
    assert result.recent_training_context.latest_known_session_rpe is None


@pytest.mark.parametrize('signals,reported,flagged', [
    ({}, 0, 0),
    (dict(sleep_quality=1, sleep_duration_minutes=0, energy_level=2,
          fatigue_level=4, soreness_level='moderate', discomfort_level='high'), 6, 5),
    (dict(sleep_quality=5, energy_level=1, discomfort_level='none'), 3, 1),
])
def test_summary(signals, reported, flagged):
    summary = build_daily_recovery_state(data(**signals)).signal_summary
    assert summary.model_dump() == dict(supported_signals=6, reported_signals=reported,
                                        missing_signals=6-reported, flagged_signals=flagged)
    assert summary.reported_signals + summary.missing_signals == 6
    assert summary.flagged_signals <= summary.reported_signals


@pytest.mark.parametrize('changes', [
    dict(supported_signals=5), dict(missing_signals=2), dict(flagged_signals=4),
])
def test_summary_invariants_rejected(changes):
    values = dict(supported_signals=6, reported_signals=3, missing_signals=3, flagged_signals=1)
    values.update(changes)
    with pytest.raises(ValidationError):
        DailyRecoverySignalSummary(**values)


def test_exact_fields_and_extra_rejection_on_every_model():
    source = data()
    result = build_daily_recovery_state(source)
    cases = [
        (source, {'current_week_state', 'reported_signals'}),
        (source.reported_signals, {'sleep_quality', 'sleep_duration_minutes', 'energy_level',
                                   'fatigue_level', 'soreness_level', 'discomfort_level'}),
        (result, {'recovery_version', 'source_week_state_version', 'state_date',
                  'reported_signals', 'recent_training_context', 'flags', 'signal_summary'}),
        (result.flags, {'low_sleep_quality', 'low_energy', 'high_fatigue',
                        'moderate_high_soreness', 'moderate_high_discomfort'}),
        (result.signal_summary, {'supported_signals', 'reported_signals', 'missing_signals', 'flagged_signals'}),
        (result.recent_training_context, {'source_week_start', 'source_week_end', 'source_as_of_date',
            'total_sessions', 'completed_sessions', 'interrupted_sessions', 'unplanned_sessions',
            'known_duration_seconds', 'due_remaining_planned_sessions', 'high_fatigue_sessions',
            'latest_known_fatigue_after', 'moderate_high_discomfort_sessions',
            'latest_known_discomfort_after', 'latest_known_session_rpe'}),
    ]
    for model, expected in cases:
        assert set(type(model).model_fields) == expected
        values = {name: getattr(model, name) for name in expected}
        with pytest.raises(ValidationError, match='extra_forbidden'):
            type(model)(**values, unexpected=True)


def test_strict_context_and_summary_counts():
    result = build_daily_recovery_state(data())
    for model in (result.recent_training_context, result.signal_summary):
        values = model.model_dump()
        fields = [name for name, value in values.items() if type(value) is int
                  and name != 'latest_known_fatigue_after']
        for field in fields:
            for invalid in (-1, True, 1.0, '1'):
                with pytest.raises(ValidationError):
                    type(model)(**(values | {field: invalid}))


@pytest.mark.parametrize('field,invalids', [
    ('latest_known_fatigue_after', [0, 6, True, 1.0, '1']),
    ('latest_known_session_rpe', [0.0, 10.1, True, '5', float('nan')]),
    ('latest_known_discomfort_after', ['unknown']),
])
def test_recent_feedback_strictness(field, invalids):
    values = build_daily_recovery_state(data()).recent_training_context.model_dump()
    for invalid in invalids:
        with pytest.raises(ValidationError):
            DailyRecentTrainingContext(**(values | {field: invalid}))


@pytest.mark.parametrize('field', ['recovery_version', 'source_week_state_version'])
def test_version_literals(field):
    values = build_daily_recovery_state(data()).model_dump()
    with pytest.raises(ValidationError):
        DailyRecoveryState(**(values | {field: 'v2'}))


def test_determinism_and_mutation_isolation():
    source = data(fatigue_level=4)
    before = source.model_dump()
    first = build_daily_recovery_state(source)
    second = build_daily_recovery_state(source)
    assert first == second
    assert source.model_dump() == before
    assert first.reported_signals is not source.reported_signals
    for field in ('reported_signals', 'recent_training_context', 'flags', 'signal_summary'):
        assert getattr(first, field) is not getattr(second, field)
    first.reported_signals.fatigue_level = 1
    first.recent_training_context.high_fatigue_sessions = 99
    first.flags.high_fatigue = False
    first.signal_summary.flagged_signals = 0
    assert source.model_dump() == before
    assert build_daily_recovery_state(source) == second


def test_pure_architecture_import_and_call_boundaries():
    root = Path(__file__).resolve().parents[1]
    allowed = {
        'app/models/daily_recovery_state.py': {'datetime', 'typing', 'pydantic',
                                              'app.models.weekly_training_state'},
        'app/services/daily_recovery_state.py': {'app.models.daily_recovery_state'},
    }
    forbidden = {'now', 'today', 'utcnow', 'open', '__import__', 'eval', 'exec',
                 'build_weekly_training_state', 'evaluate_progression'}
    for path, modules in allowed.items():
        tree = ast.parse((root / path).read_text(encoding='utf-8'))
        imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        assert imports == modules
        assert not any(isinstance(node, ast.Import) for node in ast.walk(tree))
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        names |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
        assert not names & forbidden
        assert not names & {'SessionOutcome', 'TrainingHistory', 'ProgressionDecision',
                             'sessions', 'feedback', 'started_at', 'ended_at'}
