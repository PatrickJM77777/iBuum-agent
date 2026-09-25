# iBuum Fit — Codex Development Workflow v1.0

**Status:** Canonical operational workflow  
**Applies to:** iBuum Fit V2, iBuum Agent, iBuum Fit frontend/web, iBuum Digital web and future connected repositories  
**Architecture reference:** `docs/ibuum-fit-v2-architecture-map-v1.md`

This document defines the canonical development workflow for implementation work executed by Codex.

## 1. Core workflow

```text
GitHub review
    -> exact change definition
    -> closed Codex prompt
    -> Codex implementation
    -> tests / acceptance checks
    -> Pull Request
    -> direct GitHub review
    -> human approval
    -> merge
```

Operationally:

1. Review the real current GitHub state before defining work.
2. Define the exact requested change and its architectural owner.
3. Produce a closed, implementation-ready prompt for Codex.
4. Codex implements only that scope and creates a Pull Request.
5. Review the PR directly in GitHub, including changed files, behavior, tests and architecture boundaries.
6. Merge only after human approval.

Codex is the implementation programmer. It must not invent product architecture, expand scope autonomously, duplicate domain logic in another layer, or merge automatically unless explicitly authorized.

## 2. One small block per execution

Default rule:

**One bounded architectural block per Codex execution.**

Each execution must be intentionally small enough to review, test and revert independently.

Avoid combining unrelated features, migrations, refactors or architectural layers into one task merely because they are adjacent in the roadmap.

Examples of valid small blocks:

- `preferred_locale` persistence contract only
- one Base44 bridge function only
- Session Outcome V1 only
- one API endpoint plus its dedicated contract tests
- one deterministic engine refinement with focused regression coverage

Examples of invalid oversized tasks:

- localization + full onboarding translation + backend locale storage + Kai language behavior in one PR
- Session Outcome + Training History + Progression Engine in one PR
- Form Check + camera UX + safety + premium entitlements + training adaptation in one PR

## 3. Required contents of every Codex prompt

Every implementation prompt must define, as applicable:

### A. Objective
A single, explicit outcome.

### B. Canonical architecture reference
The task must remain consistent with `iBuum Fit V2 Architecture Map v1.0`.

### C. Scope
What Codex is allowed to implement.

### D. Out of scope
What Codex must not touch, infer or redesign.

### E. Allowed files or areas
When practical, identify the files/directories that may change. If discovery is required, Codex may inspect first but must keep implementation within the approved architectural area.

### F. Protected boundaries
State the contracts or systems that must remain unchanged, for example:

- Training Engine authority
- public API shape
- authentication
- canonical domain codes
- Base44 behavior
- existing persisted values
- unrelated UI
- existing routes

### G. Acceptance criteria
Define observable completion conditions.

### H. Tests
Specify the focused test suites and regressions that must pass.

### I. STOP condition
Codex must stop after the requested implementation, validation and PR preparation.

It must not continue into the next roadmap phase without a new approved prompt.

## 4. GitHub-first rule

Before issuing a Codex implementation prompt, inspect the current repository state when that state can materially affect the task.

Do not rely on an old conversation description when GitHub can provide the current truth.

Typical pre-work checks may include:

- latest merged PRs
- current `main`
- relevant implementation files
- existing tests
- current contracts/docs
- open PRs that may overlap

The same rule applies after Codex completes work: review the actual PR in GitHub rather than relying only on Codex's summary.

## 5. Prompt closure rule

Codex prompts should be closed enough that implementation decisions are constrained by approved architecture.

A good prompt tells Codex:

```text
what to build
where it belongs
what must remain unchanged
how success is measured
which tests prove it
where to stop
```

Avoid broad prompts such as:

> Improve the app architecture and add multilingual support.

Prefer bounded prompts such as:

> Add `preferred_locale` persistence using the existing Localization Foundation V1. Do not add a language-selection screen, translations, browser detection or backend communication localization. Preserve all domain codes and onboarding behavior. Add focused tests, document the contract, create a PR and stop.

## 6. Credit/time efficiency rule

Codex usage is a constrained development resource. The workflow should minimize unnecessary exploration and repeated work.

Therefore:

- review GitHub before asking Codex to rediscover known facts;
- avoid asking Codex to propose multiple architectures when one has already been approved;
- avoid broad repo-wide refactors unless specifically required;
- avoid re-running unrelated expensive validations when focused validation plus required regression suites is sufficient;
- reuse existing contracts, models, test patterns and architecture docs;
- prefer one clear implementation path over multiple speculative alternatives;
- stop after the approved block is complete.

Efficiency must never justify weakening safety, tests or architectural boundaries.

## 7. PR requirements

Unless explicitly authorized otherwise, each Codex task should finish with a Pull Request suitable for human review.

The PR should state:

- what changed;
- why it changed;
- architectural boundary preserved;
- files/areas affected;
- validation performed;
- known limitations;
- explicit out-of-scope items;
- whether any production/runtime behavior changed.

Default final instruction:

**Ready for human review. Do not merge automatically.**

## 8. Review rule

A Codex implementation is not accepted because Codex reports that tests passed.

Review should verify directly in GitHub, as relevant:

- changed files match scope;
- no protected area changed unexpectedly;
- implementation matches the canonical contract;
- tests actually cover the intended behavior;
- no domain logic was duplicated in UI/presentation layers;
- API/domain semantics remain correct;
- no secrets or sensitive data were added;
- PR has stopped at the requested phase.

## 9. Change sequencing

When a larger feature requires multiple layers, split it into ordered PRs.

Example:

```text
Contract
  -> internal implementation
  -> focused tests
  -> API/integration boundary
  -> frontend adoption
  -> UX expansion
```

Do not collapse these phases unless there is a clear technical reason and the expanded scope is explicitly approved before Codex starts.

## 10. Canonical operating rule

For future development work, the default operating sequence is:

**I review GitHub -> define the exact change -> provide a closed Codex prompt -> Codex implements and creates a PR -> I review the PR directly in GitHub -> human approval -> merge.**

And the default execution size is:

**one small block, explicit scope, allowed/protected areas, focused tests and a hard STOP condition.**

Any deviation from this workflow should be intentional and stated before implementation begins.
