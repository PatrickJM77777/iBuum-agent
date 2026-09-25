# iBuum Fit V2 — Current Status

**Status:** Canonical operational status snapshot  
**Canonical repository:** `PatrickJM77777/iBuum-agent`  
**Canonical path:** `docs/ibuum-fit-v2-current-status.md`  
**Purpose:** Restore project context quickly after a new chat/session and define the next approved development step without re-deriving architecture from memory.

> This document is operational and intentionally dynamic. It complements, but never overrides, the canonical architecture and workflow documents.

## 1. Canonical references

Before proposing or implementing any new V2 work, read these documents in this order:

1. `docs/ibuum-fit-v2-architecture-map-v1.md`
2. `docs/codex-development-workflow-v1.md`
3. `docs/ibuum-fit-v2-current-status.md`
4. Recent merged/open PRs in the repository relevant to the task

The architecture map defines **what belongs where**.  
The Codex workflow defines **how work is executed**.  
This file defines **where the project is now and what comes next**.

---

## 2. Core invariant

**MOTOR DECIDES -> INTERPRETATION EXPLAINS -> UI PRESENTS**

Frontend, Base44, Kai/Kaia, LLMs and presentation layers must not duplicate or override authoritative domain decisions.

---

## 3. Development operating model

Codex is the implementation programmer.

Canonical execution flow:

`GitHub review -> exact change definition -> closed Codex prompt -> implementation -> focused tests -> PR -> direct GitHub review -> human approval -> merge`

Default unit of work: **one small bounded block per Codex execution**.

Every Codex prompt should define:

- exact objective
- in-scope behavior
- out-of-scope behavior
- allowed files/areas
- protected files/areas
- acceptance criteria
- focused tests
- explicit STOP condition

Do not use Codex for broad exploratory refactors when a bounded implementation can solve the task.

---

## 4. Repository map

### `PatrickJM77777/iBuum-agent`
Canonical V2 architecture, deterministic domain intelligence, APIs, orchestration, interpretation, future longitudinal intelligence and core backend contracts.

### `PatrickJM77777/iBuum-fit-frontend`
Current iBuum Fit app/frontend surface being evolved toward V2.

### `PatrickJM77777/WebiBuumfit`
iBuum Fit web surface.

### `PatrickJM77777/ibuum-digital`
iBuum Digital web surface.

### Other repositories
`ibuum-fit` and `iBuum-fit-app-empty` exist but are not treated as authoritative V2 repositories unless a specific task proves otherwise.

---

## 5. Canonical architecture status

### Completed canonical governance

- [x] **iBuum Fit V2 Architecture Map v1.0** merged to `main`
- [x] **Codex Development Workflow v1.0** merged to `main`
- [x] This Current Status document established as the operational restoration point

Architecture changes must be reviewed against the Architecture Map before implementation.

---

## 6. iBuum Agent / Training Intelligence status

The following core backend blocks are already implemented/merged:

- [x] Training Rules V1
- [x] Training Engine V1
- [x] Kaia Cycle Context normalization V1
- [x] Workout Generator V1
- [x] Exercise Library V1
- [x] Exercise Selector V1
- [x] Session Selection Policy V1.1
- [x] Workout Orchestrator V1
- [x] Profile Validation V1
- [x] Workout API V1
- [x] E2E Acceptance V1
- [x] Interpretation Core V1
- [x] Interpretation API V1
- [x] Base44 Integration Contract V1

Current interpretation remains deterministic and Spanish-first. It explains approved decisions; it does not replace the motor.

---

## 7. Current backend behavior guarantees

Current V1 behavior includes these protected semantics:

- explicit environment semantics are preserved
- missing environment is not equivalent to empty environment
- `equipment: null`, omitted equipment and `equipment: []` are distinct states
- bodyweight must not be inferred when not explicitly available
- presenter is explicit (`kai` or `kaia`), not inferred from sex
- Kai does not expose cycle-specific interpretation
- menstrual phase alone does not imply reduced capacity
- high discomfort may lead to approved recovery behavior
- unknown history is not treated as confirmed recovery failure
- rest/recovery/more-data states remain domain results rather than frontend inventions

These semantics must not be weakened by frontend integration.

---

## 8. Base44 integration status

### Completed

- [x] `docs/base44-integration-contract-v1.md`
- [x] `docs/base44-get-workout-interpretation-prompt-v1.md`
- [x] contract tests for the future bridge

### Not yet completed

- [ ] Create Base44 server-side `getWorkoutInterpretation`
- [ ] Run synthetic acceptance scenarios against the actual Base44 runtime
- [ ] Confirm authentication/secrets/runtime behavior
- [ ] Wire frontend UI only after bridge acceptance

Protected rule: Base44 must not reimplement Training Rules, progression logic, cycle adaptation or exercise selection.

---

## 9. Frontend V2 status

Repository: `PatrickJM77777/iBuum-fit-frontend`

### Completed

- [x] Existing app/frontend baseline imported to GitHub
- [x] Structural audit work completed before localization
- [x] **Localization Foundation V1** merged
- [x] `LocalizationProvider`
- [x] semantic message IDs
- [x] Spanish `es-ES` catalog
- [x] locale registry
- [x] planned locale entries for `en-GB`, `fr-FR`, `it-IT`, `pt-PT`
- [x] fallback behavior
- [x] `Intl` formatter seam
- [x] Welcome/Claim/StartButton migrated with Spanish rendered parity preserved

### Current localization limitations

- preferred locale is not yet persisted
- there is no language selector yet
- browser locale is not automatically adopted
- planned locales do not yet contain reviewed translations
- only a narrow Welcome surface is migrated

---

## 10. Next approved development block

### **Preferred Locale Persistence V1**

This is the next approved Codex block for `iBuum-fit-frontend`.

Objective:

Create the smallest safe persistence contract for `preferred_locale` on top of Localization Foundation V1, without yet adding a language-selection screen or broad translations.

Expected architectural direction:

`preferred_locale -> validated persistence -> locale resolver -> LocalizationProvider`

This block should remain presentation-only and must not affect domain codes, routes, API enums, training decisions, onboarding order, auth semantics or Base44 backend logic.

A dedicated closed Codex prompt must be prepared only after reviewing the latest `main` of `iBuum-fit-frontend`.

---

## 11. Development order after preferred locale

Subject to review after each merged block, the current intended sequence is:

1. Preferred Locale Persistence V1
2. Language Selection boundary/UI
3. Reviewed translation catalogs and gradual screen migration
4. Base44 `getWorkoutInterpretation` bridge implementation/acceptance
5. Frontend adoption of the approved Interpretation API
6. Session Outcome V1
7. Training History V1
8. Progression Engine V1
9. Weekly Training State V1
10. Program Planner V1
11. Cycle Training History / Pattern Analyzer
12. Personal Memory / Adaptive Profile / Human Adaptation Profile
13. Coach Core / Intent Router / Communication Brain
14. Daily Coach / Weekly Review / Live Workout
15. Specialist systems such as Form Check, Wearables, Nutrition and Voice
16. iBuum for Coach expansion

This order is directional, not permission to bundle multiple blocks into one PR.

---

## 12. V2 blocks not yet implemented

Major planned blocks still pending include:

- [ ] Session Outcome
- [ ] Training History
- [ ] Progression Engine
- [ ] Weekly Training State
- [ ] Program Planner
- [ ] Planner / Rescheduling
- [ ] Recovery / Daily State Engine
- [ ] Cycle Training History
- [ ] Cycle Pattern Analyzer
- [ ] Personal Memory
- [ ] Interaction Memory
- [ ] Adaptive User Profile
- [ ] Human Adaptation Profile
- [ ] Personalization Layer
- [ ] Coach Core
- [ ] Intent Router
- [ ] broader Safety/Guards layer
- [ ] Communication Brain V2
- [ ] Daily Coach
- [ ] Weekly Review
- [ ] Live Workout Companion
- [ ] Real-Time Adaptation
- [ ] Form Check production implementation
- [ ] Wearables / Health Data integration
- [ ] Nutrition Intelligence
- [ ] Food Vision / Food Resolver
- [ ] Supplement Intelligence
- [ ] Habits Engine
- [ ] Goals / Challenges / Milestones
- [ ] Travel Mode
- [ ] Voice Service
- [ ] Tool Registry
- [ ] External Knowledge
- [ ] Research / Web Layer
- [ ] Trend Knowledge
- [ ] Community
- [ ] Community Moderation
- [ ] Entitlements expansion
- [ ] Notifications / Reminders / Events
- [ ] shared App/Web operational state
- [ ] iBuum for Coach product implementation

The Architecture Map remains authoritative for responsibilities and boundaries of all these blocks.

---

## 13. iBuum for Coach status

**Architecture defined, implementation pending.**

Planned professional capabilities include:

- Coach Dashboard
- client invitation/linking
- Trainer Plans
- Planned vs Performed
- adherence
- consistency
- deterministic scores
- pattern detection
- attention queue
- Coach AI Assistant for interpretation of calculated data

Rule: Coach AI may interpret metrics; it must not fabricate them.

---

## 14. Inclusive / Human Adaptation status

Inclusive adaptation is a first-class V2 architectural requirement, not a separate stigmatizing product.

Planned Human Adaptation Profile may support declared context such as:

- mobility limitations
- sensory limitations
- communication needs
- cognitive accessibility
- disability
- Down syndrome
- training restrictions
- instruction complexity preferences
- dietary restrictions/allergies/celiac requirements

The system adapts experience/options. It must not diagnose users.

Implementation remains pending.

---

## 15. Form Check status

Form Check is architecturally reserved but not implemented as a production capability.

Current reserved configuration:

```text
FORM_CHECK_ENABLED=true
FORM_CHECK_STATUS="future_integration"
FORM_CHECK_PREMIUM=true
FORM_CHECK_AUTO_OFFER=true
FORM_CHECK_PREFERENCE="ask"
```

Do not treat Form Check as complete simply because the intent/configuration exists.

---

## 16. Kai / Kaia role

Kai and Kaia are presentation/assistant layers.

They may differ in voice, presentation, context and communication style, but must not become independent sports decision engines.

Protected chain:

`Domain engine -> approved output -> Interpretation/Communication -> Kai/Kaia -> UI`

---

## 17. Current operational Codex note

At the time this status snapshot was created, the observed Codex quota UI showed approximately:

- 5-hour window: **14% remaining**
- weekly limit: **47% remaining**
- weekly reset shown for **1 October**

This is a volatile operational note, not an architectural constraint. Re-check the Codex UI when quota matters rather than treating these values as permanent.

Efficiency rule remains canonical regardless of quota: one bounded block, no unnecessary exploration, no unrelated refactors.

---

## 18. Chat/session recovery protocol

If a future chat loses context, use this instruction:

> **Carga el estado canónico de iBuum Fit.**

Expected recovery procedure:

1. Read `docs/ibuum-fit-v2-architecture-map-v1.md`
2. Read `docs/codex-development-workflow-v1.md`
3. Read `docs/ibuum-fit-v2-current-status.md`
4. Inspect latest relevant PRs/commits in GitHub
5. Confirm the current next block before drafting a Codex prompt

Do not ask the user to reconstruct the entire architecture from memory when these canonical sources are available.

---

## 19. Current next action

**Prepare the closed Codex prompt for Preferred Locale Persistence V1 in `PatrickJM77777/iBuum-fit-frontend`, after reviewing the latest merged `main`.**

Do not start the next block until the latest repository state has been inspected.

---

## 20. Updating this document

Update this file when one of the following occurs:

- a planned block becomes implemented/merged
- the next approved block changes
- a major integration is accepted/rejected
- repository responsibility changes
- a new blocker materially changes sequencing
- a canonical document/version changes

Do not update this file for every small commit.

When changing status, preserve prior architectural truth in the Architecture Map and use Git history/PRs for detailed chronology.
