# Progression Engine V1

Pure, deterministic exercise-level direction analysis in the canonical pipeline:

`Workout Execution -> Session Outcome -> Training History -> Progression Engine -> future Weekly Training State / Planner`

TrainingHistory is the source of truth. This engine analyzes facts without
rewriting them or changing existing Training Engine behavior.

## Contracts

`ProgressionInput` requires an actual canonical `TrainingHistory` instance and a
nonempty `exercise_id` of at most 128 characters. Dictionaries and raw outcome
lists are rejected. Both new models forbid extra fields. Identifiers remain
opaque and are not trimmed. Normally validated canonical history is expected;
post-validation mutations, inconsistent hand-built indexes, and `model_construct`
bypasses are not ingestion interfaces. Session references must resolve to the
canonical history sessions.

`evaluate_progression(data: ProgressionInput) -> ProgressionDecision` returns only:

- `engine_version`: `progression-engine-v1`, exposed as `PROGRESSION_ENGINE_VERSION`
  in `app/models/progression.py`;
- `exercise_id`;
- `decision`: PROGRESS, MAINTAIN, REDUCE, DELOAD or NEEDS_MORE_DATA;
- `reason_codes`: bounded `ProgressionReasonCode` values;
- `occurrences_considered`: strict nonnegative integer, at most three;
- `latest_session_id`: nullable string.

There is no prose, score, percentage, identity or persona in the output.

## Evidence

The last three occurrences in the exercise group form the recent window. Supplied
order is canonical; timestamps never reorder history. Repeated occurrences stay
distinct. Feedback is read from SessionOutcome by session ID.

Only the latest and immediately previous occurrences are compared. Completed sets
are matched by set_number; skipped and unmatched sets supply no comparison.
Known reps compare directly. Load compares only when both values and the same
unit are present. There is no kg/lb conversion; reps can still compare when load
units differ. Planned values, duration, distance and other metrics do not become
performance evidence.

Across all comparable reps/load signals, any positive with no negative means
IMPROVED; any negative with no positive means REGRESSED; both means MIXED; only
neutral evidence means STABLE. No comparable evidence means INSUFFICIENT.

Latest negative signals are incomplete execution (partial, skipped, not_started),
fatigue_after >= 4, discomfort_after moderate/high, known mean completed-set RIR
<= 1.0, and objective regression. Unknown RIR is excluded from the mean; zero is
known. No RPE is inferred. Null fatigue/discomfort stays unknown.

## Decision precedence

1. Absent exercise: NEEDS_MORE_DATA / EXERCISE_NOT_IN_HISTORY, zero occurrences,
   null latest session. A present but empty group instead has INSUFFICIENT_HISTORY.
2. Fewer than two occurrences: NEEDS_MORE_DATA / INSUFFICIENT_HISTORY.
3. DELOAD requires three occurrences, at least two unique sessions with fatigue
   >= 4 or moderate/high discomfort, and at least two occurrences with incomplete
   execution or known mean RIR <= 1.0. A session counts once even if both systemic
   signals exist or its exercise repeats. An occurrence counts once even if both
   execution and effort issues exist. Reasons are REPEATED_STRAIN and
   REPEATED_EXECUTION_OR_EFFORT_ISSUES.
4. REDUCE requires at least two distinct latest negative signals; all applicable
   negative reasons are returned in execution, fatigue, discomfort, effort,
   regression order. This and DELOAD take precedence over missing comparison data.
5. PROGRESS requires IMPROVED comparison, both occurrences completed, fatigue
   unknown or <= 3, discomfort unknown/none/mild, and mean RIR unavailable or > 1.
   Its reason is PERFORMANCE_IMPROVED.
6. INSUFFICIENT comparison: NEEDS_MORE_DATA /
   INSUFFICIENT_COMPARABLE_PERFORMANCE.
7. Otherwise MAINTAIN with PERFORMANCE_STABLE, PERFORMANCE_MIXED, or
   NO_STRONG_CHANGE_SIGNAL. The last reason covers isolated regression or blocked
   improvement. Reason lists describe the selected rule, not every observed fact.

**No single metric can automatically produce PROGRESS, REDUCE or DELOAD.**
Improvement must pass completion and recovery/strain gates. A single negative
signal cannot reduce. Deload requires repeated longitudinal evidence from both
systemic and execution/effort families.

## Limits and boundaries

V1 decides direction only. It prescribes no exact load, reps, sets, percentages or
substitutions. It calculates no 1RM, volume load, adherence, readiness, progression
score, personal records or plateaus. It makes no medical decisions, diagnoses or
menstrual inferences. Unknown remains unknown, and missing recovery observations
are permitted by the specified progress gates rather than imputed as good recovery.

The window is occurrence-based, not time-based; repeated occurrences in one session
can supply the two performance observations. Only systemic strain deduplicates
sessions. This bounded policy is not a long-term trend or personalized planner.

There is no filesystem, clock, randomness, environment, network, database, LLM,
API, persistence, Base44 adapter or frontend dependency in the engine. No route,
deployment or Current Status change is included. Future Weekly Training State and
Planner may consume these decisions under separate contracts; neither is built.

## Exact files and validation

Exactly four files are added:

- `app/models/progression.py`
- `app/services/progression_engine.py`
- `tests/test_progression_engine.py`
- `docs/progression-engine-v1.md`

Focused tests cover decision precedence, comparison and strain thresholds,
canonical-only contracts and exact enums, unknown/zero preservation, distinct
occurrences and session deduplication, bounded order, ignored plans/skipped and
unmatched sets, mixed units, determinism, nonmutation and pure import boundaries.
The final Git change inventory verifies protected files and API files unchanged;
the existing regression suite validates existing behavior.

```text
pytest -q tests/test_progression_engine.py
pytest -q
python -m compileall app tests
git diff --check
```
