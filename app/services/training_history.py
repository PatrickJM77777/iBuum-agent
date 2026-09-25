"""Pure organization and aggregation of already-normalized session facts."""

from app.models.training_history import (
    ExerciseHistory,
    ExerciseHistoryOccurrence,
    TrainingHistory,
    TrainingHistoryInput,
    TrainingHistorySummary,
)


def build_training_history(data: TrainingHistoryInput) -> TrainingHistory:
    """Preserve supplied order and independent snapshots without analysis."""
    sessions = [outcome.model_copy(deep=True) for outcome in data.outcomes]
    groups: dict[str, ExerciseHistory] = {}
    for session in sessions:
        for exercise in session.exercises:
            if exercise.exercise_id not in groups:
                groups[exercise.exercise_id] = ExerciseHistory(
                    exercise_id=exercise.exercise_id, occurrences=[],
                )
            groups[exercise.exercise_id].occurrences.append(ExerciseHistoryOccurrence(
                session_id=session.session_id,
                session_completion_state=session.completion_state,
                session_started_at=session.started_at,
                session_ended_at=session.ended_at,
                source_action=session.source_action,
                session_type=session.session_type,
                exercise=exercise.model_copy(deep=True),
            ))

    summary = TrainingHistorySummary(
        total_sessions=len(sessions),
        completed_sessions=sum(s.completion_state == "completed" for s in sessions),
        interrupted_sessions=sum(s.completion_state == "interrupted" for s in sessions),
        total_exercises=sum(s.summary.total_exercises for s in sessions),
        completed_exercises=sum(s.summary.completed_exercises for s in sessions),
        partial_exercises=sum(s.summary.partial_exercises for s in sessions),
        skipped_exercises=sum(s.summary.skipped_exercises for s in sessions),
        not_started_exercises=sum(s.summary.not_started_exercises for s in sessions),
        completed_sets=sum(s.summary.completed_sets for s in sessions),
        skipped_sets=sum(s.summary.skipped_sets for s in sessions),
        sessions_with_known_duration=sum(s.actual_duration_seconds is not None for s in sessions),
        known_duration_seconds=sum(s.actual_duration_seconds for s in sessions
                                   if s.actual_duration_seconds is not None),
        sessions_with_feedback=sum(s.feedback is not None for s in sessions),
    )
    return TrainingHistory(sessions=sessions, exercise_history=list(groups.values()), summary=summary)
