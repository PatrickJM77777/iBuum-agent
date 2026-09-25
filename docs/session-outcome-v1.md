# Session Outcome V1

Session Outcome is the canonical structured description of explicit facts from a
finished or interrupted workout. It is a pure domain layer consistent with the
[architecture map](ibuum-fit-v2-architecture-map-v1.md) and
[development workflow](codex-development-workflow-v1.md).

```text
Workout execution facts -> Session Outcome V1
                        -> future Training History V1
                        -> future Progression Engine V1
```

**MOTOR DECIDES -> INTERPRETATION EXPLAINS -> UI PRESENTS** remains unchanged.
**PLAN != PERFORMANCE**: planned values are historical context, never defaults
for actual values. Ten planned reps and missing actual reps produce `reps: null`.

Session Outcome V1 is NOT Training History.
Session Outcome V1 is NOT Progression Engine.
Session Outcome V1 does NOT persist anything.

## Contract

Models live in `app/models/session_outcome.py`. Every model uses
`ConfigDict(extra="forbid")`, including output models; unknown fields fail
validation. Optional fields default to null. Integer metrics are strict integers
(booleans, numeric strings and fractional values are rejected). Numeric metrics
accept finite integers/floats, not strings or booleans. Datetimes may be supplied
as timezone-aware datetime objects or timezone-bearing ISO strings; naive values
are rejected. Identifiers are opaque strings and are preserved without trimming.

### SessionOutcomeInput

| Field | Contract |
| --- | --- |
| `session_id` | Required nonempty string, maximum 128 characters |
| `completion_state` | Required `completed` or `interrupted` |
| `exercises` | Required list of `ExerciseExecutionInput`; may be empty; order preserved |
| `plan_id` | Nullable string, maximum 128 characters |
| `source_action` | Nullable `train` or `recovery`; no `rest` or `request_more_data` |
| `session_type` | Nullable `upper_body`, `lower_body`, `full_body`, `cardio`, `mobility` |
| `started_at`, `ended_at` | Nullable timezone-aware datetimes |
| `actual_duration_seconds` | Nullable integer >= 0, explicitly supplied only |
| `feedback` | Nullable `SessionFeedback` |

When both timestamps exist, `ended_at >= started_at` by instant, including
different UTC offsets. Actual duration is never calculated from timestamps.
Session type is never inferred from names or selected exercises. Exercise
sequences must be unique within the session; repeated exercise IDs are allowed.

### SessionFeedback

All fields are optional and nullable: `session_rpe` is a number in 1..10,
`fatigue_after` an integer in 1..5, and `discomfort_after` one of `none`, `mild`,
`moderate`, `high`. These are user-reported facts only. None is inferred from
another field, effort, duration, RIR, cycle context or performance. `none` is an
explicit report and differs from null. No free-text health notes or medical
interpretation are supported.

### ExerciseExecutionInput

| Field | Contract |
| --- | --- |
| `sequence` | Required integer >= 1; unique within session |
| `exercise_id` | Required nonempty string, maximum 128 characters |
| `source_status` | Required `pending`, `in_progress`, `completed`, `skipped` |
| `sets` | Required list of `SetExecutionInput`; may be empty; order preserved |
| `display_name` | Nullable string, maximum 160 characters |
| `movement_pattern` | Nullable string, maximum 80 characters |
| `planned_sets` | Nullable integer >= 1 |
| `planned_rep_min`, `planned_rep_max` | Nullable integers >= 0; both present or both null; min <= max |
| `planned_target_rir` | Nullable number in 0..10 |
| `planned_rest_seconds` | Nullable integer >= 0 |

All `planned_*` fields are historical context. They never fill actual set
metrics, determine exercise completion or change the prescription.

### SetExecutionInput

| Field | Contract |
| --- | --- |
| `set_number` | Required integer >= 1; unique within its exercise |
| `status` | Required `completed` or `skipped` |
| `reps` | Nullable integer >= 0 |
| `load_value` | Nullable number > 0 and <= 1000 |
| `load_unit` | Nullable `kg` or `lb` |
| `duration_seconds` | Nullable integer > 0 and <= 36000 |
| `distance_meters` | Nullable finite number > 0 |
| `rir` | Nullable number in 0..10 |
| `actual_rest_seconds` | Nullable integer >= 0 |
| `recorded_at` | Nullable timezone-aware datetime |

Load value/unit must both be present or both null. No unit is assumed or
converted. Skipped sets must have all performance fields null, including actual
rest; `recorded_at` may exist. Completed sets may have every metric null: explicit
completion is valid even when detailed performance was not captured.

### Output

`SESSION_OUTCOME_VERSION = "session-outcome-v1"` is exposed by the model module.
`SessionOutcome.outcome_version` is `Literal["session-outcome-v1"]` with that default.
`SessionOutcome` preserves `session_id`, `plan_id`, `source_action`, `session_type`,
`completion_state`, `started_at`, `ended_at`, `actual_duration_seconds`, `feedback`;
it contains ordered `exercises: list[ExerciseOutcome]` and `summary`.

`ExerciseOutcome` preserves every exercise input field and its ordered sets. It
adds `execution_status` (`completed`, `partial`, `skipped`, `not_started`),
`completed_sets` and `skipped_sets` (integers >= 0).

`SessionOutcomeSummary` has exactly seven nonnegative integer fields:
`total_exercises`, `completed_exercises`, `partial_exercises`, `skipped_exercises`,
`not_started_exercises`, `completed_sets`, `skipped_sets`.
These are descriptive counts only. There are no adherence percentages, volume
loads, ratings, readiness, fatigue or progression scores.

## Explicit completion semantics

| Source status | Completed set entries | Execution status |
| --- | --- | --- |
| `completed` | Any, including zero | `completed` |
| `in_progress` | Any, including zero | `partial` |
| `skipped` | > 0 | `partial` |
| `skipped` | 0 | `skipped` |
| `pending` | > 0 | `partial` |
| `pending` | 0 | `not_started` |

Completed-set evidence protects performed work when source status is stale or
the rest of the exercise was skipped. Matching or exceeding planned set counts
never upgrades an exercise to completed. Only explicit source completion does.

Session terminal state is independent of exercise state. A completed session may
contain partial, skipped and not-started exercises. An interrupted session may
contain completed work or no performed work. Neither is silently rewritten.

## Builder and unknown facts

`app/services/session_outcome.py` exposes
`build_session_outcome(data: SessionOutcomeInput) -> SessionOutcome`.
It derives exercise states, counts set/exercise entries and builds a new outcome.
Input is not mutated, and nested output objects do not alias input objects.
The builder expects normally validated input; bypasses such as Pydantic
`model_construct` or post-validation mutation are not ingestion interfaces.
The builder is the normalization entry point; direct output-model construction
validates field shapes and inherited fact invariants, not recomputed summaries.

The same validated input produces the same output. No clock reads, randomness,
network, external state, storage or engine calls exist. Lists are not sorted.
Null remains unknown, and valid zero values (reps, RIR, rest and actual session
duration) remain zero. No completion or performance measurements are invented.

## Boundaries and limitations

Ownership/authenticated user binding belong to future persistence/integration.
There are no user IDs, email, profile/persona or presenter fields. Kai and Kaia
are not separate sports engines. Display names describe exercises only.
No cycle phase or menstrual inference exists; general explicitly reported
post-session discomfort is supported without diagnosis or cycle analysis.

There is no progression, recommendation, load adjustment, deload, recovery
assessment, interpretation, coaching prose or LLM call. No API route, database,
Base44 entity/adapter, frontend change, dependency, deployment or Render change
is included. No Training Engine, Training Rules, Workout Generator, Workout
Orchestrator or Interpretation Core imports are introduced.

Explicit source facts are trusted after validation: an exercise can be completed
without logs, and omitted metrics remain unavailable for future analysis.
No cross-session deduplication, unit conversion, history aggregation or ownership
verification is provided. The next expected consumer is **Training History V1**,
which will consume these facts without reconstructing them from chat or plans.

## Future Base44 mapping (documentation only)

Future integration may map `WorkoutSession.status` `completed` to
`completion_state="completed"` and `abandoned` to `completion_state="interrupted"`.
Exercise statuses in `planned_snapshot` (`pending`, `in_progress`, `completed`,
`skipped`) map to `source_status`. Factual `WorkoutSetLog` fields can map to
`SetExecutionInput`, subject to this contract, without planned-value fallbacks.
No adapter is implemented here. Live bridge acceptance remains paused pending
Base44 credits, as explicitly authorized by the task's sequencing decision.

## Tests and exact changed files

Focused tests cover the terminal/source-state matrix, stale status evidence,
planned-count independence, exact metrics/counts, order, zero/null preservation,
feedback, timestamp awareness/order, field bounds, unknown-field rejection on all
models, uniqueness, paired fields, skipped metrics, determinism, input isolation,
and dependency/route boundaries. Existing endpoint tests run in full regression.

```text
pytest -q tests/test_session_outcome.py
pytest -q
python -m compileall app tests
git diff --check
```

The existing CI establishes compile and pytest checks; no additional static tool
is configured or introduced.

Exactly four files are added:

- `app/models/session_outcome.py`
- `app/services/session_outcome.py`
- `tests/test_session_outcome.py`
- `docs/session-outcome-v1.md`
