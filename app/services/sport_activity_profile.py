"""Build a detached, deterministic snapshot of declared current activities."""

from app.models.sport_activity_profile import (
    SPORT_ACTIVITY_PROFILE_VERSION,
    SportActivityEntry,
    SportActivityProfile,
    SportActivityProfileInput,
    SportActivityProfileSummary,
)


def build_sport_activity_profile(data: SportActivityProfileInput) -> SportActivityProfile:
    """Validate declarations and preserve their order without deriving context."""
    data = SportActivityProfileInput.model_validate(data)
    # Recheck the list and entry fields at the builder boundary, including edits
    # made to mutable canonical instances since their initial validation.
    data = SportActivityProfileInput(activities=data.activities)
    activities = [
        SportActivityEntry.model_validate(entry.model_dump()).model_copy(deep=True)
        for entry in data.activities
    ]
    total = len(activities)
    custom = sum(entry.activity_type == "other" for entry in activities)
    return SportActivityProfile(
        profile_version=SPORT_ACTIVITY_PROFILE_VERSION,
        activities=activities,
        summary=SportActivityProfileSummary(
            total_activities=total,
            known_activities=total - custom,
            custom_activities=custom,
            activities_with_days_per_week=sum(entry.days_per_week is not None for entry in activities),
            activities_with_experience_level=sum(entry.experience_level is not None for entry in activities),
            activities_with_typical_duration=sum(entry.typical_duration_minutes is not None for entry in activities),
            activities_with_practice_environment=sum(entry.practice_environment is not None for entry in activities),
            has_any_activities=total > 0,
        ),
    )
