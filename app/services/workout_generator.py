"""Workout Generator V1: deterministic session-structure prescriptions."""

from dataclasses import dataclass

from app.models.training_request import Goal, TrainingLevel, TrainingRecommendationRequest
from app.models.training_response import Action, Intensity, RecommendedSession, TrainingRecommendationResponse
from app.models.workout import MovementSlot, WorkoutPlan, WorkoutPlanStatus

WORKOUT_GENERATOR_VERSION = "workout-generator-v1"

_INTENSITY_ORDER = [Intensity.low, Intensity.moderate, Intensity.high]


@dataclass(frozen=True)
class _GoalPrescription:
    rep_min: int
    rep_max: int
    rest_seconds: int
    effort_target: str


_GOAL_PRESCRIPTIONS: dict[Goal, _GoalPrescription] = {
    Goal.strength: _GoalPrescription(rep_min=4, rep_max=6, rest_seconds=150, effort_target="RPE 7-8"),
    Goal.muscle_gain: _GoalPrescription(rep_min=6, rep_max=10, rest_seconds=90, effort_target="RPE 7-8"),
    Goal.general_fitness: _GoalPrescription(rep_min=8, rep_max=12, rest_seconds=75, effort_target="RPE 6-7"),
    Goal.fat_loss: _GoalPrescription(rep_min=10, rep_max=14, rest_seconds=60, effort_target="RPE 6-7"),
    Goal.endurance: _GoalPrescription(rep_min=12, rep_max=18, rest_seconds=45, effort_target="RPE 6-7"),
    Goal.mobility: _GoalPrescription(rep_min=0, rep_max=0, rest_seconds=30, effort_target="RPE 4-5"),
}

_SESSION_TEMPLATES: dict[RecommendedSession, list[tuple[str, str | None]]] = {
    RecommendedSession.upper_body: [
        ("horizontal_push", "chest_shoulders_triceps"),
        ("horizontal_pull", "upper_back_biceps"),
        ("vertical_push", "shoulders_triceps"),
        ("vertical_pull", "lats_upper_back"),
        ("core", "trunk"),
    ],
    RecommendedSession.lower_body: [
        ("squat_pattern", "quads_glutes"),
        ("hinge_pattern", "posterior_chain"),
        ("unilateral_lower", "single_leg_control"),
        ("posterior_chain", "hamstrings_glutes"),
        ("core", "trunk"),
    ],
    RecommendedSession.full_body: [
        ("squat_pattern", "quads_glutes"),
        ("horizontal_push", "chest_shoulders_triceps"),
        ("horizontal_pull", "upper_back_biceps"),
        ("hinge_pattern", "posterior_chain"),
        ("core", "trunk"),
    ],
    RecommendedSession.cardio: [
        ("conditioning", "cardiorespiratory"),
        ("core", "trunk"),
        ("mobility", "global_mobility"),
    ],
    RecommendedSession.mobility: [
        ("mobility_spine", "thoracic_spine"),
        ("mobility_hips", "hips"),
        ("mobility_shoulders", "shoulders"),
        ("mobility_ankles", "ankles"),
        ("breathing_core_control", "trunk"),
    ],
}


@dataclass(frozen=True)
class _DurationProfile:
    max_slots: int
    set_delta: int


def _duration_profile(duration_minutes: int) -> _DurationProfile:
    if duration_minutes <= 20:
        return _DurationProfile(max_slots=3, set_delta=-1)
    if duration_minutes <= 30:
        return _DurationProfile(max_slots=4, set_delta=0)
    if duration_minutes <= 45:
        return _DurationProfile(max_slots=5, set_delta=0)
    return _DurationProfile(max_slots=5, set_delta=1)


def _clamp_intensity(intensity: Intensity) -> Intensity:
    if intensity in (Intensity.low, Intensity.moderate, Intensity.high):
        return intensity
    return Intensity.low


def _base_sets_for_intensity(intensity: Intensity) -> int:
    if intensity == Intensity.low:
        return 2
    if intensity == Intensity.high:
        return 4
    return 3


def _scale_sets_by_level(base_sets: int, level: TrainingLevel) -> int:
    if level == TrainingLevel.beginner:
        return max(1, base_sets - 1)
    if level == TrainingLevel.advanced:
        return base_sets + 1
    return base_sets


def _max_slots_by_level(base_max_slots: int, level: TrainingLevel) -> int:
    if level == TrainingLevel.beginner:
        return max(2, base_max_slots - 1)
    if level == TrainingLevel.advanced:
        return base_max_slots
    return base_max_slots


def _build_strength_slot(
    *,
    movement_pattern: str,
    target_area: str | None,
    sequence: int,
    sets: int,
    goal: Goal,
    intensity: Intensity,
) -> MovementSlot:
    profile = _GOAL_PRESCRIPTIONS[goal]
    rest = profile.rest_seconds
    if intensity == Intensity.low:
        rest = max(45, rest - 15)
    elif intensity == Intensity.high:
        rest = rest + 15

    return MovementSlot(
        movement_pattern=movement_pattern,
        target_area=target_area,
        sets=sets,
        rep_min=profile.rep_min,
        rep_max=profile.rep_max,
        work_seconds=None,
        rest_seconds=rest,
        effort_target=profile.effort_target,
        sequence=sequence,
    )


def _build_mobility_slot(
    *,
    movement_pattern: str,
    target_area: str | None,
    sequence: int,
    intensity: Intensity,
) -> MovementSlot:
    if intensity == Intensity.high:
        work_seconds = 75
        rest_seconds = 30
        effort_target = "RPE 5-6"
    elif intensity == Intensity.moderate:
        work_seconds = 60
        rest_seconds = 30
        effort_target = "RPE 4-5"
    else:
        work_seconds = 45
        rest_seconds = 20
        effort_target = "RPE 3-4"

    return MovementSlot(
        movement_pattern=movement_pattern,
        target_area=target_area,
        sets=2,
        rep_min=None,
        rep_max=None,
        work_seconds=work_seconds,
        rest_seconds=rest_seconds,
        effort_target=effort_target,
        sequence=sequence,
    )


def _is_mobility_like(session_type: RecommendedSession, action: Action) -> bool:
    return action == Action.recovery or session_type in (
        RecommendedSession.mobility,
        RecommendedSession.cardio,
    )


def _build_slots(
    *,
    session_type: RecommendedSession,
    action: Action,
    goal: Goal,
    level: TrainingLevel,
    intensity: Intensity,
    duration_minutes: int,
) -> list[MovementSlot]:
    template = _SESSION_TEMPLATES.get(session_type)
    if not template:
        return []

    duration_profile = _duration_profile(duration_minutes)
    max_slots = _max_slots_by_level(duration_profile.max_slots, level)
    selected = template[:max_slots]

    slots: list[MovementSlot] = []
    is_mobility = _is_mobility_like(session_type, action)

    base_sets = _base_sets_for_intensity(intensity)
    sets = max(1, _scale_sets_by_level(base_sets, level) + duration_profile.set_delta)

    if action == Action.recovery:
        sets = 2

    for index, (movement_pattern, target_area) in enumerate(selected, start=1):
        if is_mobility:
            slots.append(
                _build_mobility_slot(
                    movement_pattern=movement_pattern,
                    target_area=target_area,
                    sequence=index,
                    intensity=intensity,
                )
            )
        else:
            active_goal = goal if goal != Goal.mobility else Goal.general_fitness
            slots.append(
                _build_strength_slot(
                    movement_pattern=movement_pattern,
                    target_area=target_area,
                    sequence=index,
                    sets=sets,
                    goal=active_goal,
                    intensity=intensity,
                )
            )

    return slots


class WorkoutGenerator:
    """Deterministic generator that structures an approved engine decision."""

    def generate(
        self,
        request: TrainingRecommendationRequest,
        recommendation: TrainingRecommendationResponse,
    ) -> WorkoutPlan:
        if recommendation.action == Action.rest:
            return WorkoutPlan(
                status=WorkoutPlanStatus.no_workout,
                action=Action.rest,
                session_type=RecommendedSession.rest,
                intensity=Intensity.not_applicable,
                target_duration_minutes=0,
                movement_slots=[],
                generator_reason_codes=["REST_DAY"],
                generator_version=WORKOUT_GENERATOR_VERSION,
            )

        if recommendation.action == Action.request_more_data:
            return WorkoutPlan(
                status=WorkoutPlanStatus.more_data_required,
                action=recommendation.action,
                session_type=recommendation.recommended_session,
                intensity=recommendation.intensity,
                target_duration_minutes=recommendation.duration_minutes,
                movement_slots=[],
                generator_reason_codes=["ENGINE_REQUESTED_MORE_DATA"],
                generator_version=WORKOUT_GENERATOR_VERSION,
            )

        if recommendation.recommended_session not in _SESSION_TEMPLATES:
            return WorkoutPlan(
                status=WorkoutPlanStatus.more_data_required,
                action=recommendation.action,
                session_type=recommendation.recommended_session,
                intensity=recommendation.intensity,
                target_duration_minutes=recommendation.duration_minutes,
                movement_slots=[],
                generator_reason_codes=["UNSUPPORTED_SESSION_TYPE"],
                generator_version=WORKOUT_GENERATOR_VERSION,
            )

        intensity = _clamp_intensity(recommendation.intensity)
        if recommendation.action == Action.recovery and intensity == Intensity.high:
            intensity = Intensity.moderate

        slots = _build_slots(
            session_type=recommendation.recommended_session,
            action=recommendation.action,
            goal=request.goal,
            level=request.training_level,
            intensity=intensity,
            duration_minutes=recommendation.duration_minutes,
        )

        if not slots:
            return WorkoutPlan(
                status=WorkoutPlanStatus.more_data_required,
                action=recommendation.action,
                session_type=recommendation.recommended_session,
                intensity=intensity,
                target_duration_minutes=recommendation.duration_minutes,
                movement_slots=[],
                generator_reason_codes=["INSUFFICIENT_GENERATOR_INPUT"],
                generator_version=WORKOUT_GENERATOR_VERSION,
            )

        reason_codes: list[str] = []
        if recommendation.needs_more_data:
            reason_codes.append("ENGINE_NEEDS_MORE_DATA")

        return WorkoutPlan(
            status=WorkoutPlanStatus.generated,
            action=recommendation.action,
            session_type=recommendation.recommended_session,
            intensity=intensity,
            target_duration_minutes=recommendation.duration_minutes,
            movement_slots=slots,
            generator_reason_codes=reason_codes,
            generator_version=WORKOUT_GENERATOR_VERSION,
        )


_GENERATOR = WorkoutGenerator()


def generate_workout_plan(
    request: TrainingRecommendationRequest,
    recommendation: TrainingRecommendationResponse,
) -> WorkoutPlan:
    return _GENERATOR.generate(request, recommendation)
