# Exercise Selector V1 (internal only)

`select_exercises(plan, context)` in `app.services.exercise_selector` consumes a
Workout Generator `WorkoutPlan` and queries Exercise Library V1. It does not run
the engine or generator and is not connected to either public endpoint.

## Models and ownership

- `ExerciseSelectorContext`: existing `TrainingLevel`, `ExerciseEquipment`, and
  `SuitableLocation` enums, through `training_level`, `available_equipment`, and
  `training_location`. Missing fields default to `None` (unknown).
- `SelectedWorkoutPlan`: `source_plan` is a deep snapshot of the complete upstream
  plan, including status, action, session_type, intensity, target_duration_minutes,
  all movement slots, generator reasons and version. Additional fields are
  selector_status, selected_slots, unresolved_slots, and selector_version.
- `SelectedExerciseSlot`: source_slot, exercise_id, display_name, reason_codes.
  The ID references the existing library rather than embedding its metadata.
- `UnresolvedExerciseSlot`: source_slot and reason_codes.
- `ExerciseSelectionStatus`: complete, incomplete, no_workout, more_data_required.
- `SelectionReasonCode`: typed internal explanations of filtering and selection.

Each source_slot is a deep copy retaining movement_pattern, target_area, sets,
rep_min, rep_max, work_seconds, rest_seconds, effort_target, sequence and notes.
Neither inputs nor catalog entries are mutated. The engine retains decision
ownership; the generator retains prescription ownership.

## Selection policy

Process slots in their original list order; preserve sequence values without
sorting. Validate the pattern against the existing MovementPattern enum. Require
a complete context, query that exact pattern, then filter by level, location,
and equipment. Every required equipment item must be explicitly available.
Bodyweight is not implicitly granted; an empty equipment set grants nothing.

Prefer candidates whose IDs have not yet been selected in this workout. Choose
the first remaining candidate in stable library order, without asserting it is
the best. If all compatible IDs were already used, reuse the first compatible
entry and emit REUSED_AFTER_ALTERNATIVES_EXHAUSTED. DUPLICATE_AVOIDED explains
when used entries were excluded; STABLE_CATALOG_ORDER explains the tie breaker.

No randomness, timestamps, ranking, external calls or LLMs participate. Identical
validated inputs and catalog yield identical selections, ordering and reasons.

## Unresolved and blocked states

An invalid pattern or incomplete context retains the slot with an explicit reason.
Otherwise the first stage that exhausts candidates is reported:
NO_COMPATIBLE_EXERCISE, TRAINING_LEVEL_NOT_COMPATIBLE, LOCATION_NOT_COMPATIBLE,
or EQUIPMENT_NOT_AVAILABLE. Any unresolved generated slot makes selector_status
incomplete, while source_plan.status remains generated. Compatible slots can still
be selected. No filter is relaxed and no slot is silently dropped.

Upstream no_workout and more_data_required return zero selected exercises and
preserve their respective states, even without context. Unexpected slots in such
plans remain unresolved with UPSTREAM_SELECTION_BLOCKED. Recovery slots use only
their requested pattern and unchanged prescription.

## Beginner horizontal push metadata correction

`push_up` and `incline_push_up` now include `gym` in suitable_locations. Both are
existing beginner bodyweight horizontal pushes: the first uses the floor and the
second a stable elevated support, both compatible with a gym setting. Omitting
gym incorrectly blocked selection. Only these two location tuples were changed;
patterns, levels, equipment, catalog order and all other exercises are unchanged.
The selector algorithm, Training Engine, Workout Generator and public API are
unchanged by this correction.

Three selector regression cases (one slot plus real beginner upper_body and
full_body generator plans) failed before the metadata fix and pass afterward.
They now return complete with no unresolved slots under compatible gym context.
A library regression protects both entries and their existing metadata.

## Known limitations and scope

- Coverage depends on the 46-entry catalog and explicitly available equipment.
- Compatibility is limited to the three explicit context fields and movement
  pattern. It does not infer apparatus or location availability beyond metadata,
  interpret target_area as an additional constraint, or assess medical suitability.
- Changing catalog order can change selection. Reasons report the first blocking
  stage, not an exhaustive diagnosis of all possible constraints.
- No public Workout API, substitution, progression, regression, workout history,
  injury logic, cycle interpretation, nutrition, supplementation, Form Check,
  Base44/Render changes, Agent 0.2 or Session Selection Policy V1.1.

## Validation

Executed locally with Python 3.12.14 and pytest 8.4.2 in an ignored `.venv`.
Baseline before implementation: 153 passed, 0 failed, 2 warnings.
`python -m compileall app tests` succeeded. Each isolated module below ran in its
own fresh Python process using `python -m pytest -v tests/test_<module>.py`.

| Run | Collected | Passed | Failed | Warnings |
| --- | ---: | ---: | ---: | ---: |
| exercise_selector | 87 | 87 | 0 | 0 |
| training_engine | 17 | 17 | 0 | 1 |
| cycle_context | 8 | 8 | 0 | 0 |
| workout_generator | 19 | 19 | 0 | 0 |
| exercise_library | 17 | 17 | 0 | 0 |
| training_endpoint | 93 | 93 | 0 | 2 |
| Full suite `python -m pytest -v` | 241 | 241 | 0 | 2 |
| Full suite `python -m pytest -q` | 241 | 241 | 0 | 2 |

Warnings already present at baseline: Starlette's httpx TestClient deprecation
and httpx's raw-body upload deprecation in test_malformed_json_is_rejected.
No dependency requirements were changed.

Tests cover catalog order, all patterns/levels, generated sessions, strict
equipment/location compatibility, all-equipment requirements, duplicates/reuse,
determinism, incomplete context, every filter failure, blocked states, recovery,
prescription preservation, mutation isolation, and architecture/API boundaries.

## Public API and security

GET /health, POST /api/v1/training/recommendation, X-API-Key, IBUUM_API_KEY,
public request/response models, Training Rules/Engine, Kaia Cycle Context,
Workout Generator are unchanged. Exercise Library changes are limited to the two
gym location additions documented above. Source review and import
guards verify that the new service adds no secrets, PII, persistence, sensitive
logging, network/LLM calls or medical logic. Test profiles are synthetic.
