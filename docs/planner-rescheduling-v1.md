# Planner / Rescheduling V1

Planner / Rescheduling applies explicit bounded date changes to an already-approved
one-week ProgramPlan. It follows the canonical Architecture Map and Codex workflow.

```text
Session Outcome -> Training History -> Progression Engine -> Weekly Training State
 -> Program Planner V1 -> Planner / Rescheduling V1
 -> future Recovery / Daily State Engine V1
APPROVED PROGRAM -> EXPLICIT CHANGE REQUEST -> VALIDATED DATE MOVE -> UPDATED PROGRAM
MOTOR DECIDES -> INTERPRETATION EXPLAINS -> UI PRESENTS
```

Program Planner creates program structure. Rescheduling changes dates inside that
structure. Workout Generator builds one approved workout. Future Recovery / Daily
State Engine will supply richer daily recovery context; these responsibilities
remain separate.

## Canonical input and validation

`PlannerReschedulingInput` contains exactly `program_plan: ProgramPlan`,
`current_week_state: WeeklyTrainingState`, and
`requests: list[SessionRescheduleRequest]`. Plan and state must be actual canonical
instances; raw dictionaries are rejected. Requests may be empty.

The plan week start/end must exactly equal the current state week start/end.
Unique slot-ID sets must match exactly, without missing or extra slots. Each
matching slot must have the same scheduled date. A non-null weekly session type
must match the plan; null remains unknown and is allowed. Weekly state list order
does not replace canonical ProgramPlan session order.

Each request contains exactly:

- `slot_id`: nonempty string, maximum 128 characters, opaque without trimming;
- `target_date`: date;
- `reason`: exactly `SCHEDULE_CHANGE`, `AVAILABILITY_CHANGE`, or `UNRESOLVED_SESSION`.

No free-text, medical, failure or noncompliance reason is accepted. Requested slot
IDs must be unique and exist in the program. Only status `remaining` is movable.
`completed` and `partial` slots cannot be requested; V1 does not move the
uncompleted remainder of a partial session. Weekly Training State is authoritative
for execution status, linked session IDs and as_of_date.

Target dates must be inside the existing program week, inclusively, and greater
than or equal to `current_week_state.as_of_date`. Targets equal to the current
scheduled date are rejected as no-ops. Earlier and later moves are allowed under
these constraints. Multiple sessions may share one target date; there is no
per-day capacity limit. Unrequested due and future slots remain unchanged.

## Pure service and exact output

`reschedule_program(data: PlannerReschedulingInput) -> PlannerReschedulingResult`
is exposed in `app/services/planner_rescheduling.py`.
`PLANNER_RESCHEDULING_VERSION = "planner-rescheduling-v1"` is exposed in the model
module. All five new models use `ConfigDict(extra="forbid")`.

The result contains exactly:

- `rescheduler_version`: Literal `planner-rescheduling-v1`;
- `source_planner_version`: Literal `program-planner-v1`;
- `plan_week_start`, `plan_week_end`, `as_of_date`;
- `updated_plan: ProgramPlan`;
- `changes: list[RescheduleAppliedChange]`;
- `summary: ReschedulingSummary`.

`updated_plan` is a deep copy. Only explicitly requested session `scheduled_date`
values change. Planner version, source/plan week boundaries, session count, slot
IDs, session types, session list order, progression decisions, previous-week
context, progression summary and plan summary are preserved exactly.

Each applied change contains exactly `slot_id`, `original_scheduled_date`,
`new_scheduled_date`, `session_type`, and `reason`. Changes follow ProgramPlan
session order, regardless of request-list order. Equivalent reversed requests
produce the same result and audit order.

The summary contains strict nonnegative integers only:

| Field | Meaning |
| --- | --- |
| total_sessions | Number of ProgramPlan sessions |
| requested_changes | Number of valid explicit requests |
| rescheduled_sessions | Number of applied date changes |
| unchanged_sessions | total_sessions minus rescheduled_sessions |

Because no-ops are rejected, requested_changes equals rescheduled_sessions.
There are no recommendation, score or prose fields.

## Policy boundaries

**Planner / Rescheduling V1 does NOT automatically move unresolved sessions.**

**Planner / Rescheduling V1 does NOT classify unresolved sessions as failure.**

**Planner / Rescheduling V1 changes date only.**

**Planner / Rescheduling V1 is NOT recovery-aware yet.**

**Planner / Rescheduling V1 does NOT generate workouts.**

Due unresolved work remains `remaining`, with no missed/failed/noncompliant
judgment. Fatigue, discomfort, attendance, sleep, soreness, energy, readiness and
wearables do not cause date changes. Upstream recovery facts remain context.
PROGRESS, MAINTAIN, REDUCE, DELOAD and NEEDS_MORE_DATA are preserved without
reinterpretation; progression evaluation is never called. Weekly state is not
rebuilt, and workload, recovery, adherence, linked_session_id and status are not
recalculated or changed.

V1 preserves program intent: it cannot add, delete, duplicate or reorder sessions,
change types or workout content, or prescribe intensity, duration, sets, reps or
load. There are no Training Engine, Workout Generator, Exercise Selector or
Workout Orchestrator calls. Cross-week carryover is forbidden: V1 does not extend
the week, create another program or automatically carry unresolved work forward.

## Determinism, isolation and limitations

Same validated input yields the same output. There is no clock, timestamp use,
randomness, network, filesystem, database or external state in the service.
Inputs, request objects/lists and nested progression data are not mutated.
Output plan data is deeply detached, and the change list is newly allocated;
output edits cannot affect input or later results.

Normally validated canonical inputs are expected. `model_construct` and mutation
after validation are not ingestion interfaces. Canonical upstream summaries are
trusted. Input validation owns scope constraints; result models validate field
shapes and the service derives audit/summary consistency. Outputs are mutable
snapshots: manual output edits do not recalculate summaries or audit facts.

The caller supplies a current aligned weekly state and every requested date.
After a move, a subsequent operation needs a state aligned to the updated plan;
this service does not update WeeklyTrainingState. Recovery-aware scheduling and
cross-week carryover require future explicit contracts. There is no API route,
persistence, Base44/frontend integration, calendar, notification, LLM,
interpretation or deployment. Base44 live acceptance stays paused/pending and
frontend adoption stays pending.

## Exact files and validation

Exactly five files change:

- `app/models/planner_rescheduling.py`
- `app/services/planner_rescheduling.py`
- `tests/test_planner_rescheduling.py`
- `docs/planner-rescheduling-v1.md`
- `docs/ibuum-fit-v2-current-status.md`

Focused tests cover canonical inputs/alignment, eligibility, date boundaries,
no-ops, reasons, shared dates, unchanged unrequested work, all program fields,
audit order, strict/exact contracts, non-adaptive policy, deterministic results,
deep mutation isolation and pure import/call boundaries. Final Git inventory
verifies five changed files and unchanged protected files, including API routes.

```text
pytest -q tests/test_planner_rescheduling.py
pytest -q
python -m compileall app tests
git diff --check
```

Next expected bounded block: **Recovery / Daily State Engine V1**, under a separate
approved prompt. No implementation of that block is included here.
