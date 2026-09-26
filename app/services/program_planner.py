"""Pure dating of approved session templates, without adaptive planning policy."""

from datetime import timedelta

from app.models.program_planner import (
    ProgramPlan,
    ProgramPlannerInput,
    ProgramPlanSummary,
    ProgramPreviousWeekContext,
    ProgramProgressionSummary,
    ProgramSessionPlan,
)


def build_program_plan(data: ProgramPlannerInput) -> ProgramPlan:
    """Build an independent program snapshot from normally validated input."""
    data = ProgramPlannerInput.model_validate(data)
    week = data.previous_week_state
    sessions = [
        ProgramSessionPlan(
            slot_id=slot.slot_id,
            scheduled_date=data.plan_week_start + timedelta(days=slot.day_offset),
            session_type=slot.session_type,
        )
        for slot in data.session_templates
    ]
    decisions = [item.model_copy(deep=True) for item in data.progression_decisions]
    return ProgramPlan(
        source_week_start=week.week_start,
        source_week_end=week.week_end,
        plan_week_start=data.plan_week_start,
        plan_week_end=data.plan_week_start + timedelta(days=6),
        sessions=sessions,
        progression_decisions=decisions,
        previous_week_context=ProgramPreviousWeekContext(
            source_week_start=week.week_start,
            source_week_end=week.week_end,
            source_as_of_date=week.as_of_date,
            planned_sessions=week.plan_summary.total_planned_sessions,
            completed_planned_sessions=week.plan_summary.completed_planned_sessions,
            partial_planned_sessions=week.plan_summary.partial_planned_sessions,
            remaining_planned_sessions=week.plan_summary.remaining_planned_sessions,
            due_remaining_planned_sessions=week.plan_summary.due_remaining_planned_sessions,
            unplanned_sessions=week.workload.unplanned_sessions,
            attendance_ratio=week.adherence.attendance_ratio,
            high_fatigue_sessions=week.recovery.high_fatigue_sessions,
            moderate_high_discomfort_sessions=week.recovery.moderate_high_discomfort_sessions,
        ),
        progression_summary=ProgramProgressionSummary(
            total_decisions=len(decisions),
            progress_decisions=sum(item.decision == "PROGRESS" for item in decisions),
            maintain_decisions=sum(item.decision == "MAINTAIN" for item in decisions),
            reduce_decisions=sum(item.decision == "REDUCE" for item in decisions),
            deload_decisions=sum(item.decision == "DELOAD" for item in decisions),
            needs_more_data_decisions=sum(item.decision == "NEEDS_MORE_DATA" for item in decisions),
        ),
        plan_summary=ProgramPlanSummary(
            total_sessions=len(sessions),
            upper_body_sessions=sum(s.session_type == "upper_body" for s in sessions),
            lower_body_sessions=sum(s.session_type == "lower_body" for s in sessions),
            full_body_sessions=sum(s.session_type == "full_body" for s in sessions),
            cardio_sessions=sum(s.session_type == "cardio" for s in sessions),
            mobility_sessions=sum(s.session_type == "mobility" for s in sessions),
        ),
    )
