# Program Planner V1

Program Planner converts an explicitly approved session template into one future
seven-day program week and attaches authoritative progression and weekly context.
It follows the canonical Architecture Map and Codex Development Workflow.

```text
Session Outcome -> Training History -> Progression Engine -> Weekly Training State
 -> Program Planner V1 -> future Planner / Rescheduling V1
CANONICAL CONTEXT -> PROGRAM STRUCTURE -> FUTURE SESSION GENERATION
MOTOR DECIDES -> INTERPRETATION EXPLAINS -> UI PRESENTS
```

Workout Generator structures one approved workout. Program Planner organizes
multiple planned sessions; V1 limits its horizon to one explicit seven-day week.
Future Planner / Rescheduling will handle missed work and schedule changes under
a separate contract. These responsibilities remain separate.

## Input contract

`ProgramPlannerInput` has exactly:

- `previous_week_state`: an actual canonical `WeeklyTrainingState` instance;
- `progression_decisions`: a possibly empty list of actual canonical
  `ProgressionDecision` instances, with unique `exercise_id` values;
- `plan_week_start`: an explicit date;
- `session_templates`: a possibly empty list of `ProgramSessionTemplateInput`.

Raw dictionaries are rejected for weekly state and progression items. All seven
new models forbid unknown fields. Counts are strict nonnegative integers.
Normally validated canonical objects are expected; `model_construct` and edits
after validation are not ingestion interfaces. Canonical upstream facts are
trusted, including their summary values.

Each template has only `slot_id` (nonempty string, maximum 128 characters),
`day_offset` (strict integer 0..6), and `session_type` (upper_body, lower_body,
full_body, cardio, mobility). Slot IDs are unique and opaque, without trimming.
The caller approves every session type and offset. Multiple slots may share a
date. Template list order is canonical; the planner never sorts by date.

The next week must start exactly at `previous_week_state.week_end + 1 day`.
Gaps and overlaps fail validation. Monday is not required, and `as_of_date` may
precede the previous week end. Both the next-day boundary and the complete new
seven-day horizon must be representable; date overflow becomes a validation error.

## Pure planner and output

`build_program_plan(data: ProgramPlannerInput) -> ProgramPlan` lives in
`app/services/program_planner.py`. `PROGRAM_PLANNER_VERSION` is exposed in the
model module as `"program-planner-v1"`.

`ProgramPlan` contains exactly `planner_version`, `source_week_start`,
`source_week_end`, `plan_week_start`, `plan_week_end`, `sessions`,
`progression_decisions`, `previous_week_context`, `progression_summary`, and
`plan_summary`. The end date is the explicit start plus six days.

Each `ProgramSessionPlan` contains only `slot_id`, `scheduled_date`, and
`session_type`. Its date is the start plus the template offset; `day_offset` is
not exposed in the output. Session count, types and order remain caller-owned.
There is no title, prose or workout prescription.

Progression decisions are retained unchanged as deep copies, including version,
exercise ID, decision, reason codes, occurrences considered and latest session ID.
`ProgramProgressionSummary` counts only `decision`, with exactly `total_decisions`,
`progress_decisions`, `maintain_decisions`, `reduce_decisions`, `deload_decisions`,
and `needs_more_data_decisions`. No strongest decision, ranking or score is derived.

`ProgramPreviousWeekContext` copies these facts without recalculation:

| Context field | Canonical source |
| --- | --- |
| source_week_start / source_week_end / source_as_of_date | week_start / week_end / as_of_date |
| planned_sessions | plan_summary.total_planned_sessions |
| completed_planned_sessions | plan_summary.completed_planned_sessions |
| partial_planned_sessions | plan_summary.partial_planned_sessions |
| remaining_planned_sessions | plan_summary.remaining_planned_sessions |
| due_remaining_planned_sessions | plan_summary.due_remaining_planned_sessions |
| unplanned_sessions | workload.unplanned_sessions |
| attendance_ratio | adherence.attendance_ratio |
| high_fatigue_sessions | recovery.high_fatigue_sessions |
| moderate_high_discomfort_sessions | recovery.moderate_high_discomfort_sessions |

Null attendance stays null; zero stays zero. No new readiness, recovery or
adherence score is introduced.

`ProgramPlanSummary` counts only output session types: `total_sessions`,
`upper_body_sessions`, `lower_body_sessions`, `full_body_sessions`,
`cardio_sessions`, and `mobility_sessions`. There is no rest-day or load score.

## Policy boundaries and limitations

**Program Planner V1 does NOT reinterpret Progression Engine decisions.**
It never imports or calls `evaluate_progression`.

**Program Planner V1 does NOT recalculate Weekly Training State.**
It never calls `build_weekly_training_state`, infers historical membership or
inspects SessionOutcome timestamps.

**Program Planner V1 does NOT generate workouts.**
There are no Training Engine, Workout Generator, Exercise Selector or Workout
Orchestrator calls, nor exercises, sets, reps, load, intensity or duration.

**Program Planner V1 does NOT reschedule missed/unresolved sessions.**
It does not move, copy, replace or reorder slots, infer preferred days, or react
to calendar changes. Unresolved prior work is context only.

Adaptive planning policy is not yet canonically defined. Attendance, fatigue,
discomfort and every progression category remain context only and cannot change
the session template or its count. Multi-week planning, adaptive planning and
Planner / Rescheduling V1 require separate bounded contracts. There is no API,
persistence, database, Base44, frontend, LLM, interpretation or deployment change.
Base44 live acceptance remains paused; frontend adoption remains pending.

## Determinism and mutation isolation

The same validated input yields the same output. There is no system clock,
timezone inference, randomness or external I/O. The planner does not mutate
weekly state, decisions, templates or caller lists. Output sessions and lists are
new objects; progression decisions and their nested reason lists are deep copies.
Output edits cannot affect input. Outputs are mutable snapshots: editing one does
not recalculate its summaries. Input validation owns date/uniqueness constraints;
output models validate field shapes and the builder derives cross-field values.

## Exact files and validation

Exactly five files change:

- `app/models/program_planner.py`
- `app/services/program_planner.py`
- `tests/test_program_planner.py`
- `docs/program-planner-v1.md`
- `docs/ibuum-fit-v2-current-status.md`

The focused tests cover empty inputs, dates and overflow, canonical-only upstream
objects, uniqueness, strict offsets, session types, same-date slots, supplied
order, progression preservation/counts, factual context including nullable
attendance, non-adaptive policy, exact fields, extra-field rejection, strict
counts, determinism, mutation isolation, and import/clock/timestamp boundaries.
The final Git inventory checks the exact five-file scope and protected files;
full regression checks existing behavior, including existing API contracts.

```text
pytest -q tests/test_program_planner.py
pytest -q
python -m compileall app tests
git diff --check
```

Next expected bounded block: **Planner / Rescheduling V1**.
