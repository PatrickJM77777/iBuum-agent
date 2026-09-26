"""Pure same-session-type historical comparisons with bounded evidence guards."""

from math import fsum

from app.models.cycle_pattern_analyzer import (
    CYCLE_PATTERN_ANALYZER_VERSION, MIN_PHASE_METRIC_SAMPLES,
    MIN_COMPARATOR_METRIC_SAMPLES, RPE_MEAN_DIFFERENCE_THRESHOLD,
    FATIGUE_MEAN_DIFFERENCE_THRESHOLD, POST_DISCOMFORT_RATIO_DIFFERENCE_THRESHOLD,
    PHASES, SESSION_TYPES, METRICS, CyclePatternAnalyzerInput, CyclePhaseEvidence,
    CycleObservedPattern, CyclePatternAnalysisSummary, CyclePatternAnalysis,
)


def _mean(values):
    return round(fsum(values) / len(values), 4) if values else None


def _metric_values(records, metric):
    field = "discomfort_after" if metric == "post_session_discomfort" else metric
    values = []
    for record in records:
        feedback = record.session.feedback
        value = getattr(feedback, field) if feedback is not None else None
        if value is not None:
            values.append(int(value in {"moderate", "high"})
                          if metric == "post_session_discomfort" else value)
    return values


def _phase_evidence(phase, records):
    rpe, fatigue, post = (_metric_values(records, metric) for metric in METRICS)
    cycle = [int(record.cycle_context.discomfort in {"moderate", "high"})
             for record in records if record.cycle_context.discomfort is not None]
    return CyclePhaseEvidence(
        phase=phase, observed_sessions=len(records),
        completed_sessions=sum(record.session.completion_state == "completed" for record in records),
        interrupted_sessions=sum(record.session.completion_state == "interrupted" for record in records),
        sessions_with_known_rpe=len(rpe), mean_session_rpe=_mean(rpe),
        sessions_with_known_fatigue=len(fatigue), mean_fatigue_after=_mean(fatigue),
        sessions_with_known_post_discomfort=len(post),
        moderate_high_post_discomfort_sessions=sum(post),
        moderate_high_post_discomfort_ratio=_mean(post),
        sessions_with_known_cycle_discomfort=len(cycle),
        moderate_high_cycle_discomfort_sessions=sum(cycle),
        moderate_high_cycle_discomfort_ratio=_mean(cycle),
    )


def analyze_cycle_patterns(data: CyclePatternAnalyzerInput) -> CyclePatternAnalysis:
    data = CyclePatternAnalyzerInput.model_validate(data)
    history = data.cycle_history
    by_phase = {phase: [] for phase in PHASES}
    for record in history.sessions:
        if record.cycle_context is not None:
            by_phase[record.cycle_context.phase].append(record)
    evidence = [_phase_evidence(phase, by_phase[phase]) for phase in PHASES]
    samples = {
        (phase, session_type, metric): _metric_values(
            [record for record in by_phase[phase] if record.session.session_type == session_type], metric
        )
        for phase in PHASES[:-1] for session_type in SESSION_TYPES for metric in METRICS
    }
    thresholds = (RPE_MEAN_DIFFERENCE_THRESHOLD, FATIGUE_MEAN_DIFFERENCE_THRESHOLD,
                  POST_DISCOMFORT_RATIO_DIFFERENCE_THRESHOLD)
    patterns = []
    for phase in PHASES[:-1]:
        for session_type in SESSION_TYPES:
            for metric, threshold in zip(METRICS, thresholds):
                target = samples[phase, session_type, metric]
                comparator = [value for other in PHASES[:-1] if other != phase
                              for value in samples[other, session_type, metric]]
                if len(target) < MIN_PHASE_METRIC_SAMPLES or len(comparator) < MIN_COMPARATOR_METRIC_SAMPLES:
                    continue
                phase_value, comparator_value = _mean(target), _mean(comparator)
                difference = round(phase_value - comparator_value, 4)
                if abs(difference) >= threshold:
                    patterns.append(CycleObservedPattern(
                        phase=phase, session_type=session_type, metric=metric,
                        direction="higher" if difference > 0 else "lower",
                        phase_sample_size=len(target), comparator_sample_size=len(comparator),
                        phase_value=phase_value, comparator_value=comparator_value,
                        difference=difference, threshold=threshold,
                    ))
    source = history.summary
    summary = CyclePatternAnalysisSummary(
        total_sessions=source.total_sessions,
        sessions_with_cycle_context=source.sessions_with_cycle_context,
        sessions_without_cycle_context=source.sessions_without_cycle_context,
        known_phase_sessions=(source.menstruation_sessions + source.follicular_sessions
                              + source.ovulation_sessions + source.luteal_sessions),
        unknown_phase_sessions=source.unknown_phase_sessions,
        sessions_eligible_for_pattern_analysis=sum(
            record.session.session_type is not None
            for phase in PHASES[:-1] for record in by_phase[phase]
        ),
        detected_patterns=len(patterns),
        rpe_patterns=sum(pattern.metric == "session_rpe" for pattern in patterns),
        fatigue_patterns=sum(pattern.metric == "fatigue_after" for pattern in patterns),
        post_session_discomfort_patterns=sum(pattern.metric == "post_session_discomfort" for pattern in patterns),
    )
    return CyclePatternAnalysis(
        analyzer_version=CYCLE_PATTERN_ANALYZER_VERSION,
        source_cycle_history_version=history.cycle_history_version,
        phase_evidence=evidence, patterns=patterns, summary=summary,
    )
