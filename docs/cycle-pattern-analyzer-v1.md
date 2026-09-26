# Cycle Pattern Analyzer V1

Cycle Pattern Analyzer V1 identifies observed personal historical associations.
It does NOT prove that menstrual phase caused a difference.
It does NOT rank phases globally.
It does NOT recommend changing training.
It does NOT interpret a phase as reduced capacity.
It compares only the same session type.
It requires minimum evidence before emitting a pattern.
An empty pattern list does NOT mean "the cycle has no effect."

## Purpose and architecture

`Cycle Context -> Cycle Training History -> Cycle Pattern Analyzer V1 -> future personalized cycle context`

This internal pure analyzer follows Architecture Map section 17 and preserves
`MOTOR DECIDES -> INTERPRETATION EXPLAINS -> UI PRESENTS`.
Personal history must provide sufficient comparable evidence before an observed
personal association is emitted. There is no universal menstrual-phase rule.
The immediate-decision path remains separate and unchanged:
`explicit current Cycle Context -> normalize_cycle_context -> Training Rules -> Training Engine`.
The analyzer never imports or calls those services.

## Input and output contracts

`analyze_cycle_patterns(data: CyclePatternAnalyzerInput) -> CyclePatternAnalysis`
lives in `app/services/cycle_pattern_analyzer.py`. The model module exposes
`CYCLE_PATTERN_ANALYZER_VERSION = "cycle-pattern-analyzer-v1"` and the five evidence
policy constants below. All five new models use `ConfigDict(extra="forbid")`.

Input has exactly `cycle_history: CycleTrainingHistory`, requiring an actual
canonical instance; raw nested dictionaries are rejected. Empty history is valid.
There are no additional profile/current-cycle inputs, dates, prediction horizon,
TrainingHistory reconstruction or DailyRecoveryState dependencies.

Output has exactly:

- analyzer_version: literal cycle-pattern-analyzer-v1;
- source_cycle_history_version: literal cycle-training-history-v1, copied from input;
- phase_evidence: list[CyclePhaseEvidence];
- patterns: list[CycleObservedPattern];
- summary: CyclePatternAnalysisSummary.

Phase evidence always has exactly five entries, validated in order: menstruation,
follicular, ovulation, luteal, unknown. Zero-observation phases remain present.
Missing cycle context contributes to no phase; explicit unknown is preserved only
in descriptive evidence and inventory, never in a pattern comparison.

CyclePhaseEvidence has exactly phase; observed_sessions; completed_sessions;
interrupted_sessions; sessions_with_known_rpe; mean_session_rpe;
sessions_with_known_fatigue; mean_fatigue_after;
sessions_with_known_post_discomfort; moderate_high_post_discomfort_sessions;
moderate_high_post_discomfort_ratio; sessions_with_known_cycle_discomfort;
moderate_high_cycle_discomfort_sessions; moderate_high_cycle_discomfort_ratio.
Counts are strict nonnegative integers. Nullable means are strict finite floats
in 1..10 for RPE and 1..5 for fatigue; nullable ratios are strict finite floats in 0..1.

Observed sessions have that exact explicit phase. Completion counts use canonical
completion_state. Feedback metrics count only non-None values. Means use the
arithmetic mean of known values; zero known values yield None. Each discomfort
ratio divides moderate/high observations by known observations; none/mild remain
known and contribute zero to the numerator. A zero denominator yields None.
Cycle-context discomfort is descriptive only and stays separate from canonical
SessionFeedback.discomfort_after, the post-session training-response fact.
Neither overwrites or fills gaps in the other.

## Same-session-type evidence policy

Each pattern compares one known phase, one known session_type and one metric
against that same session_type across all other three known phases combined.
Unknown phases, missing contexts and None session_type never enter either sample.
Untyped sessions may still contribute to phase evidence. No session type or phase
is inferred. Completed and interrupted sessions both contribute known feedback;
completion state itself is not a pattern metric.

Only three metrics are analyzed:

| Metric | Sample value | Difference threshold |
| --- | --- | --- |
| session_rpe | Known feedback.session_rpe | RPE_MEAN_DIFFERENCE_THRESHOLD = 1.5 |
| fatigue_after | Known feedback.fatigue_after | FATIGUE_MEAN_DIFFERENCE_THRESHOLD = 1.0 |
| post_session_discomfort | Known feedback.discomfort_after: moderate/high = 1, none/mild = 0 | POST_DISCOMFORT_RATIO_DIFFERENCE_THRESHOLD = 0.30 |

Each metric independently requires MIN_PHASE_METRIC_SAMPLES = 4 target values and
MIN_COMPARATOR_METRIC_SAMPLES = 8 comparator values. Missing feedback excludes only
that metric sample. Nothing is imputed or treated as zero. These are conservative
product/domain evidence guards, not clinical thresholds or scientific proof.
There is no statistical-significance claim.

All derived means and ratios use round(value, 4). Each phase_value and comparator_value
is rounded first; difference is round(phase_value - comparator_value, 4). A pattern
is emitted only when abs(difference) >= the metric threshold, including equality.
Positive differences produce higher; negative differences produce lower.
The post-discomfort ratio association does not represent injury or medical risk.
There are no percentages, formatted numbers or localized output strings.

CycleObservedPattern has exactly phase (four known phases only), session_type,
metric, direction (higher/lower), phase_sample_size, comparator_sample_size,
phase_value, comparator_value, difference and threshold. Sample sizes are strict
nonnegative integers; the four numeric values are strict finite floats.
Patterns mean only that this user's recorded metric differed from their other
known phases for this same type by the V1 threshold with sufficient samples.

Construction order is fixed: menstruation, follicular, ovulation, luteal; then
upper_body, lower_body, full_body, cardio, mobility; then session_rpe, fatigue_after,
post_session_discomfort. Source session or timestamp order never controls output
pattern order. No arbitrary string sorting or phase ranking occurs.

## Summary and insufficient evidence

The summary has exactly these strict nonnegative counts:

- total_sessions, sessions_with_cycle_context, sessions_without_cycle_context and
  unknown_phase_sessions: copied from canonical history summary;
- known_phase_sessions: sum of the four known phase counts in that summary;
- sessions_eligible_for_pattern_analysis: records with a known phase and non-None
  session_type, regardless of feedback (inventory only);
- detected_patterns: list length;
- rpe_patterns, fatigue_patterns, post_session_discomfort_patterns: counts by metric.

Validation enforces total = with-context + without-context; with-context = known +
unknown; detected patterns = sum of the three metric counts; eligible <= known.
Empty patterns can reflect insufficient comparable samples, missing feedback,
differences below threshold or no eligible same-type comparison. No global
conclusion, best/worst phase or capacity interpretation is produced.

## Determinism, minimization and limitations

Repeated validated input yields identical output, including after reordering
records. Stable summation avoids source-order-dependent floating-point accumulation.
Evidence, patterns and summary are newly allocated; no source sessions, contexts,
feedback or exercise/set data are mutated or referenced by mutable output objects.
Output edits cannot affect input or subsequent analyses. Mutable output edits do
not automatically recalculate derived values. Normally validated canonical objects
are expected; model_construct and post-validation input mutation are not ingestion
interfaces. Upstream summaries are trusted. The service owns cross-model derivation;
models validate shape, phase inventory/order and summary count invariants.

Associations are descriptive, not causal. Same-type comparison reduces obvious
workout-type confounding but does not control exercise choice, load, effort targets,
reporting bias or other influences. V1 does not analyze duration, load, reps, volume,
adherence, performance or cycle-context discomfort as response patterns. It does
not predict phase, dates, cycle length, ovulation or fertile windows. There is no
medical interpretation, diagnosis, statistical inference, recommendation, training
adaptation, readiness score or integration into current Training Rules.

No system clock, date arithmetic, filesystem/network access, persistence, API,
Base44/frontend changes, LLM, notifications, wearables or deployment are introduced.
Only canonical history is consumed; no identity/contact, free-text cycle notes,
fertility, pregnancy, contraception, sexual-health, hormone or diagnosis fields are
added. Future personalized-cycle-context integration requires a separate contract.
Personal Memory V1 is the next expected bounded block. Interaction Memory and the
profile/personalization layers remain separate later work. Live Base44 acceptance
remains paused/pending and frontend adoption remains pending.

## Exact files and validation

Exactly five files change:

- app/models/cycle_pattern_analyzer.py
- app/services/cycle_pattern_analyzer.py
- tests/test_cycle_pattern_analyzer.py
- docs/cycle-pattern-analyzer-v1.md
- docs/ibuum-fit-v2-current-status.md

Focused parametrized tests cover canonical input, exact models, strict counts and
finite ranges, phase inventories, missing/unknown separation, known metric counts,
means/ratios and rounding, same-type boundaries, metric-specific minimum samples,
positive/negative/exact thresholds, comparator composition, canonical ordering,
summary invariants, ignored non-metrics, determinism, isolation and import/call
boundaries. Final Git inventory verifies five changed files and protected files.

```text
pytest -q tests/test_cycle_pattern_analyzer.py
pytest -q
python -m compileall app tests
git diff --check
```

Run full regression once after focused tests pass.
