"""Pure composition of detached canonical facts and inventory counts."""

from app.models.personal_memory import PersonalMemory, PersonalMemoryInput, PersonalMemorySummary


def build_personal_memory(data: PersonalMemoryInput) -> PersonalMemory:
    """Validate source relationships and preserve all supplied domain facts."""
    data = PersonalMemoryInput.model_validate(data)
    history = data.training_history
    cycle = data.cycle_training_history
    analysis = data.cycle_pattern_analysis
    return PersonalMemory(
        source_training_history_version=history.history_version,
        training_history=history.model_copy(deep=True),
        progression_decisions=[item.model_copy(deep=True) for item in data.progression_decisions],
        weekly_training_states=[item.model_copy(deep=True) for item in data.weekly_training_states],
        daily_recovery_states=[item.model_copy(deep=True) for item in data.daily_recovery_states],
        cycle_training_history=cycle.model_copy(deep=True) if cycle is not None else None,
        cycle_pattern_analysis=analysis.model_copy(deep=True) if analysis is not None else None,
        summary=PersonalMemorySummary(
            total_training_sessions=history.summary.total_sessions,
            exercise_histories=len(history.exercise_history),
            progression_decisions=len(data.progression_decisions),
            weekly_state_snapshots=len(data.weekly_training_states),
            daily_recovery_snapshots=len(data.daily_recovery_states),
            has_cycle_training_history=cycle is not None,
            cycle_training_sessions=cycle.summary.total_sessions if cycle is not None else 0,
            has_cycle_pattern_analysis=analysis is not None,
            cycle_patterns=analysis.summary.detected_patterns if analysis is not None else 0,
        ),
    )
