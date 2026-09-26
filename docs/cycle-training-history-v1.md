# Cycle Training History V1

Cycle Training History V1 records facts.
It does NOT decide training.
It does NOT infer menstrual phase.
It does NOT predict the cycle.
It does NOT compare performance across phases.
It does NOT interpret phase as reduced capacity.
It does NOT diagnose medical conditions.
Cycle Pattern Analyzer is a separate future block.

## Purpose and architecture

This internal pure builder pairs canonical training sessions with minimal explicit
cycle facts under Architecture Map section 17:

`Session Outcome -> Training History -> Cycle Training History V1 -> future Cycle Pattern Analyzer -> future personalized cycle context`

The map's `Cycle Context -> Cycle Training History -> Cycle Pattern Analyzer -> personalized cycle context`
invariant is preserved. The separate current-decision path remains unchanged:
`explicit current Cycle Context -> normalize_cycle_context -> Training Rules -> Training Engine`.
This block never imports or calls that normalization or those decision services.
No universal rule may assume menstrual phase alone implies reduced performance,
capacity or intensity.

## Exact input contract

`CycleTrainingHistoryInput` has exactly `training_history: TrainingHistory` and
`cycle_observations: list[CycleTrainingObservationInput]`. Actual canonical model
instances are required for the history and each observation; raw nested dictionaries
are rejected. The observation list may be empty. TrainingHistory is authoritative:
it is not rebuilt, modified, fetched or summarized again.

`CycleTrainingObservationInput` has exactly:

- `session_id`: string of length 1..128 identifying a canonical training session;
- `phase`: menstruation, follicular, ovulation, luteal or unknown;
- `discomfort`: none, mild, moderate, high or None (default None).

Observation session IDs must be unique and must occur in `training_history.sessions`.
No timestamps, separate dates, free text, symptom arrays or recommendations are
accepted. All six new models use `ConfigDict(extra="forbid")`.

No observation means `cycle_context=None`. An explicit unknown observation creates
a context whose phase is `unknown`. Missing discomfort remains None; explicit
`none` means reported absence. These states are never collapsed or inferred.

## Output and preserved facts

`CYCLE_TRAINING_HISTORY_VERSION = "cycle-training-history-v1"` is exposed by the
model module. `build_cycle_training_history(data: CycleTrainingHistoryInput) -> CycleTrainingHistory`
lives in `app/services/cycle_training_history.py`.

`CycleTrainingHistory` has exactly:

- `cycle_history_version`: Literal["cycle-training-history-v1"];
- `source_training_history_version`: Literal["training-history-v1"], copied from history_version;
- `sessions`: list[CycleTrainingSessionRecord];
- `summary`: CycleTrainingHistorySummary.

Each record has exactly `session: SessionOutcome` and
`cycle_context: CycleTrainingContextSnapshot | None`. Each context has exactly
`phase` and `discomfort`, with the observation types/default above.

Every canonical session appears once in the same TrainingHistory order, including
sessions without observations. This preserves the whole-history denominator.
Observation input order has no effect. There is no session-ID, phase or timestamp
sorting; started_at and ended_at may be None. Dates and spacing never infer phase.

Full SessionOutcome snapshots are deeply copied unchanged, including completion
state, session type, exercises, sets, duration, timestamps, feedback, session RPE,
fatigue_after and discomfort_after. These facts are not interpreted.
Cycle context discomfort and SessionFeedback.discomfort_after remain separate:
cycle `moderate` and session `none` both survive. Neither overwrites the other,
and no contradiction or medical meaning is inferred.

## Factual summary

Exactly these strict nonnegative integer fields are provided:

- total_sessions;
- sessions_with_cycle_context, sessions_without_cycle_context;
- menstruation_sessions, follicular_sessions, ovulation_sessions, luteal_sessions, unknown_phase_sessions;
- sessions_with_known_cycle_discomfort;
- cycle_discomfort_none_sessions, cycle_discomfort_mild_sessions, cycle_discomfort_moderate_sessions, cycle_discomfort_high_sessions.

The summary model validates four invariants:

1. with-context + without-context = total_sessions;
2. the five phase counts sum to sessions_with_cycle_context;
3. the four discomfort counts sum to sessions_with_known_cycle_discomfort;
4. sessions_with_known_cycle_discomfort <= sessions_with_cycle_context.

Empty history yields all zeros. Counts are inventory facts only. There are no
percentages, averages, ratios, scores, correlations, trends, patterns, adherence
analysis, phase-performance comparisons, fatigue/discomfort-by-phase analysis or
performance conclusions. There is no user-facing prose or training recommendation.

## Determinism, privacy and limitations

Equivalent validated inputs yield equal outputs. Output lists, canonical sessions
and nested exercises/sets/feedback are deeply detached; contexts are newly allocated.
The history, observations and input lists remain unchanged. Output edits cannot
affect input or later builds. No system clock, randomness, filesystem, network,
persistence, API, database, Base44, frontend, wearables, notifications or LLM is added.

V1 expects normally validated canonical objects. Bypassing validation with
model_construct or post-validation mutation is not an ingestion contract. Upstream
session facts are trusted; output models validate shape, summary validates count
invariants, and the builder owns cross-model derivation. Mutable output edits do not
recalculate summaries. Callers own observation accuracy and applicability.

Only minimal session-linked cycle context is collected. There is no detailed
menstrual calendar, unrelated period start/end dates, bleeding amount, fertility,
sexual activity, contraception, pregnancy status, temperature, ovulation tests,
hormone values, cycle length, predicted next period or free-text diary. No additional
identity/contact fields are introduced. There is no calendar inference, ovulation
estimation, fertile window, prediction, medical interpretation or diagnosis.

V1 performs no training adaptation, exercise selection, progression evaluation,
recovery evaluation or rescheduling. Future Cycle Pattern Analyzer V1 needs its own
approved contract before comparing evidence. Base44 live acceptance remains
paused/pending; frontend adoption remains pending.

## Exact files and validation

Exactly five files change:

- app/models/cycle_training_history.py
- app/services/cycle_training_history.py
- tests/test_cycle_training_history.py
- docs/cycle-training-history-v1.md
- docs/ibuum-fit-v2-current-status.md

Focused tests cover canonical inputs, explicit linkage, literal values, missing vs
unknown/none, order independence, complete snapshots, distinct discomfort facts,
exact counts/invariants, deterministic deep isolation, strict model fields/versions
and architecture import/call boundaries. Final Git inventory checks the exact five
files and unchanged protected files. Full regression runs once after focused tests.

```text
pytest -q tests/test_cycle_training_history.py
pytest -q
python -m compileall app tests
git diff --check
```
