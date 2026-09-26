"""Evidence boundaries, exact contracts and pure historical association checks."""

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.models import cycle_pattern_analyzer as m
from app.models.cycle_training_history import (
    CycleTrainingHistory, CycleTrainingHistorySummary, CycleTrainingSessionRecord,
    CycleTrainingContextSnapshot,
)
from app.models.session_outcome import SessionOutcomeInput
from app.services.session_outcome import build_session_outcome
from app.services.cycle_pattern_analyzer import analyze_cycle_patterns as analyze


PHASES = ['menstruation', 'follicular', 'ovulation', 'luteal', 'unknown']
TYPES = ['upper_body', 'lower_body', 'full_body', 'cardio', 'mobility']
METRICS = ['session_rpe', 'fatigue_after', 'post_session_discomfort']
EVIDENCE_FIELDS = set('phase observed_sessions completed_sessions interrupted_sessions '
    'sessions_with_known_rpe mean_session_rpe sessions_with_known_fatigue mean_fatigue_after '
    'sessions_with_known_post_discomfort moderate_high_post_discomfort_sessions '
    'moderate_high_post_discomfort_ratio sessions_with_known_cycle_discomfort '
    'moderate_high_cycle_discomfort_sessions moderate_high_cycle_discomfort_ratio'.split())
PATTERN_FIELDS = set('phase session_type metric direction phase_sample_size comparator_sample_size '
                     'phase_value comparator_value difference threshold'.split())
SUMMARY_FIELDS = set('total_sessions sessions_with_cycle_context sessions_without_cycle_context '
    'known_phase_sessions unknown_phase_sessions sessions_eligible_for_pattern_analysis '
    'detected_patterns rpe_patterns fatigue_patterns post_session_discomfort_patterns'.split())


def record(phase='luteal', session_type='lower_body', cycle=None, **changes):
    session = build_session_outcome(SessionOutcomeInput(**(dict(
        session_id='session', completion_state='completed', session_type=session_type,
        exercises=[], feedback=None,
    ) | changes)))
    return CycleTrainingSessionRecord(session=session, cycle_context=(
        CycleTrainingContextSnapshot(phase=phase, discomfort=cycle) if phase is not None else None
    ))


def source(records=()):
    counts = dict.fromkeys(CycleTrainingHistorySummary.model_fields, 0)
    for item in records:
        counts['total_sessions'] += 1
        context = item.cycle_context
        if context is None:
            counts['sessions_without_cycle_context'] += 1
            continue
        counts['sessions_with_cycle_context'] += 1
        counts['unknown_phase_sessions' if context.phase == 'unknown' else context.phase + '_sessions'] += 1
        if context.discomfort is not None:
            counts['sessions_with_known_cycle_discomfort'] += 1
            counts['cycle_discomfort_' + context.discomfort + '_sessions'] += 1
    return m.CyclePatternAnalyzerInput(cycle_history=CycleTrainingHistory(
        source_training_history_version='training-history-v1', sessions=list(records),
        summary=CycleTrainingHistorySummary(**counts),
    ))


def group(values, metric='session_rpe', **kwargs):
    field = 'discomfort_after' if metric == 'post_session_discomfort' else metric
    return [record(feedback={field: value}, **kwargs) for value in values]


def comparison(target, comparator, metric='session_rpe'):
    return source(group(target, metric) + group(comparator, metric, phase='follicular'))


def test_canonical_input_empty_and_exact_phase_inventory():
    data = source()
    result = analyze(data)
    assert result.summary.model_dump() == dict.fromkeys(SUMMARY_FIELDS, 0)
    assert [item.phase for item in result.phase_evidence] == PHASES
    assert result.patterns == []
    for item in result.phase_evidence:
        assert all(value in (0, None) for key, value in item.model_dump().items() if key != 'phase')
    for validate in (m.CyclePatternAnalyzerInput.model_validate, analyze):
        with pytest.raises(ValidationError):
            validate({'cycle_history': data.cycle_history.model_dump()})
        with pytest.raises(ValidationError):
            validate({'cycle_history': data.cycle_history, 'current_phase': 'luteal'})


def test_descriptive_evidence_missing_unknown_and_distinct_discomfort():
    data = source([
        record(feedback=dict(session_rpe=8.0, fatigue_after=4, discomfort_after='none'), cycle='high'),
        record(feedback=dict(session_rpe=7.0, fatigue_after=2, discomfort_after='mild'), cycle='none'),
        record(feedback=dict(session_rpe=7.0, fatigue_after=2, discomfort_after='moderate'), cycle='mild'),
        record(session_type=None, feedback=dict(discomfort_after='high'), cycle='moderate'),
        record(completion_state='interrupted'), record(feedback={}),
        record(phase='unknown', cycle='none'), record(phase=None),
    ])
    result = analyze(data)
    assert result.phase_evidence[3].model_dump() == dict(
        phase='luteal', observed_sessions=6, completed_sessions=5, interrupted_sessions=1,
        sessions_with_known_rpe=3, mean_session_rpe=7.3333,
        sessions_with_known_fatigue=3, mean_fatigue_after=2.6667,
        sessions_with_known_post_discomfort=4, moderate_high_post_discomfort_sessions=2,
        moderate_high_post_discomfort_ratio=0.5, sessions_with_known_cycle_discomfort=4,
        moderate_high_cycle_discomfort_sessions=2, moderate_high_cycle_discomfort_ratio=0.5,
    )
    assert result.phase_evidence[4].observed_sessions == 1
    assert sum(item.observed_sessions for item in result.phase_evidence) == 7
    assert result.summary.model_dump() == dict.fromkeys(SUMMARY_FIELDS, 0) | dict(
        total_sessions=8, sessions_with_cycle_context=7, sessions_without_cycle_context=1,
        known_phase_sessions=6, unknown_phase_sessions=1, sessions_eligible_for_pattern_analysis=5,
    )
    rounded = analyze(source(group(['none', 'none', 'high'], 'post_session_discomfort')))
    assert rounded.phase_evidence[3].moderate_high_post_discomfort_ratio == 0.3333


@pytest.mark.parametrize('metric,target,other,threshold,expected', [
    ('session_rpe', 7.49, 6.0, 1.5, None),
    ('session_rpe', 7.5, 6.0, 1.5, 'higher'),
    ('session_rpe', 4.5, 6.0, 1.5, 'lower'),
    ('session_rpe', 9.0, 6.0, 1.5, 'higher'),
    ('session_rpe', 2.0, 6.0, 1.5, 'lower'),
    ('session_rpe', 6.0, 6.0, 1.5, None),
    ('fatigue_after', 3, 3, 1.0, None),
    ('fatigue_after', 4, 3, 1.0, 'higher'),
    ('fatigue_after', 2, 3, 1.0, 'lower'),
])
def test_numeric_thresholds(metric, target, other, threshold, expected):
    result = analyze(comparison([target] * 4, [other] * 8, metric))
    patterns = result.patterns
    if expected is None:
        assert patterns == []
    else:
        assert [p.model_dump() for p in patterns] == [dict(
            phase='luteal', session_type='lower_body', metric=metric, direction=expected,
            phase_sample_size=4, comparator_sample_size=8, phase_value=float(target),
            comparator_value=float(other), difference=round(target - other, 4), threshold=threshold,
        )]


@pytest.mark.parametrize('target_high,other_high,direction', [(5, 2, 'higher'), (2, 5, 'lower'), (4, 2, None)])
def test_post_discomfort_exact_ratio_threshold(target_high, other_high, direction):
    target = ['high'] * target_high + ['mild'] * (10 - target_high) + [None]
    other = ['moderate'] * other_high + ['none'] * (10 - other_high) + [None]
    result = analyze(comparison(target, other, 'post_session_discomfort'))
    patterns = [p for p in result.patterns if p.phase == 'luteal']
    if direction is None:
        assert not patterns
    else:
        assert patterns[0].model_dump() == dict(
            phase='luteal', session_type='lower_body', metric='post_session_discomfort', direction=direction,
            phase_sample_size=10, comparator_sample_size=10, phase_value=target_high / 10,
            comparator_value=other_high / 10, difference=0.3 if direction == 'higher' else -0.3,
            threshold=0.30,
        )


@pytest.mark.parametrize('metric,high,low', [('session_rpe', 9.0, 3.0), ('fatigue_after', 5, 1),
                                           ('post_session_discomfort', 'high', 'none')])
@pytest.mark.parametrize('target_count,other_count,qualifies', [(3, 8, False), (4, 7, False), (4, 8, True)])
def test_metric_specific_minimums(metric, high, low, target_count, other_count, qualifies):
    data = comparison([high] * target_count + [None] * 10, [low] * other_count + [None] * 10, metric)
    result = analyze(data)
    assert bool(result.patterns) is qualifies
    assert all(p.metric == metric for p in result.patterns)


@pytest.mark.parametrize('phase,session_type', [('unknown', 'lower_body'), (None, 'lower_body'),
    ('follicular', None), ('follicular', 'upper_body'), ('follicular', 'cardio')])
def test_ineligible_comparators_do_not_fill_minimum(phase, session_type):
    data = source(group([9.0] * 4) + group([3.0] * 7, phase='follicular')
                  + group([1.0] * 20, phase=phase, session_type=session_type))
    assert analyze(data).patterns == []


def test_untyped_target_is_descriptive_only_and_mixed_types_never_compare():
    data = source(group([9.0] * 4, session_type=None) + group([2.0] * 8, phase='follicular'))
    result = analyze(data)
    assert not result.patterns
    assert result.phase_evidence[3].mean_session_rpe == 9.0
    for other_type in ['upper_body', 'cardio']:
        assert not analyze(source(group([9.0] * 4) + group([2.0] * 8, phase='follicular',
                                                                       session_type=other_type))).patterns


def test_comparator_combines_all_other_known_phases_and_rounded_values():
    data = source(group([8.12344] * 4) + group([3.0] * 2, phase='menstruation')
                  + group([6.0] * 3, phase='follicular') + group([7.0] * 3, phase='ovulation')
                  + group([10.0] * 20, phase='unknown') + group([10.0] * 20, phase=None))
    pattern = next(p for p in analyze(data).patterns if p.phase == 'luteal')
    assert (pattern.phase_value, pattern.comparator_value, pattern.difference) == (8.1234, 5.625, 2.4984)
    assert (pattern.phase_sample_size, pattern.comparator_sample_size) == (4, 8)


def test_independent_feedback_denominators_and_fractional_fatigue_below_threshold():
    target = [record(feedback=dict(session_rpe=9.0, fatigue_after=5 if i < 3 else None,
                                  discomfort_after='high')) for i in range(4)]
    other = [record(phase='follicular', feedback=dict(
        session_rpe=2.0, fatigue_after=1, discomfort_after='none' if i < 7 else None))
        for i in range(8)]
    assert [p.metric for p in analyze(source(target + other)).patterns] == ['session_rpe']
    assert not analyze(comparison([3, 4, 4, 4], [3] * 8, 'fatigue_after')).patterns
    evidence = analyze(source([record(cycle=value) for value in ['none', 'high', 'mild']])).phase_evidence[3]
    assert evidence.moderate_high_cycle_discomfort_ratio == 0.3333


def test_order_summary_determinism_and_mutation_isolation():
    records = [record(phase=phase, session_type=kind, feedback=dict(
        session_rpe=9.0 if phase == 'luteal' else 2.0,
        fatigue_after=5 if phase == 'luteal' else 1,
        discomfort_after='high' if phase == 'luteal' else 'none'))
        for phase in PHASES[:4] for kind in TYPES for _ in range(4)]
    data = source(records)
    before = data.model_dump()
    first, second = analyze(data), analyze(data)
    assert first == second == analyze(source(list(reversed(records))))
    assert [(p.phase, p.session_type, p.metric) for p in first.patterns] == [
        (phase, kind, metric) for phase in PHASES[:4] for kind in TYPES for metric in METRICS
    ]
    assert first.summary.model_dump() == dict(total_sessions=80, sessions_with_cycle_context=80,
        sessions_without_cycle_context=0, known_phase_sessions=80, unknown_phase_sessions=0,
        sessions_eligible_for_pattern_analysis=80, detected_patterns=60, rpe_patterns=20,
        fatigue_patterns=20, post_session_discomfort_patterns=20)
    assert first is not second and first.summary is not second.summary
    assert all(a is not b for a, b in zip(first.phase_evidence, second.phase_evidence))
    assert all(a is not b for a, b in zip(first.patterns, second.patterns))
    first.phase_evidence[0].observed_sessions = 999
    first.patterns[0].phase_value = 1.0
    first.summary.total_sessions = 999
    assert data.model_dump() == before
    assert analyze(data) == second


def test_unanalyzed_facts_do_not_generate_patterns():
    records = [record(phase=phase, cycle='high' if phase == 'luteal' else 'none',
        completion_state='interrupted' if phase == 'luteal' else 'completed',
        actual_duration_seconds=30 if phase == 'luteal' else 3000,
        exercises=[dict(sequence=1, exercise_id='squat', source_status='completed', sets=[dict(
            set_number=1, status='completed', reps=1 if phase == 'luteal' else 20,
            load_value=10.0 if phase == 'luteal' else 100.0, load_unit='kg')])])
        for phase in PHASES[:4] for _ in range(8)]
    data = source(records)
    before = data.model_dump()
    assert not analyze(data).patterns
    assert data.model_dump() == before


@pytest.mark.parametrize('field', ['total_sessions', 'sessions_with_cycle_context', 'detected_patterns',
                                  'sessions_eligible_for_pattern_analysis'])
def test_summary_invariants(field):
    values = dict.fromkeys(SUMMARY_FIELDS, 0) | {field: 1}
    with pytest.raises(ValidationError):
        m.CyclePatternAnalysisSummary(**values)


def output_models():
    result = analyze(comparison([9.0] * 4, [2.0] * 8))
    return [result, result.phase_evidence[0], result.patterns[0], result.summary]


def test_exact_fields_versions_extras_and_no_policy_fields():
    models = output_models()
    expected = [set('analyzer_version source_cycle_history_version phase_evidence patterns summary'.split()),
                EVIDENCE_FIELDS, PATTERN_FIELDS, SUMMARY_FIELDS]
    assert set(m.CyclePatternAnalyzerInput.model_fields) == {'cycle_history'}
    assert m.CYCLE_PATTERN_ANALYZER_VERSION == models[0].analyzer_version == 'cycle-pattern-analyzer-v1'
    assert models[0].source_cycle_history_version == 'cycle-training-history-v1'
    assert (m.MIN_PHASE_METRIC_SAMPLES, m.MIN_COMPARATOR_METRIC_SAMPLES) == (4, 8)
    assert (m.RPE_MEAN_DIFFERENCE_THRESHOLD, m.FATIGUE_MEAN_DIFFERENCE_THRESHOLD,
            m.POST_DISCOMFORT_RATIO_DIFFERENCE_THRESHOLD) == (1.5, 1.0, 0.3)
    for obj, fields in zip(models, expected):
        assert set(type(obj).model_fields) == fields
        assert obj.model_config['extra'] == 'forbid'
        with pytest.raises(ValidationError):
            type(obj).model_validate(obj.model_dump() | {'recommendation': 'reduce'})
    for field in ['analyzer_version', 'source_cycle_history_version']:
        with pytest.raises(ValidationError):
            m.CyclePatternAnalysis.model_validate(models[0].model_dump() | {field: 'v2'})
    for phases in [[], models[0].phase_evidence[:4], list(reversed(models[0].phase_evidence))]:
        with pytest.raises(ValidationError):
            m.CyclePatternAnalysis.model_validate(models[0].model_dump() | {'phase_evidence': phases})


@pytest.mark.parametrize('bad', [-1, True, 1.0, '1'])
def test_all_count_fields_strict_nonnegative(bad):
    for obj in output_models()[1:]:
        for field, value in obj.model_dump().items():
            if type(value) is int:
                with pytest.raises(ValidationError):
                    type(obj).model_validate(obj.model_dump() | {field: bad})


@pytest.mark.parametrize('bad', [float('nan'), float('inf'), -float('inf'), True, '1.0'])
def test_numeric_fields_strict_and_finite(bad):
    _, evidence, pattern, _ = output_models()
    for obj, fields in [(evidence, ['mean_session_rpe', 'mean_fatigue_after',
                                  'moderate_high_post_discomfort_ratio', 'moderate_high_cycle_discomfort_ratio']),
                        (pattern, ['phase_value', 'comparator_value', 'difference', 'threshold'])]:
        for field in fields:
            with pytest.raises(ValidationError):
                type(obj).model_validate(obj.model_dump() | {field: bad})


@pytest.mark.parametrize('field,values', [('mean_session_rpe', [0.9, 10.1]),
    ('mean_fatigue_after', [0.9, 5.1]), ('moderate_high_post_discomfort_ratio', [-0.1, 1.1]),
    ('moderate_high_cycle_discomfort_ratio', [-0.1, 1.1])])
def test_evidence_ranges(field, values):
    evidence = output_models()[1].model_dump()
    for value in values:
        with pytest.raises(ValidationError):
            m.CyclePhaseEvidence(**(evidence | {field: value}))


@pytest.mark.parametrize('field,value', [('phase', 'unknown'), ('session_type', None),
    ('metric', 'cycle_discomfort'), ('metric', 'duration'), ('direction', 'equal')])
def test_pattern_literals(field, value):
    with pytest.raises(ValidationError):
        m.CycleObservedPattern(**(output_models()[2].model_dump() | {field: value}))


def test_architecture_import_and_call_boundaries():
    root = Path(__file__).resolve().parents[1]
    allowed = {'typing', 'pydantic', 'math', 'app.models.cycle_pattern_analyzer',
               'app.models.cycle_training_history', 'app.models.session_outcome'}
    for relative in ['app/models/cycle_pattern_analyzer.py', 'app/services/cycle_pattern_analyzer.py']:
        tree = ast.parse((root / relative).read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.module in allowed
            if isinstance(node, ast.Import):
                assert all(alias.name in allowed for alias in node.names)
            if isinstance(node, ast.Call):
                name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, 'id', '')
                assert name not in {'now', 'today', 'utcnow', 'open', 'eval', 'exec', '__import__',
                                    'normalize_cycle_context', 'build_training_history'}
