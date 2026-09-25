"""Pure normalization and descriptive counting of validated execution facts."""

from typing import Literal

from app.models.session_outcome import (
    ExerciseExecutionInput,
    ExerciseOutcome,
    SessionOutcome,
    SessionOutcomeInput,
    SessionOutcomeSummary,
)


def _exercise_outcome(data: ExerciseExecutionInput) -> ExerciseOutcome:
    completed = sum(entry.status == "completed" for entry in data.sets)
    skipped = sum(entry.status == "skipped" for entry in data.sets)
    status: Literal["completed", "partial", "skipped", "not_started"]
    if data.source_status == "completed":
        status = "completed"
    elif data.source_status == "in_progress" or completed > 0:
        status = "partial"
    elif data.source_status == "skipped":
        status = "skipped"
    else:
        status = "not_started"
    return ExerciseOutcome(
        **data.model_dump(), execution_status=status,
        completed_sets=completed, skipped_sets=skipped,
    )


def build_session_outcome(data: SessionOutcomeInput) -> SessionOutcome:
    """Preserve facts and order without deriving performance from the plan."""
    exercises = [_exercise_outcome(exercise) for exercise in data.exercises]
    summary = SessionOutcomeSummary(
        total_exercises=len(exercises),
        completed_exercises=sum(e.execution_status == "completed" for e in exercises),
        partial_exercises=sum(e.execution_status == "partial" for e in exercises),
        skipped_exercises=sum(e.execution_status == "skipped" for e in exercises),
        not_started_exercises=sum(e.execution_status == "not_started" for e in exercises),
        completed_sets=sum(e.completed_sets for e in exercises),
        skipped_sets=sum(e.skipped_sets for e in exercises),
    )
    return SessionOutcome(
        **data.model_dump(exclude={"exercises"}), exercises=exercises, summary=summary,
    )
