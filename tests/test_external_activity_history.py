"""Bounded factual contract, mutation safety and domain separation."""

import ast
from datetime import date
from itertools import product
from pathlib import Path
from typing import get_args

import pytest
from pydantic import ValidationError

from app.models.external_activity_history import (
    EXTERNAL_ACTIVITY_HISTORY_VERSION,
    ExternalActivityFeedback as Feedback,
    ExternalActivityHistory as History,
    ExternalActivityHistoryInput as HistoryInput,
    ExternalActivityHistorySummary as Summary,
    ExternalActivityRecord as Record,
)
from app.models.sport_activity_profile import SportActivityEntry
from app.services.external_activity_history import build_external_activity_history as build


TAXONOMY = (
    "strength_training", "functional_training", "calisthenics", "cardio_fitness",
    "running", "walking", "cycling", "swimming", "football", "basketball",
    "volleyball", "tennis", "padel", "yoga", "pilates", "dance", "hiking",
    "climbing", "rowing", "combat_sport", "mobility_training", "team_sport", "other",
)
FIELDS = {
    Feedback: {"activity_rpe", "fatigue_after", "discomfort_after"},
    Record: {"activity_id", "activity_type", "custom_activity_name", "activity_date",
             "completion_state", "actual_duration_minutes", "distance_meters", "feedback"},
    HistoryInput: {"records"},
    History: {"history_version", "records", "summary"},
    Summary: {"total_records", "known_activity_records", "custom_activity_records",
              "completed_records", "partial_records", "records_without_completion_state",
              "records_with_known_duration", "records_with_known_distance",
              "records_with_feedback", "has_any_records"},
}
COUNT_FIELDS = FIELDS[Summary] - {"has_any_records"}


def record(**changes):
    return Record(**({"activity_id": "record-1", "activity_type": "running",
                     "activity_date": date(2026, 9, 20)} | changes))


def snapshot(*records):
    return build(HistoryInput(records=list(records)))


def summary_values():
    return {field: 0 for field in COUNT_FIELDS} | {"has_any_records": False}


def valid_payload(model):
    return {
        Feedback: {}, Record: record().model_dump(), HistoryInput: {"records": [record()]},
        Summary: summary_values(), History: snapshot().model_dump(),
    }[model]


@pytest.mark.parametrize("model", FIELDS)
def test_exact_fields_and_extra_forbidden(model):
    assert set(model.model_fields) == FIELDS[model]
    assert model.model_config["extra"] == "forbid"
    with pytest.raises(ValidationError):
        model(**(valid_payload(model) | {"unexpected": None}))


def test_canonical_input_and_empty_snapshot():
    original = [record()]
    data = HistoryInput(records=original)
    assert data.records == original
    assert original == [record()]
    assert snapshot(*original).records == original
    empty = snapshot()
    assert empty.records == []
    assert empty.summary.model_dump() == summary_values()
    assert empty.history_version == EXTERNAL_ACTIVITY_HISTORY_VERSION == "external-activity-history-v1"
    with pytest.raises(ValidationError):
        HistoryInput()
    with pytest.raises(ValidationError):
        History(**(empty.model_dump() | {"history_version": "v2"}))


@pytest.mark.parametrize("records", [[record().model_dump()], [None], ["running"], (), None])
def test_noncanonical_records_rejected_at_input_and_builder(records):
    with pytest.raises(ValidationError):
        HistoryInput(records=records)
    data = HistoryInput(records=[])
    data.records = records
    with pytest.raises(ValueError):
        build(data)


@pytest.mark.parametrize("activity", TAXONOMY)
def test_exact_taxonomy_and_independent_distance(activity):
    item = record(activity_type=activity,
                  custom_activity_name="Skiing" if activity == "other" else None)
    assert snapshot(item).records[0] == item
    assert item.distance_meters is None
    assert snapshot(item).records[0].feedback is None
    assert record(**(item.model_dump() | {"distance_meters": 12.5})).distance_meters == 12.5


def test_taxonomy_parity_without_runtime_profile_dependency():
    assert get_args(Record.model_fields["activity_type"].annotation) == TAXONOMY
    assert set(TAXONOMY) == set(get_args(SportActivityEntry.model_fields["activity_type"].annotation))


@pytest.mark.parametrize("name", ["Surfing", "wheelchair basketball", "滑雪", "Straße  SURF", "x" * 80])
def test_custom_names_preserved_without_classification(name):
    item = record(activity_type="other", custom_activity_name=name)
    assert snapshot(item).records[0].custom_activity_name == name
    assert snapshot(item).records[0].activity_type == "other"
    with pytest.raises(ValidationError):
        record(custom_activity_name=name)


@pytest.mark.parametrize("name", [None, "", " ", "\t\n", " Surf", "Surf ", "\u2003Surf", "x" * 81, 1, True])
def test_invalid_custom_names(name):
    with pytest.raises(ValidationError):
        record(activity_type="other", custom_activity_name=name)


@pytest.mark.parametrize("identifier", ["x", "x" * 128, " ID preserved \t", "記録"])
def test_ids_preserved_without_generation(identifier):
    assert snapshot(record(activity_id=identifier)).records[0].activity_id == identifier


@pytest.mark.parametrize("field,value", [
    ("activity_id", ""), ("activity_id", "x" * 129), ("activity_id", 1),
    ("activity_id", True), ("activity_id", b"id"), ("activity_type", "skiing"),
    ("activity_type", "Running"), ("activity_type", None),
    ("completion_state", "failed"), ("completion_state", "abandoned"),
    ("completion_state", "skipped"), ("completion_state", "success"),
    ("activity_date", "invalid-date"), ("activity_date", None),
] + [("actual_duration_minutes", v) for v in [0, 1441, True, 1.0, "60"]]
  + [("distance_meters", v) for v in [0.0, -1.0, float("nan"), float("inf"), -float("inf"), "bad", "10", True]] )
def test_invalid_record_values_at_construction_and_builder(field, value):
    with pytest.raises(ValidationError):
        record(**{field: value})
    data = HistoryInput(records=[record()])
    setattr(data.records[0], field, value)
    with pytest.raises(ValidationError):
        build(data)


@pytest.mark.parametrize("field", ["activity_id", "activity_type", "activity_date"])
def test_required_record_fields(field):
    values = record().model_dump()
    del values[field]
    with pytest.raises(ValidationError):
        Record(**values)


def test_order_and_unique_identity_rechecked_without_sorting():
    items = [record(activity_id="z"), record(activity_id="a", activity_type="football"),
             record(activity_id="later", activity_date=date(9999, 12, 31))]
    assert snapshot(*items).records == items
    assert [r.activity_id for r in snapshot(*items).records] == ["z", "a", "later"]
    for invalid in ([items[2], items[0]], [items[0], items[0].model_copy(deep=True)]):
        before = [r.model_dump() for r in invalid]
        with pytest.raises(ValidationError):
            HistoryInput(records=invalid)
        data = HistoryInput(records=[])
        data.records.extend(invalid)
        with pytest.raises(ValidationError):
            build(data)
        assert [r.model_dump() for r in invalid] == before


@pytest.mark.parametrize("change", [{"activity_id": "first"}, {"activity_date": date(2026, 9, 19)}])
def test_mutated_identity_or_date_rejected(change):
    data = HistoryInput(records=[record(activity_id="first"), record(activity_id="second")])
    for key, value in change.items():
        setattr(data.records[1], key, value)
    with pytest.raises(ValidationError):
        build(data)


@pytest.mark.parametrize("field,value", [
    ("activity_rpe", v) for v in [0.0, 10.1, float("nan"), float("inf"), -float("inf"), True, "9"]
] + [("fatigue_after", v) for v in [0, 6, True, 1.0, "5"]]
  + [("discomfort_after", "severe")])
def test_invalid_feedback_revalidated(field, value):
    with pytest.raises(ValidationError):
        Feedback(**{field: value})
    data = HistoryInput(records=[record(feedback=Feedback())])
    setattr(data.records[0].feedback, field, value)
    with pytest.raises(ValidationError):
        build(data)


@pytest.mark.parametrize("rpe,fatigue,discomfort", product([None, 1.0, 10.0], [None, 1, 5], [None, "none", "mild", "moderate", "high"]))
def test_feedback_facts_remain_independent(rpe, fatigue, discomfort):
    feedback = Feedback(activity_rpe=rpe, fatigue_after=fatigue, discomfort_after=discomfort)
    result = snapshot(record(feedback=feedback)).records[0]
    assert result.feedback.model_dump() == {
        "activity_rpe": rpe, "fatigue_after": fatigue, "discomfort_after": discomfort,
    }
    assert result.completion_state is None
    assert result.actual_duration_minutes is None
    assert result.distance_meters is None


@pytest.mark.parametrize("completion,duration,distance,feedback", product(
    [None, "completed", "partial"], [None, 1, 1440], [None, 0.5], [None, Feedback()],
))
def test_optional_facts_and_inventory(completion, duration, distance, feedback):
    item = record(completion_state=completion, actual_duration_minutes=duration,
                  distance_meters=distance, feedback=feedback)
    result = snapshot(item)
    assert result.records[0].model_dump() == item.model_dump()
    assert result.summary.model_dump() == {
        "total_records": 1, "known_activity_records": 1, "custom_activity_records": 0,
        "completed_records": int(completion == "completed"),
        "partial_records": int(completion == "partial"),
        "records_without_completion_state": int(completion is None),
        "records_with_known_duration": int(duration is not None),
        "records_with_known_distance": int(distance is not None),
        "records_with_feedback": int(feedback is not None), "has_any_records": True,
    }


def test_mixed_inventory_and_no_current_profile_membership_requirement():
    result = snapshot(
        record(completion_state="completed", actual_duration_minutes=45, distance_meters=8000.0),
        record(activity_id="2", activity_type="football", completion_state="partial", feedback=Feedback()),
        record(activity_id="3", activity_type="other", custom_activity_name="Skiing"),
    )
    assert result.summary.model_dump() == {
        "total_records": 3, "known_activity_records": 2, "custom_activity_records": 1,
        "completed_records": 1, "partial_records": 1, "records_without_completion_state": 1,
        "records_with_known_duration": 1, "records_with_known_distance": 1,
        "records_with_feedback": 1, "has_any_records": True,
    }


@pytest.mark.parametrize("field", sorted(COUNT_FIELDS))
@pytest.mark.parametrize("value", [-1, True, 0.0, "0"])
def test_summary_counts_are_strict_nonnegative(field, value):
    with pytest.raises(ValidationError):
        Summary(**(summary_values() | {field: value}))


@pytest.mark.parametrize("value", [0, 1, "false", None])
def test_summary_flag_is_strict_bool(value):
    with pytest.raises(ValidationError):
        Summary(**(summary_values() | {"has_any_records": value}))


@pytest.mark.parametrize("changes", [
    {"known_activity_records": 1}, {"custom_activity_records": 1},
    {"completed_records": 1}, {"partial_records": 1}, {"records_without_completion_state": 1},
    {"records_with_known_duration": 1}, {"records_with_known_distance": 1},
    {"records_with_feedback": 1}, {"has_any_records": True},
    {"total_records": 1, "known_activity_records": 1, "records_without_completion_state": 1},
])
def test_summary_invariants(changes):
    with pytest.raises(ValidationError):
        Summary(**(summary_values() | changes))


def test_recursive_detachment_determinism_and_bidirectional_mutation():
    original = [record(feedback=Feedback(activity_rpe=9.0))]
    data = HistoryInput(records=original)
    first, second = build(data), build(data)
    assert first == second
    assert first.records is not second.records and first.records is not data.records
    assert first.records is not original
    for result in (first, second):
        assert result.records[0] is not data.records[0]
        assert result.records[0].feedback is not data.records[0].feedback
    assert first.records[0] is not second.records[0]
    assert first.records[0].feedback is not second.records[0].feedback
    first.records[0].feedback.activity_rpe = 2.0
    first.records[0].activity_id = "output edit"
    first.records.append(record(activity_id="new"))
    assert data.records == original == second.records
    data.records[0].feedback.activity_rpe = 5.0
    data.records[0].activity_id = "input edit"
    data.records.clear()
    assert second.records == [record(feedback=Feedback(activity_rpe=9.0))]
    assert first.records[0].feedback.activity_rpe == 2.0
    assert first.records[0].activity_id == "output edit"


@pytest.mark.parametrize("module,allowed", [
    ("models", {"datetime", "typing", "pydantic"}),
    ("services", {"app.models.external_activity_history"}),
])
def test_domain_import_and_call_boundaries(module, allowed):
    path = Path(__file__).resolve().parents[1] / "app" / module / "external_activity_history.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert imports == allowed
    assert not any(isinstance(node, ast.Import) for node in ast.walk(tree))
    permitted_calls = {
        "ConfigDict", "Field", "model_validator", "field_validator", "ValueError",
        "isinstance", "any", "len", "set", "zip", "strip", "dict", "vars", "append",
        "model_validate", "model_copy", "require_canonical_records",
        "ExternalActivityHistoryInput", "ExternalActivityHistorySummary", "ExternalActivityHistory",
        "sum", "bool",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr
            assert name in permitted_calls
        assert not isinstance(node, (ast.Mult, ast.Div, ast.Pow))
