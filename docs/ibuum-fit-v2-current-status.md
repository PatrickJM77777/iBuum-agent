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

The Architecture Map defines **what belongs where**.  
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

Every Codex prompt must define objective, allowed/protected areas, out-of-scope behavior, acceptance criteria, focused tests and an explicit STOP condition.

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

## 5. Canonical governance status

Completed:

- [x] **iBuum Fit V2 Architecture Map v1.0** merged to `main`
- [x] **Codex Development Workflow v1.0** merged to `main`
- [x] **Current Status** established as the operational restoration point

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

### Protected backend guarantees

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

## 7. Base44 integration status

### Completed

- [x] `docs/base44-integration-contract-v1.md`
- [x] `docs/base44-get-workout-interpretation-prompt-v1.md`
- [x] contract tests for the future bridge

### Pending

- [ ] Create Base44 server-side `getWorkoutInterpretation`
- [ ] Run synthetic acceptance scenarios against the actual Base44 runtime
- [ ] Confirm authentication/secrets/runtime behavior
- [ ] Wire frontend UI only after bridge acceptance

Protected rule: Base44 must not reimplement Training Rules, progression logic, cycle adaptation or exercise selection.

---

## 8. Frontend V2 localization status

Repository: `PatrickJM77777/iBuum-fit-frontend`

### Localization Foundation V1 — completed

Merged in frontend PR #2.

- [x] `LocalizationProvider`
- [x] semantic message IDs
- [x] Spanish `es-ES` catalog
- [x] canonical locale registry
- [x] planned locale entries for `en-GB`, `fr-FR`, `it-IT`, `pt-PT`
- [x] fallback behavior
- [x] `Intl` formatter seam
- [x] Welcome/Claim/StartButton migrated with Spanish rendered parity preserved

### Preferred Locale Persistence V1 — completed

Merged in frontend PR #3.

- [x] dedicated `UserPreference` entity
- [x] `preferred_locale` stored separately from `User`
- [x] user-owned CRUD RLS
- [x] guest key `ibuum_preferred_locale_guest`
- [x] exact registered-locale validation
- [x] deterministic precedence: explicit session -> authenticated preference -> guest preference -> `es-ES`
- [x] `preferredLocale` distinct from `resolvedLocale`
- [x] planned locales may be stored without becoming renderable
- [x] no browser-language auto-detection
- [x] no automatic guest-to-account promotion
- [x] account/session-change protections

### Language Selection V1 — completed

Merged in frontend PR #4, with auth-boundary hotfix merged in PR #5.

Current approved journey:

`Welcome -> /onboarding/language -> /onboarding/profile -> existing auth/consent/persona onboarding`

Implemented behavior:

- [x] explicit Language Selection screen
- [x] five choices rendered from the canonical locale registry
- [x] native locale names, no flag-based language identity
- [x] guest and authenticated users can make an explicit language choice
- [x] authenticated writes use `setAuthenticatedPreferredLocale(locale)` without caller ownership IDs
- [x] guest writes use the existing guest preference boundary
- [x] guest storage failure may retain a session-only choice without claiming durable persistence
- [x] authenticated save failures remain on the selector and are retryable
- [x] planned locales remain safely rendered through `es-ES`
- [x] `LocalizationProvider` exposes `preferredLocale`, safe renderable `locale`, `sessionLocale` and validated `setSessionLocale`
- [x] `document.documentElement.lang` follows the resolved/renderable locale
- [x] Profile auth/consent semantics remain unchanged
- [x] `/onboarding/language` may pass the auth boundary for no error or `auth_required`
- [x] `user_not_registered` is not bypassed
- [x] other routes retain existing `auth_required` login redirect behavior
- [x] no browser-language detection
- [x] no additional translation catalogs activated
- [x] no domain/training/API behavior changed

PR #5 validation reported 31/31 repository Node tests passing, build passing, focused lint clean and `git diff --check` passing.

---

## 9. Current localization limitations

- only `es-ES` is an active reviewed catalog
- `en-GB`, `fr-FR`, `it-IT`, `pt-PT` remain registered but not yet active translation catalogs
- only Welcome and Language Selection use the localization boundary meaningfully; most onboarding/product copy remains hard-coded Spanish
- authenticated preference hydration is screen-local on Language Selection rather than a global auth/provider hydration system
- browser locale is intentionally not automatically adopted
- generated Kai/Kaia/Coach content remains a separate Communication Brain/localization problem
- persisted domain values and API codes must remain language-neutral/canonical and must never be translated as identifiers

---

## 10. Next approved development block

### **Reviewed Translation Catalogs V1 — Welcome + Language Selection**

This is the next approved bounded Codex block for `PatrickJM77777/iBuum-fit-frontend`.

Goal: extend the localization system from Spanish-only rendering to reviewed translation catalogs for the surfaces that are **already semantic and bounded**, without translating the entire application.

Initial scope is limited to:

- Welcome
- Claim/StartButton strings already owned by the Welcome localization surface
- Language Selection

Target registered locales:

- `en-GB`
- `fr-FR`
- `it-IT`
- `pt-PT`

Before implementation, inspect latest frontend `main`, enumerate the exact existing semantic message IDs and define the review/activation rule for each catalog.

### Protected boundaries

This block must not:

- translate canonical domain codes, API enums or persisted training answers
- broaden into all onboarding screens
- change auth or consent semantics
- change Training Brain, Coach/Kai/Kaia decisions or Agent APIs
- introduce browser-language detection
- silently activate incomplete/unreviewed catalogs
- add an external i18n dependency unless separately approved

If a target catalog is incomplete or not reviewed, it must remain non-renderable and continue to fall back safely to Spanish.

---

## 11. Directional development order after Reviewed Translation Catalogs V1

Subject to review after each merged block:

1. Reviewed Translation Catalogs V1 — Welcome + Language Selection
2. Gradual onboarding screen localization in small bounded groups
3. Base44 `getWorkoutInterpretation` bridge implementation/acceptance
4. Frontend adoption of the approved Interpretation API
5. Session Outcome V1
6. Training History V1
7. Progression Engine V1
8. Weekly Training State V1
9. Program Planner V1
10. Cycle Training History / Pattern Analyzer
11. Personal Memory / Adaptive Profile / Human Adaptation Profile
12. Coach Core / Intent Router / Communication Brain
13. Daily Coach / Weekly Review / Live Workout
14. Specialist systems such as Form Check, Wearables, Nutrition and Voice
15. iBuum for Coach expansion

This order is directional, not permission to bundle multiple blocks into one PR.

---

## 12. Major V2 blocks still pending

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
- [ ] Coach Core V2
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

## 13. Inclusive / Human Adaptation status

Inclusive adaptation is a first-class V2 architectural requirement, not a separate stigmatizing product.

The future Human Adaptation Profile may support declared context such as mobility/sensory limitations, communication or cognitive accessibility needs, disability, Down syndrome, training restrictions and instruction-complexity preferences.

The system adapts experience/options. It must not diagnose users.

Implementation remains pending.

---

## 14. Form Check status

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

## 15. Kai / Kaia role

Kai and Kaia are presentation/assistant layers.

They may differ in voice, presentation, context and communication style, but must not become independent sports decision engines.

Protected chain:

`Domain engine -> approved output -> Interpretation/Communication -> Kai/Kaia -> UI`

---

## 16. Operational Codex note

Quota is volatile and must be checked in the Codex UI when relevant.

During Preferred Locale Persistence V1, Codex reached the active usage limit after implementing core files and resumed later in the same session. The canonical efficiency rule remains:

**one bounded block per execution, no unnecessary exploration, no unrelated refactors.**

Do not treat earlier percentage screenshots as permanent quota values.

---

## 17. Chat/session recovery protocol

If a future chat loses context, use this instruction:

> **Carga el estado canónico de iBuum Fit.**

Expected recovery procedure:

1. Read `docs/ibuum-fit-v2-architecture-map-v1.md`
2. Read `docs/codex-development-workflow-v1.md`
3. Read `docs/ibuum-fit-v2-current-status.md`
4. Inspect latest relevant PRs/commits in GitHub
5. Confirm the current next block before drafting a Codex prompt

Do not ask the user to reconstruct the architecture from memory when these canonical sources are available.

---

## 18. Current next action

**Review latest `main` of `PatrickJM77777/iBuum-fit-frontend` and prepare the closed Codex prompt for Reviewed Translation Catalogs V1 — Welcome + Language Selection.**

Do not begin broad onboarding localization inside the same block.

---

## 19. Updating this document

Update this file when one of the following occurs:

- a planned block becomes implemented/merged
- the next approved block changes
- a major integration is accepted/rejected
- repository responsibility changes
- a new blocker materially changes sequencing
- a canonical document/version changes

Do not update this file for every small commit.

When changing status, preserve architectural truth in the Architecture Map and use Git history/PRs for detailed chronology.
