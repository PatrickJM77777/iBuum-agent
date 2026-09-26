# External / Multisport Activity History V1

External Activity History V1 answers:
"What external physical activities actually occurred?"

It does NOT answer: "How much training load did the user accumulate?"
It does NOT answer: "How recovered is the user?"
It does NOT answer: "What should the user train next?"

## Purpose and architecture

This pure domain snapshot stores factual caller-supplied activities outside the
canonical iBuum workout execution pipeline. It follows the Architecture Map's
separation of facts, history and decisions and preserves
`MOTOR DECIDES -> INTERPRETATION EXPLAINS -> UI PRESENTS`.

TrainingHistory remains authoritative for canonical iBuum SessionOutcome execution.
ExternalActivityHistory remains authoritative only for its own caller-supplied
external activity records. These are parallel histories: no SessionOutcome is
imported, embedded, converted or copied between them. Training History is not
modified. If an activity already has a canonical iBuum SessionOutcome, that
canonical execution belongs to TrainingHistory. This contract cannot identify
duplicate real-world events across histories and performs no cross-history
deduplication by date, duration, sport, distance or feedback.

Sport Activity Profile describes currently declared activities; this history
describes dated occurrences. No profile is required, and historical activity need
not belong to a current profile. A historical skiing record or a one-off activity
is valid. No frequency, experience, typical duration or environment is copied or
compared with the profile, and the profile is not mutated.

The model module exposes
`EXTERNAL_ACTIVITY_HISTORY_VERSION = "external-activity-history-v1"`.
All five models use `ConfigDict(extra="forbid")`.
`build_external_activity_history(data: ExternalActivityHistoryInput) -> ExternalActivityHistory`
is the pure builder in `app/services/external_activity_history.py`.

## Exact record contract

| Field | Contract |
| --- | --- |
| activity_id | Required strict string, 1..128 characters, caller-supplied record identifier |
| activity_type | Required exact taxonomy identifier below |
| custom_activity_name | Optional strict string, 1..80 characters; required for other and forbidden for known types |
| activity_date | Required datetime.date, calendar date assigned by the caller |
| completion_state | Optional completed or partial |
| actual_duration_minutes | Optional strict integer 1..1440 |
| distance_meters | Optional strict finite float greater than zero |
| feedback | Optional ExternalActivityFeedback |

Exact taxonomy, shared with Sport Activity Profile V1:

```text
strength_training
functional_training
calisthenics
cardio_fitness
running
walking
cycling
swimming
football
basketball
volleyball
tennis
padel
yoga
pilates
dance
hiking
climbing
rowing
combat_sport
mobility_training
team_sport
other
```

Tests compare this exact identifier set with `SportActivityEntry.activity_type`.
Production models do not import Sport Activity Profile for runtime introspection.
Canonical identifiers remain untranslated; no language or locale is stored.

For `other`, custom_activity_name must contain a non-whitespace character and
have no leading/trailing whitespace. Unicode, case and interior whitespace are
preserved exactly. There is no trimming, lowercasing, translation or free-text
classification. Known types require None. `wheelchair basketball` is only the
supplied activity label; it does not imply wheelchair use, disability, mobility
limitation or Human Adaptation data.

IDs are preserved exactly and must be unique within one history. There is no ID,
UUID or hash generation. An ID identifies an activity record, never a user,
account, device or wearable provider. Duplicate sport/date combinations with
distinct IDs are allowed; no event identity is inferred from metrics.

Dates intentionally have calendar-date resolution. No started_at, ended_at,
timezone, UTC conversion or time-of-day inference exists. No clock is consulted;
even a far-future date is valid. Application validation of future dates is outside
this contract. Records must already have non-decreasing dates. Same-day records
retain caller order exactly. Descending dates are rejected, never silently sorted
by date, ID, sport, duration or feedback.

`completed` means the caller reports completion; `partial` means the caller reports
partial completion; None means not supplied. There is no failed, abandoned,
skipped, success or quality judgment. Actual duration is factual performed time,
not typical, planned or target time and not load. Distance is allowed for any
activity when meaningful to the caller; running and cycling do not require it,
and football can include it. No pace, speed, calories or performance is derived.
Numeric strictness follows Pydantic strict fields: float fields reject strings
and booleans and accept numeric integers as floats; integer fields reject floats,
booleans and strings. Nonfinite float values are rejected.

## Feedback and unknown values

ExternalActivityFeedback contains exactly:

| Field | Contract |
| --- | --- |
| activity_rpe | Optional strict finite float 1..10 |
| fatigue_after | Optional strict integer 1..5 |
| discomfort_after | Optional none, mild, moderate or high |

Every optional record/feedback field defaults to None: not supplied / unknown.
An all-None feedback object is valid and counts as present. The explicit discomfort
category `none` differs from an unknown None. Facts remain independent: high RPE
does not imply fatigue or partial completion; high discomfort does not imply
injury, diagnosis, illness, overtraining, medical risk or recovery advice;
completion does not imply feedback; partial completion does not imply fatigue;
duration and distance do not imply each other. No missing value is generated.

## Input, output and summary

ExternalActivityHistoryInput has exactly one required field,
`records: list[ExternalActivityRecord]`. Every entry must be an actual canonical
instance; raw record dictionaries and non-list containers are rejected. Empty
records are valid and mean only that no external records are supplied in this
snapshot. No profile-derived records, default walking activities or rest days
are invented. Input validation checks unique IDs and chronological order without
mutating the caller list or records.

ExternalActivityHistory contains exactly `history_version` (literal
`external-activity-history-v1`), `records: list[ExternalActivityRecord]`, and
`summary: ExternalActivityHistorySummary`.

| Summary field | Meaning |
| --- | --- |
| total_records | len(records) |
| known_activity_records | Count with activity_type != other |
| custom_activity_records | Count with activity_type == other |
| completed_records | Count with completion_state == completed |
| partial_records | Count with completion_state == partial |
| records_without_completion_state | Count with completion_state is None |
| records_with_known_duration | Count with actual_duration_minutes is not None |
| records_with_known_distance | Count with distance_meters is not None |
| records_with_feedback | Count with feedback is not None, including all-None feedback |
| has_any_records | total_records > 0 |

All counts are strict nonnegative integers, and the flag is a strict boolean.
Validation enforces known plus custom equals total, completion partitions equal
total, each optional presence count is at most total, and the flag matches total
greater than zero. Empty history has zero counts and false. This is an inventory,
without averages, scores, rankings, recommendations or duration/distance totals.
Heterogeneous sport distances are not combined into an accidental domain metric.
Duration aggregation is deferred to future explicitly contracted context/workload
semantics, not introduced as implicit load here.

## Revalidation, isolation and determinism

At the builder boundary canonical record instances are checked again. Raw mutable
record field values and nested feedback field values are revalidated before ID
and chronological checks. Invalid post-construction mutations are rejected.
Validated records are deep-copied with `model_copy(deep=True)` into a new list.
Every output record and nested feedback is detached from input and other builds.
Output mutations cannot affect input; later input mutations cannot affect output.
Equal validated inputs produce equal values with independent objects.

No clock, randomness, external I/O or hidden state is used. Mutable output edits
do not automatically revalidate or recalculate summaries; build a new snapshot
when needed. Direct output construction validates field types and summary
invariants; canonical ingestion, chronology, uniqueness and summary-to-record
derivation belong to the input/builder contract. This is not a persistence, merge,
patch, provenance or synchronization system.

## Domain boundaries and limitations

- No records are inferred from profiles, Training History, chat, calendar, GPS,
  steps, wearables, health APIs, sensors, photos, video or location. There is no
  automatic detection, LLM, embeddings or semantic classification.
- No training load, duration multiplied by RPE, TRIMP, TSS, acute/chronic load,
  calories, weekly aggregation, weekly minutes or recovery demand is calculated.
- No Recovery/Daily State, Weekly Training State, Program Planner, Rescheduling,
  Progression Engine, Training Rules, Training Engine, Workout Generator,
  Exercise Selector or Orchestrator is imported, modified or called. A football
  record cannot cancel/move a workout, change frequency or produce progression.
- Personal Memory and Interaction Memory remain unchanged. Neither embeds this
  history; activity facts are not communication preferences.
- Human Adaptation Profile is the next bounded block, under a separate contract.
  No disability, sensory/cognitive need, assistance, support or restriction is
  inferred or stored here, including from custom names.
- Adaptive User Profile remains future: no primary/favorite sport, athlete type,
  effective experience, capacity, fitness, performance or adherence is inferred.
- Personalization Layer remains future: no ranking, relevant-activity selection,
  task context, prompt context or training-decision context is assembled.
- Unified Activity Context remains future: TrainingHistory and this history are
  not combined into recent workload, recovery, planner or weekly activity context.
- No Apple Health, Health Connect, Garmin, Fitbit, WHOOP, Oura or Strava adapter,
  provider ID, wearable ID, import status or sync status exists. Future adapters
  may supply facts under separate contracts; this history is source agnostic.
- No high-resolution sensor data: GPS/route, heart-rate samples/zones, cadence,
  power/watts, steps, elevation, speed/pace or stroke counts.
- No identity/PII or location fields: user/account/device ID, personal name,
  email, phone, gym/club, address, city, country or coordinates. Ownership and
  authorization are outside this user-agnostic domain. Custom activity names are
  labels, not identity storage; no semantic PII detector or rewriting is provided.
- No notes, descriptions, journal, comments, activity summary or free-text
  feedback. The only descriptive free text is the bounded custom activity name.
- No database, SQL, ORM, repository layer, CRUD, Redis, filesystem/cloud/account
  persistence, API, Base44 entity, frontend/onboarding work or deployment.

Base44 live runtime acceptance remains paused/pending; frontend adoption remains
pending. Human Adaptation Profile V1 and all later blocks require separate work.

## Files and validation

Exactly five files change:

- `app/models/external_activity_history.py`
- `app/services/external_activity_history.py`
- `tests/test_external_activity_history.py`
- `docs/external-activity-history-v1.md`
- `docs/ibuum-fit-v2-current-status.md`

Parametrized tests cover exact contracts, taxonomy parity, custom names, strict
metrics, independent facts, presence combinations, summary invariants, IDs,
chronology, mutation revalidation, recursive isolation and allowlisted domain
imports/calls. Git inventory verifies the five-file scope and protected files.

```text
pytest -q tests/test_external_activity_history.py
pytest -q
python -m compileall app tests
git diff --check
```

Full regression runs once after focused tests pass.
