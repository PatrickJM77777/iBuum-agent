# Ready-to-paste Base44 prompt V1

Implement the following additive integration in the existing Base44 product.
This entire document is one prompt. Create exactly one new server-side function
named `getWorkoutInterpretation`, then test it and stop for human review.
Do not wire or change frontend/UI.

## Scope and existing context

The iBuum Agent already exposes the approved deterministic
`POST /api/v1/interpretation` endpoint. It returns recommendation, workout,
interpretation and versions in a single response.

MOTOR DECIDES. INTERPRETATION EXPLAINS. UI PRESENTS.

The Training Engine / Orchestrator decides the workout; Interpretation Core
explains it; the explicit Kai/Kaia presenter supplies presentation context;
the future UI renders it. This function is only an authenticated bridge.

Keep `getTrainingRecommendation`, `getWorkout`, `workoutSession`,
`generateKaiInsight` and `generateKaiaInsight` unchanged. Their code was not
available to the repository task that prepared this prompt; no implementation
assumptions about them are authoritative. Inspect existing Base44 server-side
auth and runtime conventions before implementing. Use actual supported APIs;
do not invent an SDK call, auth mechanism or runtime capability. If required
conventions/configuration are unavailable or conflict with this contract, stop
and report the concrete blocker rather than guessing.

Do not modify existing functions. Reuse an existing shared utility without
editing it where possible; if shared utility reuse explicitly requires changes
to existing code, stop and describe the exact minimal change for separate review.
Do not create another function, backend endpoint, frontend component, data model,
LLM call, interpretation engine or training policy. Do not change Render, backend
code, deployment configuration or existing function behavior.

## Authentication and server configuration

Authenticate the current Base44 user using existing server-side conventions
before calling iBuum Agent. Unauthenticated calls must make no upstream request.
Never trust caller-supplied identity as authentication. Do not enrich the request
with PII. If using optional `training.user_id`, bind it to an existing anonymous
identifier for the authenticated user under established product policy; otherwise
omit it. It is not an authentication credential.

Read the existing `IBUUM_AGENT_URL` server-side configuration and existing
`IBUUM_API_KEY` server-side secret. Do not create placeholder credentials or
hardcode real secrets. Missing configuration must produce the safe configuration
error below. Never accept endpoint URL, secret or outbound headers from clients.
Require the configured trusted HTTPS origin and append `/api/v1/interpretation`
without a duplicate slash. Reject redirects rather than forwarding the key to
another destination.

Make one request:

```text
POST ${IBUUM_AGENT_URL}/api/v1/interpretation
Content-Type: application/json
X-API-Key: ${IBUUM_API_KEY}
```

Use a 45-second server-side deadline covering fetch and body reading, with
supported cancellation and cleanup. Render cold starts can exceed shorter
timeouts. Do not change Render or add automatic retries. Do not call
`/api/v1/workout` or `/api/v1/training/recommendation` to reconstruct the result.

## Input validation and sanitization

Accept only this JSON body structure:

```text
{
  "presenter": "kai" | "kaia",
  "training": TrainingRecommendationRequest,
  "environment": WorkoutEnvironmentApiRequest | null
}
```

Require a JSON object with explicit `presenter` and `training`. Reject unknown
outer and environment properties with the validation error below. Validate
structure and types without coercing strings, defaulting missing facts, dropping
nulls/empty arrays, or altering the requested presenter. Forward only supported
training/cycle fields; do not send profile objects, email, name or other PII.
Let Render remain the authoritative domain validator; do not implement decision
rules under the guise of validation. Backend 422 must remain a validation error.

Current training fields and valid values:

| Field | Contract |
| --- | --- |
| `age` | Required integer, 10..100 |
| `sex` | Required `male` or `female` |
| `height_cm` | Required number >0 and <=300 |
| `weight_kg` | Required number >0 and <=400 |
| `goal` | Required `general_fitness`, `fat_loss`, `muscle_gain`, `strength`, `endurance`, `mobility` |
| `training_level` | Required `beginner`, `intermediate`, `advanced` |
| `training_days_per_week` | Required integer 1..7 |
| `fatigue_level` | Required integer 1..5 |
| `user_id` | Optional/null anonymous string, at most 128 characters and no `@`; subject to authenticated identity policy above |
| `last_session_type` | Optional/null `upper_body`, `lower_body`, `full_body`, `cardio`, `mobility`, `rest`, `unknown` |
| `hours_since_last_session` | Optional/null integer >=0 |
| `cycle_context` | Optional/null object with required `phase` and optional `discomfort` |

Cycle phase values: `menstruation`, `follicular`, `ovulation`, `luteal`, `unknown`.
Discomfort values: `none`, `mild`, `moderate`, `high`. The backend defaults omitted
discomfort to `none`; the bridge need not insert it. Forward only these two
cycle fields. The backend currently ignores nested training/cycle extras, while
forbidding outer/environment extras; the bridge allowlist minimizes data without
claiming a stricter nested backend schema.

Presenter is exactly lowercase `kai` or `kaia`, chosen by product/UI state.
Never infer it from sex, cycle_context, profile, goal or name. Do not normalize
`Kai` to `kai`; reject unsupported values. Either presenter is valid with either
supported sex.

The environment object allows only:

- `available_equipment`: optional/null array containing only `bodyweight`,
  `dumbbell`, `barbell`, `kettlebell`, `resistance_band`, `cable`, `machine`.
- `training_location`: optional/null `home`, `gym`, `minimal_equipment`.

Preserve the distinction among omitted/null environment, an environment object
with omitted/null equipment, and `available_equipment: []`. Preserve `{}` and
any supplied location. Empty equipment means explicitly no equipment; null means
unknown. Never infer bodyweight, add equipment, derive equipment from location,
or replace empty/null values through truthiness defaults.

## Success and interpretation boundary

For a valid HTTP 200 upstream response, return HTTP 200 and the public backend
JSON itself, faithfully, with exactly these top-level keys:

```text
{
  "recommendation": ...,
  "workout": ...,
  "interpretation": ...,
  "versions": ...
}
```

Do not add an application-level `data` or `ok` wrapper. A standard Base44 SDK
transport wrapper is separate; report its actual behavior without changing the
JSON result contract. Validate the success envelope sufficiently to reject
malformed/non-JSON responses safely; do not rebuild the decision objects.

`recommendation` fields: `action`, `recommended_session`, `intensity`,
`duration_minutes`, `reason_codes`, `needs_more_data`, `agent_version`.

`workout` fields: `plan_status`, `selector_status`, `action`, `session_type`,
`intensity`, `duration_minutes`, `exercises`, `unresolved_slots`,
`generator_reason_codes`. Pass through complete nested exercise/slot objects.
Shared slot fields are `sequence`, `movement_pattern`, `target_area`, `sets`,
`rep_min`, `rep_max`, `work_seconds`, `rest_seconds`, `effort_target`, `notes`.
Exercises also contain `exercise_id`, `display_name`, `selection_reason_codes`;
unresolved slots also contain `reason_codes`. Do not filter public reason codes.

`interpretation` fields are exactly:
`presenter`, `tone`, `action`, `session`, `intensity`, `duration_minutes`,
`needs_more_data`, `title`, `summary`, `reasons`, `today_plan`, `avatar_message`,
`missing_data_message`, `environment_message`, `cycle_insight`, `reason_codes`,
`interpretation_version`.

`versions` fields are exactly: `agent_version`, `generator_version`,
`selector_version`, `orchestrator_version`, `interpretation_version`.
Interpretation version is currently `interpretation-core-v1` in both places;
do not generate version values. No `source_plan`, `source_slot` or internal
orchestration models belong in the public response.

Keep all text, values, ordering, uncertainty and nulls intact. Action, session,
intensity, duration, reason codes, workout selection and interpretation text are
authoritative from Render. Do not re-evaluate fatigue, cycle phase/discomfort,
recovery, level, goal, equipment or history. Do not create a second interpretation
model or call generative AI for training interpretation.

Kai returns null cycle insight even when the training request includes cycle
context. Kaia can explain supplied context. Menstruation alone must not become
a new restriction; high reported discomfort may explain the backend's recovery
decision. Forward deterministic Spanish wording without rewriting or medical
inference. Rest, recovery and incomplete selection are valid successes, not
failures or requests for a substitute plan.

Future UI can use recommendation for status, workout for exercises, and
interpretation text for presentation. It must not derive competing decisions
from reason codes. No UI work in this task. `workoutSession` still owns execution,
state and history after the user starts a workout; this function is pre-session
only and must not start or persist sessions. `generateKaiInsight` and
`generateKaiaInsight` may remain for conversation/open-ended experiences but must
not override deterministic training decisions. Keep `getWorkout` unchanged;
future migration/deprecation is outside this task.

## Safe errors and privacy

Use this bridge-only failure envelope with exactly these fields:

```json
{"error":{"code":"VALIDATION_ERROR","message":"Invalid training request.","retryable":false,"upstream_status":422}}
```

This is not a new backend response model. `upstream_status` is an integer or
null. Apply the following mapping using real Base44 response conventions:

| Condition | HTTP | Code | Fixed message | Retryable | Upstream status |
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

Distinguish upstream service authentication failure from Base44 login failure.
Never transform failures into success or invented advice. Never return raw
upstream bodies, FastAPI validation details (which may echo submitted input),
exceptions, stack traces, headers or secrets. Do not expose `IBUUM_API_KEY` to
frontend, browser, console, logs, JSON, error messages or test reports. Do not
log whole training payloads, cycle context, profiles or raw response/error bodies.
No PII enrichment or sensitive telemetry; any future telemetry design needs
explicit security review. Minimal technical status/timing metadata is enough.

## Required tests and final report

Use synthetic data only, authenticated test users under existing Base44 test
conventions, and the existing server secret without printing it. Start with:

```json
{
  "presenter": "kai",
  "training": {
    "age": 30,
    "sex": "male",
    "height_cm": 178,
    "weight_kg": 80,
    "goal": "strength",
    "training_level": "intermediate",
    "training_days_per_week": 4,
    "fatigue_level": 1
  },
  "environment": {
    "training_location": "gym",
    "available_equipment": [
      "bodyweight", "dumbbell", "barbell", "kettlebell",
      "resistance_band", "cable", "machine"
    ]
  }
}
```

For each scenario start from a fresh copy; do not accumulate overrides:

1. Kai normal: base payload. Expect train/full_body/high/45 minutes, generated
   complete workout, nonempty exercises and null cycle insight.
2. Kaia menstruation/no discomfort: set presenter `kaia`, sex `female`, add
   `cycle_context: {"phase":"menstruation","discomfort":"none"}`. Expect
   unchanged train/full_body/high/45 decision and a nonempty cycle insight;
   no phase-only reduction. Compare with the same profile without cycle context.
3. Kaia high discomfort: same as case 2 with discomfort `high`. Expect
   recovery/mobility/low and `CYCLE_HIGH_DISCOMFORT`; preserve exact backend
   duration and text attributing adaptation to discomfort.
4. Rest: base with fatigue `5`. Expect rest, zero duration, `no_workout` plan
   and selector status, no exercises or unresolved slots, no substitute plan.
5. Recovery: base with `last_session_type: "full_body"` and
   `hours_since_last_session: 12`. Expect recovery/mobility/low with approved
   duration greater than zero and at most 20 minutes.
6. Missing environment: omit environment from base; repeat with null. Expect
   equal backend results, HTTP 200, train decision, incomplete selection,
   no exercises, unresolved slots and a nonempty environment message.

Verify every success preserves the entire backend JSON, all four top-level
objects, exact interpretation/version properties and nullable messages. Verify
each allowed invocation sends one request with the required auth header and
45-second deadline. Test explicit presenter independently of sex and reject
missing/invalid presenter and unknown outer/environment fields.

Also test omitted equipment, null equipment and `[]` with supplied location;
the forwarded representations must remain distinct, with no inferred bodyweight
or location-derived equipment. For the normal gym fixture, `[]` must stay an
incomplete plan with no exercises and `EQUIPMENT_NOT_AVAILABLE` on unresolved
slots, different from the missing-equipment explanation.

Test unauthenticated Base44 access (no upstream request), local validation,
missing configuration, upstream 401 and 422, 5xx, timeout, network failure,
redirect and invalid success data. Use the existing test framework and mocked
outbound transport for fault injection; do not change production secrets or
cause a real outage. Verify safe envelopes and no secret/profile/cycle leakage
in logs or results. If tests cannot run, report them as unverified, not passed.

Stop after function creation and tests. Report the new function, files changed,
auth convention used, timeout handling, each scenario/error test result and
limitations without payloads or credentials. Confirm all five existing functions
and frontend/UI are unchanged, no duplicate interpretation or LLM exists, and
no backend/Render changes occurred. Do not proceed to frontend wiring,
session changes, legacy deprecation or any further rollout. Wait for human review.
