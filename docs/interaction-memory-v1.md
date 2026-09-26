# Interaction Memory V1

Interaction Memory V1 stores explicit communication/presentation preferences.
It does NOT alter Training Engine decisions.
It does NOT infer preferences from behavior or conversation.
It does NOT infer disability or cognitive state.
It does NOT implement accessibility adaptation.
It does NOT implement response generation.
It does NOT persist data.

## Purpose and architecture

Architecture Map section 8.2 places this snapshot on the explanation/presentation
side of `MOTOR DECIDES -> INTERPRETATION EXPLAINS -> UI PRESENTS`.
It is separate from Personal Memory: no PersonalMemory imports or embedded sports
history, progression, weekly state, recovery, cycle history or cycle patterns.
No Training Rules, Training Engine, progression, planner, recovery, cycle analyzer,
workout generator, selector or orchestrator is imported or called.

The model module exposes `INTERACTION_MEMORY_VERSION = "interaction-memory-v1"`.
`build_interaction_memory(data: InteractionMemoryInput) -> InteractionMemory` is a
pure builder. All four models use `ConfigDict(extra="forbid")`.

## Exact preferences and meanings

Every field is optional and defaults to `None`.

| Field | Exact non-None values and meanings |
| --- | --- |
| explanation_length | `short`: concise explanations; `balanced`: moderate length; `detailed`: more complete explanations |
| technical_depth | `simple`: plain language; `standard`: normal domain terminology; `technical`: deeper technical/domain detail |
| voice_preference | `text`: text interaction/presentation; `either`: no strong text-versus-voice preference; `voice`: voice where available |
| visual_preference | `text`: primarily textual; `balanced`: text plus visuals where useful; `visual`: visual presentation where available |
| step_by_step_preference | `summary`: compact result-first presentation; `adaptive`: steps when context benefits; `step_by_step`: ordered step-by-step explanations |
| repetition_preference | `minimal`: avoid unnecessary repetition; `standard`: normal repetition; `reinforced`: repeat/reinforce important instructions |

`None` means not explicitly specified / unavailable. It never means balanced,
default preference, no voice/visual preference or no accessibility need. Explicit
`either`, `balanced` and `standard` values are distinct from unspecified values.
All six may be None. The caller supplies structured current values; there is no
free-text extraction, automatic learning or inference from chats, clicks, response
times, prior conversations, training behavior, disability, age, sex, language,
device or analytics.

Each field is independent. Technical depth does not imply detailed explanations;
voice does not imply textual visuals; step-by-step does not imply reinforced
repetition. The builder preserves every explicit value and None exactly.

Technical detail cannot authorize advanced training or additional risk. Voice
preference does not enable Voice Service, bypass entitlements, guarantee capability
or start audio. Visual preference does not imply blindness, deafness, sensory
impairment or cognitive need. Reinforced repetition does not imply cognitive
impairment, Down syndrome, disability, memory disorder or any medical condition.

## Input, output and factual summary

`InteractionMemoryInput` has exactly one required field, `preferences`, which must
be an actual `InteractionPreferences` instance. Raw nested dictionaries are rejected.
Normally validated model instances are the ingestion contract; `model_construct`
and invalid post-validation mutation are not supported ingestion interfaces.

`InteractionMemory` has exactly `memory_version` (literal `interaction-memory-v1`),
`preferences: InteractionPreferences`, and `summary: InteractionMemorySummary`.

| Summary field | Meaning |
| --- | --- |
| supported_preferences | Always 6 |
| specified_preferences | Number of non-None fields |
| unspecified_preferences | 6 minus specified_preferences |
| has_any_preferences | specified_preferences > 0 |

Counts are strict nonnegative integers, rejecting booleans, floats and strings.
The presence flag is a strict boolean. Validation enforces supported count 6,
specified count at most supported, counts summing to supported and the presence
flag matching specified > 0. There are no completeness, confidence, quality,
importance, ranking or recommendation scores.

## Isolation, determinism and limitations

Preferences are copied with `model_copy(deep=True)`. Output preferences differ
from the input object, output edits cannot mutate input, and repeated builds
allocate independent outputs. The same validated input produces equal output
without clocks, timestamps, randomness, network access or other side effects.
Mutable output edits do not automatically recalculate summaries; build a new
snapshot when needed. Direct output construction validates types and summary
invariants; summary-to-preference counting is the builder's responsibility.

This is a current declared snapshot, not an event log. There is no created_at,
updated_at, observed_at or learned_at; no merge, patch, precedence, conflict
resolution, old-versus-new policy or preference history. Persistence/version
history requires a separate future contract.

No stable sports preferences (intensity, load, reps, sets, exercise, sport,
session type/duration or frequency) are stored. No training decision is produced.
No language, preferred_locale, country or region competes with the frontend's
canonical preferred-locale persistence contract. Generated Kai/Kaia localization
remains a future Communication Brain concern.

Human Adaptation Profile separately owns future declared mobility, vision,
hearing, communication, cognitive support, assistance and exercise restrictions;
this snapshot implements none of those dimensions or medical/dietary restrictions.
Preferences must never serve as disability proxies. Adaptive User Profile remains
separate: no archetype, learning style, effective level, capacity, adherence
quality, personality, behavioral class or technical/cognitive ability is inferred.

Personalization Layer remains responsible for future selection, ranking,
prioritization and task-specific context assembly. Communication Brain may consume
this snapshot under a separate contract; no prompts, rewriting, formatting,
explanation generation, tone transformation, voice generation or LLM calls occur.
There are no chat transcripts, conversation summaries, message history, embeddings,
semantic memory, vector retrieval or interaction analytics.

No database, SQL, ORM, repository, CRUD, Redis, filesystem storage, Base44 entity,
cloud/account/API persistence, frontend, wearables, notifications or deployment
is introduced. No identity/PII fields (user/account/device ID, name, email, phone,
IP address or location) exist. Ownership and authentication remain external to
this user-agnostic domain snapshot.

## Exact files and validation

Exactly five files change:

- `app/models/interaction_memory.py`
- `app/services/interaction_memory.py`
- `tests/test_interaction_memory.py`
- `docs/interaction-memory-v1.md`
- `docs/ibuum-fit-v2-current-status.md`

Focused parametrized tests cover canonical input, every enum and None, invalid
values, field independence, all 64 presence combinations, exact field/version
contracts, extra-field rejection, strict summary invariants, mutation isolation,
determinism and architecture import/call boundaries. Final Git inventory checks
the exact five changed files and confirms protected files remain unchanged.

```text
pytest -q tests/test_interaction_memory.py
pytest -q
python -m compileall app tests
git diff --check
```

Full regression runs once after focused tests pass. Sport Activity Profile V1 is
the next bounded block and requires its own closed contract. Base44 live runtime
acceptance remains paused/pending; frontend adoption remains pending.
