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
4. Recent merged/open PRs relevant to the task

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
Current iBuum Fit app/frontend surface, Base44 product bindings/functions and presentation layer being evolved toward V2.

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
- [x] Session Outcome V1 — PR #27, merge commit `9852a1d233955a97d5e6b61370c88de2464d31a6`
- [x] Training History V1 — PR #28, merge commit `04a81e3b45446d1cc58c780771a0aabe4d7aea1d`
- [x] Progression Engine V1 — PR #29, merge commit `bd55e8852bd7c7252841f9afef91fa4c25645ce2`
- [x] Weekly Training State V1 — internal factual weekly aggregate; contract: `docs/weekly-training-state-v1.md`
- [x] Program Planner V1 — explicit one-week program structure and authoritative context; contract: `docs/program-planner-v1.md`
- [x] Planner / Rescheduling V1 — explicit within-week date changes only; contract: `docs/planner-rescheduling-v1.md`
- [x] Recovery / Daily State Engine V1 — explicit daily self-report and separate factual weekly context; contract: `docs/recovery-daily-state-v1.md`
- [x] Cycle Training History V1 — canonical session snapshots with optional explicit cycle facts; contract: `docs/cycle-training-history-v1.md`
- [x] Cycle Pattern Analyzer V1 — observed personal historical associations with same-session-type evidence guards; contract: `docs/cycle-pattern-analyzer-v1.md`

Canonical pipeline status:

```text
Workout Execution
 -> Session Outcome V1 ✅
 -> Training History V1 ✅
 -> Progression Engine V1 ✅
 -> Weekly Training State V1 ✅
 -> Program Planner V1 ✅
 -> Planner / Rescheduling V1 ✅
 -> Recovery / Daily State Engine V1 ✅
 -> Cycle Training History V1 ✅
 -> Cycle Pattern Analyzer V1 ✅
 -> Personal Memory V1 ← NEXT
```

Current Interpretation Core remains deterministic and Spanish-first. It explains approved decisions; it does not replace the motor.

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

These semantics must not be weakened by Base44 or frontend integration.

---

## 7. Base44 integration status

### Completed contract and bridge implementation

- [x] `docs/base44-integration-contract-v1.md`
- [x] `docs/base44-get-workout-interpretation-prompt-v1.md`
- [x] contract tests for the bridge
- [x] Base44 server-side `getWorkoutInterpretation` Bridge V1 — frontend PR #7, merge commit `8eab5315ef66c86fb327a3361d0f296b2d7fee79`
- [x] local validation of request allowlisting, auth, server-only URL/API-key handling, timeout and error mapping
- [x] approved synthetic cases covered by local Agent fixtures and bridge tests; this does not establish live Base44 runtime acceptance

Approved architecture:

`Base44 UI -> authenticated server-side getWorkoutInterpretation -> POST ${IBUUM_AGENT_URL}/api/v1/interpretation -> recommendation + workout + interpretation + versions -> UI`

Existing Base44 Agent-facing functions such as `getTrainingRecommendation` and `getWorkout` are integration adapters, not decision engines. The implemented bridge remains additive and must not duplicate Training Rules, fatigue/cycle evaluation, exercise selection, interpretation logic or fallback workouts.

### Paused / pending

- [ ] Live Base44 runtime acceptance — paused because Base44 credits/runtime access are currently unavailable
- [ ] Run the approved acceptance cases in the actual Base44 environment, including platform auth/secrets and real connectivity
- [ ] Frontend adoption / UI wiring — pending until live runtime acceptance

The merged implementation preserves the contract's environment distinctions, explicit presenter semantics, server-only secret handling, 45-second deadline, no automatic retry in phase 1, deterministic error envelope and no sensitive payload logging.

### Protected bridge boundaries

The bridge must not:

- call recommendation/workout endpoints separately to reconstruct a competing answer
- re-evaluate fatigue, recovery, cycle, goal, level, equipment or history
- infer presenter from sex/profile
- invent bodyweight or equipment
- collapse omitted/null/empty environment states
- rewrite backend decision fields or interpretation text
- add a second LLM/AI interpretation step
- expose `IBUUM_API_KEY` or trusted server URL to the browser
- trust client-supplied identity as authentication
- change existing Base44 bridge functions except where a separately proven shared safety seam is strictly required
- wire frontend UI before live runtime acceptance
- modify localization, consent, onboarding, Training Engine or progression systems

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
- [x] no browser-language auto-detection
- [x] no automatic guest-to-account promotion
- [x] account/session-change protections

### Language Selection V1 — completed

Merged in frontend PR #4, with auth-boundary hotfix merged in PR #5.

Current approved journey:

`Welcome -> /onboarding/language -> /onboarding/profile -> existing auth/consent/persona onboarding`

Implemented behavior:

- [x] explicit Language Selection screen
- [x] five choices from the canonical locale registry
- [x] native locale names and no flag-based identity
- [x] guest and authenticated explicit selection
- [x] authenticated persistence without caller ownership IDs
- [x] guest persistence using the existing guest boundary
- [x] session-only recovery path when guest storage fails
- [x] retryable authenticated save errors
- [x] `LocalizationProvider` exposes `preferredLocale`, renderable `locale`, `sessionLocale` and validated `setSessionLocale`
- [x] `document.documentElement.lang` follows the renderable locale
- [x] `/onboarding/language` may pass `auth_required` without bypassing `user_not_registered`
- [x] Profile auth/consent semantics remain unchanged
- [x] no browser-language detection
- [x] no domain/training/API behavior changed

### Reviewed Translation Catalogs V1 — completed

Merged in frontend PR #6 (`feat: add Reviewed Translation Catalogs V1`), merge commit `173ac7205c6d90bac3536d528844aed3021f5b63`.

Reviewed active locales:

- [x] `es-ES`
- [x] `en-GB`
- [x] `fr-FR`
- [x] `it-IT`
- [x] `pt-PT`

Implemented contract:

- [x] all five locales are active in the single canonical registry
- [x] all five catalogs are registered in the existing localization core
- [x] exact semantic-key parity across catalogs: 18 reviewed keys
- [x] Spanish remains default and fallback
- [x] unknown/unregistered locale resolves safely to Spanish
- [x] missing active-catalog message retains Spanish fallback and diagnostics
- [x] Welcome renders reviewed localized claim, description, logo alt and CTA
- [x] Language Selection renders localized title, subtitle, CTA, loading/errors and session-only action
- [x] explicit locale selection immediately updates session presentation
- [x] `preferredLocale === resolvedLocale` for the five active locales
- [x] document language follows each locale's configured `htmlLang`
- [x] non-Spanish choices show an explicit partial-coverage notice
- [x] the shared onboarding header retains Spanish `Volver` by default while Language Selection receives a localized accessibility label
- [x] no browser-language detection
- [x] persistence/auth/consent semantics unchanged
- [x] Profile and the rest of onboarding intentionally remain outside this translated surface
- [x] no domain/API/training behavior changed
- [x] no dependencies or lockfiles changed

PR #6 reported 36/36 Node tests passing, build passing, focused lint clean and `git diff --check` passing. Global lint still reports only the pre-existing unused imports in unchanged `ExperienceCard.jsx`.

---

## 9. Current localization limitations / deferred work

- reviewed translations currently cover Welcome and Language Selection only
- Profile, consent and the remainder of onboarding/product surfaces remain primarily Spanish
- authenticated persisted preference hydration is still screen-local on Language Selection rather than global app startup hydration
- no browser locale auto-detection by design
- generated Kai/Kaia/Coach content remains a separate Communication Brain/localization concern
- domain values, API enums, reason codes and persisted training identifiers remain canonical and must never be translated as identifiers

These limitations are accepted for now. **Broad onboarding localization is deferred and is not a blocker for returning to Agent integration and V2 motor-adjacent work.**

---

## 10. Next approved development block

### **Personal Memory V1**

This is the next approved bounded Codex development block in `PatrickJM77777/iBuum-agent`.

Weekly Training State V1 supplies authoritative weekly facts. Program Planner V1 is completed: it dates an explicit caller-approved session template for one contiguous future seven-day week and preserves canonical progression decisions and factual previous-week context.

Program Planner does not reinterpret progression, recalculate weekly state, adapt the template, generate workouts or reschedule unresolved work. Its contract is documented in `docs/program-planner-v1.md`.

Planner / Rescheduling V1 is completed: explicit validated requests move only remaining sessions within the approved program week, preserving program intent and progression decisions. It changes dates only, does not automatically move unresolved work, and is not recovery-aware. Its contract is documented in `docs/planner-rescheduling-v1.md`.

Recovery / Daily State Engine V1 is completed: it preserves explicit daily signals and separate canonical weekly facts, derives factual flags/counts, and provides no readiness score, training recommendation, adaptation, rescheduling or medical interpretation. Its contract is documented in `docs/recovery-daily-state-v1.md`.

Cycle Training History V1 is completed: it attaches only explicit session-linked cycle observations to deeply copied canonical TrainingHistory sessions, preserves every session and its order, and provides factual counts without phase inference, prediction, analysis, training adaptation or medical interpretation. Its contract is documented in `docs/cycle-training-history-v1.md`.

Cycle Pattern Analyzer V1 is completed: it identifies observed personal historical associations for RPE, fatigue and post-session discomfort using only same-session-type comparisons across known phases, with minimum evidence guards. It provides no causal inference, global phase ranking, training adaptation, medical interpretation or cycle prediction. Its contract is documented in `docs/cycle-pattern-analyzer-v1.md`.

Personal Memory V1 is the next approved bounded block and requires a separate closed prompt reviewed against the canonical Architecture Map and Codex workflow. Interaction Memory remains separate and later; Adaptive User Profile, Human Adaptation Profile and Personalization Layer remain later. Weekly Review remains outside these completed domain blocks.

---

## 11. Directional development order from current state

Subject to review after each merged block:

1. Personal Memory V1 — current next approved development block
2. Interaction Memory (separate) / Adaptive User Profile / Human Adaptation Profile / Personalization Layer — later
3. Coach Core / Intent Router / Communication Brain
4. Daily Coach / Weekly Review / Live Workout
5. Specialist systems such as Form Check, Wearables, Nutrition and Voice
6. iBuum for Coach expansion

Base44 bridge implementation, Session Outcome V1, Training History V1, Progression Engine V1, Weekly Training State V1, Program Planner V1, Planner / Rescheduling V1, Recovery / Daily State Engine V1, Cycle Training History V1 and Cycle Pattern Analyzer V1 are complete. Live Base44 runtime acceptance remains paused until credits/runtime access are available; frontend adoption remains pending until that acceptance.

Additional onboarding localization can proceed later in separate bounded groups when product priority requires it; it is no longer an immediate prerequisite for Agent integration.

This order is directional, not permission to bundle multiple blocks into one PR.

---

## 12. Major V2 blocks — completed / pending

- [x] Session Outcome V1
- [x] Training History V1
- [x] Progression Engine V1
- [x] Weekly Training State V1
- [x] Program Planner V1
- [x] Planner / Rescheduling V1
- [x] Recovery / Daily State Engine V1
- [x] Cycle Training History V1
- [x] Cycle Pattern Analyzer V1
- [ ] Personal Memory V1 — NEXT
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

The canonical efficiency rule remains:

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

**Prepare the closed Codex prompt for Personal Memory V1, using the canonical Architecture Map, Codex workflow and completed domain documentation, including Cycle Pattern Analyzer V1.**

Keep this to one bounded block per Codex execution. Personal Memory V1 implementation requires that separate approved prompt. Live Base44 runtime acceptance remains paused, and frontend adoption remains pending until acceptance.

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
