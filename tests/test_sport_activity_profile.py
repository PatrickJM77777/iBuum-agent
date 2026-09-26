"""Declarative contract, factual inventory, isolation and dependency boundaries."""

import ast
from itertools import product
from pathlib import Path
from typing import get_args

import pytest
from pydantic import ValidationError

from app.models.sport_activity_profile import (
    SPORT_ACTIVITY_PROFILE_VERSION,
    SportActivityEntry,
    SportActivityProfile,
    SportActivityProfileInput,
    SportActivityProfileSummary,
)
from app.services.sport_activity_profile import build_sport_activity_profile


KNOWN = (
    "strength_training", "functional_training", "calisthenics", "cardio_fitness",
    "running", "walking", "cycling", "swimming", "football", "basketball",
    "volleyball", "tennis", "padel", "yoga", "pilates", "dance", "hiking",
    "climbing", "rowing", "combat_sport", "mobility_training", "team_sport",
)
OPTIONAL = {
    "days_per_week": (None, 1, 7),
    "experience_level": (None, "beginner", "intermediate", "advanced"),
    "typical_duration_minutes": (None, 1, 720),
    "practice_environment": (None, "home", "gym", "outdoors", "pool", "court_or_field",
                             "studio", "sports_facility", "mixed", "other"),
}
COUNTS = {
    "days_per_week": "activities_with_days_per_week",
    "experience_level": "activities_with_experience_level",
    "typical_duration_minutes": "activities_with_typical_duration",
    "practice_environment": "activities_with_practice_environment",
}


def entry(activity_type="running", **values):
    return SportActivityEntry(activity_type=activity_type, **values)


def custom(name):
    return entry("other", custom_activity_name=name)


def build(*activities):
    return build_sport_activity_profile(SportActivityProfileInput(activities=list(activities)))


def summary(**changes):
    return dict(total_activities=0, known_activities=0, custom_activities=0,
                **{name: 0 for name in COUNTS.values()}, has_any_activities=False) | changes


@pytest.mark.parametrize("activity_type", KNOWN)
def test_known_activity_and_all_omitted_fields_preserved(activity_type):
    activity = entry(activity_type)
    supplied = [activity]
    data = SportActivityProfileInput(activities=supplied)
    assert data.activities[0] is activity
    expected = dict(activity_type=activity_type, custom_activity_name=None,
                    **{name: None for name in OPTIONAL})
    assert build_sport_activity_profile(data).activities[0].model_dump() == expected
    assert supplied == [activity]
    assert set(get_args(SportActivityEntry.model_fields["activity_type"].annotation)) == set(KNOWN) | {"other"}


@pytest.mark.parametrize("field,value", [
    (field, value) for field, values in OPTIONAL.items() for value in values
])
def test_optional_values_are_independent(field, value):
    result = build(entry(**{field: value})).activities[0]
    assert result.model_dump() == dict(
        activity_type="running", custom_activity_name=None,
        **{name: value if name == field else None for name in OPTIONAL},
    )


@pytest.mark.parametrize("field,values", [
    ("activity_type", ["invalid", "Running", "", None, True, 1]),
    ("days_per_week", [0, 8, True, False, 1.0, "1"]),
    ("typical_duration_minutes", [0, 721, True, False, 1.0, "1"]),
    ("experience_level", ["expert", "Advanced", "", 1, True]),
    ("practice_environment", ["road", "Pool", "", 1, True]),
])
def test_invalid_entry_values(field, values):
    for value in values:
        with pytest.raises(ValidationError):
            SportActivityEntry(**(dict(activity_type="running") | {field: value}))


@pytest.mark.parametrize("value", [None, "", " ", "\t\n", " Surfing", "Surfing ",
                                       "\u2003Surfing", "Surfing\u00a0", "x" * 81, 1, b"Surfing"])
def test_invalid_custom_names(value):
    with pytest.raises(ValidationError):
        custom(value)


def test_other_requires_name():
    with pytest.raises(ValidationError):
        entry("other")


@pytest.mark.parametrize("activity_type", KNOWN)
def test_known_activity_rejects_custom_alias(activity_type):
    with pytest.raises(ValidationError):
        entry(activity_type, custom_activity_name="Alias")


@pytest.mark.parametrize("name", ["S", "x" * 80, "Surfing", "滑雪", "Póle  Dance",
                                      "wheelchair basketball", "Straße"])
def test_custom_text_preserved_without_classification_or_adaptation(name):
    result = build(custom(name))
    assert result.activities[0].model_dump() == dict(
        activity_type="other", custom_activity_name=name, **{key: None for key in OPTIONAL},
    )


@pytest.mark.parametrize("value", [[{"activity_type": "running"}], [None], ["running"],
                                       [entry(), {}], None, {}, (entry(),)])
def test_input_requires_list_of_canonical_entries(value):
    with pytest.raises(ValidationError):
        SportActivityProfileInput(activities=value)


def test_required_list_and_empty_snapshot():
    with pytest.raises(ValidationError):
        SportActivityProfileInput()
    result = build()
    assert result.activities == []
    assert result.summary.model_dump() == summary()


@pytest.mark.parametrize("activities", [
    [entry(), entry()], [custom("Surfing"), custom("Surfing")],
    [custom("Surfing"), custom("surfing")], [custom("Straße"), custom("STRASSE")],
])
def test_duplicates_rejected_without_mutation(activities):
    before = [item.model_dump() for item in activities]
    with pytest.raises(ValidationError, match="duplicate"):
        SportActivityProfileInput(activities=activities)
    assert [item.model_dump() for item in activities] == before


@pytest.mark.parametrize("activities", [
    [entry("football"), entry(), entry("strength_training")],
    [custom("Surfing"), entry(), custom("Skiing"), entry("football")],
    [entry(), custom("Running")],
])
def test_order_and_distinct_identities_preserved(activities):
    assert [item.model_dump() for item in build(*activities).activities] == [
        item.model_dump() for item in activities
    ]


def test_multisport_fields_do_not_constrain_each_other():
    result = build(entry("strength_training", days_per_week=4, experience_level="advanced"),
                   entry("running", days_per_week=3, practice_environment="pool"),
                   entry("swimming", days_per_week=2, experience_level="beginner"))
    assert [item.days_per_week for item in result.activities] == [4, 3, 2]
    assert [item.experience_level for item in result.activities] == ["advanced", None, "beginner"]
    assert result.activities[1].practice_environment == "pool"


@pytest.mark.parametrize("mask", product((False, True), repeat=4))
def test_summary_counts_presence_only(mask):
    declared = {field: OPTIONAL[field][1] if present else None
                for field, present in zip(OPTIONAL, mask)}
    activities = [entry("football", **declared), custom("Surfing"),
                  entry("swimming", **{field: values[-1] for field, values in OPTIONAL.items()})]
    result = build(*activities)
    assert result.summary.model_dump() == summary(
        total_activities=3, known_activities=2, custom_activities=1, has_any_activities=True,
        **{COUNTS[field]: 1 + int(present) for field, present in zip(OPTIONAL, mask)},
    )
    assert [item.model_dump() for item in result.activities] == [item.model_dump() for item in activities]


@pytest.mark.parametrize("changes", [
    {"known_activities": 1}, {"custom_activities": 1},
    {"total_activities": 1, "has_any_activities": True},
    {"has_any_activities": True}, {"total_activities": 1, "known_activities": 1},
    *({name: 1} for name in COUNTS.values()),
])
def test_summary_invariants(changes):
    with pytest.raises(ValidationError):
        SportActivityProfileSummary(**summary(**changes))


@pytest.mark.parametrize("field", [name for name in summary() if name != "has_any_activities"])
@pytest.mark.parametrize("value", [-1, True, False, 0.0, "0", None])
def test_summary_counts_are_strict_nonnegative(field, value):
    with pytest.raises(ValidationError):
        SportActivityProfileSummary(**summary(**{field: value}))


@pytest.mark.parametrize("value", [0, 1, "true", "false", None])
def test_summary_presence_strict_bool(value):
    with pytest.raises(ValidationError):
        SportActivityProfileSummary(**summary(has_any_activities=value))


@pytest.mark.parametrize("model,fields,payload", [
    (SportActivityEntry, {"activity_type", "custom_activity_name", *OPTIONAL}, {"activity_type": "running"}),
    (SportActivityProfileInput, {"activities"}, {"activities": []}),
    (SportActivityProfile, {"profile_version", "activities", "summary"}, build().model_dump()),
    (SportActivityProfileSummary, set(summary()), summary()),
])
def test_exact_fields_and_extra_forbid(model, fields, payload):
    # Exact field inventories exclude history, dates, GPS, load, decisions,
    # identity/PII, language, primary sport and Human Adaptation dimensions.
    assert set(model.model_fields) == fields
    assert model.model_config["extra"] == "forbid"
    with pytest.raises(ValidationError, match="extra_forbidden"):
        model(**(payload | {"unexpected": "value"}))


def test_version_contract():
    assert SPORT_ACTIVITY_PROFILE_VERSION == build().profile_version == "sport-activity-profile-v1"
    with pytest.raises(ValidationError):
        SportActivityProfile(**(build().model_dump() | {"profile_version": "sport-activity-profile-v2"}))


def test_deep_isolation_and_determinism():
    activities = [entry("football", days_per_week=2), custom("Surfing")]
    data = SportActivityProfileInput(activities=activities)
    before = data.model_dump()
    first, second = build_sport_activity_profile(data), build_sport_activity_profile(data)
    assert first == second
    assert first.activities is not data.activities and first.activities is not activities
    assert first.activities is not second.activities
    assert first.summary is not second.summary
    for original, one, two in zip(activities, first.activities, second.activities):
        assert one is not original and two is not original and one is not two
    first.activities[0].days_per_week = 7
    first.activities[1].custom_activity_name = "Skiing"
    first.activities.pop()
    assert data.model_dump() == before
    activities[0].days_per_week = 4
    data.activities[1].custom_activity_name = "Rowing"
    data.activities.clear()
    assert [item.model_dump() for item in second.activities] == before["activities"]


@pytest.mark.parametrize("mutation", ["duplicate", "raw_dict", "invalid_days"])
def test_builder_revalidates_mutable_input(mutation):
    data = SportActivityProfileInput(activities=[entry()])
    if mutation == "duplicate":
        data.activities.append(entry())
    elif mutation == "raw_dict":
        data.activities.append({"activity_type": "swimming"})
    else:
        data.activities[0].days_per_week = True
    with pytest.raises(ValidationError):
        build_sport_activity_profile(data)


@pytest.mark.parametrize("relative,allowed_imports,allowed_calls", [
    ("app/models/sport_activity_profile.py", {"typing", "pydantic"},
     {"ConfigDict", "Field", "field_validator", "model_validator", "isinstance", "ValueError",
      "name.strip", "any", "set", "entry.custom_activity_name.casefold", "identities.add"}),
    ("app/services/sport_activity_profile.py", {"app.models.sport_activity_profile"},
     {"SportActivityProfileInput.model_validate", "SportActivityProfileInput",
      "SportActivityEntry.model_validate", "entry.model_dump",
      "SportActivityEntry.model_validate(entry.model_dump()).model_copy", "len", "sum",
      "SportActivityProfile", "SportActivityProfileSummary"}),
])
def test_architecture_import_and_call_boundaries(relative, allowed_imports, allowed_calls):
    tree = ast.parse((Path(__file__).resolve().parents[1] / relative).read_text(encoding="utf-8"))
    imports, calls = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module)
        elif isinstance(node, ast.Call):
            calls.add(ast.unparse(node.func))
    # No memory/engine/planner/recovery integration, history, clock, randomness,
    # I/O, persistence, routes, embeddings or LLM calls.
    assert imports == allowed_imports
    assert calls <= allowed_calls
