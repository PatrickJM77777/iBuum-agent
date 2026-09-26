# Sport Activity Profile V1

Sport Activity Profile V1 answers:
"What sports / physical activities does the user explicitly declare they currently practice?"

It does NOT answer: "What did the user do today?"
It does NOT answer: "How much training load did they accumulate?"
It does NOT answer: "What should they train next?"

## Purpose and architecture

This canonical current declarative snapshot represents multisport users without
assuming that all physical activity originates in the iBuum Training Engine.
Strength training, running and football can coexist as declarations. They are
not dated sessions. This is a bounded profile contract within the Architecture
Map's separation of declared context, observed history and domain decisions.
`MOTOR DECIDES -> INTERPRETATION EXPLAINS -> UI PRESENTS` remains unchanged.

The model module exposes
`SPORT_ACTIVITY_PROFILE_VERSION = "sport-activity-profile-v1"`.
All four models use `ConfigDict(extra="forbid")`.
`build_sport_activity_profile(data: SportActivityProfileInput) -> SportActivityProfile`
is a pure builder in `app/services/sport_activity_profile.py`.

## Entry contract

`SportActivityEntry` has exactly these six fields:

| Field | Contract |
| --- | --- |
| activity_type | Required exact identifier from the taxonomy below |
| custom_activity_name | String of 1..80 characters for `other` only; otherwise None |
| days_per_week | Optional strict integer 1..7 |
| experience_level | Optional `beginner`, `intermediate` or `advanced` |
| typical_duration_minutes | Optional strict integer 1..720 |
| practice_environment | Optional `home`, `gym`, `outdoors`, `pool`, `court_or_field`, `studio`, `sports_facility`, `mixed` or `other` |

Exact activity taxonomy:

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

This taxonomy is intentionally bounded, not an exhaustive inventory of the
world's sports. `other` can represent rugby, handball, skating, skiing, surfing,
pole dance, equestrian sport, wheelchair basketball or another activity without
expanding this version. Canonical identifiers remain untranslated; UI translation
belongs to frontend/localization. There is no locale/language field.

`other` requires `custom_activity_name`; known types require it to be None.
Names must contain a non-whitespace character and have no leading/trailing
whitespace. Unicode is allowed. Valid text is preserved exactly, including case
and interior whitespace: no stripping, lowercasing, translation, sanitization
into another sport or automatic classification. Non-string names are rejected.

Each optional field defaults to None, meaning **not explicitly supplied**.
No field supplies defaults for another field. Running does not imply outdoors,
swimming does not imply pool, football does not imply court_or_field, strength
training does not imply gym, yoga does not imply studio or a duration, advanced
does not imply more days, and seven days does not imply advanced experience.
All environment categories are valid independently of the activity type.

`days_per_week` is the declared typical frequency for that activity, not planned
or completed sessions, exact history or load. Frequencies across activities may
sum above seven: strength training 4, running 3 and football 2 is valid because
activities may share a day. No dates or schedule are inferred.

Experience is declared per activity: advanced strength training and beginner
swimming can coexist. No effective level, skill or physical capacity is inferred.
Typical duration is descriptive, not an actual session duration, required workout
duration or planner instruction. Duration is never multiplied by frequency.
Environment is only a broad declared category, not a place or location record.

## Input, identity and order

`SportActivityProfileInput` has exactly one required field:
`activities: list[SportActivityEntry]`. Every item must be an actual canonical
instance. Raw nested dictionaries are rejected. The builder rechecks canonical
instances, duplicate identities and entry field validation before producing output.
An empty list is valid and means this snapshot contains no declared current
sport/activity entries; it never inserts a default activity.

Known activity types must be unique. Custom identities use
`custom_activity_name.casefold()`: `Surfing` and `surfing`, or `Straße` and
`STRASSE`, are duplicates. Original spelling is still preserved in stored output.
Different custom names may coexist. There is no semantic/synonym resolution:
known `running` and `other("Running")` remain distinct valid declarations.
Duplicates cause validation errors; none are silently removed or merged.
Caller order is preserved exactly, including mixed known/custom lists. There is
no alphabetical sorting, ranking, prioritization or inferred primary sport.
Validation and building do not mutate the caller's list or entries.

## Output and factual summary

`SportActivityProfile` contains exactly `profile_version` (literal
`sport-activity-profile-v1`), `activities: list[SportActivityEntry]` and
`summary: SportActivityProfileSummary`.

| Summary field | Meaning |
| --- | --- |
| total_activities | len(activities) |
| known_activities | Count with activity_type != other |
| custom_activities | Count with activity_type == other |
| activities_with_days_per_week | Count with days_per_week is not None |
| activities_with_experience_level | Count with experience_level is not None |
| activities_with_typical_duration | Count with typical_duration_minutes is not None |
| activities_with_practice_environment | Count with practice_environment is not None |
| has_any_activities | total_activities > 0 |

All counts are strict nonnegative integers; booleans, floats and strings are
rejected. The presence flag is a strict bool. Summary validation enforces known
plus custom equals total, each optional-field count is at most total, and the
presence flag matches total > 0. Empty profiles have all zero counts and false.
There is no completeness, fitness, diversity, experience, adherence or load score,
recommendation or ranking.

## Determinism, isolation and limitations

Each output activity is validated and copied with `model_copy(deep=True)` into a
new list. Every explicit value and None survives unchanged. Mutating output does
not affect input; mutating input after building does not affect output. Repeated
builds produce equal values with independent lists and entries. There is no clock,
randomness, I/O, automatic detection or inferred missing data.

Mutable output edits do not automatically revalidate or recalculate the summary;
build a new snapshot when needed. Direct output construction validates its field
types and summary invariants; canonical ingestion, duplicate checking and
summary-to-activity derivation are the input/builder contract. This is not a merge,
patch, event log, provenance, persistence or version-history system.

## Domain and privacy boundaries

- Existing `TrainingRecommendationRequest.training_level`,
  `training_days_per_week`, `goal` and training-engine context remain unchanged.
  No replacement, reinterpretation or synchronization occurs. A future explicit
  profile/personalization contract may reconcile context; this version does not.
- Training History remains the owner of canonical executed training facts.
  No activities are inferred from it, Workout History, engine sessions, wearables,
  chat, clicks, calendar, GPS, health data, age, sex, disability, equipment or location.
- Personal Memory V1 and Interaction Memory V1 are unchanged and do not embed
  this profile. Activity declarations are not communication preferences.
- External / Multisport Activity History V1 is the next bounded block. No activity
  dates, timestamps, start/end, distance, pace, speed, heart rate, calories, GPS,
  steps, actual duration, results, RPE, fatigue, completion or source fields exist.
- Human Adaptation Profile remains separate and future. The custom declaration
  `wheelchair basketball` stores only an activity label, never wheelchair use,
  disability, mobility limitation or support needs. Walking, mobility training
  and yoga imply no injury, impairment, medical or mental-health context.
- Adaptive User Profile remains future: no primary/favorite sport, athlete type,
  identity, effective experience, capacity, fitness, performance, adherence,
  behavior class or specialization is inferred.
- Personalization Layer remains future: no task context, prompt context, activity
  relevance, selection, ranking or prioritization is produced.
- Unified Activity Context remains future: this profile is not combined with
  iBuum Training History into training/recovery state or external load.
- No load calculations, weekly minutes, volume, calories, acute/chronic load,
  TRIMP, TSS, sport stress or recovery requirement are calculated. No Weekly
  Training State, Program Planner, Rescheduling or Recovery integration exists.
- Training Rules, Training Engine, Workout Generator, Exercise Selector,
  Orchestrator and Progression Engine are neither modified nor called. No workout
  creation/change, progression, rescheduling or training decision occurs.
- No identity/PII or location fields: user/account/device IDs, personal name,
  email, phone, gym/club name, address, city, country, route or coordinates.
  Custom names are activity labels, not an identity storage contract; there is
  no semantic PII detector or content rewriting. Ownership/authentication remains
  outside this user-agnostic domain contract.
- No database, SQL, ORM, CRUD, repository layer, Redis, filesystem/cloud/account
  persistence, Base44 entity, API endpoint, frontend/onboarding change or deployment.
  No LLM, embeddings or free-text extraction system is introduced.

Base44 live runtime acceptance remains paused/pending. Frontend adoption remains
pending. All future blocks require separate approved contracts.

## Files and validation

Exactly five changed files:

- `app/models/sport_activity_profile.py`
- `app/services/sport_activity_profile.py`
- `tests/test_sport_activity_profile.py`
- `docs/sport-activity-profile-v1.md`
- `docs/ibuum-fit-v2-current-status.md`

Parametrized tests cover taxonomy, exact fields, custom validation, canonical
ingestion, duplicates, ordering, independence, strict types, all optional-field
presence combinations, summary invariants, deep isolation, determinism and
allowlisted imports/calls. Final Git inventory verifies the exact five changed
files and unchanged protected files.

```text
pytest -q tests/test_sport_activity_profile.py
pytest -q
python -m compileall app tests
git diff --check
```

The full regression suite runs once after focused tests pass.
