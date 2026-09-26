"""Pure association of canonical training sessions with explicit cycle facts."""

from app.models.cycle_training_history import (
    CycleTrainingContextSnapshot,
    CycleTrainingHistory,
    CycleTrainingHistoryInput,
    CycleTrainingHistorySummary,
    CycleTrainingSessionRecord,
)


def build_cycle_training_history(data: CycleTrainingHistoryInput) -> CycleTrainingHistory:
    """Preserve canonical order and return deeply detached factual snapshots."""
    data = CycleTrainingHistoryInput.model_validate(data)
    history = data.training_history
    observations = {item.session_id: item for item in data.cycle_observations}
    records = []
    counts = dict.fromkeys(CycleTrainingHistorySummary.model_fields, 0)
    for session in history.sessions:
        observation = observations.get(session.session_id)
        context = None
        counts["total_sessions"] += 1
        if observation is None:
            counts["sessions_without_cycle_context"] += 1
        else:
            context = CycleTrainingContextSnapshot(
                phase=observation.phase, discomfort=observation.discomfort,
            )
            counts["sessions_with_cycle_context"] += 1
            phase_field = (
                "unknown_phase_sessions" if context.phase == "unknown"
                else f"{context.phase}_sessions"
            )
            counts[phase_field] += 1
            if context.discomfort is not None:
                counts["sessions_with_known_cycle_discomfort"] += 1
                counts[f"cycle_discomfort_{context.discomfort}_sessions"] += 1
        records.append(CycleTrainingSessionRecord(
            session=session.model_copy(deep=True), cycle_context=context,
        ))
    return CycleTrainingHistory(
        source_training_history_version=history.history_version,
        sessions=records,
        summary=CycleTrainingHistorySummary(**counts),
    )
