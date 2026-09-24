# Profile Validation V1

## Purpose and architecture

Deterministic software/logic validation of the approved internal pipeline:

TrainingRecommendationRequest → Training Rules → Training Engine → Workout
Generator → Exercise Selector → Workout Orchestrator → WorkoutOrchestrationResult.

Behavioral checks enter through `orchestrate_workout`. Direct calls to the real
Engine, Generator and Selector independently verify that the coordinator preserves
all outputs, prescriptions and reason codes. Additional assertions validate safety,
policy and compatibility rather than relying only on service-to-service equality.
This is not clinical validation or scientific validation of training programming.

Only `tests/test_profile_validation.py` and this document are added. No production
modules, requirements, public routes, authentication or deployment settings change.

## Methodology and exact scenario accounting

All inputs are synthetic. There are no random draws, added dependencies, network
or LLM calls, real identifiers, persistent telemetry or health-data logging.
Tests use bounded deterministic products, focused loops and named parametrization.
Failures in the shared validator include a label and complete synthetic request,
environment and result. Aggregate counters remain in memory; pytest can display
them using `-rP`. Assertions, not printed counts, determine pass/fail.

| Layer | Scenarios | Design |
|---|---:|---|
| Core | 630 | 6 goals × 3 levels × 7 weekly frequencies × fatigue 1–5 |
| History | 288 | 6 goals × 8 history types × 6 hour boundaries |
| Environment | 60 | 10 environments × 6 goals |
| Cycle | 162 | 9 contexts × 6 goals × fatigue 1, 4, 5 |
| Canonical | 14 | Explicit human-readable named profiles |
| Matrix subtotal | **1,154** | One orchestrator execution per scenario |
| Determinism/mutation | 30 | 10 environments × train/rest/recovery |
| Total scenario cases | **1,184** | Some inputs intentionally overlap across layers |
| Total orchestrator executions | **1,244** | 1,154 + 30 × 3 executions |

Counts are per run of the new test file, not accumulated over regression reruns.
They count scenario cases, not globally deduplicated profiles. Direct service calls
for preservation and cycle comparisons are not additional orchestrator scenarios.
The public API regression is one additional test, excluded from profile counts.
There are **29 pytest items**, using loops to avoid thousands of collected items.

The core uses gym with every explicitly available catalog equipment type. History
covers None, upper_body, lower_body, full_body, cardio, mobility, rest, unknown,
at None, 0, 12, 23, 24 and 48 hours. Level and frequency rotate over beginner/2,
intermediate/4 and advanced/7 rather than multiplying another Cartesian product.

Environment coverage: full gym; gym/bodyweight; home/bodyweight;
minimal_equipment/bodyweight; minimal_equipment/resistance_band; explicitly empty
equipment; unknown equipment; unknown location; no environment; and partial gym
with bodyweight/dumbbell. Equipment and bodyweight are always explicit. Unknown
context yields SELECTION_CONTEXT_INCOMPLETE; explicit empty equipment yields
EQUIPMENT_NOT_AVAILABLE, while preserving the upstream work.

Cycle contexts: absent; menstruation with none/mild/moderate/high discomfort;
follicular/none; ovulation/none; luteal/none; unknown/none. None and mild are compared
to an otherwise identical no-cycle request using full recommendation equality.
Moderate discomfort preserves the session and applies the existing moderate
intensity/35-minute ceilings. High discomfort produces low-intensity, 20-minute
recovery. Fatigue 4 retains its stricter ceilings; fatigue 5 remains rest.
No medical interpretation is introduced.

Canonical profiles: beginner fat loss at home (3 days); intermediate strength in
full gym (4 days); advanced muscle gain (5 days); beginner general fitness with
bodyweight (2 days); intermediate endurance (4 days); advanced fatigue 5; recent
full-body recovery; unknown recent session; high cycle discomfort; missing equipment;
explicit zero equipment; mobility goal; recent upper; recent lower.

## Validated invariants and findings

- Safety: fatigue 5 remains inactive rest, with no movement, selected or unresolved
  work. Fatigue 4 caps low intensity and 30 minutes; fatigue 3 caps moderate.
  Beginners never receive high intensity. Recovery remains low, at most 20 minutes,
  with timed mobility/breathing prescriptions, at most two sets, and RPE 3–4.
- Session policy: strength-style bootstrap and frequency-dependent rotation,
  recent split avoidance, recent full-body recovery, deterministic recovered
  full-body re-entry, and uncertainty without invented recovery evidence pass.
- Generator: action, session, duration and intensity ceiling remain authoritative;
  valid machine-readable patterns, positive prescriptions and ordered sequences
  pass. Every generated slot appears exactly once downstream, selected or unresolved.
- Selector: every chosen exercise exists in the catalog, matches its movement
  pattern, supports the request level and explicit location, and requires only
  available equipment. Incomplete selection preserves all upstream data and reasons.
- Orchestrator: exact equality with all three direct service outputs passes.
  The environment rejects an external training_level; the request is its sole source.
- Determinism/isolation: three executions for each of 30 environment/action cases
  produce equal original snapshots. Mutations to returned decisions, nested notes,
  sets, reason lists and selected/unresolved lists leave request, environment,
  catalog, another result and subsequent results unchanged.

Endurance remains cardio-oriented when no higher-priority
fatigue/recovery/cycle/recent-session rule has already selected or constrained the
session. The same priority hierarchy governs mobility preferences.

Policy observation: endurance can currently be redirected by a
higher-priority recent-session rule. This is existing approved behavior,
not introduced by Profile Validation V1. Whether endurance should remain
within cardio/recovery modalities under recent-session conflicts is a
future product-policy question and is NOT changed in this task.

The earlier absolute endurance expectation was reviewed and classified as a
validation expectation issue, not a confirmed production bug. History scenarios
now accept the approved alternate split. No other logic issue was discovered.

### Aggregate matrix results

| Matrix | Train | Recovery | Rest | Complete | Incomplete | No workout |
|---|---:|---:|---:|---:|---:|---:|
| Core | 504 | 0 | 126 | 504 | 0 | 126 |
| History | 270 | 18 | 0 | 288 | 0 | 0 |
| Environment | 60 | 0 | 0 | 14 | 46 | 0 |
| Cycle | 96 | 12 | 54 | 108 | 0 | 54 |

Request-more-data actions and more-data-required outputs are zero in these
matrices. The real engine currently does not emit request_more_data; its boundary
contract remains covered by the existing orchestrator suite with an injected
upstream decision. This is an unexercised natural-engine branch, not a newly
validated real-profile behavior.

## Public API non-impact

An in-process TestClient regression verifies exactly GET /health and
POST /api/v1/training/recommendation in OpenAPI. Missing and invalid API keys return
401; a valid key returns the unchanged Engine response. The response exposes exactly
action, recommended_session, intensity, duration_minutes, reason_codes,
needs_more_data, agent_version. Orchestrator/selected-workout schemas do not leak
into OpenAPI. No workout endpoint or new product functionality is implemented.

## Validation commands and results

Clean main was updated to `58e82f25b8a98f535b31f8595102f46516b6e923` before branch
`feature/profile-validation-v1` was created. The Windows `python` alias could not
execute; all commands below used `.venv\Scripts\python.exe` instead.

| Command after Python executable | Collected / passed | Failed | Warnings | Time |
|---|---:|---:|---:|---:|
| `-m pytest -q` (clean-main baseline) | 324 / 324 | 0 | 2 | 4.11s |
| `-m compileall app tests` | Completed successfully | — | — | — |
| `-m pytest -v tests/test_profile_validation.py` | 29 / 29 | 0 | 1 | 2.93s |
| `-m pytest -v tests/test_workout_orchestrator.py` | 29 / 29 | 0 | 1 | 1.20s |
| `-m pytest -v tests/test_training_engine.py` | 71 / 71 | 0 | 1 | 1.14s |
| `-m pytest -v tests/test_training_endpoint.py` | 93 / 93 | 0 | 2 | 4.08s |
| `-m pytest -v tests/test_cycle_context.py` | 8 / 8 | 0 | 0 | 0.30s |
| `-m pytest -v tests/test_workout_generator.py` | 19 / 19 | 0 | 0 | 0.51s |
| `-m pytest -v tests/test_exercise_library.py` | 17 / 17 | 0 | 0 | 0.43s |
| `-m pytest -v tests/test_exercise_selector.py` | 87 / 87 | 0 | 0 | 0.62s |
| `-m pytest -v` | 353 / 353 | 0 | 2 | 6.73s |
| `-m pytest -q` | 353 / 353 | 0 | 2 | 6.01s |

The two existing warnings concern Starlette/httpx TestClient deprecation and raw
upload content in the malformed-JSON test. The isolated new suite reports only
the existing TestClient warning. No warning was suppressed. `git diff --check`
and staged whitespace review pass; only the two intended files are added.

## Limits and review boundary

These are validated software invariants over a structured synthetic matrix, not
exhaustive proofs, clinical claims, or validation of exercise-programming science.
The matrix uses representative fixed demographics and the current catalog and
configuration. Partial equipment can legitimately leave slots unresolved; full
gym compatibility does not establish catalog coverage for every environment.
Repeated same-process outputs demonstrate determinism for the tested inputs and
configuration, not every possible runtime. No elapsed-time or random dependency
is introduced. No new product behavior is implemented by these tests.

All requested invariant groups pass within this scope. Human review is required
before merging; this task does not merge the branch.
