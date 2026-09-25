"""Pure analysis of canonical facts; no prescriptions or history rewrites."""

from app.models.progression import ProgressionDecision, ProgressionInput, ProgressionReasonCode
from app.models.session_outcome import ExerciseOutcome, SessionFeedback


Reason = ProgressionReasonCode


def _high_effort(exercise: ExerciseOutcome) -> bool:
    values = [entry.rir for entry in exercise.sets
              if entry.status == "completed" and entry.rir is not None]
    return bool(values) and sum(values) / len(values) <= 1.0


def _strain(feedback: SessionFeedback | None) -> list[ProgressionReasonCode]:
    reasons = []
    if feedback is not None:
        if feedback.fatigue_after is not None and feedback.fatigue_after >= 4:
            reasons.append(Reason.LATEST_HIGH_FATIGUE)
        if feedback.discomfort_after in {"moderate", "high"}:
            reasons.append(Reason.LATEST_MODERATE_HIGH_DISCOMFORT)
    return reasons


def _compare(previous: ExerciseOutcome, latest: ExerciseOutcome) -> ProgressionReasonCode:
    previous_sets = {entry.set_number: entry for entry in previous.sets
                     if entry.status == "completed"}
    signals = []
    for entry in latest.sets:
        if entry.status != "completed" or entry.set_number not in previous_sets:
            continue
        before = previous_sets[entry.set_number]
        if entry.reps is not None and before.reps is not None:
            signals.append((entry.reps > before.reps) - (entry.reps < before.reps))
        if (entry.load_value is not None and before.load_value is not None
                and entry.load_unit is not None and entry.load_unit == before.load_unit):
            signals.append((entry.load_value > before.load_value)
                           - (entry.load_value < before.load_value))
    if not signals:
        return Reason.INSUFFICIENT_COMPARABLE_PERFORMANCE
    if 1 in signals and -1 in signals:
        return Reason.PERFORMANCE_MIXED
    if 1 in signals:
        return Reason.PERFORMANCE_IMPROVED
    if -1 in signals:
        return Reason.PERFORMANCE_REGRESSED
    return Reason.PERFORMANCE_STABLE


def evaluate_progression(data: ProgressionInput) -> ProgressionDecision:
    """Evaluate the supplied last three occurrences in canonical order."""
    group = next((group for group in data.history.exercise_history
                  if group.exercise_id == data.exercise_id), None)
    recent = group.occurrences[-3:] if group is not None else []

    def result(decision, *reasons):
        return ProgressionDecision(
            exercise_id=data.exercise_id, decision=decision, reason_codes=list(reasons),
            occurrences_considered=len(recent),
            latest_session_id=recent[-1].session_id if recent else None,
        )

    if group is None:
        return result("NEEDS_MORE_DATA", Reason.EXERCISE_NOT_IN_HISTORY)
    if len(recent) < 2:
        return result("NEEDS_MORE_DATA", Reason.INSUFFICIENT_HISTORY)

    sessions = {session.session_id: session for session in data.history.sessions}
    if len(recent) == 3:
        strained_sessions = sum(bool(_strain(sessions[session_id].feedback))
                                for session_id in {item.session_id for item in recent})
        issues = sum(item.exercise.execution_status != "completed" or _high_effort(item.exercise)
                     for item in recent)
        if strained_sessions >= 2 and issues >= 2:
            return result("DELOAD", Reason.REPEATED_STRAIN,
                          Reason.REPEATED_EXECUTION_OR_EFFORT_ISSUES)

    previous, latest = recent[-2].exercise, recent[-1].exercise
    comparison = _compare(previous, latest)
    negatives = []
    if latest.execution_status != "completed":
        negatives.append(Reason.LATEST_EXECUTION_INCOMPLETE)
    negatives.extend(_strain(sessions[recent[-1].session_id].feedback))
    if _high_effort(latest):
        negatives.append(Reason.LATEST_HIGH_EFFORT)
    if comparison == Reason.PERFORMANCE_REGRESSED:
        negatives.append(comparison)
    if len(negatives) >= 2:
        return result("REDUCE", *negatives)
    if (not negatives and previous.execution_status == "completed"
            and comparison == Reason.PERFORMANCE_IMPROVED):
        return result("PROGRESS", comparison)
    if comparison == Reason.INSUFFICIENT_COMPARABLE_PERFORMANCE:
        return result("NEEDS_MORE_DATA", comparison)
    if comparison in {Reason.PERFORMANCE_STABLE, Reason.PERFORMANCE_MIXED}:
        return result("MAINTAIN", comparison)
    return result("MAINTAIN", Reason.NO_STRONG_CHANGE_SIGNAL)
