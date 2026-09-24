# Interpretation API V1

`POST /api/v1/interpretation` combines the approved workout and its deterministic
Kai or Kaia explanation in one authenticated response. Existing Workout API V1,
training recommendation and health contracts are unchanged.

MOTOR DECIDES.
INTERPRETATION EXPLAINS.
UI PRESENTS.

## Architecture

For an authenticated, valid request:

1. Validate the public DTO using the existing training and environment contracts.
2. Map the environment with `to_internal_environment()` from Workout API V1.
3. Execute `orchestrate_workout(training, environment)` **exactly once**.
4. Pass that result to the existing `to_workout_api_response()` mapper.
5. Pass the same result instance, training request and mapped environment to
   `present_kai()` or `present_kaia()`.
6. Combine the public workout values and an explicit interpretation projection.

There is no internal HTTP call to `/api/v1/workout`, no second engine execution,
and no reconstruction from public fields. The route selects only the explicitly
requested presenter. Neither route nor mapper implements training, cycle,
equipment-selection or medical policy.

## Authentication and errors

Send `X-API-Key` with the configured API key. The endpoint uses the existing
`verify_api_key` dependency. Missing, empty and incorrect keys return HTTP 401
with `{"detail":"Invalid or missing API key."}` and do not execute orchestration.
Never put a real key in source code or request examples committed to the repository.

Valid requests return HTTP 200, including rest, recovery, incomplete selection
and uncertainty results. Invalid presenter, invalid existing training/environment
values, extra top-level/environment fields and malformed JSON return HTTP 422.
Other HTTP methods return 405. Unexpected exceptions use the existing generic
HTTP 500 handler; no stack traces or configured secrets are returned.
As with the existing routes, malformed JSON can be rejected by FastAPI before
dependency evaluation; the single-orchestration guarantee concerns valid requests.

## Request contract

| Field | Contract |
| --- | --- |
| `presenter` | Required, exactly `kai` or `kaia`; case-sensitive |
| `training` | Required existing `TrainingRecommendationRequest` |
| `environment` | Optional/null existing `WorkoutEnvironmentApiRequest` |

The new request forbids extra top-level fields. The reused environment DTO also
forbids extra fields, including `environment.training_level`. Training validation
remains owned by `TrainingRecommendationRequest`, with its existing bounds,
enums, anonymous-ID guard and nested-field behavior. This endpoint introduces no
alternative age, sex, goal, fatigue, history or cycle fields.

Presenter is never inferred from sex, cycle context, name, goal or profile.
A male profile can explicitly choose Kaia; a female profile can choose Kai.

### Environment semantics

| Input | Meaning |
| --- | --- |
| Environment omitted or `null` | Environment unknown |
| `environment: {}` | Environment supplied with unknown equipment and location |
| Equipment omitted or `null` | Equipment unknown |
| `available_equipment: []` | Explicitly no equipment available |
| Populated equipment list | Exactly the declared equipment |
| Location alone | Does not imply any equipment |

Supported equipment is `bodyweight`, `dumbbell`, `barbell`, `kettlebell`,
`resistance_band`, `cable`, `machine`. Locations follow the existing public
environment DTO. Gym does not imply machines or weights; home does not imply
bodyweight. Bodyweight is never added automatically. Unknown context and explicit
empty equipment retain different unresolved reason codes and explanations.
Partial selection remains the selector's responsibility; interpretation never
chooses substitutes.

## Response contract

Successful top-level keys are **exactly**:

| Field | Content |
| --- | --- |
| `recommendation` | Existing public training recommendation |
| `workout` | Existing Workout API V1 payload, unchanged |
| `interpretation` | Explicit public interpretation below |
| `versions` | Five component version values |

For identical training and environment, `recommendation` and the entire `workout`
object equal `/api/v1/workout`, including status, action, session, intensity,
duration, exercises, unresolved slots and generator reason codes.

The public interpretation fields are:

| Fields | Type / meaning |
| --- | --- |
| `presenter` | `kai` or `kaia` |
| `tone` | `training`, `recovery`, `rest`, `incomplete` |
| `action`, `session`, `intensity` | Existing approved recommendation enums |
| `duration_minutes` | Approved integer duration |
| `needs_more_data` | Approved boolean uncertainty |
| `title`, `summary`, `today_plan`, `avatar_message` | Core text, copied verbatim |
| `reasons` | Ordered array of Core explanation strings |
| `missing_data_message`, `environment_message`, `cycle_insight` | Core string or `null` |
| `reason_codes` | Ordered recommendation reason codes |
| `interpretation_version` | `interpretation-core-v1`, from Core output |

New response DTOs forbid extra fields. Mapping builds independent mutable lists
and deep-copies the public recommendation/workout so consumers cannot mutate
upstream results. Wording, ordering, facts and uncertainty are never rewritten.

### Versioning and internal boundary

`versions` contains exactly `agent_version`, `generator_version`,
`selector_version`, `orchestrator_version`, `interpretation_version`. The first
four come from the existing workout mapping of the approved result. The last
comes from Interpretation Core, also preserved in the interpretation payload.

`InterpretationResult` is not an HTTP DTO. Its `generator_reason_codes`,
`selected_reason_codes` and `unresolved_reason_codes` provenance is excluded from
the interpretation object. Existing public workout generator/slot reason codes
remain available in the unchanged workout contract. Internal orchestration,
plan, slot and selector/environment context models, `source_plan` and
`source_slot` are absent from public payloads and OpenAPI endpoint schemas.

Public OpenAPI paths are exactly `/health`, `/api/v1/training/recommendation`,
`/api/v1/workout`, `/api/v1/interpretation`.

## Presenter and cycle semantics

Both presenters preserve the same approved decisions. Kai always returns
`cycle_insight: null`, even when supplied cycle context affects the engine result.
Kaia may explain only supplied cycle context through the existing Core logic;
without context her cycle insight is null.

Phase alone, including menstruation, does not imply lower capacity, reduced
intensity, rest or recovery. High reported discomfort can explain an approved
recovery decision; the explanation attributes adaptation to reported discomfort,
not merely menstruation. There is no hormonal inference or medical interpretation.

Rest retains zero duration, no exercises and no substitute workout. Unknown
history retains `needs_more_data` and `INSUFFICIENT_DATA`; the explanation does not
assert a recovery conflict or an adequate recovery window without the corresponding
engine reason. Incomplete environment/selection is explained without inventing
equipment or exercises. Core V1 currently supplies deterministic Spanish text.

## Examples

Send this JSON to `/api/v1/interpretation` with the `X-API-Key` header:

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

The result is HTTP 200: `recommendation.action = train`, workout generated with
complete selection and non-empty exercises, and interpretation facts
`presenter = kai`, `session = full_body`, `intensity = high`,
`duration_minutes = 45`, `cycle_insight = null`.

For Kaia, set `presenter` to `kaia`, `sex` to `female`, and add to `training`:

```json
"cycle_context": {"phase": "menstruation", "discomfort": "none"}
```

The decision remains equivalent to that profile without cycle context; the
cycle insight is `Fase menstrual indicada. Has indicado que no tienes molestias.`
Changing discomfort to `high` preserves the approved recovery/mobility/low
decision and its exact duration, with an explanation of reported discomfort.
Choosing Kai for the same input preserves that decision and returns null cycle insight.

Other variations on the first request:

- Set fatigue to `5`: rest, no workout, zero interpretation duration.
- Set `last_session_type: "full_body"` and `hours_since_last_session: 12`:
  recovery/mobility/low, at most 20 minutes, exactly matching the engine.
- Set `last_session_type: "unknown"` with those hours: uncertainty is preserved.
- Omit environment: incomplete selection, no exercises, unresolved slots retained.
- Set gym equipment to `[]`: explicit no-equipment explanation, no invented bodyweight.
- Set gym equipment to `["barbell"]`: existing partial selection is preserved.

## Validation and limitations

`tests/test_interpretation_endpoint.py` uses in-process FastAPI TestClient with
real authentication, validation, orchestration, engine, generator, selector,
catalog, Core, presenters and mappers. Pass-through instrumentation verifies
execution count, result identity and immutability; rejected-authentication tests
block orchestration. Tests cover endpoint/Core parity, determinism, request
isolation, safety, validation, public schemas and unchanged legacy contracts.
Automated acceptance makes no external service calls.

Interpretation API V1 is not an LLM endpoint, chat, voice synthesis, streaming,
long-term memory, performance trend analysis, workout history persistence,
progression engine, clinical cycle analysis, medical advice, nutrition,
supplementation, Form Check, live coaching, Base44 integration or frontend
rendering. Base44 integration remains a future phase after Render/API validation.
This change adds no dependencies and changes no deployment/runtime configuration.
