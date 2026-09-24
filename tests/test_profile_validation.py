"""Deterministic synthetic validation of the real internal workout pipeline."""

import os
from collections import Counter
from itertools import product

import pytest
from pydantic import ValidationError

os.environ.setdefault("IBUUM_API_KEY", "test-secret-key")

from app.models.exercise import ExerciseEquipment, MovementPattern
from app.models.exercise_selection import ExerciseSelectorContext
from app.models.training_request import TrainingRecommendationRequest
from app.models.training_response import TrainingRecommendationResponse
from app.models.workout_orchestration import WorkoutEnvironmentContext, WorkoutOrchestrationResult
from app.services import exercise_library, exercise_selector, training_engine, workout_generator
from app.services.workout_orchestrator import WORKOUT_ORCHESTRATOR_VERSION, orchestrate_workout

GOALS = ("general_fitness", "fat_loss", "muscle_gain", "strength", "endurance", "mobility")
LEVELS = ("beginner", "intermediate", "advanced")
HISTORY = (None, "upper_body", "lower_body", "full_body", "cardio", "mobility", "rest", "unknown")
HOURS = (None, 0, 12, 23, 24, 48)
RANK = {"not_applicable": -1, "low": 0, "moderate": 1, "high": 2}


def request(**changes):
    return TrainingRecommendationRequest(**(dict(
        age=30, sex="male", height_cm=178, weight_kg=80, goal="strength",
        training_level="intermediate", training_days_per_week=4, fatigue_level=1,
    ) | changes))


def environment(location="gym", equipment=frozenset(ExerciseEquipment)):
    return WorkoutEnvironmentContext(training_location=location, available_equipment=equipment)


ENVIRONMENTS = (
    ("full-gym", environment()),
    ("gym-bodyweight", environment(equipment={"bodyweight"})),
    ("home-bodyweight", environment("home", {"bodyweight"})),
    ("minimal-bodyweight", environment("minimal_equipment", {"bodyweight"})),
    ("minimal-band", environment("minimal_equipment", {"resistance_band"})),
    ("explicit-empty", environment(equipment=set())),
    ("unknown-equipment", environment(equipment=None)),
    ("unknown-location", environment(None, {"bodyweight"})),
    ("no-environment", None),
    ("partial-gym", environment(equipment={"bodyweight", "dumbbell"})),
)
CYCLES = (None,) + tuple(
    {"phase": phase, "discomfort": discomfort}
    for phase, discomfort in (
        ("menstruation", "none"), ("menstruation", "mild"),
        ("menstruation", "moderate"), ("menstruation", "high"),
        ("follicular", "none"), ("ovulation", "none"),
        ("luteal", "none"), ("unknown", "none"),
    )
)
CANONICAL = (
    ("beginner-fat-loss-home", dict(goal="fat_loss", training_level="beginner", training_days_per_week=3), 2),
    ("intermediate-strength-gym", {}, 0),
    ("advanced-muscle-gain", dict(goal="muscle_gain", training_level="advanced", training_days_per_week=5), 0),
    ("beginner-general-fitness", dict(goal="general_fitness", training_level="beginner", training_days_per_week=2), 1),
    ("intermediate-endurance", dict(goal="endurance"), 0),
    ("advanced-fatigue-five", dict(training_level="advanced", fatigue_level=5), 0),
    ("recent-full-body", dict(last_session_type="full_body", hours_since_last_session=12), 0),
    ("unknown-recent-session", dict(last_session_type="unknown", hours_since_last_session=12), 0),
    ("high-cycle-discomfort", dict(sex="female", cycle_context={"phase": "menstruation", "discomfort": "high"}), 0),
    ("missing-equipment", {}, 6),
    ("explicit-zero-equipment", {}, 5),
    ("mobility-goal", dict(goal="mobility"), 0),
    ("recent-upper-body", dict(last_session_type="upper_body", hours_since_last_session=12), 0),
    ("recent-lower-body", dict(last_session_type="lower_body", hours_since_last_session=12), 0),
)


def validate(label, req, env):
    """Check independent invariants plus exact direct-service preservation."""
    result = orchestrate_workout(req, env)
    rec, selected = result.recommendation, result.selected_workout
    plan = selected.source_plan
    detail = (f"{label}: request={req.model_dump_json()} "
              f"environment={env.model_dump_json() if env else None} "
              f"result={result.model_dump_json()}")

    def check(condition, invariant):
        assert condition, f"{invariant}\n{detail}"

    direct_rec = training_engine.evaluate(req)
    direct_plan = workout_generator.generate_workout_plan(req, direct_rec)
    direct_selected = exercise_selector.select_exercises(direct_plan, ExerciseSelectorContext(
        training_level=req.training_level,
        training_location=env.training_location if env else None,
        available_equipment=env.available_equipment if env else None,
    ))
    check(rec.model_dump() == direct_rec.model_dump(), "Engine decision preserved")
    check(plan.model_dump() == direct_plan.model_dump(), "Generator prescription preserved")
    check(selected.model_dump() == direct_selected.model_dump(), "Selector output/reasons preserved")
    check(result.orchestrator_version == WORKOUT_ORCHESTRATOR_VERSION, "Orchestrator version")
    check(plan.action == rec.action and plan.session_type == rec.recommended_session
          and plan.target_duration_minutes == rec.duration_minutes, "Engine authority")
    check(RANK[plan.intensity] <= RANK[rec.intensity], "Generator intensity ceiling")
    check(req.training_level != "beginner" or rec.intensity != "high", "Beginner ceiling")
    check(req.fatigue_level != 5 or rec.action == "rest", "Fatigue five requires rest")
    if req.fatigue_level == 4:
        check(RANK[rec.intensity] <= RANK["low"] and rec.duration_minutes <= 30, "Fatigue four caps")
    if req.fatigue_level == 3:
        check(RANK[rec.intensity] <= RANK["moderate"], "Fatigue three ceiling")
    if rec.action == "rest":
        check(rec.intensity == "not_applicable" and rec.duration_minutes == 0, "Inactive rest")
        check(plan.status == selected.selector_status == "no_workout", "Rest propagation")
        check(not plan.movement_slots and not selected.selected_slots and not selected.unresolved_slots, "No rest work")
    if rec.action == "recovery":
        check(rec.intensity == "low" and rec.duration_minutes <= 20, "Recovery caps")
        check(rec.recommended_session == "mobility", "Recovery modality")
        check(all((s.movement_pattern.startswith("mobility") or s.movement_pattern == "breathing_core_control")
                  and s.rep_min is None and s.rep_max is None and s.sets <= 2
                  and s.work_seconds <= 45 and s.effort_target == "RPE 3-4"
                  for s in plan.movement_slots), "Recovery-compatible prescriptions")
    check([s.sequence for s in plan.movement_slots] == list(range(1, len(plan.movement_slots) + 1)), "Slot sequences")
    for slot in plan.movement_slots:
        check(slot.movement_pattern in {p.value for p in MovementPattern}, "Machine-readable pattern")
        check(slot.sets > 0 and slot.rest_seconds >= 0, "Positive prescription")
        check((slot.work_seconds is not None and slot.work_seconds > 0 and slot.rep_min is None and slot.rep_max is None)
              or (slot.work_seconds is None and slot.rep_min is not None and 0 < slot.rep_min <= slot.rep_max), "Reps or timed work")
    all_slots = selected.selected_slots + selected.unresolved_slots
    check(Counter(s.source_slot.model_dump_json() for s in all_slots)
          == Counter(s.model_dump_json() for s in plan.movement_slots), "Every source slot retained exactly once")
    for slot in selected.selected_slots:
        exercise = exercise_library.get_exercise_by_id(slot.exercise_id)
        check(exercise is not None, "Catalog exercise exists")
        check(exercise.movement_pattern == slot.source_slot.movement_pattern, "Pattern compatibility")
        check(req.training_level in exercise.training_levels, "Request-level compatibility")
        check(env is not None and env.training_location in exercise.suitable_locations, "Location compatibility")
        check(env.available_equipment is not None and set(exercise.equipment) <= env.available_equipment, "Explicit equipment only")
    if selected.selector_status == "complete":
        check(not selected.unresolved_slots and len(selected.selected_slots) == len(plan.movement_slots), "Complete selection accounts for all work")
    if selected.selector_status == "incomplete":
        check(bool(selected.unresolved_slots), "Incomplete selection explains gaps")
    if plan.status == "generated":
        check(bool(plan.movement_slots), "Generated work exists")
        missing = env is None or env.available_equipment is None or env.training_location is None
        if missing:
            check(selected.selector_status == "incomplete" and not selected.selected_slots, "Missing context not invented")
            check(all(s.reason_codes == ["SELECTION_CONTEXT_INCOMPLETE"] for s in selected.unresolved_slots), "Unknown context reason")
        elif not env.available_equipment:
            check(selected.selector_status == "incomplete" and not selected.selected_slots, "Empty equipment is not bodyweight")
            check(all(s.reason_codes == ["EQUIPMENT_NOT_AVAILABLE"] for s in selected.unresolved_slots), "Explicit empty differs from unknown")

    # Approved priority hierarchy: recent-session choices precede goal preferences.
    if rec.action == "train":
        last, hours = req.last_session_type, req.hours_since_last_session
        recent = hours is not None and hours < 24
        if (last in (None, "unknown") and recent) or (last == "full_body" and hours is None):
            expected = "mobility"
        elif last in ("upper_body", "lower_body") and (hours is None or recent):
            expected = "lower_body" if last == "upper_body" else "upper_body"
        elif req.goal in ("endurance", "mobility"):
            expected = "cardio" if req.goal == "endurance" else "mobility"
        elif req.training_days_per_week >= 4:
            expected = {"upper_body": "lower_body", "lower_body": "upper_body", "full_body": "upper_body"}.get(last, "full_body")
        else:
            expected = "full_body"
        check(rec.recommended_session == expected, "Session policy with higher-priority overrides")
        uncertain = (last in (None, "unknown") and recent) or (last in ("upper_body", "lower_body", "full_body") and hours is None)
        if uncertain:
            check(rec.needs_more_data and "INSUFFICIENT_DATA" in rec.reason_codes and rec.intensity != "high", "History uncertainty retained")
            check("RECOVERY_WINDOW_OK" not in rec.reason_codes and "INSUFFICIENT_RECOVERY" not in rec.reason_codes, "Uncertainty is not recovery evidence")
        if last in (None, "unknown"):
            check("RECOVERY_WINDOW_OK" not in rec.reason_codes, "Unknown history cannot confirm recovery")
        if last in ("upper_body", "lower_body") and recent:
            check(rec.intensity != "high" and "INSUFFICIENT_RECOVERY" in rec.reason_codes, "Recent split ceiling")
    if req.last_session_type == "full_body" and req.hours_since_last_session is not None and req.hours_since_last_session < 24:
        check(rec.action in ("rest", "recovery"), "Recent full-body safety")
    return result


def sweep(cases, expected_count):
    actions, statuses = Counter(), Counter()
    for label, req, env in cases:
        result = validate(label, req, env)
        actions[result.recommendation.action.value] += 1
        statuses[result.selected_workout.selector_status.value] += 1
    assert sum(actions.values()) == sum(statuses.values()) == expected_count
    assert set(actions) <= {"train", "recovery", "rest", "request_more_data"}
    assert set(statuses) <= {"complete", "incomplete", "no_workout", "more_data_required"}
    # In-memory only; pytest -rP displays these aggregate synthetic counters.
    print(f"profiles={expected_count}; actions={dict(actions)}; selectors={dict(statuses)}")
    return actions, statuses


def test_core_matrix():
    cases = ((f"core/{goal}/{level}/{days}/{fatigue}", request(goal=goal, training_level=level,
              training_days_per_week=days, fatigue_level=fatigue), environment())
             for goal, level, days, fatigue in product(GOALS, LEVELS, range(1, 8), range(1, 6)))
    actions, statuses = sweep(cases, 630)
    assert actions == {"train": 504, "rest": 126}
    assert statuses == {"complete": 504, "no_workout": 126}


def test_history_matrix():
    # Full semantic boundaries; rotate level/frequency instead of multiplying them.
    cases = ((f"history/{goal}/{last}/{hours}", request(goal=goal,
              training_level=LEVELS[index % 3], training_days_per_week=(2, 4, 7)[index % 3],
              last_session_type=last, hours_since_last_session=hours), environment())
             for index, (goal, last, hours) in enumerate(product(GOALS, HISTORY, HOURS)))
    actions, _ = sweep(cases, 288)
    assert actions == {"train": 270, "recovery": 18}


def test_environment_matrix():
    sweep(((f"environment/{name}/{goal}", request(goal=goal), env)
           for (name, env), goal in product(ENVIRONMENTS, GOALS)), 60)


def test_cycle_matrix():
    cases = []
    for goal, fatigue, cycle in product(GOALS, (1, 4, 5), CYCLES):
        req = request(goal=goal, fatigue_level=fatigue, sex="female", cycle_context=cycle)
        cases.append((f"cycle/{goal}/{fatigue}/{cycle}", req, environment()))
    sweep(cases, 162)
    # Compare to absence of cycle context; no clinical interpretation is added.
    for label, req, env in cases:
        base = training_engine.evaluate(req.model_copy(update={"cycle_context": None}))
        actual = training_engine.evaluate(req)
        discomfort = req.cycle_context.discomfort if req.cycle_context else "none"
        if discomfort in ("none", "mild") or req.fatigue_level == 5:
            assert actual.model_dump() == base.model_dump(), label
        elif discomfort == "moderate":
            assert actual.action == base.action and actual.recommended_session == base.recommended_session, label
            assert RANK[actual.intensity] == min(RANK[base.intensity], RANK["moderate"]), label
            assert actual.duration_minutes == min(base.duration_minutes, 35), label
            assert "CYCLE_MODERATE_DISCOMFORT" in actual.reason_codes, label
        else:
            assert actual.action == "recovery" and actual.intensity == "low" and actual.duration_minutes == 20, label
            assert "CYCLE_HIGH_DISCOMFORT" in actual.reason_codes, label


@pytest.mark.parametrize("label,changes,env_index", CANONICAL, ids=[c[0] for c in CANONICAL])
def test_canonical_profile(label, changes, env_index):
    validate(label, request(**changes), ENVIRONMENTS[env_index][1])


@pytest.mark.parametrize("name,env", ENVIRONMENTS, ids=[e[0] for e in ENVIRONMENTS])
def test_determinism_and_mutation_isolation(name, env):
    catalog_before = [e.model_dump() for e in exercise_library.list_exercises()]
    for mode, changes in (("train", {}), ("rest", {"fatigue_level": 5}),
                          ("recovery", {"last_session_type": "full_body", "hours_since_last_session": 12})):
        req = request(sex="female", cycle_context={"phase": "follicular", "discomfort": "none"}, **changes)
        req_before, env_before = req.model_dump(), env.model_dump() if env else None
        first = validate(f"isolation/{name}/{mode}", req, env)
        other = orchestrate_workout(req, env)
        snapshot = other.model_dump()
        assert first.model_dump() == snapshot, (name, mode, req_before, env_before)
        first.recommendation.reason_codes.clear()
        first.recommendation.duration_minutes = 999
        first.selected_workout.source_plan.generator_reason_codes.append("synthetic mutation")
        for slot in first.selected_workout.source_plan.movement_slots:
            slot.notes.append("synthetic mutation")
            slot.sets = 999
        for slot in first.selected_workout.selected_slots + first.selected_workout.unresolved_slots:
            slot.source_slot.notes.append("synthetic mutation")
            slot.source_slot.sets = 999
            slot.reason_codes.clear()
        first.selected_workout.selected_slots.clear()
        first.selected_workout.unresolved_slots.clear()
        assert req.model_dump() == req_before, (name, mode)
        assert (env.model_dump() if env else None) == env_before, (name, mode)
        assert [e.model_dump() for e in exercise_library.list_exercises()] == catalog_before, (name, mode)
        assert other.model_dump() == snapshot, (name, mode)
        assert orchestrate_workout(req, env).model_dump() == snapshot, (name, mode)


def test_public_api_and_internal_contracts():
    from fastapi.testclient import TestClient
    from app.main import app

    assert set(WorkoutEnvironmentContext.model_fields) == {"available_equipment", "training_location"}
    with pytest.raises(ValidationError):
        WorkoutEnvironmentContext(training_level="advanced")
    assert set(WorkoutOrchestrationResult.model_fields) == {"recommendation", "selected_workout", "orchestrator_version"}
    fields = {"action", "recommended_session", "intensity", "duration_minutes", "reason_codes", "needs_more_data", "agent_version"}
    assert set(TrainingRecommendationResponse.model_fields) == fields
    schema = app.openapi()
    assert set(schema["paths"]) == {"/health", "/api/v1/training/recommendation"}
    assert set(schema["paths"]["/health"]) == {"get"}
    assert set(schema["paths"]["/api/v1/training/recommendation"]) == {"post"}
    assert not any("Orchestrat" in name or "SelectedWorkout" in name for name in schema["components"]["schemas"])
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        path, payload = "/api/v1/training/recommendation", request().model_dump(mode="json")
        assert client.post(path, json=payload).status_code == 401
        assert client.post(path, json=payload, headers={"X-API-Key": "invalid-synthetic-key"}).status_code == 401
        response = client.post(path, json=payload, headers={"X-API-Key": os.environ["IBUUM_API_KEY"]})
        assert response.status_code == 200
        assert set(response.json()) == fields
        assert response.json() == training_engine.evaluate(request()).model_dump(mode="json")
