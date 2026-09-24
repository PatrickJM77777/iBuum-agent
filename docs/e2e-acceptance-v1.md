# E2E Acceptance V1

## Scope and execution

Repository acceptance means an HTTP request through FastAPI TestClient, the real
public request DTO, route, Workout API mapper, orchestrator, Training Engine,
Workout Generator, Exercise Selector and exercise library, then the public
response DTO and HTTP response. Automated acceptance is network-independent:
it makes no Render or Base44 calls and needs no external credentials.

`tests/test_e2e_acceptance.py` uses the existing `X-API-Key` test setup. All normal
cases execute the real production pipeline. Only the three rejected-authentication
cases replace orchestration with a failing mock, proving that it cannot execute.
No production files, dependencies, deployment settings, API contracts, Training
Rules or Session Selection Policy were changed. Existing tests remain unchanged.

The suite contains **65 collected acceptance tests**:

| Coverage | Count | Evidence |
| --- | ---: | --- |
| Canonical A-P scenarios | 19 | `test_canonical_acceptance`; L includes all four known phases |
| Safety precedence across six goals | 18 | Fatigue 5, recent full-body session, high cycle discomfort |
| Exact repeated HTTP JSON | 5 | Normal, rest, recovery, omitted environment, partial equipment |
| Request and catalog isolation | 1 | Normal/rest/recovery/missing/partial/normal sequence |
| Rejected authentication | 3 | Missing, empty and wrong key; safe error and no orchestration |
| Invalid public requests | 11 | Enums, both bounds, forbidden fields and email-like ID |
| Malformed JSON | 1 | HTTP 422 |
| OpenAPI boundary | 1 | Exact public routes and public DTO references |
| Legacy recommendation parity | 5 | Normal, rest, recovery, endurance, cycle discomfort |
| Health | 1 | Unauthenticated HTTP 200 |

Every successful workout request checks exact public keys, all four versions,
recommendation/workout agreement, recursive absence of internal wrappers,
exercise catalog identity, movement pattern, explicit equipment, location and
training-level compatibility, selector status invariants, and applicable rest,
recovery and beginner ceilings. Recovery prescriptions remain mobility/breathing,
timed, at most two sets and 45 seconds per slot, with RPE 3-4 and no strength rep
ranges. No diagnosis or medical inference field is introduced; the public
response remains the approved deterministic recommendation and prescription.

All 19 canonical cases additionally compare the entire public result against an
independent projection of direct `orchestrate_workout()` output. This oracle does
not call the API mapper. It preserves recommendation, action, session, intensity,
duration, statuses, exercise IDs/names, every prescription field (including notes
and effort), selection/unresolved/generator reasons and all versions. Multiset
comparison of full generated prescriptions with selected plus unresolved public
slots detects loss, duplication and alteration; sequence uniqueness is checked.

## Canonical acceptance results

| Case | Scenario | Status | Checked behavior |
| --- | --- | --- | --- |
| A | Normal complete workout | PASS | Train, generated, complete, concrete exercises, no unresolved work |
| B | Fatigue 5 | PASS | Rest, no_workout, zero duration, no active prescription |
| C | Full body 12 hours ago | PASS | Recovery, mobility, low, <=20 minutes, complete |
| D | Environment omitted | PASS | Generated/incomplete, no exercises, SELECTION_CONTEXT_INCOMPLETE on every gap |
| E | Gym with explicit empty equipment | PASS | No exercises, incomplete, EQUIPMENT_NOT_AVAILABLE |
| F | Gym with barbell only | PASS | Partial selection, incompatible work unresolved; no relaxed equipment |
| G | Home with bodyweight | PASS | Concrete selections compatible with home and explicit bodyweight |
| H | Home with no equipment | PASS | No invented bodyweight, incomplete |
| I | Beginner | PASS | No high intensity; every exercise supports beginner |
| J | Endurance | PASS | Cardio recommendation and workout |
| K | Mobility | PASS | Mobility recommendation and workout |
| L | Phase alone, discomfort none | PASS | Exact equality to absent cycle context for menstruation, follicular, ovulation, luteal |
| M | High menstrual discomfort | PASS | Approved low-intensity mobility recovery and conservative prescriptions |
| N | Upper body 12 hours ago | PASS | Lower-body rotation, recovery evidence and intensity ceiling |
| O | Lower body 12 hours ago | PASS | Upper-body rotation, recovery evidence and intensity ceiling |
| P | Unknown session 12 hours ago | PASS | Needs more data, INSUFFICIENT_DATA, conservative mobility; neither recovery claim fabricated |

## Automated acceptance status

PASS means the applicable repository acceptance and existing regression tests
passed; it makes no claim about external deployment or real-user outcomes.

| Component | Status | Evidence |
| --- | --- | --- |
| Training Rules | PASS | Safety precedence, canonical policy cases, existing rules tests |
| Training Engine | PASS | HTTP/direct recommendation parity and existing engine tests |
| Workout Generator | PASS | Prescription parity, safety ceilings, slot accounting, existing generator tests |
| Cycle Context | PASS | L/M and safety precedence; existing cycle tests |
| Exercise Library | PASS | Catalog compatibility and isolation; existing library tests |
| Exercise Selector | PASS | A, D-H, slot accounting, existing selector tests |
| Session Policy V1.1 | PASS | N/O/P, J/K and existing policy regression coverage |
| Workout Orchestrator | PASS | Independent parity for all canonical cases; 29 existing tests |
| Profile Validation | PASS | All 29 existing tests unchanged, including profile matrices |
| Workout API | PASS | 65 acceptance tests and 62 existing endpoint tests |
| Authentication | PASS | Valid keys exercise the real pipeline; invalid keys reject safely |
| Public Contract | PASS | Exact fields, OpenAPI boundary and full semantic parity |
| Determinism | PASS | Four identical HTTP responses for each of five profiles |
| Mutation Isolation | PASS | Interleaved requests preserve normal output, input and catalog |
| Legacy API Regression | PASS | Health and recommendation parity before/after workout requests |

## Validation record

Execution date: 2026-09-24. Windows, Python 3.12.14, pytest 8.4.2.
Clean `main` was updated from origin to `02b2e5f` before the baseline.
Implementation branch: `test/e2e-acceptance-v1`.

The shell did not resolve `python`, so commands used the existing repository
interpreter `.\.venv\Scripts\python.exe`, with
the same arguments below. No dependency installation or environment configuration
change was needed.

| Command (using the existing virtual-environment Python) | Collected | Passed | Failed | Warnings |
| --- | ---: | ---: | ---: | ---: |
| `python -m pytest -q` before implementation | 415 | 415 | 0 | 2 |
| `python -m pytest -v tests/test_e2e_acceptance.py` | 65 | 65 | 0 | 1 |
| `python -m pytest -v tests/test_profile_validation.py` | 29 | 29 | 0 | 1 |
| `python -m pytest -v tests/test_workout_endpoint.py` | 62 | 62 | 0 | 1 |
| `python -m pytest -v tests/test_workout_orchestrator.py` | 29 | 29 | 0 | 1 |
| Remaining existing regression suites, verbose | 295 | 295 | 0 | 2 |
| `python -m pytest -v` final full suite | 480 | 480 | 0 | 2 |
| `python -m pytest -q` final full suite | 480 | 480 | 0 | 2 |

The remaining regression command uses `--ignore` for the four explicitly run
files above. Both final full-suite runs passed with the same two baseline warnings.
`python -m compileall app tests` passed.

The two existing warnings are Starlette's deprecation of `httpx` in TestClient
and the legacy training endpoint test's use of `data=` for raw JSON. The new
malformed-JSON test uses `content=`. No warnings were suppressed.

## Manual external acceptance (separate evidence)

### Render Manual Acceptance: NOT RECORDED

The task brief reports prior manual Render validation. No dated runtime evidence,
deployment revision or response captures were supplied or independently collected
in this run. The following checks remain unchecked in this record; automated
repository PASS results do not complete them.

- [ ] A. Deployment: service live; `/health` HTTP 200; `/api/v1/workout` exists.
- [ ] B. Normal workout: HTTP 200, generated, complete, concrete exercises returned.
- [ ] C. REST: HTTP 200, rest, no_workout, no exercises.
- [ ] D. RECOVERY: HTTP 200, recovery, mobility, low, <=20 minutes.
- [ ] E. Omitted environment: HTTP 200, generated, incomplete, zero selected
  exercises, every unresolved slot has SELECTION_CONTEXT_INCOMPLETE.
- [ ] F. Missing API key: HTTP 401 with safe error only.

Use the canonical training profile: age 30, male, 178 cm, 80 kg, strength,
intermediate, four days/week, fatigue 1. The normal environment is gym with
bodyweight, dumbbell, barbell, kettlebell, resistance_band, cable and machine.
For REST change fatigue to 5; for RECOVERY add full_body and 12 hours since the
last session; for E omit the entire environment key. Use the configured key only
through the approved secret mechanism; never paste keys in acceptance evidence.

Evidence to record: reviewer, UTC timestamp, service/deployment revision, case,
sanitized request, status and sanitized response, PASS/FAIL, evidence location.

### Base44 Manual Acceptance: NOT RECORDED

The task brief reports a server-side `getWorkout` bridge. This run did not access
the Base44 runtime and does not claim that the bridge was directly verified.

- [ ] G. `getWorkout` is an authenticated backend-only function.
- [ ] Uses `IBUUM_AGENT_URL` and `IBUUM_API_KEY` server-side.
- [ ] Calls `POST /api/v1/workout`.
- [ ] Successful normal response includes `recommendation`, `workout`, `versions`.
- [ ] Normal example returns concrete exercises.
- [ ] Omitted environment remains incomplete and no equipment is invented.

Evidence to record: reviewer, UTC timestamp, Base44 revision/runtime, sanitized
bridge invocation/result, PASS/FAIL, evidence location. Do not include secrets.
Base44 and Render were not modified by this task.

## Known limitations

E2E Acceptance V1 is not clinical validation, scientific validation, medical
validation, real-user outcome validation, load testing, penetration testing,
UI automation, Base44 browser automation, Render SLA testing, progression
validation, history/persistence validation, Form Check validation, nutrition
validation or supplementation validation. Recent-session inputs test the approved
stateless policy; they do not validate stored history. Real-pipeline parity covers
values produced by the selected scenarios, with existing mapper tests retaining
coverage for synthetic nondefault notes and versions.

## Failure policy and review

No production logic inconsistency was discovered. If a future acceptance failure
exposes one, stop without changing production and report the smallest reproducer:
acceptance case, request, environment, expected, actual, failed invariant, likely
owner (Rules, Engine, Generator, Library, Selector, Orchestrator, DTO, Mapper,
Route/Auth or test assumption), and production change required YES/NO/UNKNOWN.
Wait for human review. Do not weaken existing coverage to obtain a pass.

Diff review must confirm only the new acceptance test and this document changed:
production NO; requirements NO; deployment NO; Base44 NO; public API NO; Training
Rules NO; Session Selection Policy NO; test coverage weakened NO.
The pull request is for human review and must not be merged by this task.
