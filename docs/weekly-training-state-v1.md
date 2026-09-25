# Weekly Training State V1

Weekly Training State is a pure, deterministic internal domain aggregate of an
explicit weekly schedule and canonical Training History facts. It follows the
[Architecture Map](ibuum-fit-v2-architecture-map-v1.md) and
[Codex workflow](codex-development-workflow-v1.md).

```text
Workout Execution -> Session Outcome V1 -> Training History V1
 -> Progression Engine V1 -> Weekly Training State V1 -> future Program Planner V1
FACTS -> WEEKLY AGGREGATE -> FUTURE PLANNING
MOTOR DECIDES -> INTERPRETATION EXPLAINS -> UI PRESENTS
```

This architectural sequence does not introduce a dependency on Progression Engine:
the future Program Planner can consume progression decisions and weekly facts as
separate authoritative inputs.

**Weekly Training State V1 is NOT Weekly Review.** Weekly Review is a future
user-facing explanation; this aggregate contains only structured facts.
**Weekly Training State V1 does NOT decide what next week's program should be.**
**Weekly Training State V1 does NOT classify a due unresolved session as failure.**

## Input and explicit scope

`WeeklyTrainingStateInput` has exactly `history`, `week_start`, `as_of_date`,
`planned_sessions`, and `included_session_ids`. `history` must be an actual
canonical `TrainingHistory` instance; dictionaries and raw outcome lists are
rejected. Both input lists may be empty.

The week contains seven calendar dates, from caller-selected `week_start` through
`week_start + 6 days`, inclusive. Monday is not required. `as_of_date` and all
planned dates must be inside this window. The anchor must permit a representable
seven-day date window.

`included_session_ids: list[str]` defines actual weekly membership. IDs must be
unique and resolve to `history.sessions`. Timestamps do not define membership:
they may be null, timezone policy is not a storage contract, and history order is
already canonical. The service never reads timestamps or a system clock. It scans
history in supplied order, ignoring the input ID list's order. Only included
sessions contribute workload and recovery, including explicitly scoped sessions
whose timestamps fall outside the date window.

Each `WeeklyPlannedSessionInput` contains:

| Field | Contract |
| --- | --- |
| `slot_id` | Unique nonempty string, maximum 128 characters |
| `scheduled_date` | Date inside the explicit week |
| `session_type` | Nullable `upper_body`, `lower_body`, `full_body`, `cardio`, `mobility` |
| `linked_session_id` | Nullable nonempty string, maximum 128 characters |

Each linked ID must exist in history and in the explicit included IDs. One actual
session may link to at most one slot. Identifiers remain opaque, without trimming.
No matching is inferred from date or session type.

All eight new models use `ConfigDict(extra="forbid")`. Counts are strict integers
>= 0, rejecting booleans, numeric strings and floats. Feedback latest values retain
canonical bounds: fatigue 1..5, RPE 1..10, discomfort none/mild/moderate/high.

## Output contract

`build_weekly_training_state(data: WeeklyTrainingStateInput) -> WeeklyTrainingState`
is exposed in `app/services/weekly_training_state.py`. Its exact output fields are:

- `state_version`: `Literal["weekly-training-state-v1"]`, defaulting to the model
  module's `WEEKLY_TRAINING_STATE_VERSION` constant;
- `week_start`, derived `week_end`, `as_of_date`;
- `planned_sessions: list[WeeklyPlannedSessionState]` in supplied plan order;
- `included_session_ids`, `unplanned_session_ids` in canonical history order;
- `plan_summary: WeeklyPlanSummary`;
- `workload: WeeklyWorkloadFacts`;
- `recovery: WeeklyRecoveryFacts`;
- `adherence: WeeklyAdherenceFacts`.

Each planned output retains the four input fields and adds `status` and `is_due`.
A linked completed outcome produces `completed`; a linked interrupted outcome
produces `partial`; no link produces `remaining`. `is_due` means
`scheduled_date <= as_of_date`. A future slot completed early remains completed
but does not enter the due denominator. Due unresolved slots stay remaining:
there is no missed, failed or noncompliant state. Future planning/rescheduling
owns any decisions about unresolved work.

`WeeklyPlanSummary` derives only from planned states: `total_planned_sessions`,
`completed_planned_sessions`, `partial_planned_sessions`,
`remaining_planned_sessions`, `due_remaining_planned_sessions`, and
`future_remaining_planned_sessions`.

An included session with no planned link is unplanned for this aggregate. It is
factual execution, with no penalty or implication that it was wrong.

## Workload and duration

`WeeklyWorkloadFacts` contains `total_sessions`, `completed_sessions`,
`interrupted_sessions`, `unplanned_sessions`, `total_exercises`,
`completed_exercises`, `partial_exercises`, `skipped_exercises`,
`not_started_exercises`, `completed_sets`, `skipped_sets`,
`sessions_with_known_duration`, and `known_duration_seconds`.

Only included outcomes count. Exercise/set counts sum canonical
`SessionOutcome.summary` values without recomputing execution statuses or reading
sets to normalize them again. History-wide summaries are not weekly evidence.

Null duration is unknown and excluded from known-duration counts and sums. Zero
duration is known zero and counts as a known duration. Timestamps never supply
missing duration. An empty known-duration sum is zero, accompanied by its count
so that no observations remain distinguishable from an observed zero.

No volume load, tonnage, 1RM, load averages, kg/lb conversion, training stress or
workload score is calculated.

## Recovery facts

Only explicit `SessionOutcome.feedback` contributes:

| Fields | Meaning |
| --- | --- |
| `sessions_with_feedback` | Non-null objects, including all-null feedback |
| `sessions_with_known_fatigue`, `high_fatigue_sessions` | Non-null fatigue count; fatigue >= 4 count |
| `latest_known_fatigue_after` | Final non-null fatigue in canonical order |
| `sessions_with_known_discomfort`, `moderate_high_discomfort_sessions` | Non-null discomfort count; moderate/high count |
| `latest_known_discomfort_after` | Final non-null discomfort in canonical order |
| `sessions_with_known_session_rpe`, `latest_known_session_rpe` | Non-null RPE count and final non-null RPE |

No known observations means null latest values. A trailing null never erases an
earlier known value. Explicit discomfort `none` is known and differs from null.
Canonical fatigue and RPE do not allow zero; the aggregate does not invent it.
There are no averages, recovery/readiness/fatigue scores, medical interpretation
or diagnoses. Sleep, energy, soreness and wearable data remain future Recovery /
Daily State Engine responsibilities.

## Attendance/adherence facts

`WeeklyAdherenceFacts` contains `due_planned_sessions`, `completed_due_sessions`,
`partial_due_sessions`, `unresolved_due_sessions`, and `attendance_ratio`.
Only due planned slots contribute:

```text
attendance_ratio = (completed_due_sessions + partial_due_sessions)
                   / due_planned_sessions
```

With no due slots the ratio is null; due unresolved slots alone yield 0.0. The
ratio stays within 0..1. Partial execution counts as attendance, not completion.
Future slots are excluded from the denominator; unplanned execution is excluded
from the numerator. This ratio is neither a quality/motivation score nor a
compliance judgment or standalone progression signal.

## Determinism, isolation and limitations

The same validated input yields the same output. The builder does not mutate
history, outcomes, planned slots or the input ID list. Output lists and planned
models are independent objects, so output edits cannot affect input. Outputs are
mutable snapshots; editing one does not recalculate its other derived fields.
Normally validated canonical input is expected: `model_construct` and mutation
after validation are not ingestion interfaces. Canonical summaries are trusted.
The input validator owns scope validation; output models validate field shapes,
while the builder owns derivation of cross-field aggregate consistency.

There is no progression import/invocation or `ProgressionDecision` field, no
planner/rescheduling, recommendation, prescription, interpretation, coach prose,
API, persistence, database, Base44, frontend, LLM or deployment. Existing Training
Engine behavior and protected production files remain unchanged. Caller-selected
membership and dates remain caller responsibility; V1 does not establish a
storage timezone policy. The next expected block is **Program Planner V1** under
a separate bounded prompt. Base44 live acceptance remains paused and frontend
adoption remains pending.

## Exact files and validation

Exactly five files change:

- `app/models/weekly_training_state.py`
- `app/services/weekly_training_state.py`
- `tests/test_weekly_training_state.py`
- `docs/weekly-training-state-v1.md`
- `docs/ibuum-fit-v2-current-status.md`

The focused suite covers empty inputs, scope validation, planned state and due
boundaries, canonical ordering, authoritative workload summaries, explicit
duration, recovery thresholds/latest values, attendance, strict/exact contracts,
determinism, mutation isolation and pure import boundaries. Full regression
checks existing API behavior; the final Git inventory verifies the five-file
boundary and unchanged protected production files.

```text
pytest -q tests/test_weekly_training_state.py
pytest -q
python -m compileall app tests
git diff --check
```
