# Interpretation Core V1

MOTOR DECIDES.
INTERPRETATION EXPLAINS.

The internal, deterministic Spanish interpretation layer explains an already
approved workout. It does not evaluate a profile or make training decisions.

## Architecture and use

Training Rules → Engine → Generator → Selector → Orchestrator → Interpretation
Core → Kai / Kaia presentation → future UI.

```python
from app.services.workout_orchestrator import orchestrate_workout
from app.services.kai_presenter import present_kai
from app.services.kaia_presenter import present_kaia

approved = orchestrate_workout(request, environment)
kai = present_kai(request, approved, environment)
kaia = present_kaia(request, approved, environment)
```

The caller supplies the matching `TrainingRecommendationRequest`,
`WorkoutOrchestrationResult`, and optional `WorkoutEnvironmentContext` used for
that result. The core does not verify provenance by rerunning the engine.
Recommendation action, session, intensity, duration, uncertainty, and reason
codes are authoritative. The selected workout supplies exercise counts,
unresolved counts, generator codes, and per-slot selection codes. The environment
only explains declared or missing context; it never selects exercises.

No existing service imports this new capability. Public endpoints, DTOs, OpenAPI,
authentication, Base44, and deployment behavior remain unchanged. Future API/UI
adapters can call these pure functions; there is no FastAPI coupling.

## Output

`InterpretationResult` is a strict, frozen Pydantic model with extra fields
forbidden. All collections are tuples, including nested per-slot reason groups.
Its fields are:

- `presenter`: `kai` or `kaia`.
- `tone`: `training`, `recovery`, `rest`, or `incomplete`.
- Copied facts: `action`, `session`, `intensity`, `duration_minutes`, `needs_more_data`.
- Spanish `title`, `summary`, `reasons`, `today_plan`, `avatar_message`.
- Nullable `missing_data_message`, `environment_message`, `cycle_insight`.
- Original ordered `reason_codes`, `generator_reason_codes`,
  `selected_reason_codes`, and `unresolved_reason_codes`. Slot groups preserve
  their source order and repetitions.
- Stable `interpretation_version`: `interpretation-core-v1`.

Rest keeps the rest tone. Other results with requested data or incomplete
selection receive incomplete tone. This metadata never changes the copied
action; recovery with unresolved exercises can therefore have incomplete tone.

## Kai and Kaia

Both presenters use exactly the same general interpretation and facts. Kai has
no cycle insight. General reason translations can mention reported discomfort
without identifying it as cycle-specific. Kaia additionally describes provided
phase and discomfort, without attributing adaptation to phase alone.

Absent cycle context produces `null`. A known phase with explicitly reported
none or mild discomfort is only an observation, never a claim of reduced
capacity. An unknown phase remains unknown. The input model defaults omitted
discomfort to `none`; the core checks `model_fields_set` so it never presents
that default as a reported value. If the approved engine requests cycle data,
Kaia explains that uncertainty. Unknown phase alone does not create a new
request for information because the existing engine does not require that.

Moderate-discomfort wording describes applied limits only when the matching
reason code exists. High-discomfort recovery attribution requires both the
matching code and approved recovery action. High fatigue can terminate the
engine before cycle adaptation; Kaia then only reports supplied cycle context
and does not claim it caused the rest decision.

## Translation policy

The read-only translation table covers every current training and selection
enum member and all generator reason strings. Translations describe emitted
codes, never infer new ones. They do not promise complete physiological
recovery or assign a diagnosis. Repeated codes are translated once in first
occurrence order for readable reasons, while the machine fields retain all
original values and groupings.

Unknown future codes are preserved verbatim in their machine fields and receive
the neutral fallback: “El motor ha aplicado una condición adicional de
entrenamiento.” Raw unknown text is never inserted into user-facing prose.
Current upstream training enums reject unknown values at validation; tests use
an internal model copy to simulate future enum expansion without changing DTOs.

## Examples

| Approved scenario | Interpretation |
| --- | --- |
| Train / full body / high / 45 minutes | “Hoy toca cuerpo completo”; “45 minutos de cuerpo completo a intensidad alta.” |
| Recent full-body recovery / mobility / low / 20 minutes | “Hoy priorizamos recuperación”; emitted recovery restriction is explained. |
| Rest / zero minutes | “No hay una sesión activa programada para hoy.” No substitute workout. |
| Unknown recent session, more data requested | Explicit uncertainty; no claim about a good or insufficient recovery window. |
| Unknown environment | Missing location/equipment is identified from the supplied context and selector evidence. |
| Explicit empty equipment | Declared absence is acknowledged, never treated as unknown or implicit bodyweight. |
| Partial selection | Selected and pending counts are shown; no replacement is chosen. |
| Menstruation / no discomfort | Reported phase and absence of discomfort only; no reduction claim. |
| High discomfort / approved recovery | “Por las molestias reportadas, el motor ha indicado recuperación.” |

## Determinism and safety

No network, external APIs, generative AI, randomness, clock, mutable global state,
or new dependency is used. Repeated identical inputs yield identical serialized
outputs. Inputs, plans, prescriptions, order, equipment, and catalog remain
untouched. No coaching cues, exercises, alternatives, medical causality,
hormonal claims, injuries, treatment, or unsupported recovery states are added.

Tests exercise the real pipeline across training, goals, levels, fatigue,
recovery, equipment availability, phase/discomfort combinations, and uncertainty.
Additional tests cover frozen strict outputs, future codes, presenter parity,
determinism, mutation isolation, no policy calls, and public API boundaries.

## Known limitations

This is a finite Spanish template layer, not an LLM conversation system, voice
generation, long-term memory, progression analysis, performance trend analysis,
medical advice, clinical cycle modeling, nutrition interpretation, supplement
interpretation, form check, live coaching, history persistence, UI rendering,
or Base44 integration. It does not create a public endpoint.

The caller must supply a consistent approved bundle; arbitrary contradictory
or invalid pipeline results are outside V1's contract. The layer cannot identify
why a future unknown code was emitted. It does not invent absent provenance or
change engine contracts. Cycle causality is explained only from approved codes;
observed phase never establishes a training restriction.

## Validation record

Executed with the repository's `.venv/Scripts/python.exe` (Python 3.12.14;
`python` is not on this shell's PATH).

| Suite | Collected / passed | Failed | Warnings |
| --- | --- | --- | --- |
| Main baseline | 480 / 480 | 0 | 2 |
| Interpretation | 92 / 92 | 0 | 0 |
| E2E acceptance | 65 / 65 | 0 | 1 |
| Profile validation | 29 / 29 | 0 | 1 |
| Workout API | 62 / 62 | 0 | 1 |
| Workout orchestrator | 29 / 29 | 0 | 1 |
| Full suite, verbose and quiet | 572 / 572 | 0 | 2 |

`compileall app tests` and `git diff --check` passed. Existing production files
were not modified. One existing architecture test's allowlist was extended to
permit the new interpretation services to consume orchestration contracts; its
prohibition on direct selector access remains. The full suite initially caught
this outdated allowlist and passed after its update. The two full-suite warnings
are the existing Starlette/httpx deprecations.
