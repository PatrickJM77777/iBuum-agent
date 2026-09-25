"""Pure aggregation of explicitly scoped history and planned-slot facts."""

from datetime import timedelta

from app.models.weekly_training_state import (
    WeeklyAdherenceFacts,
    WeeklyPlannedSessionState,
    WeeklyPlanSummary,
    WeeklyRecoveryFacts,
    WeeklyTrainingState,
    WeeklyTrainingStateInput,
    WeeklyWorkloadFacts,
)


def build_weekly_training_state(data: WeeklyTrainingStateInput) -> WeeklyTrainingState:
    """Build an independent factual snapshot from normally validated input."""
    included = set(data.included_session_ids)
    sessions = [s for s in data.history.sessions if s.session_id in included]
    by_id = {s.session_id: s for s in sessions}
    linked = {slot.linked_session_id for slot in data.planned_sessions
              if slot.linked_session_id is not None}
    unplanned = [s.session_id for s in sessions if s.session_id not in linked]
    planned = []
    for slot in data.planned_sessions:
        status = "remaining"
        if slot.linked_session_id is not None:
            status = ("completed" if by_id[slot.linked_session_id].completion_state
                      == "completed" else "partial")
        planned.append(WeeklyPlannedSessionState(
            **slot.model_dump(), status=status,
            is_due=slot.scheduled_date <= data.as_of_date,
        ))

    plan_summary = WeeklyPlanSummary(
        total_planned_sessions=len(planned),
        completed_planned_sessions=sum(s.status == "completed" for s in planned),
        partial_planned_sessions=sum(s.status == "partial" for s in planned),
        remaining_planned_sessions=sum(s.status == "remaining" for s in planned),
        due_remaining_planned_sessions=sum(s.status == "remaining" and s.is_due for s in planned),
        future_remaining_planned_sessions=sum(s.status == "remaining" and not s.is_due for s in planned),
    )
    workload = WeeklyWorkloadFacts(
        total_sessions=len(sessions),
        completed_sessions=sum(s.completion_state == "completed" for s in sessions),
        interrupted_sessions=sum(s.completion_state == "interrupted" for s in sessions),
        unplanned_sessions=len(unplanned),
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
    )
    feedback = [s.feedback for s in sessions if s.feedback is not None]
    fatigue = [f.fatigue_after for f in feedback if f.fatigue_after is not None]
    discomfort = [f.discomfort_after for f in feedback if f.discomfort_after is not None]
    rpe = [f.session_rpe for f in feedback if f.session_rpe is not None]
    recovery = WeeklyRecoveryFacts(
        sessions_with_feedback=len(feedback),
        sessions_with_known_fatigue=len(fatigue),
        high_fatigue_sessions=sum(value >= 4 for value in fatigue),
        latest_known_fatigue_after=fatigue[-1] if fatigue else None,
        sessions_with_known_discomfort=len(discomfort),
        moderate_high_discomfort_sessions=sum(value in {"moderate", "high"} for value in discomfort),
        latest_known_discomfort_after=discomfort[-1] if discomfort else None,
        sessions_with_known_session_rpe=len(rpe),
        latest_known_session_rpe=rpe[-1] if rpe else None,
    )
    due = [s for s in planned if s.is_due]
    completed_due = sum(s.status == "completed" for s in due)
    partial_due = sum(s.status == "partial" for s in due)
    adherence = WeeklyAdherenceFacts(
        due_planned_sessions=len(due),
        completed_due_sessions=completed_due,
        partial_due_sessions=partial_due,
        unresolved_due_sessions=sum(s.status == "remaining" for s in due),
        attendance_ratio=(completed_due + partial_due) / len(due) if due else None,
    )
    return WeeklyTrainingState(
        week_start=data.week_start, week_end=data.week_start + timedelta(days=6),
        as_of_date=data.as_of_date, planned_sessions=planned,
        included_session_ids=[s.session_id for s in sessions],
        unplanned_session_ids=unplanned, plan_summary=plan_summary,
        workload=workload, recovery=recovery, adherence=adherence,
    )
