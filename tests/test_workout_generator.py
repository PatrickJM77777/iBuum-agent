from app.models.training_request import Goal, TrainingLevel, TrainingRecommendationRequest
from app.models.training_response import (
    Action,
    Intensity,
    ReasonCode,
    RecommendedSession,
    TrainingRecommendationResponse,
)
from app.models.workout import WorkoutPlanStatus
from app.services.workout_generator import WORKOUT_GENERATOR_VERSION, generate_workout_plan


def _request(**overrides) -> TrainingRecommendationRequest:
    payload = {
        "age": 30,
        "sex": "male",
        "height_cm": 178.0,
        "weight_kg": 80.0,
        "goal": "general_fitness",
        "training_level": "intermediate",
        "training_days_per_week": 4,
        "fatigue_level": 2,
        "last_session_type": "unknown",
        "hours_since_last_session": 48,
    }
    payload.update(overrides)
    return TrainingRecommendationRequest(**payload)


def _recommendation(**overrides) -> TrainingRecommendationResponse:
    payload = {
        "action": Action.train,
        "recommended_session": RecommendedSession.upper_body,
        "intensity": Intensity.moderate,
        "duration_minutes": 45,
        "reason_codes": [ReasonCode.LOW_FATIGUE],
        "needs_more_data": False,
        "agent_version": "0.1",
    }
    payload.update(overrides)
    return TrainingRecommendationResponse(**payload)


def test_workout_generator_is_deterministic_for_identical_inputs():
    request = _request(goal="muscle_gain", training_level="intermediate")
    recommendation = _recommendation()

    first = generate_workout_plan(request, recommendation)
    second = generate_workout_plan(request, recommendation)

    assert first.model_dump() == second.model_dump()


def test_upper_body_moderate_prescription_contains_expected_patterns():
    plan = generate_workout_plan(_request(goal="muscle_gain"), _recommendation())

    assert plan.status == WorkoutPlanStatus.generated
    assert plan.session_type == RecommendedSession.upper_body
    assert [slot.movement_pattern for slot in plan.movement_slots][:4] == [
        "horizontal_push",
        "horizontal_pull",
        "vertical_push",
        "vertical_pull",
    ]


def test_lower_body_moderate_prescription_contains_expected_patterns():
    plan = generate_workout_plan(
        _request(goal="general_fitness"),
        _recommendation(recommended_session=RecommendedSession.lower_body),
    )

    assert [slot.movement_pattern for slot in plan.movement_slots][:3] == [
        "squat_pattern",
        "hinge_pattern",
        "unilateral_lower",
    ]


def test_full_body_prescription_contains_push_pull_lower_core():
    plan = generate_workout_plan(
        _request(goal="general_fitness"),
        _recommendation(recommended_session=RecommendedSession.full_body, duration_minutes=30),
    )

    patterns = {slot.movement_pattern for slot in plan.movement_slots}
    assert "horizontal_push" in patterns
    assert "horizontal_pull" in patterns
    assert "squat_pattern" in patterns or "hinge_pattern" in patterns
    assert len(plan.movement_slots) >= 4


def test_mobility_prescription_is_time_based_and_mobility_focused():
    plan = generate_workout_plan(
        _request(goal="mobility"),
        _recommendation(
            recommended_session=RecommendedSession.mobility,
            intensity=Intensity.low,
            duration_minutes=20,
        ),
    )

    assert all(slot.work_seconds is not None for slot in plan.movement_slots)
    assert all(slot.rep_min is None and slot.rep_max is None for slot in plan.movement_slots)
    assert all("mobility" in slot.movement_pattern or "breathing" in slot.movement_pattern for slot in plan.movement_slots)


def test_beginner_plan_is_more_conservative_than_intermediate():
    recommendation = _recommendation(recommended_session=RecommendedSession.full_body, duration_minutes=30)
    beginner = generate_workout_plan(_request(training_level="beginner"), recommendation)
    intermediate = generate_workout_plan(_request(training_level="intermediate"), recommendation)

    assert len(beginner.movement_slots) <= len(intermediate.movement_slots)
    assert all(
        (slot.sets or 0) <= ((intermediate.movement_slots[i].sets or 0))
        for i, slot in enumerate(beginner.movement_slots)
    )


def test_advanced_can_support_slightly_more_volume_than_intermediate():
    recommendation = _recommendation(duration_minutes=60)
    intermediate = generate_workout_plan(_request(training_level="intermediate"), recommendation)
    advanced = generate_workout_plan(_request(training_level="advanced"), recommendation)

    assert sum(slot.sets or 0 for slot in advanced.movement_slots) >= sum(
        slot.sets or 0 for slot in intermediate.movement_slots
    )


def test_high_intensity_generated_only_when_engine_permits_high():
    moderate_plan = generate_workout_plan(_request(goal="strength"), _recommendation(intensity=Intensity.moderate))
    high_plan = generate_workout_plan(_request(goal="strength"), _recommendation(intensity=Intensity.high))

    assert all((slot.effort_target or "") != "RPE 7-8" or moderate_plan.intensity != Intensity.high for slot in moderate_plan.movement_slots)
    assert high_plan.intensity == Intensity.high


def test_generator_never_exceeds_engine_intensity_ceiling():
    recommendation = _recommendation(intensity=Intensity.low)
    plan = generate_workout_plan(_request(goal="strength"), recommendation)

    assert plan.intensity == Intensity.low


def test_rest_action_generates_no_active_workout():
    plan = generate_workout_plan(
        _request(),
        _recommendation(
            action=Action.rest,
            recommended_session=RecommendedSession.rest,
            intensity=Intensity.not_applicable,
            duration_minutes=0,
        ),
    )

    assert plan.status == WorkoutPlanStatus.no_workout
    assert plan.movement_slots == []


def test_recovery_never_creates_demanding_strength_work():
    plan = generate_workout_plan(
        _request(goal="strength"),
        _recommendation(
            action=Action.recovery,
            recommended_session=RecommendedSession.mobility,
            intensity=Intensity.low,
            duration_minutes=20,
        ),
    )

    assert plan.action == Action.recovery
    assert all(slot.work_seconds is not None for slot in plan.movement_slots)
    assert plan.intensity != Intensity.high


def test_duration_budget_shorter_sessions_are_smaller_than_longer_sessions():
    recommendation_short = _recommendation(duration_minutes=20, recommended_session=RecommendedSession.full_body)
    recommendation_long = _recommendation(duration_minutes=60, recommended_session=RecommendedSession.full_body)

    short_plan = generate_workout_plan(_request(), recommendation_short)
    long_plan = generate_workout_plan(_request(), recommendation_long)

    assert len(short_plan.movement_slots) <= len(long_plan.movement_slots)
    assert sum(slot.sets or 0 for slot in short_plan.movement_slots) < sum(
        slot.sets or 0 for slot in long_plan.movement_slots
    )


def test_strength_goal_uses_lower_reps_and_longer_rest_than_muscle_gain():
    recommendation = _recommendation(intensity=Intensity.high)
    strength = generate_workout_plan(_request(goal="strength"), recommendation)
    muscle = generate_workout_plan(_request(goal="muscle_gain"), recommendation)

    assert strength.movement_slots[0].rep_max < muscle.movement_slots[0].rep_max
    assert strength.movement_slots[0].rest_seconds > muscle.movement_slots[0].rest_seconds


def test_general_fitness_vs_fat_loss_prescription_is_reasonable_not_extreme():
    recommendation = _recommendation()
    general = generate_workout_plan(_request(goal="general_fitness"), recommendation)
    fat_loss = generate_workout_plan(_request(goal="fat_loss"), recommendation)

    assert fat_loss.movement_slots[0].rep_min >= general.movement_slots[0].rep_min
    assert fat_loss.movement_slots[0].rest_seconds <= general.movement_slots[0].rest_seconds
    assert all(slot.rest_seconds >= 45 for slot in fat_loss.movement_slots if slot.rest_seconds is not None)


def test_needs_more_data_is_handled_conservatively_without_fabricating_data():
    plan = generate_workout_plan(
        _request(goal="muscle_gain"),
        _recommendation(needs_more_data=True, intensity=Intensity.moderate),
    )

    assert plan.status == WorkoutPlanStatus.generated
    assert "ENGINE_NEEDS_MORE_DATA" in plan.generator_reason_codes
    assert plan.intensity == Intensity.moderate


def test_movement_slots_are_machine_readable_and_no_exercise_catalog_needed():
    plan = generate_workout_plan(_request(), _recommendation())

    assert all(slot.movement_pattern for slot in plan.movement_slots)
    assert all(" " not in slot.movement_pattern for slot in plan.movement_slots)
    assert all(slot.sequence >= 1 for slot in plan.movement_slots)


def test_public_training_recommendation_contract_unchanged_with_generator_usage():
    recommendation = _recommendation()
    _ = generate_workout_plan(_request(), recommendation)
    keys = set(recommendation.model_dump().keys())

    assert keys == {
        "action",
        "recommended_session",
        "intensity",
        "duration_minutes",
        "reason_codes",
        "needs_more_data",
        "agent_version",
    }


def test_generator_has_no_mutation_leakage_between_requests():
    recommendation = _recommendation(recommended_session=RecommendedSession.mobility)
    first = generate_workout_plan(_request(), recommendation)
    first.movement_slots[0].notes.append("first-call-note")

    second = generate_workout_plan(_request(), recommendation)

    assert second.movement_slots[0].notes == []


def test_generator_version_is_explicit_and_stable():
    plan = generate_workout_plan(_request(), _recommendation())
    assert plan.generator_version == WORKOUT_GENERATOR_VERSION
