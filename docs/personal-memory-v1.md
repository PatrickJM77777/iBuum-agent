# Personal Memory V1

Personal Memory V1 stores canonical facts and context.
It does NOT fabricate conclusions.
It does NOT make training decisions.
It does NOT infer a user profile.
It does NOT persist data.
It does NOT store chat history.
It does NOT implement Interaction Memory.
It does NOT invent stable preferences.

## Purpose and architecture

Architecture Map section 8.1 owns this structured in-memory domain snapshot.
`MOTOR DECIDES -> INTERPRETATION EXPLAINS -> UI PRESENTS` remains unchanged.
Memory composes already-canonical sports-domain outputs; it is neither an engine
nor a database, recommendation system, personalization system or LLM memory.

`build_personal_memory(data: PersonalMemoryInput) -> PersonalMemory` lives in
`app/services/personal_memory.py`. The model module exposes
`PERSONAL_MEMORY_VERSION = "personal-memory-v1"`. All three new models use
`ConfigDict(extra="forbid")`.

## Exact canonical sources

PersonalMemoryInput has exactly these fields:

| Field | Canonical type | Requirement |
| --- | --- | --- |
| training_history | TrainingHistory | Required, including empty history |
| progression_decisions | list[ProgressionDecision] | Required, may be empty |
| weekly_training_states | list[WeeklyTrainingState] | Required, may be empty |
| daily_recovery_states | list[DailyRecoveryState] | Required, may be empty |
| cycle_training_history | CycleTrainingHistory or None | Defaults to None |
| cycle_pattern_analysis | CyclePatternAnalysis or None | Defaults to None |

Every source and list item must be an actual canonical model instance. Raw nested
dictionaries are rejected rather than reconstructed. Normally validated upstream
objects and their summaries are trusted; model_construct and post-validation
mutation are not ingestion interfaces.

TrainingHistory remains authoritative for executed sessions, exercise history,
exercise performance occurrences and feedback. Exercise performance is represented
only through `training_history.exercise_history`; no competing history is built.

ProgressionDecision has no independent decision timestamp. The progression list
is a caller-supplied per-exercise snapshot set, not a time-series event log.
Exercise IDs must be unique. Caller order, decisions, reason codes,
occurrences_considered and latest_session_id are preserved exactly. There is no
sorting by ID, inferred chronology, timestamp creation or progression evaluation.

## Explicit chronology and cross-history consistency

Weekly snapshots must already be in strictly ascending `(week_start, as_of_date)`
tuple order. Duplicate tuples and reversed/nonmonotonic order are rejected.
Multiple snapshots from one week with later as_of dates are valid. Every included,
unplanned and non-None planned linked session ID must exist in TrainingHistory.
The current history may be a superset of an older weekly snapshot. No weekly
state is rebuilt. Adherence history remains `WeeklyTrainingState.adherence`;
its facts and the embedded weekly recovery facts remain unchanged.

Daily recovery snapshots must have unique, strictly ascending state_date values.
Missing dates are allowed and never filled. No sorting, clock or date inference
is used. A recovery state's source weekly snapshot need not appear in the weekly
list: independently available canonical sources are valid. Daily reports, flags,
recent training context and weekly recovery facts remain separate. They are never
merged, averaged, scored or turned into a recovery/adherence trend.

Optional cycle history must have exactly the same session count as TrainingHistory.
At each index both session_id and the full canonical SessionOutcome model_dump
must match. This checks facts and order without rebuilding cycle history. Explicit
cycle observations are preserved, including distinctions between missing context,
unknown phase and reported discomfort.

Optional cycle analysis requires cycle history. Its source_cycle_history_version
must equal cycle_history_version. Both summaries must agree on total_sessions,
sessions_with_cycle_context, sessions_without_cycle_context and unknown_phase_sessions.
Analysis known_phase_sessions must equal the sum of history menstruation,
follicular, ovulation and luteal counts. This is an inventory check, not proof of
analysis provenance or a rerun of the analyzer. Evidence and observed patterns
remain unchanged and are never converted into training rules or recommendations.

## Output and factual summary

PersonalMemory contains exactly the six source fields above plus memory_version
(literal personal-memory-v1), source_training_history_version (literal
training-history-v1, copied from history_version), and summary: PersonalMemorySummary.
Output optional sources are explicit nullable fields. Output construction also
enforces the canonical instance and source consistency rules.

PersonalMemorySummary contains exactly:

| Field | Mapping |
| --- | --- |
| total_training_sessions | training_history.summary.total_sessions |
| exercise_histories | len(training_history.exercise_history) |
| progression_decisions | len(progression_decisions) |
| weekly_state_snapshots | len(weekly_training_states) |
| daily_recovery_snapshots | len(daily_recovery_states) |
| has_cycle_training_history | cycle_training_history is not None |
| cycle_training_sessions | cycle history summary.total_sessions, otherwise 0 |
| has_cycle_pattern_analysis | cycle_pattern_analysis is not None |
| cycle_patterns | cycle analysis summary.detected_patterns, otherwise 0 |

Counts are strict nonnegative integers, rejecting bool, float and string inputs.
Presence flags are strict booleans. Absent cycle history requires zero cycle
sessions; absent analysis requires zero patterns; analysis presence requires
history presence. Present-but-empty sources are valid.

## Isolation, determinism and limitations

Every stored source is model_copy(deep=True), including every list item and all
nested sessions, sets, feedback, exercise occurrences, weekly facts, recovery
signals, cycle contexts, evidence and patterns. Output lists are newly allocated.
Editing output cannot mutate input or the original canonical objects. Repeated
validated input produces equal output. Mutable output edits do not automatically
revalidate or recalculate its summary; callers build a new snapshot when needed.
The builder creates the factual summary; direct output construction validates
shape and source relationships, not summary-to-source derivation.

There is no new readiness, capacity, effective level, adherence quality, recovery
tendency, cycle sensitivity, user archetype, diagnosis, recommendation or training
decision. Existing canonical progression decisions are stored unchanged. No
upstream builder, analyzer, Training Rules or Training Engine is called.

Stable sports preferences are deferred pending a separate authoritative contract.
No favorite exercise, time, intensity or duration is invented. Interaction Memory
owns future presentation preferences; Adaptive User Profile owns future inferred
profiles; Human Adaptation Profile owns separately contracted accessibility and
declared restriction context. Personalization Layer owns future task-relevant
selection, ranking and compression. This snapshot implements none of those layers,
nor Coach Core, retrieval, expiry, database deduplication or personalized prompts.

Privacy/minimization: no user_id, account, name, email, phone, username or device
fields are introduced. Ownership and authorization remain outside this user-agnostic
domain model and require a future persistence contract. Only the supplied canonical
sports facts are held; no additional sensitive profile, medical interpretation,
free-text facts, conversation summaries, chat history, embeddings or vector search
are collected. There is no SQL, ORM, repository layer, filesystem/network storage,
Redis, database, API, Base44 entity, frontend, wearable, notification or deployment.

Interaction Memory V1 is the next expected bounded block. Base44 live acceptance
remains paused/pending and frontend adoption remains pending.

## Exact files and validation

Exactly five files change:

- app/models/personal_memory.py
- app/services/personal_memory.py
- tests/test_personal_memory.py
- docs/personal-memory-v1.md
- docs/ibuum-fit-v2-current-status.md

Focused parametrized tests cover canonical instance rejection, empty/optional
sources, exact fields and versions, progression uniqueness and preservation,
weekly/recovery chronology, references, matching cycle histories and inventory,
summary mappings/invariants, deep mutation isolation, determinism and architecture
import/call boundaries. Final Git inventory verifies the exact five files and
unchanged protected files. The full regression suite runs once after focused tests.

```text
pytest -q tests/test_personal_memory.py
pytest -q
python -m compileall app tests
git diff --check
```
