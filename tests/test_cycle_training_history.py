"""Bounded factual association, strict contracts and isolation checks."""

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.models import cycle_training_history as models
from app.models.cycle_training_history import (
    CycleTrainingObservationInput as Observation,
    CycleTrainingHistoryInput as Input,
    CycleTrainingContextSnapshot as Context,
    CycleTrainingSessionRecord as Record,
    CycleTrainingHistorySummary as Summary,
    CycleTrainingHistory as History,
)
from app.models.session_outcome import SessionOutcomeInput
from app.models.training_history import TrainingHistoryInput
from app.services.session_outcome import build_session_outcome
from app.services.training_history import build_training_history
from app.services.cycle_training_history import build_cycle_training_history as build


SUMMARY_FIELDS = {
    'total_sessions', 'sessions_with_cycle_context', 'sessions_without_cycle_context',
    'menstruation_sessions', 'follicular_sessions', 'ovulation_sessions',
    'luteal_sessions', 'unknown_phase_sessions', 'sessions_with_known_cycle_discomfort',
    'cycle_discomfort_none_sessions', 'cycle_discomfort_mild_sessions',
    'cycle_discomfort_moderate_sessions', 'cycle_discomfort_high_sessions',
}
PHASES = ['menstruation', 'follicular', 'ovulation', 'luteal', 'unknown']
DISCOMFORTS = ['none', 'mild', 'moderate', 'high', None]


def session(identifier='z', **changes):
    return build_session_outcome(SessionOutcomeInput(**(dict(
        session_id=identifier, completion_state='completed', session_type='lower_body',
        source_action='train', plan_id='plan', actual_duration_seconds=300,
        exercises=[dict(sequence=1, exercise_id='squat', source_status='completed',
                        planned_sets=1, sets=[dict(set_number=1, status='completed',
                                                  reps=8, load_value=20.0, load_unit='kg')])],
        feedback=dict(session_rpe=8.5, fatigue_after=4, discomfort_after='none'),
    ) | changes)))


def source(sessions=None, observations=None):
    return Input(
        training_history=build_training_history(TrainingHistoryInput(
            outcomes=[session()] if sessions is None else sessions,
        )),
        cycle_observations=[] if observations is None else observations,
    )


def test_empty_and_unobserved_history():
    empty = build(source([]))
    assert empty.sessions == []
    assert empty.summary.model_dump() == dict.fromkeys(SUMMARY_FIELDS, 0)
    result = build(source())
    assert result.sessions[0].cycle_context is None
    assert result.summary.model_dump() == (
        dict.fromkeys(SUMMARY_FIELDS, 0)
        | dict(total_sessions=1, sessions_without_cycle_context=1)
    )


@pytest.mark.parametrize('field', ['training_history', 'cycle_observations'])
def test_canonical_nested_inputs_only(field):
    data = source(observations=[Observation(session_id='z', phase='unknown')])
    values = dict(training_history=data.training_history, cycle_observations=data.cycle_observations)
    values[field] = (data.training_history.model_dump() if field == 'training_history'
                     else [data.cycle_observations[0].model_dump()])
    for validate in (Input.model_validate, build):
        with pytest.raises(ValidationError):
            validate(values)
    assert build(data).sessions[0].cycle_context.phase == 'unknown'


@pytest.mark.parametrize('changes', [
    {'session_id': ''}, {'session_id': 'x' * 129}, {'phase': 'fertile'},
    {'phase': None}, {'discomfort': 'severe'}, {'date': '2026-01-01'},
])
def test_invalid_observation(changes):
    with pytest.raises(ValidationError):
        Observation(**(dict(session_id='z', phase='unknown') | changes))


def test_identifier_boundary_and_required_phase():
    assert len(Observation(session_id='x' * 128, phase='unknown').session_id) == 128
    with pytest.raises(ValidationError):
        Observation(session_id='z')


@pytest.mark.parametrize('phase,discomfort', zip(PHASES, DISCOMFORTS))
def test_all_explicit_values(phase, discomfort):
    data = source(observations=[Observation(session_id='z', phase=phase, discomfort=discomfort)])
    assert build(data).sessions[0].cycle_context == Context(phase=phase, discomfort=discomfort)


@pytest.mark.parametrize('ids', [('z', 'z'), ('missing',)])
def test_unique_existing_observation_linkage(ids):
    with pytest.raises(ValidationError):
        source(observations=[Observation(session_id=i, phase='unknown') for i in ids])


def test_missing_unknown_and_explicit_none_are_distinct():
    data = source([session(i) for i in ['missing', 'unknown', 'none']], [
        Observation(session_id='unknown', phase='unknown'),
        Observation(session_id='none', phase='unknown', discomfort='none'),
    ])
    result = build(data)
    assert [r.cycle_context for r in result.sessions] == [
        None, Context(phase='unknown', discomfort=None), Context(phase='unknown', discomfort='none'),
    ]
    assert result.summary.unknown_phase_sessions == 2
    assert result.summary.sessions_with_known_cycle_discomfort == 1
    assert result.summary.cycle_discomfort_none_sessions == 1


def test_exact_mixed_counts_order_and_determinism():
    ids = ['z', 'a', 'y', 'b', 'x', 'c', 'w']
    observations = [Observation(session_id=i, phase=p, discomfort=d)
                    for i, p, d in zip(ids, PHASES, DISCOMFORTS)]
    observations.append(Observation(session_id='c', phase='menstruation', discomfort='high'))
    data = source([session(i) for i in ids], observations)
    result = build(data)
    assert [r.session.session_id for r in result.sessions] == ids
    assert result.summary.model_dump() == dict(
        total_sessions=7, sessions_with_cycle_context=6, sessions_without_cycle_context=1,
        menstruation_sessions=2, follicular_sessions=1, ovulation_sessions=1,
        luteal_sessions=1, unknown_phase_sessions=1, sessions_with_known_cycle_discomfort=5,
        cycle_discomfort_none_sessions=1, cycle_discomfort_mild_sessions=1,
        cycle_discomfort_moderate_sessions=1, cycle_discomfort_high_sessions=2,
    )
    assert build(data) == result
    assert build(Input(training_history=data.training_history,
                       cycle_observations=list(reversed(observations)))) == result


def test_timestamps_preserved_without_sorting_or_phase_inference():
    data = source([
        session('z', started_at='2026-03-03T08:00:00Z', ended_at='2026-03-05T09:00:00Z'),
        session('a', started_at='2026-03-01T08:00:00Z', ended_at='2026-03-06T09:00:00Z'),
        session('b', started_at='2026-03-02T08:00:00Z', ended_at='2026-03-04T09:00:00Z'),
        session('c'),
    ])
    result = build(data)
    assert [r.session for r in result.sessions] == data.training_history.sessions
    assert [r.session.session_id for r in result.sessions] == ['z', 'a', 'b', 'c']
    assert all(r.cycle_context is None for r in result.sessions)
    assert result.sessions[-1].session.started_at is None
    assert result.sessions[-1].session.ended_at is None


@pytest.mark.parametrize('state,kind', [('completed', 'lower_body'), ('interrupted', 'mobility')])
def test_all_session_facts_and_conflicting_discomfort_preserved(state, kind):
    data = source([session(completion_state=state, session_type=kind)], [
        Observation(session_id='z', phase='luteal', discomfort='moderate'),
    ])
    record = build(data).sessions[0]
    assert record.session.model_dump() == data.training_history.sessions[0].model_dump()
    assert record.cycle_context.discomfort == 'moderate'
    assert record.session.feedback.model_dump() == dict(
        session_rpe=8.5, fatigue_after=4, discomfort_after='none',
    )


def test_deep_isolation_and_no_input_mutation():
    observations = [Observation(session_id='z', phase='luteal', discomfort='high')]
    data = source(observations=observations)
    before = data.model_dump()
    result = build(data)
    original = data.training_history.sessions[0]
    copied = result.sessions[0].session
    assert data.model_dump() == before
    assert observations == data.cycle_observations
    assert result.sessions is not data.training_history.sessions
    assert copied is not original
    assert copied.exercises is not original.exercises
    assert copied.exercises[0] is not original.exercises[0]
    assert copied.exercises[0].sets is not original.exercises[0].sets
    assert copied.exercises[0].sets[0] is not original.exercises[0].sets[0]
    assert copied.feedback is not original.feedback
    assert result.sessions[0].cycle_context is not observations[0]
    assert result.sessions[0].cycle_context is not build(data).sessions[0].cycle_context
    copied.session_id = 'edited'
    copied.exercises[0].exercise_id = 'edited'
    copied.exercises[0].sets[0].reps = 99
    copied.feedback.discomfort_after = 'high'
    result.sessions[0].cycle_context.phase = 'unknown'
    result.sessions.clear()
    assert data.model_dump() == before
    assert observations[0].phase == 'luteal'
    assert build(data).sessions[0].session == original


def test_exact_fields_extra_forbid_and_versions():
    data = source(observations=[Observation(session_id='z', phase='unknown')])
    result = build(data)
    contracts = [
        (Observation, {'session_id', 'phase', 'discomfort'}, data.cycle_observations[0].model_dump()),
        (Input, {'training_history', 'cycle_observations'}, dict(
            training_history=data.training_history, cycle_observations=data.cycle_observations)),
        (Context, {'phase', 'discomfort'}, result.sessions[0].cycle_context.model_dump()),
        (Record, {'session', 'cycle_context'}, result.sessions[0].model_dump()),
        (Summary, SUMMARY_FIELDS, result.summary.model_dump()),
        (History, {'cycle_history_version', 'source_training_history_version', 'sessions', 'summary'},
         result.model_dump()),
    ]
    for model, fields, payload in contracts:
        assert set(model.model_fields) == fields  # No analysis, calendar or recommendation fields.
        assert model.model_config['extra'] == 'forbid'
        with pytest.raises(ValidationError):
            model.model_validate(payload | {'unexpected': 1})
    assert result.cycle_history_version == models.CYCLE_TRAINING_HISTORY_VERSION == 'cycle-training-history-v1'
    assert result.source_training_history_version == data.training_history.history_version == 'training-history-v1'
    for field in ['cycle_history_version', 'source_training_history_version']:
        with pytest.raises(ValidationError):
            History.model_validate(result.model_dump() | {field: 'v2'})


@pytest.mark.parametrize('invalid', [-1, True, 1.0, '1'])
def test_every_summary_integer_is_strict_and_nonnegative(invalid):
    for field in SUMMARY_FIELDS:
        with pytest.raises(ValidationError):
            Summary(**(dict.fromkeys(SUMMARY_FIELDS, 0) | {field: invalid}))


@pytest.mark.parametrize('changes', [
    {'total_sessions': 1},
    {'total_sessions': 1, 'sessions_with_cycle_context': 1},
    {'cycle_discomfort_high_sessions': 1},
    {'sessions_with_known_cycle_discomfort': 1, 'cycle_discomfort_high_sessions': 1},
])
def test_summary_invariants(changes):
    with pytest.raises(ValidationError):
        Summary(**(dict.fromkeys(SUMMARY_FIELDS, 0) | changes))


def test_architecture_import_and_call_boundaries():
    root = Path(__file__).resolve().parents[1]
    allowed = {'typing', 'pydantic', 'app.models.session_outcome',
               'app.models.training_history', 'app.models.cycle_training_history'}
    forbidden_calls = {'now', 'today', 'utcnow', 'time', 'sorted', 'sort',
                       'build_training_history', 'normalize_cycle_context', 'open',
                       'evaluate_progression', 'build_daily_recovery_state'}
    for relative in ['app/models/cycle_training_history.py', 'app/services/cycle_training_history.py']:
        tree = ast.parse((root / relative).read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.module in allowed
            elif isinstance(node, ast.Import):
                assert all(alias.name in allowed for alias in node.names)
            elif isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, 'attr', '')
                assert name not in forbidden_calls
