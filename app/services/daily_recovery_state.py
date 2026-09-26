"""Pure daily factual context builder; no training policy or interpretation."""

from app.models.daily_recovery_state import (
    DailyRecentTrainingContext,
    DailyRecoveryFlags,
    DailyRecoverySignalSummary,
    DailyRecoveryState,
    DailyRecoveryStateInput,
)


def build_daily_recovery_state(data: DailyRecoveryStateInput) -> DailyRecoveryState:
    """Return a detached snapshot from normally validated canonical input."""
    data = DailyRecoveryStateInput.model_validate(data)
    week = data.current_week_state
    signals = data.reported_signals.model_copy(deep=True)
    flags = DailyRecoveryFlags(
        low_sleep_quality=signals.sleep_quality is not None and signals.sleep_quality <= 2,
        low_energy=signals.energy_level is not None and signals.energy_level <= 2,
        high_fatigue=signals.fatigue_level is not None and signals.fatigue_level >= 4,
        moderate_high_soreness=signals.soreness_level in {"moderate", "high"},
        moderate_high_discomfort=signals.discomfort_level in {"moderate", "high"},
    )
    reported = sum(value is not None for value in signals.model_dump().values())
    return DailyRecoveryState(
        source_week_state_version=week.state_version,
        state_date=week.as_of_date,
        reported_signals=signals,
        recent_training_context=DailyRecentTrainingContext(
            source_week_start=week.week_start,
            source_week_end=week.week_end,
            source_as_of_date=week.as_of_date,
            total_sessions=week.workload.total_sessions,
            completed_sessions=week.workload.completed_sessions,
            interrupted_sessions=week.workload.interrupted_sessions,
            unplanned_sessions=week.workload.unplanned_sessions,
            known_duration_seconds=week.workload.known_duration_seconds,
            due_remaining_planned_sessions=week.plan_summary.due_remaining_planned_sessions,
            high_fatigue_sessions=week.recovery.high_fatigue_sessions,
            latest_known_fatigue_after=week.recovery.latest_known_fatigue_after,
            moderate_high_discomfort_sessions=week.recovery.moderate_high_discomfort_sessions,
            latest_known_discomfort_after=week.recovery.latest_known_discomfort_after,
            latest_known_session_rpe=week.recovery.latest_known_session_rpe,
        ),
        flags=flags,
        signal_summary=DailyRecoverySignalSummary(
            supported_signals=6,
            reported_signals=reported,
            missing_signals=6 - reported,
            flagged_signals=sum(flags.model_dump().values()),
        ),
    )
