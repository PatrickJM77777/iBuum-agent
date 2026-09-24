# Workout Orchestrator V1

## Purpose and ownership

The internal `WorkoutOrchestrator.orchestrate(request, environment=None)` service
(and `orchestrate_workout` entry point) connects the existing approved pipeline:

`TrainingRecommendationRequest -> TrainingEngine.evaluate -> generate_workout_plan -> select_exercises -> WorkoutOrchestrationResult`

Every invocation calls these stages once, in order, including rest and recovery.
The Engine/Training Rules own action, session, intensity, duration, reasons and
uncertainty. The Generator owns movement patterns, prescription, effort and
sequence. The Selector owns concrete compatibility selection in stable catalog
order. The orchestrator changes none of these outputs or policies, including
Session Selection Policy V1.1. It adds no status enum or decision logic.

## Inputs

The request is the existing `TrainingRecommendationRequest`, unchanged.
`WorkoutEnvironmentContext` contains only:

- `available_equipment: frozenset[ExerciseEquipment] | None = None`
- `training_location: SuitableLocation | None = None`

Existing enums are reused. None means unknown; an empty equipment set explicitly
means nothing is available. Location never implies equipment. Bodyweight must be
explicitly supplied, like any other equipment. No equipment is inferred or added.
Extra environment fields are rejected, including `training_level`.
`request.training_level` is the single source of truth, copied into the internally
constructed `ExerciseSelectorContext` along with the two environment fields.
Omitting the environment preserves both fields as unknown.

## Result and provenance

`WorkoutOrchestrationResult` contains exactly:

- `recommendation`: full original Engine response, including reasons,
  `needs_more_data` and `agent_version`.
- `selected_workout`: full Selector result, including selected/unresolved slots,
  their reasons and `selector_version`. Its `source_plan` retains the complete
  Generator prescription, generator reasons and `generator_version`.
- `orchestrator_version`: `workout-orchestrator-v1`.

There is no duplicated WorkoutPlan or orchestrator status. Both result branches
are defensively deep-copied. Caller mutation cannot affect retained upstream
outputs, original inputs, catalog entries or independent orchestration results.
The existing selected-workout schema does not carry a library version; V1 does
not add one or duplicate catalog metadata.

## Execution semantics

Rest propagates to `no_workout`, with no active slots or selected exercises.
Recovery preserves upstream low-intensity, short mobility prescriptions and only
selects exercises for their requested patterns. `request_more_data` or a blocked
Generator plan propagates to `more_data_required` without selection. The current
Engine does not emit `request_more_data`; that contract boundary is tested with
a supplied Engine response and the real Generator and Selector.

Missing selector context leaves generated slots unresolved with
`SELECTION_CONTEXT_INCOMPLETE`. Explicitly empty equipment instead produces
`EQUIPMENT_NOT_AVAILABLE` for otherwise compatible candidates. A partially
compatible environment retains resolved and unresolved slots and their reasons.
An incomplete selector result never rewrites the Engine response or becomes rest.
`needs_more_data` alone does not force a blocked plan: existing upstream rules
can produce a conservative generated workout while preserving uncertainty.

Composition is stateless and deterministic for identical validated inputs and
unchanged upstream configuration/catalog. There is no randomness, clock, LLM,
external API, database, persistence or sensitive-data logging in this layer.
Existing Engine configuration requirements (including IBUUM_API_KEY) still apply.

## Public API and scope

GET /health and POST /api/v1/training/recommendation, public request/response
contracts, X-API-Key and IBUUM_API_KEY behavior remain unchanged. No existing
production module, training rule, library entry or dependency was modified.
The existing selector import guard now explicitly permits only the new internal
orchestration files and also guards against their use elsewhere in the app.

V1 does not include a public workout endpoint, Base44 integration, Render changes,
a progression engine, historical personalization, exercise ranking/scoring,
substitutions, injury/rehab logic, medical recommendations, Form Check, nutrition,
supplementation, database persistence or Agent 0.2. Catalog compatibility can
remain incomplete; this layer deliberately offers no fallback or relaxed constraint.

## Validation

Validated on Python 3.12.14 with the repository virtual environment. Commands use
`.venv/Scripts/python.exe` as `python`. `python -m compileall app tests` succeeded.
Baseline on clean updated main (fc52a8b): 295 collected, 295 passed, 0 failed,
2 existing warnings (`python -m pytest -q`).

Each isolated suite ran in a fresh process with `python -m pytest -v <file>`:

| Suite | Collected | Passed | Failed | Warnings |
| --- | ---: | ---: | ---: | ---: |
| tests/test_workout_orchestrator.py | 29 | 29 | 0 | 1 |
| tests/test_training_engine.py | 71 | 71 | 0 | 1 |
| tests/test_training_endpoint.py | 93 | 93 | 0 | 2 |
| tests/test_cycle_context.py | 8 | 8 | 0 | 0 |
| tests/test_workout_generator.py | 19 | 19 | 0 | 0 |
| tests/test_exercise_library.py | 17 | 17 | 0 | 0 |
| tests/test_exercise_selector.py | 87 | 87 | 0 | 0 |
| Full suite: python -m pytest -v | 324 | 324 | 0 | 2 |
| Full suite: python -m pytest -q | 324 | 324 | 0 | 2 |

The initial isolated selector run had 86 passed and 1 failure due to its old
blanket ban on any application consumer of the selector. The narrowly scoped
import-guard update resolved it; the final selector run above passed.
Warnings are the existing Starlette/httpx deprecation and raw-content upload
deprecation. Behavioral tests use real modules and catalog; spies verify call
order/identity and defensive snapshots. Coverage includes strength bootstrap,
upper/lower rotation and recent conflicts, fatigue rest, full-body and cycle
recovery, uncertain history, beginner compatibility, home/bodyweight, unavailable
or missing equipment/context, endurance, mobility, provenance, determinism,
mutation isolation and unchanged API routes/authentication/response fields.
