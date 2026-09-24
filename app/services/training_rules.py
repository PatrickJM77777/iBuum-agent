"""
Training Rules V1 — deterministic decision engine.

This is NOT a workout generator. It decides four things:
  - action:              train / recovery / rest / request_more_data
  - recommended_session:  a coarse session category
  - intensity:            an intensity ceiling
  - duration_minutes
and attaches machine-readable reason_codes explaining why.

--------------------------------------------------------------------------
PRIORITY HIERARCHY (highest wins; a lower tier can never override a
decision already made by a higher tier)
--------------------------------------------------------------------------
  1. Fatigue / Recovery   (app/services/training_rules.py: _apply_fatigue)
  2. Cycle Context         (_apply_cycle_context)
  3. Recent Session        (_apply_recent_session)
  4. Training Level        (_apply_training_level)
  5. Training Objective     (_apply_goal)
  6. Weekly Frequency       (_apply_weekly_frequency)
  7. Finalize / invariants  (_finalize) — always runs, cannot be skipped

Tiers 1 and 2 are grouped as "safety" constraints: either can end the
pipeline early (fatigue -> rest) or force it onto a non-train path
(cycle -> recovery), in which case tiers 3-6 are skipped entirely
(they only ever refine a *training* session, never second-guess a
safety decision already made above them).

Tiers 3-6 never set `action`. They only narrow an "intensity ceiling"
(which can only ever go down, never up) and shape the session category
and duration. This is what makes a higher-priority rule's decision
impossible to override from below: nothing later in the pipeline is
capable of raising intensity past a ceiling a safety rule already set,
or of turning a `rest`/`recovery` action back into `train`.
"""

from dataclasses import dataclass, field

from app.core.config import get_settings
from app.models.training_request import (
    Goal,
    SessionType,
    TrainingLevel,
    TrainingRecommendationRequest,
)
from app.models.training_response import (
    Action,
    Intensity,
    ReasonCode,
    RecommendedSession,
    TrainingRecommendationResponse,
)
from app.services.cycle_context import NormalizedCycleContext, normalize_cycle_context

# --- tunable constants (deterministic, no magic numbers scattered around) -

BASE_DURATION_MINUTES = 45
FATIGUE4_DURATION_CAP = 30
RECOVERY_DURATION_CAP = 20
CYCLE_MODERATE_DURATION_CAP = 35
HIGH_FREQUENCY_DURATION_CAP = 30

_INTENSITY_ORDER = [Intensity.low, Intensity.moderate, Intensity.high]

# Tier 5 (Goal): the base intensity a goal would ask for, BEFORE any
# higher-priority ceiling is applied. This is the only place "high"
# intensity can originate — it is always still subject to being capped
# by fatigue, a genuine recovery conflict, training level, or cycle
# context above it. High intensity therefore requires: low fatigue, no
# recent-session conflict, and (for beginners) never applies at all.
BASE_INTENSITY_BY_GOAL: dict[Goal, Intensity] = {
    Goal.general_fitness: Intensity.moderate,
    Goal.fat_loss: Intensity.moderate,
    Goal.muscle_gain: Intensity.high,
    Goal.strength: Intensity.high,
    Goal.endurance: Intensity.moderate,
    Goal.mobility: Intensity.low,
}

# Tier 5 (Goal): coarse session-category preference. Only used when no
# higher-priority rule (recent session conflict) has already fixed the
# session category. Deliberately generic — this is NOT workout
# programming, just a category pick among the existing enum values.
#
# `full_body` is only used as the default for goals in this set, and only
# at low weekly frequency (<=2 days) — see _select_preferred_session().
# It must never be a blind/generic default at 3+ days/week.
_FULL_BODY_STYLE_GOALS = {
    Goal.general_fitness,
    Goal.fat_loss,
    Goal.muscle_gain,
    Goal.strength,
}


def _select_preferred_session(request: TrainingRecommendationRequest) -> RecommendedSession:
    """
    Tier 5 (Goal) session pick, only used when Tier 3 (Recent Session) left
    the category undetermined (i.e. no <24h same-muscle-group conflict).

    training_days_per_week is read here as *context* for the Goal tier's
    own decision (it does not let Tier 6 / Weekly Frequency override
    anything — that tier still only ever touches duration).
    """
    if request.goal == Goal.endurance:
        return RecommendedSession.cardio
    if request.goal == Goal.mobility:
        return RecommendedSession.mobility

    # goal in _FULL_BODY_STYLE_GOALS
    if request.training_days_per_week <= 2:
        # Infrequent training: a complete full-body session is reasonable.
        return RecommendedSession.full_body

    # 3+ days/week: full_body must never be the generic default. Use
    # whatever real signal exists (even an old, non-conflicting last
    # session) to rotate sensibly; otherwise fall back to the one category
    # that's safe and appropriate regardless of goal, without guessing a
    # muscle-group split we have no information to justify.
    last_type = request.last_session_type
    if last_type == SessionType.upper_body:
        return RecommendedSession.lower_body
    if last_type == SessionType.lower_body:
        return RecommendedSession.upper_body
    return RecommendedSession.mobility


def _cap_intensity(intensity: Intensity, ceiling: Intensity) -> Intensity:
    """Return the lower of the two intensities (never allow an increase)."""
    if _INTENSITY_ORDER.index(intensity) > _INTENSITY_ORDER.index(ceiling):
        return ceiling
    return intensity


@dataclass
class _State:
    """Internal, mutable working state for one pipeline run."""

    action: Action = Action.train
    recommended_session: RecommendedSession | None = None
    duration_base: int = BASE_DURATION_MINUTES
    duration_ceiling: int = BASE_DURATION_MINUTES
    intensity_ceiling: Intensity = Intensity.high
    needs_more_data: bool = False
    reason_codes: list = field(default_factory=list)

    def add_reason(self, code: ReasonCode) -> None:
        if code not in self.reason_codes:
            self.reason_codes.append(code)

    def lower_intensity_ceiling(self, ceiling: Intensity) -> bool:
        """Lower the ceiling if `ceiling` is stricter. Returns True if it changed."""
        new_ceiling = _cap_intensity(self.intensity_ceiling, ceiling)
        changed = new_ceiling != self.intensity_ceiling
        self.intensity_ceiling = new_ceiling
        return changed

    def lower_duration_ceiling(self, minutes: int) -> None:
        self.duration_ceiling = min(self.duration_ceiling, minutes)


# --------------------------------------------------------------------
# Tier 1 — Fatigue / Recovery
# --------------------------------------------------------------------


def _apply_fatigue(state: _State, request: TrainingRecommendationRequest) -> None:
    fatigue = request.fatigue_level

    if fatigue >= 5:
        state.action = Action.rest
        state.add_reason(ReasonCode.HIGH_FATIGUE)
        return  # terminal: nothing below this tier may run

    if fatigue == 4:
        # Fatigue itself (regardless of cause) reduces intensity/duration.
        # This is NOT recovery evidence — INSUFFICIENT_RECOVERY is reserved
        # for actual recovery-conflict signals (see _apply_recent_session),
        # since fatigue can come from many non-training causes.
        state.lower_intensity_ceiling(Intensity.low)
        state.lower_duration_ceiling(FATIGUE4_DURATION_CAP)
        state.add_reason(ReasonCode.MODERATE_FATIGUE)
    elif fatigue == 3:
        # "Avoid unnecessary high intensity" — cap at moderate, no duration cut.
        state.lower_intensity_ceiling(Intensity.moderate)
        state.add_reason(ReasonCode.MODERATE_FATIGUE)
    else:
        # fatigue 1-2: normal training eligibility, no ceiling reduction.
        state.add_reason(ReasonCode.LOW_FATIGUE)


# --------------------------------------------------------------------
# Tier 2 — Cycle Context (safety/context tier, alongside fatigue)
# --------------------------------------------------------------------


def _apply_cycle_context(state: _State, cycle: NormalizedCycleContext) -> None:
    if state.action != Action.train:
        return  # already resting; a safety decision above stands.

    if not cycle.available:
        return

    if cycle.requires_more_data:
        state.needs_more_data = True

    for reason_code in cycle.reason_codes:
        state.add_reason(reason_code)

    if cycle.action is not None:
        state.action = cycle.action
    if cycle.recommended_session is not None:
        state.recommended_session = cycle.recommended_session
    if cycle.intensity_ceiling is not None:
        state.lower_intensity_ceiling(cycle.intensity_ceiling)
    if cycle.duration_ceiling is not None:
        state.lower_duration_ceiling(cycle.duration_ceiling)


# --------------------------------------------------------------------
# Tier 3 — Recent Session
# --------------------------------------------------------------------


def _apply_recent_session(state: _State, request: TrainingRecommendationRequest) -> None:
    if state.action != Action.train:
        return  # session category already decided by a higher tier.

    last_type = request.last_session_type
    hours = request.hours_since_last_session
    demanding_types = (SessionType.upper_body, SessionType.lower_body)

    if last_type not in demanding_types:
        # unknown/full_body/cardio/mobility/rest/None: no muscle-group
        # conflict is possible, leave the session category undetermined
        # for the Goal tier to decide.
        if hours is not None:
            state.add_reason(ReasonCode.RECOVERY_WINDOW_OK)
        return

    opposite = (
        RecommendedSession.upper_body
        if last_type == SessionType.lower_body
        else RecommendedSession.lower_body
    )

    if hours is None:
        # We know a demanding session happened but not when. Don't invent
        # a recovery window — flag it, stay conservative, and treat
        # recovery status as unconfirmed (caps intensity like a genuine
        # conflict, since we cannot rule one out).
        state.needs_more_data = True
        state.add_reason(ReasonCode.INSUFFICIENT_DATA)
        state.lower_intensity_ceiling(Intensity.moderate)
        state.recommended_session = opposite
        return

    if hours < 24:
        # A genuine recovery conflict: this is real recovery evidence, so
        # it caps intensity (high intensity requires "no recent-session
        # conflict" — see BASE_INTENSITY_BY_GOAL) in addition to steering
        # the session category away from the same muscle group.
        state.recommended_session = opposite
        state.lower_intensity_ceiling(Intensity.moderate)
        state.add_reason(ReasonCode.INSUFFICIENT_RECOVERY)
        if last_type == SessionType.lower_body:
            state.add_reason(ReasonCode.RECENT_LOWER_BODY_SESSION)
        else:
            state.add_reason(ReasonCode.RECENT_UPPER_BODY_SESSION)
    else:
        state.add_reason(ReasonCode.RECOVERY_WINDOW_OK)


# --------------------------------------------------------------------
# Tier 4 — Training Level
# --------------------------------------------------------------------


def _apply_training_level(state: _State, request: TrainingRecommendationRequest) -> None:
    if state.action != Action.train:
        return

    if request.training_level == TrainingLevel.beginner:
        if state.lower_intensity_ceiling(Intensity.moderate):
            state.add_reason(ReasonCode.BEGINNER_INTENSITY_LIMIT)


# --------------------------------------------------------------------
# Tier 5 — Training Objective (Goal)
# --------------------------------------------------------------------


def _apply_goal(state: _State, request: TrainingRecommendationRequest) -> Intensity:
    """Returns the goal's requested base intensity (before ceilings apply)."""
    if state.recommended_session is None:
        state.recommended_session = _select_preferred_session(request)

    if state.action != Action.train:
        return Intensity.not_applicable

    return BASE_INTENSITY_BY_GOAL[request.goal]


# --------------------------------------------------------------------
# Tier 6 — Weekly Frequency (duration shaping only)
# --------------------------------------------------------------------


def _apply_weekly_frequency(state: _State, request: TrainingRecommendationRequest) -> None:
    if state.action != Action.train:
        return

    days = request.training_days_per_week
    if days <= 2:
        # Infrequent training: a complete, full-length session is fine.
        state.add_reason(ReasonCode.LOW_WEEKLY_FREQUENCY)
    elif days >= 5:
        # Frequent training: favor shorter sessions rather than raising
        # cumulative weekly load.
        state.lower_duration_ceiling(HIGH_FREQUENCY_DURATION_CAP)
        state.add_reason(ReasonCode.HIGH_WEEKLY_FREQUENCY)
    # 3-4 days/week: baseline, no adjustment, no reason code needed.


# --------------------------------------------------------------------
# Tier 7 — Finalize / hard invariants (always runs)
# --------------------------------------------------------------------


def _finalize(
    state: _State, goal_base_intensity: Intensity, agent_version: str
) -> TrainingRecommendationResponse:
    # --- Hard invariant: INSUFFICIENT_DATA must always mean needs_more_data.
    if ReasonCode.INSUFFICIENT_DATA in state.reason_codes:
        state.needs_more_data = True

    if state.action == Action.rest:
        # Hard invariant: rest is never anything but fully inactive.
        return TrainingRecommendationResponse(
            action=Action.rest,
            recommended_session=RecommendedSession.rest,
            intensity=Intensity.not_applicable,
            duration_minutes=0,
            reason_codes=state.reason_codes,
            needs_more_data=state.needs_more_data,
            agent_version=agent_version,
        )

    if state.action == Action.recovery:
        # Hard invariant: recovery never reaches high intensity, no matter
        # what any upstream tier computed.
        intensity = _cap_intensity(state.intensity_ceiling, Intensity.moderate)
        return TrainingRecommendationResponse(
            action=Action.recovery,
            recommended_session=state.recommended_session or RecommendedSession.mobility,
            intensity=intensity,
            duration_minutes=min(state.duration_base, state.duration_ceiling),
            reason_codes=state.reason_codes,
            needs_more_data=state.needs_more_data,
            agent_version=agent_version,
        )

    # action == train
    intensity = _cap_intensity(goal_base_intensity, state.intensity_ceiling)
    return TrainingRecommendationResponse(
        action=Action.train,
        recommended_session=state.recommended_session or RecommendedSession.full_body,
        intensity=intensity,
        duration_minutes=min(state.duration_base, state.duration_ceiling),
        reason_codes=state.reason_codes,
        needs_more_data=state.needs_more_data,
        agent_version=agent_version,
    )


def run_pipeline(
    request: TrainingRecommendationRequest, agent_version: str
) -> TrainingRecommendationResponse:
    """Run the deterministic Training Rules V1 pipeline."""
    state = _State()
    cycle = normalize_cycle_context(
        request,
        moderate_duration_cap=CYCLE_MODERATE_DURATION_CAP,
        recovery_duration_cap=RECOVERY_DURATION_CAP,
    )

    _apply_fatigue(state, request)
    _apply_cycle_context(state, cycle)
    _apply_recent_session(state, request)
    _apply_training_level(state, request)
    goal_base_intensity = _apply_goal(state, request)
    _apply_weekly_frequency(state, request)

    return _finalize(state, goal_base_intensity, agent_version)


def evaluate(request: TrainingRecommendationRequest) -> TrainingRecommendationResponse:
    """Run the full Training Rules V1 pipeline and return the recommendation."""
    return run_pipeline(request, get_settings().agent_version)
