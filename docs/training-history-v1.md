# Training History V1

Training History organizes canonical Session Outcome facts for a future
Progression Engine V1 consumer. It is a pure deterministic domain layer aligned
with the [architecture map](ibuum-fit-v2-architecture-map-v1.md).

```text
Workout execution -> Session Outcome V1 -> Training History V1 -> future Progression Engine V1
FACTS -> HISTORY -> FUTURE ANALYSIS
MOTOR DECIDES -> INTERPRETATION EXPLAINS -> UI PRESENTS
```

Training History V1 is NOT Session Outcome normalization.
Training History V1 is NOT Progression Engine.
Training History V1 does NOT calculate adherence.
Training History V1 does NOT calculate trends.
Training History V1 does NOT persist anything.
Training History V1 must not be reconstructed from chat transcripts.

## Input and source of truth

`TrainingHistoryInput.outcomes` is a required `list[SessionOutcome]`; it may be
empty. Only canonical `SessionOutcome` model objects from
`app.models.session_outcome` are accepted. Raw `SessionOutcomeInput`, dictionaries
(including serialized canonical outputs), transcripts, messages, prescriptions
and inferred behavior are not ingestion interfaces. A caller deserializing stored
canonical data must first validate it as `SessionOutcome`.

Duplicate `session_id` values fail validation, including distinct objects with
the same ID. Repeated exercise IDs are valid. All five new Pydantic models use
`ConfigDict(extra="forbid")`; unknown fields fail validation.

Session Outcome owns normalization, execution status, completed/skipped set
counts, session summary and completion state. History copies these facts without
re-deriving them or calling `build_session_outcome`. **PLAN != PERFORMANCE**:
planned fields remain historical context, never defaults for actual metrics or
evidence of completion. Matching planned and completed set counts changes nothing.

## Output contract

`build_training_history(data: TrainingHistoryInput) -> TrainingHistory` returns:

| Field | Type and meaning |
| --- | --- |
| `history_version` | `Literal["training-history-v1"]`, default from `TRAINING_HISTORY_VERSION` |
| `sessions` | `list[SessionOutcome]`, supplied order and all values preserved |
| `exercise_history` | `list[ExerciseHistory]`, first-appearance group order |
| `summary` | `TrainingHistorySummary`, factual counts only |

The version constant is exposed in `app.models.training_history`.
The caller/storage boundary supplies chronology. V1 never sorts IDs, exercise
sequences or timestamps. Null timestamps are valid; their chronological placement
cannot be inferred. Even decreasing timestamps leave supplied order unchanged.

### Summary

Every field is a strict integer >= 0; strings, booleans and floats are rejected.

| Fields | Definition |
| --- | --- |
| `total_sessions` | Number of outcomes |
| `completed_sessions`, `interrupted_sessions` | Counts of explicit terminal states |
| `total_exercises`, `completed_exercises`, `partial_exercises`, `skipped_exercises`, `not_started_exercises` | Sums of the corresponding canonical Session Outcome summary values |
| `completed_sets`, `skipped_sets` | Sums of canonical summary values, without scanning sets to recalculate them |
| `sessions_with_known_duration` | Count of non-null `actual_duration_seconds`, including zero |
| `known_duration_seconds` | Sum of non-null explicit durations; never inferred from timestamps |
| `sessions_with_feedback` | Count of non-null feedback objects, including an object with all fields null |

Empty history has empty collections and zero for every count.
No averages, percentages, adherence, completion rates, scores, volume-load,
estimated 1RM, personal records, comparisons, trends or recommendations exist.

### Exercise index

`ExerciseHistory` has exactly `exercise_id` (nonempty string, maximum 128
characters) and `occurrences: list[ExerciseHistoryOccurrence]`. There is no group
display name. Groups follow first appearance while scanning sessions in supplied
order and each session's exercises in their existing order, without sorting.

Each occurrence has exactly:

- `session_id`: nonempty string, maximum 128 characters;
- `session_completion_state`: `completed` or `interrupted`;
- `session_started_at`, `session_ended_at`: nullable timezone-aware datetimes;
- `source_action`: nullable `train` or `recovery`;
- `session_type`: nullable `upper_body`, `lower_body`, `full_body`, `cardio` or `mobility`;
- `exercise`: canonical `ExerciseOutcome` snapshot.

Occurrences follow the same session-then-exercise scan order. The same ID across
sessions, or repeated at different sequences within one session, creates separate
occurrences in one group. Sets are never merged or occurrences deduplicated.

## Snapshot and value guarantees

Every session value and nested exercise value is preserved, including version,
source/execution status, names, movement patterns, planned context, actual sets,
set order, metrics, feedback and nulls. Renamed exercises retain each historical
name; new metadata never rewrites old snapshots.

Null means unknown/not captured. Valid zero means explicit zero: reps, RIR, rest
and session duration remain zero. Missing actual values stay missing regardless
of planned values. `50 kg` and `110 lb` remain separate recorded values, without
conversion, comparison or summed loads. General reported `discomfort_after` is
retained only as an existing fact; no cycle phase, day or pattern is inferred.

The builder deep-copies sessions and occurrence exercises. No mutable output
model/list aliases input models/lists; occurrence exercises are also independent
of the output session exercises. Input is never mutated. These are detached
snapshots, not frozen Pydantic models: callers can edit outputs, but derived
collections will not automatically resynchronize after such edits.

## Boundaries and limitations

The same validated input produces the same output. No clock, randomness,
filesystem, environment, network, database or external state is consulted.
The builder expects normally validated input; `model_construct` and mutations
after validation are not ingestion interfaces. Canonical summary values are
trusted, even for directly constructed Session Outcome outputs; History does not
repair or verify normalization by recomputing those values.

There is no identity/persona: no user ID, account ID, email, profile, presenter,
Kai or Kaia fields. Ownership/authentication belongs to future integration and
storage boundaries. Exercise display names are historical exercise metadata.

No progression, scoring, cycle analysis, weekly state, planning, interpretation,
user-facing prose or LLM is implemented. There is no API, persistence/storage
adapter, Base44 integration, frontend, Render change or deployment. Session
Outcome and existing endpoints remain unchanged. Base44 runtime acceptance
remains paused; the canonical Current Status document is not refreshed here.

Future Progression Engine V1 may consume this evidence under a separately
approved analysis contract and explicit mixed-unit policy. History itself only
organizes facts and cannot determine what should happen next.

## Tests and exact changed files

Focused tests cover empty/completed/interrupted histories; canonical-only input;
duplicate IDs; exact contracts and strict counts; canonical summary authority;
ordering with reversed/null timestamps; repeated exercise occurrences; historical
metadata and mixed units; null/zero/feedback presence; deterministic output;
recursive mutable-reference isolation; and import/route boundaries. Full existing
regression tests cover unchanged endpoint behavior.

```text
pytest -q tests/test_training_history.py
pytest -q
python -m compileall app tests
git diff --check
```

Existing CI uses pytest and compile checks; no static tooling or dependencies are
added. Exactly these files are added:

- `app/models/training_history.py`
- `app/services/training_history.py`
- `tests/test_training_history.py`
- `docs/training-history-v1.md`
