# Recovery / Daily State Engine V1

Recovery / Daily State Engine V1 provides context. It normalizes explicit daily
self-report and attaches canonical recent training facts under Architecture Map
section 16, preserving `MOTOR DECIDES -> INTERPRETATION EXPLAINS -> UI PRESENTS`.

```text
Workout Execution -> Session Outcome -> Training History -> Progression Engine
 -> Weekly Training State -> Program Planner -> Planner / Rescheduling
 -> Recovery / Daily State Engine V1 -> future Cycle Training History V1

CANONICAL RECENT TRAINING FACTS + EXPLICIT DAILY SELF-REPORT
 -> DAILY RECOVERY CONTEXT
```

The completed sequence describes architecture, not service calls. This engine
imports only the WeeklyTrainingState contract as its upstream domain dependency.
WeeklyTrainingState is the authoritative recent training source; this service does
not rebuild it, query history, inspect individual outcomes/timestamps, recalculate
workload/adherence or infer session membership.

## Input and six supported signals

`DailyRecoveryStateInput` contains exactly `current_week_state: WeeklyTrainingState`
and `reported_signals: DailyRecoverySignals`. Both must be actual canonical model
instances; nested raw dictionaries are rejected. No separate state date is accepted:
`current_week_state.as_of_date` is authoritative. All six new models forbid extras.

All six daily signals are optional, default to None, and an all-None report is valid.
Integers are strict, rejecting booleans, floats and numeric strings.

| Signal | Values and semantics |
| --- | --- |
| sleep_quality | Integer 1..5; 1 very poor, 5 very good |
| sleep_duration_minutes | Integer 0..1440; factual reported duration |
| energy_level | Integer 1..5; 1 very low, 5 very high |
| fatigue_level | Integer 1..5; 1 very low fatigue, 5 very high fatigue |
| soreness_level | none, mild, moderate, high |
| discomfort_level | none, mild, moderate, high |

Soreness and discomfort remain separate self-reports. None means unknown;
explicit `none` and duration zero are known values. Sleep duration has no short-sleep
threshold or classification in V1.

## Daily flags

`DailyRecoveryFlags` contains exactly these boolean facts:

| Flag | True exactly when |
| --- | --- |
| low_sleep_quality | Known sleep_quality <= 2 |
| low_energy | Known energy_level <= 2 |
| high_fatigue | Known fatigue_level >= 4 |
| moderate_high_soreness | soreness_level is moderate or high |
| moderate_high_discomfort | discomfort_level is moderate or high |

Unknown signals produce False flags. These flags describe explicit signals only;
they are not diagnoses, readiness categories or recommendations.

## Exact recent context mapping

`DailyRecentTrainingContext` copies these values without calculation or interpretation:

| Output | WeeklyTrainingState source |
| --- | --- |
| source_week_start | week_start |
| source_week_end | week_end |
| source_as_of_date | as_of_date |
| total_sessions | workload.total_sessions |
| completed_sessions | workload.completed_sessions |
| interrupted_sessions | workload.interrupted_sessions |
| unplanned_sessions | workload.unplanned_sessions |
| known_duration_seconds | workload.known_duration_seconds |
| due_remaining_planned_sessions | plan_summary.due_remaining_planned_sessions |
| high_fatigue_sessions | recovery.high_fatigue_sessions |
| latest_known_fatigue_after | recovery.latest_known_fatigue_after |
| moderate_high_discomfort_sessions | recovery.moderate_high_discomfort_sessions |
| latest_known_discomfort_after | recovery.latest_known_discomfort_after |
| latest_known_session_rpe | recovery.latest_known_session_rpe |

Source dates are dates; counts/duration are strict nonnegative integers. Latest
fatigue is nullable strict integer 1..5; discomfort is nullable none/mild/moderate/high;
RPE is nullable strict float 1..10, matching the upstream Pydantic contract.

Daily reported signals and recent weekly training facts remain distinct. Weekly
fatigue 5 and daily fatigue 1 both survive unchanged. Weekly high-fatigue counts or
high discomfort cannot activate daily flags when today's corresponding report is
unknown. No averages, worst-value selection, merging, overwriting or inferred
recency arbitration occurs. Due remaining sessions are factual context only.

## Summary and exact output

`DailyRecoverySignalSummary` contains strict nonnegative integers:

- supported_signals = 6;
- reported_signals = count of non-None daily signals;
- missing_signals = 6 minus reported_signals;
- flagged_signals = count of True values among the five flags.

Validation requires supported_signals == 6, reported_signals + missing_signals ==
supported_signals, and flagged_signals <= reported_signals. Duration counts as
reported even though it has no flag. These are counts, with no percentages or score.

`build_daily_recovery_state(data: DailyRecoveryStateInput) -> DailyRecoveryState`
lives in `app/services/daily_recovery_state.py`. The model module exposes
`RECOVERY_DAILY_STATE_VERSION = "recovery-daily-state-v1"`.

`DailyRecoveryState` has exactly:

- recovery_version: Literal["recovery-daily-state-v1"];
- source_week_state_version: Literal["weekly-training-state-v1"], copied from state_version;
- state_date: date, copied from as_of_date;
- reported_signals: DailyRecoverySignals;
- recent_training_context: DailyRecentTrainingContext;
- flags: DailyRecoveryFlags;
- signal_summary: DailyRecoverySignalSummary.

## Boundaries, determinism and limitations

It does NOT decide whether the user should train.
It does NOT generate a readiness score.
It does NOT change workout intensity.
It does NOT reschedule sessions.
It does NOT diagnose medical conditions.

There is no composite recovery/fatigue/wellness/risk score or overall category,
training recommendation, action, prose, medical interpretation, workout adaptation,
exercise/set/rep/load/duration/type prescription, progression evaluation, planning,
cycle logic or wearable data. Training Engine authority remains unchanged.
Future wearable data requires a separate integration contract.

The same validated input produces the same output. There is no clock, timezone
inference, randomness, network, filesystem, database or persistence. Explicit
signals are deeply copied; recent context, flags and summary are newly allocated.
Input weekly state and reports remain unchanged; output edits cannot affect inputs
or later builds. Outputs are mutable snapshots: manual edits do not recalculate
derived fields. Normally validated canonical objects are expected; model_construct
and post-validation mutation are not ingestion interfaces. Upstream summaries are
trusted. The builder owns cross-model derivation; output models validate shapes
and the summary model validates its three count invariants.

The caller owns the accuracy and daily applicability of the explicit report and
weekly snapshot. V1 has no recovery history, cross-week window, wearable adapter,
API, Base44/frontend wiring, notifications, calendar, LLM or deployment. Base44
live acceptance remains paused/pending; frontend adoption remains pending.
Future separately contracted policy engines may consume the factual state;
Daily Coach, Weekly Review and interpretation may present it under their own
contracts. This block implements none of those consumers. The next expected
bounded block is Cycle Training History V1, followed by Cycle Pattern Analyzer.

## Exact files and validation

Exactly five files change:

- app/models/daily_recovery_state.py
- app/services/daily_recovery_state.py
- tests/test_daily_recovery_state.py
- docs/recovery-daily-state-v1.md
- docs/ibuum-fit-v2-current-status.md

Focused tests cover canonical inputs, strict ranges/categories, all flag boundaries,
unknown/zero signals, exact factual copying, conflicting daily/weekly evidence,
summary invariants, exact fields, extras, versions, determinism, mutation isolation
and import/clock boundaries. Final Git inventory verifies the five-file scope and
unchanged protected files. Full regression runs once after focused tests pass.

```text
pytest -q tests/test_daily_recovery_state.py
pytest -q
python -m compileall app tests
git diff --check
```
