"""Pure validation, detached snapshots and inventory of external activity facts."""

from app.models.external_activity_history import (
    EXTERNAL_ACTIVITY_HISTORY_VERSION,
    ExternalActivityFeedback,
    ExternalActivityHistory,
    ExternalActivityHistoryInput,
    ExternalActivityHistorySummary,
    ExternalActivityRecord,
)


def build_external_activity_history(data: ExternalActivityHistoryInput) -> ExternalActivityHistory:
    """Revalidate mutable facts and preserve supplied order without inference."""
    ExternalActivityHistoryInput.require_canonical_records(data.records)
    records = []
    for record in data.records:
        # Validate raw field values, not a serialized/coerced representation or
        # an existing model instance that Pydantic would otherwise trust.
        values = dict(vars(record))
        if isinstance(record.feedback, ExternalActivityFeedback):
            values["feedback"] = ExternalActivityFeedback.model_validate(dict(vars(record.feedback)))
        records.append(ExternalActivityRecord.model_validate(values).model_copy(deep=True))
    records = ExternalActivityHistoryInput(records=records).records

    summary = ExternalActivityHistorySummary(
        total_records=len(records),
        known_activity_records=sum(r.activity_type != "other" for r in records),
        custom_activity_records=sum(r.activity_type == "other" for r in records),
        completed_records=sum(r.completion_state == "completed" for r in records),
        partial_records=sum(r.completion_state == "partial" for r in records),
        records_without_completion_state=sum(r.completion_state is None for r in records),
        records_with_known_duration=sum(r.actual_duration_minutes is not None for r in records),
        records_with_known_distance=sum(r.distance_meters is not None for r in records),
        records_with_feedback=sum(r.feedback is not None for r in records),
        has_any_records=bool(records),
    )
    return ExternalActivityHistory(
        history_version=EXTERNAL_ACTIVITY_HISTORY_VERSION, records=records, summary=summary,
    )
