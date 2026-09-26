"""Pure application of explicit, validated within-week date moves."""

from app.models.planner_rescheduling import (
    PlannerReschedulingInput,
    PlannerReschedulingResult,
    RescheduleAppliedChange,
    ReschedulingSummary,
)


def reschedule_program(data: PlannerReschedulingInput) -> PlannerReschedulingResult:
    """Return an independent program snapshot and canonically ordered audit facts."""
    data = PlannerReschedulingInput.model_validate(data)
    updated_plan = data.program_plan.model_copy(deep=True)
    requests = {request.slot_id: request for request in data.requests}
    changes = []
    for slot in updated_plan.sessions:
        request = requests.get(slot.slot_id)
        if request is None:
            continue
        changes.append(RescheduleAppliedChange(
            slot_id=slot.slot_id,
            original_scheduled_date=slot.scheduled_date,
            new_scheduled_date=request.target_date,
            session_type=slot.session_type,
            reason=request.reason,
        ))
        slot.scheduled_date = request.target_date
    return PlannerReschedulingResult(
        source_planner_version=updated_plan.planner_version,
        plan_week_start=updated_plan.plan_week_start,
        plan_week_end=updated_plan.plan_week_end,
        as_of_date=data.current_week_state.as_of_date,
        updated_plan=updated_plan,
        changes=changes,
        summary=ReschedulingSummary(
            total_sessions=len(updated_plan.sessions),
            requested_changes=len(data.requests),
            rescheduled_sessions=len(changes),
            unchanged_sessions=len(updated_plan.sessions) - len(changes),
        ),
    )
