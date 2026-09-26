"""Build a detached, deterministic snapshot of declared presentation choices."""

from app.models.interaction_memory import (
    INTERACTION_MEMORY_VERSION,
    InteractionMemory,
    InteractionMemoryInput,
    InteractionMemorySummary,
)


def build_interaction_memory(data: InteractionMemoryInput) -> InteractionMemory:
    """Preserve explicit values and unknowns without deriving preferences."""
    data = InteractionMemoryInput.model_validate(data)
    preferences = data.preferences.model_copy(deep=True)
    specified = sum(value is not None for value in preferences.model_dump().values())
    return InteractionMemory(
        memory_version=INTERACTION_MEMORY_VERSION,
        preferences=preferences,
        summary=InteractionMemorySummary(
            supported_preferences=6,
            specified_preferences=specified,
            unspecified_preferences=6 - specified,
            has_any_preferences=specified > 0,
        ),
    )
