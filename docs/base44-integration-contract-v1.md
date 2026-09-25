# Base44 Integration Contract V1

## Purpose and current backend state

Define the future additive Base44 bridge `getWorkoutInterpretation` to the
approved Interpretation API V1. This document specifies an integration; it does
not implement Base44, change backend behavior or configure Render.

MOTOR DECIDES. INTERPRETATION EXPLAINS. UI PRESENTS.

Training Rules/Engine, Workout Generator, Kaia Cycle Context, Exercise
Library/Selector, Session Selection Policy V1.1, Workout Orchestrator, Profile
Validation, Workout API, E2E Acceptance, Interpretation Core and Interpretation
API are already approved. The supplied project context reports Render validation;
this task performs local validation only. Updated `main` baseline: 675 passed,
2 existing warnings.

Public application paths (excluding framework documentation routes) remain:

| Method | Path |
| --- | --- |
| GET | `/health` |
| POST | `/api/v1/training/recommendation` |
| POST | `/api/v1/workout` |
| POST | `/api/v1/interpretation` |

The source of truth is current `app.openapi()` and
[interpretation DTOs](../app/models/interpretation_api.py),
[training input](../app/models/training_request.py),
[training output](../app/models/training_response.py),
[workout DTOs](../app/models/workout_api.py), and
[authentication](../app/core/security.py). See also
[Interpretation API V1](interpretation-api-v1.md).

## Architecture and responsibilities

```text
Base44 UI -> authenticated server-side getWorkoutInterpretation
          -> POST ${IBUUM_AGENT_URL}/api/v1/interpretation
             X-API-Key: ${IBUUM_API_KEY}
          <- recommendation + workout + interpretation + versions
Base44 UI <- unchanged public success object
```

Training Engine / Orchestrator decides the workout. Interpretation Core explains
the approved decision. The explicitly chosen Kai / Kaia presenter supplies
presentation context. Base44 UI renders the result. One future server-side
function obtains all four objects in one request; do not call the recommendation
or workout endpoints separately to assemble a competing result.

Base44 must not re-evaluate fatigue, cycle phase/discomfort, recovery, level,
goal, equipment or history. Backend action, session, intensity, duration,
reason codes, exercise selection and interpretation text are authoritative.
No second interpretation model, generative AI call, substitute workout or
rewriting of backend decision fields belongs in this bridge.

## Security, authentication and privacy

Authenticate the current Base44 user using the product's existing server-side
auth conventions before any outbound call. Those conventions and function source
are external and have not been inspected here. Never trust a client-supplied
identity as authentication. Optional anonymous `training.user_id` is not proof
of identity; omit it or bind it to the authenticated user's existing anonymous
identifier under established product policy. Do not enrich with PII.

`IBUUM_AGENT_URL` is existing server-side configuration; `IBUUM_API_KEY` is an
existing server-side secret. Resolve both on the server. Never accept URL, API
key or outbound headers from the caller. Use the configured trusted HTTPS origin,
append `/api/v1/interpretation` without a duplicate slash, and do not follow
redirects that could forward the secret to another destination.

The browser must never call Render with the secret or receive it. Never expose
the key in frontend code, browser/console output, logs, returned JSON, errors or
test reports. Do not log entire training payloads, cycle context, profiles or
raw upstream error bodies. No such telemetry is authorized without a future
explicit security review. Minimal technical outcome/status/timing metadata is
sufficient; avoid logging exceptions that may contain request headers/bodies.

Backend auth uses `X-API-Key` (case-insensitive); OpenAPI currently describes it
as a nullable `x-api-key` header parameter, not a security scheme. Runtime auth
is mandatory: missing, empty or incorrect keys yield 401 with
`{"detail":"Invalid or missing API key."}`. The header's optional schema
representation does not make authenticated access optional.

## Request contract

```text
POST ${IBUUM_AGENT_URL}/api/v1/interpretation
Content-Type: application/json
X-API-Key: <server-side IBUUM_API_KEY>

{
  "presenter": "kai" | "kaia",
  "training": TrainingRecommendationRequest,
  "environment": WorkoutEnvironmentApiRequest | null
}
```

The body has exactly these three allowed properties. `presenter` and `training`
are required; `environment` may be omitted or null. Unknown top-level and
environment properties are forbidden. Sanitize by validating structure and
allowlisting supported fields, without filling missing facts or normalizing
presenter case. Reject invalid values; leave domain validation authoritative
in Render. Do not silently remove invalid top-level/environment fields.

`TrainingRecommendationRequest` fields:

| Fields | Input contract |
| --- | --- |
| `age` | Required integer, 10..100 |
| `sex` | Required `male` or `female` |
| `height_cm`, `weight_kg` | Required numbers, respectively >0..300 and >0..400 |
| `goal` | Required `general_fitness`, `fat_loss`, `muscle_gain`, `strength`, `endurance`, `mobility` |
| `training_level` | Required `beginner`, `intermediate`, `advanced` |
| `training_days_per_week` | Required integer, 1..7 |
| `fatigue_level` | Required integer, 1..5 |
| `user_id` | Optional/null anonymous string, max 128 characters, no `@`; never email/name |
| `last_session_type` | Optional/null `upper_body`, `lower_body`, `full_body`, `cardio`, `mobility`, `rest`, `unknown` |
| `hours_since_last_session` | Optional/null integer >=0 |
| `cycle_context` | Optional/null object: required `phase`, optional `discomfort` defaulting to `none` in the backend |

Cycle phase accepts `menstruation`, `follicular`, `ovulation`, `luteal`, `unknown`;
discomfort accepts `none`, `mild`, `moderate`, `high`. Reuse these fields only.
The backend training/cycle models currently use Pydantic's default extra-field
ignore behavior, unlike the strict outer/environment DTOs. The bridge should
forward only known training/cycle fields; this is data minimization, not a
claim that the backend forbids nested extras. Do not invent domain defaults.

## Presenter semantics and Kai/Kaia behavior

Require exactly `kai` or `kaia` from product/UI state on every request. Never
infer it from sex, cycle context, profile, goal or name. Either presenter can
be explicitly chosen for either supported sex.

Both presenters preserve the same approved training decision. Kai always
returns `cycle_insight: null`; Kaia may explain supplied cycle context and
returns null without it. Phase alone, including menstruation, does not imply
reduced capacity or intensity. High discomfort can explain an approved recovery
decision. Forward the backend wording; do not add hormonal or medical inference.
Current deterministic text is Spanish. Null messages must stay null.

## Environment semantics

`WorkoutEnvironmentApiRequest` allows only `available_equipment` and
`training_location`, both optional/null. Location accepts `home`, `gym`,
`minimal_equipment`. Equipment is an array of `bodyweight`, `dumbbell`, `barbell`,
`kettlebell`, `resistance_band`, `cable`, `machine`.

| Input | Required preservation |
| --- | --- |
| Environment omitted/null | Unknown environment; preserve omission/null |
| Environment `{}` | Supplied object with unknown equipment/location |
| Equipment omitted/null in object | Unknown equipment; preserve any supplied location |
| `available_equipment: []` | Explicitly no equipment; keep the empty array |
| Nonempty equipment | Only the declared equipment |
| Location alone | Never derive equipment from location |

Do not collapse these cases with truthiness/defaulting, add bodyweight, or infer
home/gym equipment. Unknown and explicit empty equipment can both produce
incomplete selection but different reasons and text. An incomplete plan is a
valid HTTP 200 result, not a transport error or permission to invent exercises.

## Response contract and Base44 return policy

On success return HTTP 200 with the backend JSON object itself, without an
application-level `data`/`ok` wrapper or new fields. Any transport wrapper used
by the existing Base44 SDK is external to this JSON contract.

| Exact top-level property | Existing public model |
| --- | --- |
| `recommendation` | `TrainingRecommendationResponse` |
| `workout` | `WorkoutApiPayload` |
| `interpretation` | `InterpretationApiPayload` |
| `versions` | `InterpretationVersionsApiResponse` |

`recommendation` contains `action`, `recommended_session`, `intensity`,
`duration_minutes`, `reason_codes`, `needs_more_data`, `agent_version`.

`workout` contains `plan_status`, `selector_status`, `action`, `session_type`,
`intensity`, `duration_minutes`, `exercises`, `unresolved_slots`,
`generator_reason_codes`. Plan status is `generated`, `no_workout` or
`more_data_required`; selector status is `complete`, `incomplete`, `no_workout`
or `more_data_required`. Each exercise/unresolved slot has `sequence`,
`movement_pattern`, nullable `target_area`, `sets`, `rep_min`, `rep_max`,
`work_seconds`, `rest_seconds`, `effort_target`, and `notes` (string array).
Exercises additionally have `exercise_id`, `display_name`,
`selection_reason_codes`; unresolved slots additionally have `reason_codes`.
All fields and array ordering pass through unchanged.

The exact interpretation properties are:

| Properties | Type |
| --- | --- |
| `presenter` | `kai` or `kaia` |
| `tone` | `training`, `recovery`, `rest`, `incomplete` |
| `action` | `train`, `recovery`, `rest`, `request_more_data` |
| `session` | `upper_body`, `lower_body`, `full_body`, `cardio`, `mobility`, `rest`, `not_applicable` |
| `intensity` | `low`, `moderate`, `high`, `not_applicable` |
| `duration_minutes` | integer |
| `needs_more_data` | boolean |
| `title`, `summary`, `today_plan`, `avatar_message` | string |
| `reasons`, `reason_codes` | string array |
| `missing_data_message`, `environment_message`, `cycle_insight` | string or null |
| `interpretation_version` | `interpretation-core-v1` |

All listed response fields are present, including nullable values. `versions`
contains exactly `agent_version`, `generator_version`, `selector_version`,
`orchestrator_version`, `interpretation_version` (strings). The last is
`interpretation-core-v1` and matches the interpretation's version; the others
are backend-owned and must not be hardcoded in Base44.

Internal orchestration/selection models, `source_plan`, `source_slot` and Core
provenance fields are not exposed. Public workout/slot reason codes remain
public; do not strip them as if they were internal provenance.

## Error contract and timeout

The following is a **proposed future Base44 failure envelope**, not an existing
iBuum endpoint response or a new success field:

```json
{"error":{"code":"VALIDATION_ERROR","message":"Invalid training request.","retryable":false,"upstream_status":422}}
```

Every failure contains only `error`, with exactly `code` (string), `message`
(fixed safe string), `retryable` (boolean), `upstream_status` (integer or null).
No payload, stack trace, raw exception or raw validation `detail` is returned.
FastAPI validation details may contain submitted values: do not forward them.

| Condition | Bridge HTTP | Code | Safe message | Retryable | Upstream status |
| --- | --- | --- | --- | --- | --- |
| Base44 user unauthenticated | 401 | `UNAUTHENTICATED` | Authentication required. | false | null |
| Local structural validation | 422 | `VALIDATION_ERROR` | Invalid training request. | false | null |
| Missing/invalid server config | 500 | `CONFIGURATION_ERROR` | Training service is not configured. | false | null |
| Agent 401 | 401 | `UPSTREAM_AUTH_ERROR` | Training service authentication failed. | false | 401 |
| Agent 422 | 422 | `VALIDATION_ERROR` | Invalid training request. | false | 422 |
| Agent 5xx | Same upstream 5xx | `BACKEND_ERROR` | Training service temporarily unavailable. | true | Actual status |
| Deadline exceeded | 504 | `TIMEOUT` | Training service timed out. | true | null |
| Network failure | 502 | `NETWORK_ERROR` | Training service could not be reached. | true | null |
| Unexpected status, redirect or invalid success JSON/shape | 502 | `UPSTREAM_CONTRACT_ERROR` | Unexpected training service response. | false | Actual status |

An upstream 401 is a service-credential failure, not evidence that the user's
Base44 session expired. Preserve that distinction with the code. A valid
rest/recovery/incomplete result remains success. Never convert an error into
workout advice. Runtime mechanics must follow actual Base44 conventions, which
are not invented in this repository.

Use a **45-second server-side deadline**, including response-body reading,
with cancellation and cleanup according to the available runtime. Render cold
starts may exceed short timeouts. No automatic retries in phase 1; a retryable
failure permits a later user retry. Do not change Render settings.

## UI consumption

Future UI may use `recommendation` for high-level decision/status, `workout`
for concrete exercises and unresolved slots, and `interpretation.title`,
`summary`, `reasons`, `today_plan`, `avatar_message`, `environment_message`,
`missing_data_message`, `cycle_insight` for presentation. Hide nullable messages
when null; preserve text, ordering and uncertainty. Render text safely as text,
not executable HTML. Keep versions available for compatibility diagnostics.
Do not reinterpret reason codes into a competing decision. No frontend wiring
is authorized in the first implementation prompt.

## Existing Base44 functions and session relationship

`getTrainingRecommendation`, `getWorkout`, `workoutSession`, `generateKaiInsight`
and `generateKaiaInsight` are known external product context. Their source is
absent from this repository and their exact implementation is unknown here.
All five remain unchanged in phase 1; `getWorkoutInterpretation` is additive.

```text
getWorkoutInterpretation -> render approved workout + explanation
                        -> user starts workout
                        -> workoutSession -> execution / state / history
```

Interpretation is pre-session explanation; `workoutSession` remains the
execution/state owner. Do not replace it or start/persist a session in the bridge.
Keep `getWorkout` unchanged. After Base44 acceptance, product may retain it for
lightweight consumers, migrate training screens, or deprecate it if unused.
That choice is outside V1 scope.

`generateKaiInsight` / `generateKaiaInsight` may remain for conversational or
open-ended experiences. No replacement code change is proposed here. They must
not override approved training decisions or supply generative interpretation
where the deterministic API already provides the approved explanation.

## Rollout plan and acceptance criteria

1. Review this contract and the [single Base44 prompt](base44-get-workout-interpretation-prompt-v1.md).
2. In a later authorized Base44 task, inspect real auth/runtime conventions and
   existing server configuration, then add only `getWorkoutInterpretation`.
3. Run the six specified synthetic scenarios and auth/error/privacy checks in
   that prompt. Verify exact public success pass-through and environment cases.
4. Stop and report function/test results for human review; no frontend wiring.
5. Only after acceptance, separately authorize UI adoption and any legacy choice.

Acceptance requires explicit presenter, no inferred equipment, one authenticated
backend request, server-only secrets, 45-second deadline, unchanged decisions,
nulls and versions, safe distinct failures, unchanged existing functions, and no
LLM or duplicate training logic. Rest has no substitute workout; missing
environment remains a valid incomplete response. Tests must never use real
profiles or expose credentials.

The local [contract lock](../tests/test_base44_integration_contract.py) verifies
routes, method, header, runtime rejected authentication, request fields/model
reuse, presenter enums, environment preservation/strict extras, exact response
properties and hidden internal schemas. The existing endpoint suite retains
responsibility for decision parity and complete runtime behavior; the E2E suite
checks approved cross-component behavior. These tests do not call Base44.

## Known limitations

This repository cannot validate external Base44 auth, SDK wrappers, runtime
timeout limits, secret configuration, deployed connectivity or existing function
internals. No Base44 or Render calls/configuration changes occur in this task.
The failure envelope above is a future bridge decision, not a backend addition.
Backend domain validation remains authoritative. Interpretation V1 is Spanish,
deterministic and pre-session; it is not conversational AI, clinical analysis,
history persistence, progression or live coaching. Stop for review if actual
schemas/runtime constraints disagree; do not modify production to fit this doc.
