"""Bounded contract, isolation and architecture checks for Interaction Memory."""

import ast
from itertools import product
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.models.interaction_memory import (
    INTERACTION_MEMORY_VERSION,
    InteractionMemory,
    InteractionMemoryInput,
    InteractionMemorySummary,
    InteractionPreferences,
)
from app.services.interaction_memory import build_interaction_memory


VALUES = {
    "explanation_length": ("short", "balanced", "detailed"),
    "technical_depth": ("simple", "standard", "technical"),
    "voice_preference": ("text", "either", "voice"),
    "visual_preference": ("text", "balanced", "visual"),
    "step_by_step_preference": ("summary", "adaptive", "step_by_step"),
    "repetition_preference": ("minimal", "standard", "reinforced"),
}
MODELS = (InteractionPreferences, InteractionMemoryInput, InteractionMemorySummary, InteractionMemory)


def build(**preferences):
    return build_interaction_memory(
        InteractionMemoryInput(preferences=InteractionPreferences(**preferences))
    )


def summary(**changes):
    return dict(supported_preferences=6, specified_preferences=0,
                unspecified_preferences=6, has_any_preferences=False) | changes


@pytest.mark.parametrize("field,value", [
    (field, value) for field, values in VALUES.items() for value in (*values, None)
])
def test_preserves_each_value_without_cross_field_inference(field, value):
    preferences = InteractionPreferences(**{field: value})
    data = InteractionMemoryInput(preferences=preferences)
    assert data.preferences is preferences
    result = build_interaction_memory(data)
    assert result.preferences.model_dump() == {
        name: value if name == field else None for name in VALUES
    }


@pytest.mark.parametrize("field", VALUES)
@pytest.mark.parametrize("value", ["invalid", "", True, 1, 1.5, [], {}])
def test_invalid_preference_rejected(field, value):
    with pytest.raises(ValidationError):
        InteractionPreferences(**{field: value})


@pytest.mark.parametrize("value", [{}, {"technical_depth": "technical"}, None, "voice"])
def test_input_requires_canonical_instance(value):
    with pytest.raises(ValidationError):
        InteractionMemoryInput(preferences=value)


def test_input_requires_preferences():
    with pytest.raises(ValidationError):
        InteractionMemoryInput()


@pytest.mark.parametrize("mask", product((False, True), repeat=6))
def test_factual_summary_for_every_presence_combination(mask):
    declared = {field: VALUES[field][0] if supplied else None
                for field, supplied in zip(VALUES, mask)}
    result = build(**declared)
    specified = sum(mask)
    assert result.preferences.model_dump() == declared
    assert result.summary.model_dump() == summary(
        specified_preferences=specified, unspecified_preferences=6 - specified,
        has_any_preferences=specified > 0,
    )


@pytest.mark.parametrize("model,fields", [
    (InteractionPreferences, set(VALUES)),
    (InteractionMemoryInput, {"preferences"}),
    (InteractionMemory, {"memory_version", "preferences", "summary"}),
    (InteractionMemorySummary, set(summary())),
])
def test_exact_contract_excludes_unrelated_data(model, fields):
    # Exact inventories exclude decisions, sports preferences, locale, identity,
    # timestamps, disability, free text, confidence and conversation history.
    assert set(model.model_fields) == fields
    assert model.model_config["extra"] == "forbid"


@pytest.mark.parametrize("model", MODELS)
def test_unknown_fields_rejected(model):
    payloads = {
        InteractionPreferences: {},
        InteractionMemoryInput: {"preferences": InteractionPreferences()},
        InteractionMemorySummary: summary(),
        InteractionMemory: build().model_dump(),
    }
    with pytest.raises(ValidationError, match="extra_forbidden"):
        model(**(payloads[model] | {"unexpected": "value"}))


def test_exact_version():
    assert INTERACTION_MEMORY_VERSION == build().memory_version == "interaction-memory-v1"
    with pytest.raises(ValidationError):
        InteractionMemory(**(build().model_dump() | {"memory_version": "interaction-memory-v2"}))


@pytest.mark.parametrize("changes", [
    {"supported_preferences": 5},
    {"supported_preferences": 7, "unspecified_preferences": 7},
    {"specified_preferences": 1},
    {"specified_preferences": 7, "unspecified_preferences": 0, "has_any_preferences": True},
    {"has_any_preferences": True},
    {"specified_preferences": 1, "unspecified_preferences": 5},
])
def test_summary_invariants(changes):
    with pytest.raises(ValidationError):
        InteractionMemorySummary(**summary(**changes))


@pytest.mark.parametrize("field", ["supported_preferences", "specified_preferences", "unspecified_preferences"])
@pytest.mark.parametrize("value", [-1, True, False, 0.0, 6.0, "0", "6", None])
def test_summary_counts_strict_nonnegative(field, value):
    with pytest.raises(ValidationError):
        InteractionMemorySummary(**summary(**{field: value}))


@pytest.mark.parametrize("value", [0, 1, "true", "false", None])
def test_presence_strict_bool(value):
    with pytest.raises(ValidationError):
        InteractionMemorySummary(**summary(has_any_preferences=value))


def test_determinism_and_mutation_isolation():
    preferences = InteractionPreferences(**{name: values[0] for name, values in VALUES.items()})
    data = InteractionMemoryInput(preferences=preferences)
    before = data.model_dump()
    first = build_interaction_memory(data)
    second = build_interaction_memory(data)
    assert first == second
    assert first is not second
    assert first.preferences is not preferences
    assert first.preferences is not second.preferences
    assert first.summary is not second.summary
    assert data.model_dump() == before
    for name, values in VALUES.items():
        setattr(first.preferences, name, values[-1])
    assert data.model_dump() == before
    assert second.preferences.model_dump() == before["preferences"]
    preferences.explanation_length = None
    assert second.preferences.explanation_length == "short"


@pytest.mark.parametrize("relative,allowed_imports,allowed_calls", [
    ("app/models/interaction_memory.py", {"typing", "pydantic"},
     {"ConfigDict", "Field", "field_validator", "model_validator", "isinstance", "ValueError"}),
    ("app/services/interaction_memory.py", {"app.models.interaction_memory"},
     {"InteractionMemoryInput.model_validate", "data.preferences.model_copy", "sum",
      "preferences.model_dump", "preferences.model_dump().values", "InteractionMemory",
      "InteractionMemorySummary"}),
])
def test_architecture_dependencies_and_calls(relative, allowed_imports, allowed_calls):
    tree = ast.parse((Path(__file__).resolve().parents[1] / relative).read_text(encoding="utf-8"))
    imports = set()
    calls = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module)
        elif isinstance(node, ast.Call):
            calls.add(ast.unparse(node.func))
    # No sports engines/memory, clock, DB/ORM, routes, persistence, vectors or LLMs.
    assert imports == allowed_imports
    assert calls <= allowed_calls
