# Workout API V1

`POST /api/v1/workout` exposes the approved Engine → Generator → Selector →
Orchestrator pipeline through dedicated public DTOs. The route authenticates,
validates, maps the environment, calls `orchestrate_workout()` exactly once,
and maps its result. The mapper is stateless and only transforms data.

## Authentication and HTTP semantics

Send `X-API-Key` with the key configured by `IBUUM_API_KEY`, using the same
authentication dependency as the recommendation endpoint. Missing, empty or
incorrect keys return 401 with `Invalid or missing API key.` and no secret or
request data. Invalid request structure, enums, forbidden fields or malformed
JSON return the normal FastAPI 422 validation response.

HTTP 200 represents a valid domain result, including incomplete selection,
rest, recovery and upstream `request_more_data` / `more_data_required`.
Training eligibility is not an HTTP error. Unexpected failures retain the
existing generic 500 handler.

## Request

`WorkoutApiRequest` contains required `training: TrainingRecommendationRequest`
and optional nullable `environment: WorkoutEnvironmentApiRequest`.
The existing training model and its validation are reused unchanged.
Both new request models forbid extra fields. In particular,
`environment.training_level` is rejected; `training.training_level` is the only
source of truth.

Environment contains only:

| Field | Accepted values | Semantics |
| --- | --- | --- |
| `available_equipment` | nullable array of `bodyweight`, `dumbbell`, `barbell`, `kettlebell`, `resistance_band`, `cable`, `machine` | omitted/null: unknown; `[]`: explicitly none; populated: exactly those types |
| `training_location` | nullable `home`, `gym`, `minimal_equipment` | omitted/null: unknown |

Omitted/null environment means unknown selector context. Location never implies
equipment. Bodyweight must be explicitly supplied, including at home. Mapping
to an internal frozenset removes duplicate equipment entries without adding any.

## Response and provenance

`WorkoutApiResponse` contains:

- `recommendation`: unchanged `TrainingRecommendationResponse` with `action`,
  `recommended_session`, `intensity`, `duration_minutes`, `reason_codes`,
  `needs_more_data`, `agent_version`.
- `workout`: `plan_status` (`generated`, `no_workout`, `more_data_required`),
  `selector_status` (`complete`, `incomplete`, `no_workout`, `more_data_required`),
  `action`, `session_type`, `intensity`, `duration_minutes`, `exercises`,
  `unresolved_slots`, `generator_reason_codes`.
- `versions`: `agent_version` from the recommendation, `generator_version` from
  the source plan, `selector_version` from selection, and `orchestrator_version`
  from the orchestration result. No version is hard-coded by the adapter.

Each exercise has `exercise_id`, `display_name`, `selection_reason_codes` plus
the flat generated prescription: `sequence`, `movement_pattern`, `target_area`,
`sets`, `rep_min`, `rep_max`, `work_seconds`, `rest_seconds`, `effort_target`,
`notes`. Nullable prescription fields remain null when not applicable.
Each unresolved slot retains that same prescription plus `reason_codes`.
Slot order, notes, prescriptions and reasons are preserved without interpretation.

Rest returns `no_workout` for both statuses and empty exercise/unresolved lists.
Recovery returns the actual recovery workout from the pipeline. Missing context
can return generated work with empty exercises and unresolved slots carrying
`SELECTION_CONTEXT_INCOMPLETE`. Explicit empty equipment instead yields
`EQUIPMENT_NOT_AVAILABLE`. Partial compatible selection is retained alongside
unresolved work; there are no fallback exercises or relaxed constraints.

## Public boundary and privacy

The application OpenAPI paths are exactly `/health`,
`/api/v1/training/recommendation`, `/api/v1/workout`, and `/api/v1/interpretation`. Existing FastAPI
documentation infrastructure remains unchanged.
Internal orchestration, environment, plan and selector models are not public
request/response schemas. The API has no `source_plan` or `source_slot` wrappers.
Public status literals are independent of internal model classes.
The existing recommendation endpoint continues to call only the training engine.

The new route and mapper add no logging. Never log age, weight, height, cycle
context, user ID, equipment, history or full request JSON. Existing global
exception handling remains unchanged and returns a generic client error;
its logging policy is technical metadata only. Validation errors use the
existing FastAPI behavior and can identify invalid input to the caller.

## Validation results

Local Python 3.12.14, using `.venv/Scripts/python.exe` (the system `python`
alias was inaccessible). Baseline on clean, updated main: 353 collected,
353 passed, 0 failed, 2 existing warnings.

`compileall app tests` passed. Requested individual verbose runs:

| Suite | Collected / passed | Failed | Warnings |
| --- | --- | --- | --- |
| Workout endpoint | 62 / 62 | 0 | 1 |
| Profile validation | 29 / 29 | 0 | 1 |
| Workout orchestrator | 29 / 29 | 0 | 1 |
| Training endpoint | 93 / 93 | 0 | 2 |
| Training engine | 71 / 71 | 0 | 1 |
| Cycle context | 8 / 8 | 0 | 0 |
| Workout generator | 19 / 19 | 0 | 0 |
| Exercise library | 17 / 17 | 0 | 0 |
| Exercise selector | 87 / 87 | 0 | 0 |
| Full suite (`pytest -v` and `pytest -q`) | 415 / 415 | 0 | 2 |

The two full-suite warnings are the existing Starlette/httpx TestClient
deprecation and the existing raw-body upload deprecation in the training test.

The endpoint suite has 62 cases covering authentication, HTTP validation,
environment semantics, real-pipeline parity for 11 representative profiles,
rest/recovery, bodyweight, beginner/cycle behavior, determinism, provenance,
copy isolation, recommendation regression and OpenAPI boundaries. The
more-data test supplies an upstream decision because the current engine does
not emit that action; the actual generator, selector and route remain in use.

Existing test changes extend the OpenAPI path set in
`test_workout_orchestrator.py` and `test_profile_validation.py`, and permit the
new route/mapper to import orchestration in `test_exercise_selector.py` while
retaining its prohibition on direct selector imports. No profile behavior
assertions or internal production logic changed.

## Known limitations and exclusions

V1 depends on the existing deterministic catalog and pipeline policies.
Unknown environment may leave every slot unresolved; consumers must present
unresolved work explicitly. Versions describe pipeline provenance, not persisted
workouts. Deployment verification is a later step.

Workout API V1 does NOT include Base44 integration, Render-specific changes,
persistence, workout history storage, progression engine, exercise substitutions,
injury rehabilitation, medical advice, nutrition, supplementation, Form Check,
personalization memory, or Agent 0.2.

## Examples

The following synthetic examples are generated through the real local endpoint.
Use `Content-Type: application/json` and `X-API-Key: <your configured key>`.

### Example request

```json
{
  "training": {
    "age": 30,
    "sex": "male",
    "height_cm": 178,
    "weight_kg": 80,
    "goal": "endurance",
    "training_level": "intermediate",
    "training_days_per_week": 4,
    "fatigue_level": 1
  },
  "environment": {
    "training_location": "gym",
    "available_equipment": [
      "bodyweight",
      "dumbbell",
      "barbell",
      "kettlebell",
      "resistance_band",
      "cable",
      "machine"
    ]
  }
}
```

### Example complete response

```json
{
  "recommendation": {
    "action": "train",
    "recommended_session": "cardio",
    "intensity": "moderate",
    "duration_minutes": 45,
    "reason_codes": [
      "LOW_FATIGUE"
    ],
    "needs_more_data": false,
    "agent_version": "0.1"
  },
  "workout": {
    "plan_status": "generated",
    "selector_status": "complete",
    "action": "train",
    "session_type": "cardio",
    "intensity": "moderate",
    "duration_minutes": 45,
    "exercises": [
      {
        "sequence": 1,
        "movement_pattern": "conditioning",
        "target_area": "cardiorespiratory",
        "sets": 2,
        "rep_min": null,
        "rep_max": null,
        "work_seconds": 60,
        "rest_seconds": 30,
        "effort_target": "RPE 4-5",
        "notes": [],
        "exercise_id": "brisk_walk",
        "display_name": "Brisk Walk",
        "selection_reason_codes": [
          "STABLE_CATALOG_ORDER"
        ]
      },
      {
        "sequence": 2,
        "movement_pattern": "core",
        "target_area": "trunk",
        "sets": 2,
        "rep_min": null,
        "rep_max": null,
        "work_seconds": 60,
        "rest_seconds": 30,
        "effort_target": "RPE 4-5",
        "notes": [],
        "exercise_id": "plank",
        "display_name": "Plank",
        "selection_reason_codes": [
          "STABLE_CATALOG_ORDER"
        ]
      },
      {
        "sequence": 3,
        "movement_pattern": "mobility",
        "target_area": "global_mobility",
        "sets": 2,
        "rep_min": null,
        "rep_max": null,
        "work_seconds": 60,
        "rest_seconds": 30,
        "effort_target": "RPE 4-5",
        "notes": [],
        "exercise_id": "dynamic_mobility_flow",
        "display_name": "Dynamic Mobility Flow",
        "selection_reason_codes": [
          "STABLE_CATALOG_ORDER"
        ]
      }
    ],
    "unresolved_slots": [],
    "generator_reason_codes": []
  },
  "versions": {
    "agent_version": "0.1",
    "generator_version": "workout-generator-v1",
    "selector_version": "exercise-selector-v1",
    "orchestrator_version": "workout-orchestrator-v1"
  }
}
```

### Example incomplete response (same training, environment omitted)

```json
{
  "recommendation": {
    "action": "train",
    "recommended_session": "cardio",
    "intensity": "moderate",
    "duration_minutes": 45,
    "reason_codes": [
      "LOW_FATIGUE"
    ],
    "needs_more_data": false,
    "agent_version": "0.1"
  },
  "workout": {
    "plan_status": "generated",
    "selector_status": "incomplete",
    "action": "train",
    "session_type": "cardio",
    "intensity": "moderate",
    "duration_minutes": 45,
    "exercises": [],
    "unresolved_slots": [
      {
        "sequence": 1,
        "movement_pattern": "conditioning",
        "target_area": "cardiorespiratory",
        "sets": 2,
        "rep_min": null,
        "rep_max": null,
        "work_seconds": 60,
        "rest_seconds": 30,
        "effort_target": "RPE 4-5",
        "notes": [],
        "reason_codes": [
          "SELECTION_CONTEXT_INCOMPLETE"
        ]
      },
      {
        "sequence": 2,
        "movement_pattern": "core",
        "target_area": "trunk",
        "sets": 2,
        "rep_min": null,
        "rep_max": null,
        "work_seconds": 60,
        "rest_seconds": 30,
        "effort_target": "RPE 4-5",
        "notes": [],
        "reason_codes": [
          "SELECTION_CONTEXT_INCOMPLETE"
        ]
      },
      {
        "sequence": 3,
        "movement_pattern": "mobility",
        "target_area": "global_mobility",
        "sets": 2,
        "rep_min": null,
        "rep_max": null,
        "work_seconds": 60,
        "rest_seconds": 30,
        "effort_target": "RPE 4-5",
        "notes": [],
        "reason_codes": [
          "SELECTION_CONTEXT_INCOMPLETE"
        ]
      }
    ],
    "generator_reason_codes": []
  },
  "versions": {
    "agent_version": "0.1",
    "generator_version": "workout-generator-v1",
    "selector_version": "exercise-selector-v1",
    "orchestrator_version": "workout-orchestrator-v1"
  }
}
```
