# iBuum Fit V2 Architecture Map v1.0

**Status:** Canonical architecture baseline  
**Owner:** iBuum Fit product architecture  
**Canonical repository:** `PatrickJM77777/iBuum-agent`  
**Canonical path:** `docs/ibuum-fit-v2-architecture-map-v1.md`

This document is the single source of truth for iBuum Fit V2 architecture. Other repositories may reference it, but must not maintain divergent copies. Any new engine, tool, product surface, integration or data contract must declare where it fits in this map before implementation.

## 1. Core architectural rule

**MOTOR DECIDES -> INTERPRETATION EXPLAINS -> UI PRESENTS**

Training, progression, recovery, safety-sensitive adaptation and other domain decisions must be owned by explicit domain engines or deterministic services. Kai, Kaia, frontend code, Base44 functions, LLMs and presentation layers must not silently override approved domain outputs.

Codex is the implementation programmer. The development flow is:

`architecture + contract + acceptance criteria -> Codex implementation -> tests -> PR -> human review -> merge`

Codex is not part of the production runtime and must not invent architecture outside the authorized scope of a task.

---

## 2. Macro architecture

```text
User
  |
  v
Experience Layer
(App / Web / iBuum for Coach)
  |
  v
Coach Core + Intent Router + Guards
  |
  v
Personalization Layer
  |
  +--> Personal Memory
  +--> Interaction Memory
  +--> Adaptive User Profile
  +--> Human Adaptation Profile
  |
  v
Domain Intelligence
  |
  +--> Training Intelligence
  +--> Recovery Intelligence
  +--> Nutrition Intelligence
  +--> Supplement Intelligence
  +--> Cycle Intelligence
  |
  v
Safety / Policy Boundary
  |
  v
Interpretation + Communication Brain
  |
  v
Kai / Kaia
  |
  v
UI
```

Specialist capabilities connect through a **Tool Registry** rather than being embedded into one monolithic agent.

---

## 3. Product surfaces

### 3.1 iBuum Fit Consumer

User-facing app/web experience containing onboarding, training, progress, nutrition, recovery, cycle, habits, Kai/Kaia, Daily Coach, Weekly Review, Community and future tools.

### 3.2 Shared Web + App experience

App and web must consume shared identity, profile, memory, history, entitlements and backend state.

```text
App --\
       > Shared backend / identity / data
Web --/
```

App and web must not be treated as two independent products with duplicated business state.

### 3.3 iBuum for Coach

Professional product surface for trainers/coaches.

Core capabilities:

- Coach Dashboard
- Client Management
- invite/code relationship
- Trainer Plans
- Planned vs Performed
- adherence and consistency
- deterministic scores and patterns
- attention queue / clients needing review
- Coach AI Assistant for interpretation of already-calculated data
- professional entitlements/pricing by active-client model where applicable

Coach AI may explain metrics; it must not fabricate metrics.

---

## 4. Globalization / Localization

Localization is presentation only. Canonical domain codes must remain untranslated.

Current foundation includes:

- `LocalizationProvider`
- semantic message IDs
- `es-ES` active catalog
- planned locale registry (`en-GB`, `fr-FR`, `it-IT`, `pt-PT`)
- fallback behavior
- `Intl` formatting seam

Required evolution:

`preferred_locale -> persistence contract -> resolver -> selector -> reviewed catalogs -> Kai/Kaia communication locale`

Localization must never construct persisted domain values, routes, commands, cache keys or API enums.

---

## 5. Coach Core

Coach Core is the intelligent entry point for Kai/Kaia. It is not the Training Engine.

Responsibilities:

- receive intent + current context
- determine which domain/tool should handle the request
- build a bounded context summary
- enforce tool availability and guardrails
- route to the correct capability
- pass domain output to interpretation/communication

It must not duplicate domain rules.

---

## 6. Intent Router

Planned intent families include:

- `TRAINING`
- `PROGRESS`
- `RECOVERY`
- `NUTRITION`
- `SUPPLEMENTATION`
- `CYCLE`
- `FORM_CHECK`
- `HABITS`
- `COACH`
- `KNOWLEDGE`
- `GENERAL_CONVERSATION`

Form Check remains architecturally reserved with:

```text
FORM_CHECK_ENABLED=true
FORM_CHECK_STATUS="future_integration"
FORM_CHECK_PREMIUM=true
FORM_CHECK_AUTO_OFFER=true
FORM_CHECK_PREFERENCE="ask"
```

---

## 7. Guards & Safety Layer

Safety is transversal and must exist around sensitive operations.

```text
Input -> Validation -> Safety Guard -> Domain Engine -> Output Guard -> Interpretation
```

High-priority areas include pain/injury signals, health context, cycle data, nutrition, supplementation, Form Check, accessibility adaptations and sensitive personal data.

Safety may block, constrain, require more information or redirect the type of action. It must not become an unstructured replacement for domain logic.

---

## 8. Personalization and memory

### 8.1 Personal Memory

Longitudinal user context such as:

- Training History
- Exercise Performance
- Recovery History
- Progression History
- Adherence History
- Cycle Response History
- stable preferences

Memory stores facts/context. It must not fabricate conclusions.

### 8.2 Interaction Memory

Separate from sports history. Stores useful interaction preferences such as explanation length, technical depth, voice preference, visual preference, step-by-step preference and repetition needs.

Interaction preferences may change presentation but must not directly alter training decisions.

### 8.3 Adaptive User Profile

Combines declared profile and observed behavior, including effective training level, adherence, recovery, capacity, preferences and training response.

Declared values and inferred/observed state must remain distinguishable.

### 8.4 Human Adaptation Profile

Supports inclusive product adaptation. May contain declared context for mobility, sensory, cognitive or communication needs; Down syndrome; disability; training restrictions; dietary restrictions; allergies/celiac requirements; and preferred instruction complexity.

The system adapts experience and allowed options; it must not diagnose or label beyond the user's supplied/authorized context.

### 8.5 Personalization Layer

Produces a bounded, task-relevant context from memory + profiles + current state. Domain engines should receive only information relevant to the current decision, not an unrestricted dump of personal history.

---

## 9. Training Intelligence

Current/approved core components:

- Training Rules
- Training Engine
- Session Selection Policy
- Workout Generator
- Exercise Library
- Exercise Selector
- Workout Orchestrator
- Profile Validation
- Workout API
- E2E Acceptance
- Interpretation Core
- Interpretation API

Current pipeline:

```text
Training Request
   -> Training Engine
   -> Workout Generator
   -> Exercise Selector
   -> Workout Orchestrator
   -> Interpretation
```

Training Engine remains authoritative for high-level action/session/intensity/duration decisions.

---

## 10. Exercise Library, Search and Selection

### Exercise Library

Canonical exercise metadata, including stable exercise ID, movement pattern, level, required equipment, suitable location and relevant movement properties.

### Exercise Search / Resolver

Future capability for retrieving compatible candidates using movement pattern, location, equipment, level, restrictions and accessibility context.

### Exercise Selector

Deterministically selects from permitted candidates. Search/resolution and selection must not rewrite the upstream prescription.

---

## 11. Workout Session / Execution Engine

Workout generation and workout execution are separate domains.

The execution layer owns:

- session start/end
- current exercise
- set/rep state
- rest state
- skip/pause/resume
- partial completion
- completion state

`workoutSession` belongs to execution/state, not workout generation.

---

## 12. Session Outcome and Training History

A completed or interrupted session should produce a structured Session Outcome containing applicable data such as completion state, actual duration, exercises/sets/reps/load, effort, fatigue, discomfort and skipped work.

```text
Workout Session -> Session Outcome -> Training History
```

Training History must not be reconstructed from chat transcripts.

---

## 13. Progression Engine

Uses longitudinal evidence such as performance, volume, load, reps, effort, adherence, fatigue, recovery and recent history.

Possible domain outcomes include:

- `PROGRESS`
- `MAINTAIN`
- `REDUCE`
- `DELOAD`
- `NEEDS_MORE_DATA`

No single metric may automatically dictate progression.

---

## 14. Weekly Training State

Internal aggregate of the current training week, including planned/completed/partial/remaining sessions, volume, fatigue, recovery and adherence.

Weekly Training State is an internal domain object. It is not the same as the user-facing Weekly Review.

---

## 15. Program Planner + Rescheduling

Workout Generator structures one approved session. Program Planner organizes multiple sessions/weeks and consumes progression + weekly state.

Planner/Rescheduling handles missed sessions and schedule changes by recalculating remaining work while respecting recovery and program intent.

A missed workout must not simply become a failure flag if a safe reorganization is possible.

---

## 16. Recovery / Daily State Engine

Builds daily recovery context from available signals such as recent training, fatigue, sleep, energy, soreness/discomfort and future wearable data.

It provides context for domain decisions; it does not bypass Training Engine authority.

---

## 17. Cycle Intelligence

Architecture:

`Cycle Context -> Cycle Training History -> Cycle Pattern Analyzer -> personalized cycle context`

No universal rule may assume menstrual phase alone implies reduced performance or intensity. Adaptation should be based on reported context and, later, individual historical patterns.

---

## 18. Interpretation Core + Communication Brain

Interpretation Core is the first deterministic explanation layer.

It must preserve approved action, session, intensity, duration, selection and reason codes.

Communication Brain is the future broader presentation layer that decides how to communicate an already-approved result based on language, timing, Kai/Kaia, user communication preferences and required detail.

**Communication can vary; domain truth cannot.**

---

## 19. Kai / Kaia Experience

Kai and Kaia are user-facing assistant/personality layers, not independent decision engines.

Planned presentation states include Neutral, Coach, Training, Analysis, Success, Motivation, Typing, Voice and future animated/avatar states.

They may differ in presentation/context, but not in core safety or sports rules.

---

## 20. Daily Coach, Weekly Review and Live Workout

### Daily Coach

Brief contextual experience combining daily state, training recommendation, recovery, habits, cycle context where applicable and relevant reminders.

### Weekly Review

User-facing explanation of already-calculated consistency, completed work, progress, volume, recovery, highlights and next-week recommendations.

### Live Workout Companion

Kai/Kaia presentation during execution: next exercise, rest, session status, allowed adaptations, voice prompts and feedback capture. Source of truth remains Workout Session Engine.

---

## 21. Real-Time Adaptation

When runtime context changes:

```text
new signal -> Safety -> domain adaptation policy -> approved new state -> Kai/Kaia explanation
```

Kai/Kaia must never improvise unapproved substitutions or prescriptions.

---

## 22. Specialist tools

### Form Check

Vision-based movement feedback tool. It analyzes movement and returns bounded observations/feedback. It must not act as a clinical diagnostic system or independently rewrite the full program.

### Wearables / Health Data

Future signals may include steps, heart rate, sleep, activity, recorded workouts and recovery. Wearables provide context; a single value must not directly prescribe training.

### Voice Service

Separate text-to-speech service. Initial provider may be ElevenLabs, but provider choice must remain replaceable without changing domain logic.

### Tool Registry

Canonical registry of available capabilities such as Training, Progression, Recovery, Nutrition, Form Check, Wearables, Supplements, Knowledge and Voice.

---

## 23. Nutrition Intelligence

Independent domain for food, nutrition entries, recipes, hydration, goals and dietary restrictions.

### Food Vision / Food Resolver

```text
Food image -> Vision recognition -> Food Resolver -> candidates/amounts -> user confirmation when needed -> Nutrition Engine
```

A visual model must not be treated as an unquestionable source of nutritional truth.

---

## 24. Supplement Intelligence

Handles supplement context, timing, habits, evidence and training relationship while remaining separate from Training Brain and medical prescribing.

Commerce must never bias supplement recommendations.

---

## 25. Habits, Goals, Challenges and Travel Mode

### Habits Engine

Hydration, steps, sleep, mobility, recovery routines and other wellness habits.

### Goals / Challenges / Milestones

Motivational layer for goals, achievements, challenges and carefully designed streaks. Rest, recovery and illness/injury must not be punished by gamification.

### Travel Mode

Temporary environment context for hotel/travel, limited equipment, limited time, changed location or timezone, while preserving program continuity.

---

## 26. Knowledge architecture

### External Knowledge

Versioned, validated knowledge separate from personal memory. Domains may include training science, nutrition, female-health context, supplements, exercise knowledge and safety guidance.

### Research / Web Layer

Used selectively for fresh information with explicit source/freshness/safety policies. It must not be invoked by default for every interaction.

### Trend Knowledge

Temporary trend information must remain separate from stable scientific/safety knowledge.

---

## 27. Community

Potential capabilities include posts, comments, reactions, recipes, challenges, progress sharing and profiles.

### Community Moderation

Possible content states:

- `PUBLISH`
- `PUBLISH_WITH_WARNING`
- `REVIEW`
- `BLOCK`

Health-related content receives stricter controls.

---

## 28. Entitlements / Free / Premium

Free and Premium must use the same core intelligence. Entitlements control access to capabilities; they do not create separate brains.

Potential premium capabilities include advanced coaching, voice, Form Check, deeper history, advanced progression, cycle analytics and professional tools.

Consent and entitlement are separate concepts.

---

## 29. Events / Reminders / Notifications

Independent system for workout reminders, habit reminders, weekly reviews, coach follow-ups, scheduled events and product notifications.

Notifications are not memory and must not become a hidden source of domain state.

---

## 30. Commerce

Store capabilities such as Catalog, Cart, Order, Inventory, Payment and Customer remain isolated from Training/Health decision engines.

Commercial interests must never influence training, nutrition or supplementation recommendations.

---

## 31. Data Layer

Conceptual entities may include:

- `UserProfile`
- `Assessment`
- `AdaptiveProfile`
- `HumanAdaptationProfile`
- `CoachMemory`
- `WorkoutSession`
- `SessionOutcome`
- `TrainingHistory`
- `ProgressEntry`
- `WeeklyTrainingState`
- `Program`
- `NutritionEntry`
- `SupplementEntry`
- `CycleEntry`
- `CoachConversation`
- `HabitEntry`
- `PreferredLocale`
- `Entitlement`
- `CoachClientRelationship`

Physical schema may evolve; domain ownership and boundaries must remain explicit.

---

## 32. Identity, Privacy and Consent

Authenticated identity is separate from domain `user_id` values. Caller-supplied user IDs must never be accepted as proof of authentication.

Privacy/consent must cover, as applicable:

- privacy consent/version
- health-related data
- cycle data
- camera/voice permissions
- retention/deletion policies
- data minimization

---

## 33. Admin / Configuration / Feature Flags

Features under rollout should be controllable through configuration/flags such as Form Check, Voice, Coach, Wearables or Research.

Feature flags control availability, not domain truth.

---

## 34. Evaluation & QA

Every V2 block must be independently testable.

Required testing layers as appropriate:

- unit
- contract
- regression
- matrix/profile
- integration
- E2E
- security/privacy
- acceptance

Deterministic engines must produce reproducible outputs from equivalent inputs.

---

## 35. Repository ownership

### `PatrickJM77777/iBuum-agent`

Owns domain intelligence and APIs, including Training Brain, generation, exercise selection, orchestration, interpretation and future progression/program/safety domain services.

### `PatrickJM77777/iBuum-fit-frontend`

Owns iBuum Fit UI/UX, onboarding, localization presentation, Kai/Kaia presentation and client-side interaction. It must not own authoritative training rules.

### `PatrickJM77777/WebiBuumfit`

Owns the iBuum Fit web product surface. It should consume shared product/domain services rather than reimplementing V2 intelligence.

### Base44 runtime/functions

Own app-specific authenticated server bridges, product workflows and platform services where appropriate. It must not duplicate domain engines.

### `PatrickJM77777/ibuum-digital`

Separate iBuum Digital product/web repository. It is part of the broader iBuum ecosystem but does not own iBuum Fit domain intelligence.

---

## 36. Prohibited dependency patterns

The following are architecture violations unless explicitly approved by a future architecture revision:

- UI reimplements Training Rules.
- Kai/Kaia independently choose a workout.
- Localization generates domain codes.
- Community changes Training Engine decisions.
- Commerce influences health/training/supplement recommendations.
- LLM fabricates deterministic metrics/scores.
- Form Check rewrites the entire program without domain-engine approval.
- Wearable signals directly prescribe training without policy/engine evaluation.
- Base44 creates a competing workout from multiple endpoint responses.
- Memory stores inferred conclusions as if they were user-declared facts without provenance.

---

## 37. Single-authority table

| Information | Authority |
| --- | --- |
| Training decision | Training Engine |
| Workout structure | Workout Generator |
| Exercise compatibility/selection | Exercise Library + Selector |
| Session execution state | Workout Session Engine |
| Session result | Session Outcome |
| Progression | Progression Engine |
| Weekly state | Weekly Training State |
| Program structure | Program Planner |
| Cycle pattern analysis | Cycle Intelligence |
| Personal history | Memory/Data Layer |
| Accessibility adaptation context | Human Adaptation Profile |
| Communication/explanation | Interpretation / Communication Brain |
| Localization | Localization Layer |
| Authentication | Identity layer |
| Feature access | Entitlements |
| UI rendering | Frontend/Web |
| Coach metrics | Deterministic Coach analytics |

---

## 38. Current implementation baseline

### Implemented / approved

- Training Rules
- Training Engine
- Workout Generator
- Exercise Library
- Exercise Selector
- Workout Orchestrator
- Workout API
- Profile Validation
- E2E Acceptance
- Interpretation Core V1
- Interpretation API V1
- Base44 Integration Contract V1
- Localization Foundation V1 in `iBuum-fit-frontend`

### Next foundation work

- `preferred_locale` persistence contract
- Base44 `getWorkoutInterpretation` bridge implementation/acceptance
- Session Outcome
- Training History

### Subsequent intelligence work

- Progression Engine
- Weekly Training State
- Program Planner
- Cycle Pattern Analyzer

### Subsequent personalization/experience work

- Personal Memory
- Interaction Memory
- Adaptive User Profile
- Human Adaptation Profile
- Personalization Layer
- Coach Core
- Intent Router
- Communication Brain
- Daily Coach
- Weekly Review
- Live Workout Companion

### Later specialist/ecosystem work

- Real-Time Adaptation
- Voice
- Form Check
- Wearables
- Nutrition / Food Resolver
- Supplements
- Habits
- Community
- iBuum for Coach

---

## 39. Recommended implementation order

```text
FOUNDATION
Localization persistence
Base44 <-> iBuum Agent bridge
Session Outcome
Training History

INTELLIGENCE
Progression Engine
Weekly Training State
Program Planner
Cycle Pattern Analyzer

PERSONALIZATION
Adaptive User Profile
Human Adaptation Profile
Memory
Personalization Layer

COACH
Coach Core
Intent Router
Communication Brain
Daily Coach
Weekly Review

LIVE EXPERIENCE
Workout Session V2
Real-Time Adaptation
Voice
Form Check
Wearables

EXPANSION
Nutrition
Habits
Supplements
Community
iBuum for Coach
```

Order may change only when dependency analysis supports it. Architecture boundaries must not be bypassed for speed.

---

## 40. Architectural invariants

1. Training Engine is authoritative for training decisions.
2. LLMs explain/interpret; deterministic engines own deterministic decisions and metrics.
3. Frontends never contain authoritative sports logic.
4. Personalization never weakens safety rules.
5. Kai/Kaia are interfaces, not independent brains.
6. Memory stores facts/context with provenance; it does not invent truth.
7. iBuum for Coach shares calculated data but has a separate professional experience.
8. Free/Premium share core intelligence; Entitlements control access.
9. Localization affects presentation only.
10. External integrations contribute signals/tools, not domain authority.
11. Every block must be testable independently.
12. Codex implements only an explicitly authorized scope/contract.
13. New features must map to an existing block or require an architecture revision before coding.
14. A single domain responsibility must not have competing implementations across repositories.

---

## 41. Governance and change policy

This file is canonical. Changes to this architecture must:

1. be made in a dedicated branch/PR;
2. explain the architectural reason for the change;
3. identify affected repositories and boundaries;
4. preserve or explicitly revise the invariants above;
5. avoid silent architectural changes inside feature PRs;
6. receive human review before merge.

Feature PRs may reference this document, but must not redefine its architecture locally.

When Codex receives a V2 implementation task, the task should state:

> This implementation must remain consistent with `docs/ibuum-fit-v2-architecture-map-v1.md`. If the requested implementation conflicts with the canonical architecture, stop and report the conflict instead of inventing a workaround.

---

## 42. Versioning

This document is **iBuum Fit V2 Architecture Map v1.0**.

Future architecture revisions should increment the document version deliberately and preserve reviewable history in Git. Minor feature work does not automatically change the architecture version.
