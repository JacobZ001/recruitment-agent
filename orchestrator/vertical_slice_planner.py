"""
Deterministic vertical-slice workflow policy for recruiter orchestration.

Purpose
-------
Map canonical bus :class:`~interfaces.event_bus_interface.EventEnvelope` records
plus the current :class:`~schemas.state_schema.OrchestrationState` snapshot into an
:class:`~orchestrator.orchestrator.OrchestrationPlan` (transitions, bounded skills,
and optional emissions). This module is **policy only**: it does not execute plans,
call the transition engine, publish events, or touch persistence.

Boundaries
----------
- **In scope**: explicit event → plan tables, idempotent-ish handling of duplicate
  ingress signals, stable skill name strings, ``event:<name>`` triggers aligned with
  ``state_machine.transition_engine`` naming rules, ``human_override`` passthrough
  from envelope extensions/payload for governance compatibility.
- **Out of scope**: LLM calls, scoring math, ranking, autonomous routing, mutation of
  ``OrchestrationState``, transition validation (the orchestrator + engine own that),
  clocks/randomness, async.

Deterministic workflow policy philosophy
-----------------------------------------
Programs decide *what should happen next* given typed facts (event + state snapshot).
The planner never interprets CV content or scores; it only names **which** registered
skills to invoke and **which** graph edge to request. Bounded behavior: each path
returns a small fixed upper bound of skills and emissions.

Scoring stage progression semantics
-----------------------------------
**Light scoring** (early pipeline): when ``light_scoring_completed`` arrives in
``hard_filter_passed``, the slice advances to ``light_scored`` and schedules the
questionnaire leg (emission ``questionnaire_requested``)—mirroring
``hard_filter_passed_to_light_scored`` in the default transition registry.

**Deep scoring** (post-questionnaire): ``deep_scoring_completed`` is modeled as the
**completion of the deep scoring gate after questionnaire work**, i.e. the edge
``questionnaire_completed`` → ``deep_scored`` (registry rule
``questionnaire_completed_to_deep_scored``). Entering ``deep_scored`` is distinct
from **shortlisting** (``deep_scored`` → ``shortlisted``), which is a separate
registry edge and is **not** bound to ``deep_scoring_completed`` in this slice
unless a future explicit event path is added.

Questionnaire stage semantics
-----------------------------
The default pipeline registry advances the questionnaire **leg** as three edges:
``light_scored`` → ``questionnaire_pending`` → ``questionnaire_sent`` →
``questionnaire_completed``. The slice binds ingress events to those edges so
``questionnaire_completed`` (schema ``questionnaire_completed``) is reachable before
``deep_scoring_completed`` can fire: deep scoring is strictly **after** the
questionnaire phase snapshot is ``questionnaire_completed``.


Relationship to orchestrator / transition engine
------------------------------------------------
:class:`~orchestrator.orchestrator.Orchestrator` calls ``plan(...)`` then validates
``ProposedTransition`` via :class:`state_machine.transition_engine.TransitionEngine`.
This planner therefore **must** emit triggers and from/to pairs that exist in the
wired registry (typically ``default_pipeline_registry()``). One deliberate semantic
compression exists for ``hard_filter_failed`` (see ``plan`` implementation notes).
``deep_scoring_completed`` is aligned with ``questionnaire_completed_to_deep_scored``,
not ``deep_scored_to_shortlisted``. Questionnaire ingress events mirror
``light_scored_to_questionnaire_pending``, ``questionnaire_pending_to_sent``, and
``questionnaire_sent_to_completed`` so the deep scoring hop is reachable in order.

Replay expectations
---------------------
The planner is pure in ``state`` + ``envelope`` + ``delivery`` (delivery is accepted
for interface symmetry; this implementation ignores ``delivery`` except via future
extensions). Replay runs must supply the same envelopes and state snapshots the
live slice would have observed at each step; the planner does not consult wall-clock
time or external IO.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from interfaces.event_bus_interface import DeliveryContext, EventEnvelope

from .orchestrator import (
    OrchestrationEmissionDraft,
    OrchestrationPlan,
    ProposedTransition,
    SkillInvocationSpec,
)
from interfaces.skill_interface import SkillInputEnvelope
from schemas.state_schema import DecisionActorType, OrchestrationState, PipelinePhase, StateActor, StateDomain


# Stable skill identifiers — must match keys in the orchestrator skill registry wiring.
SKILL_CANDIDATE_CREATED = "recruitment.vertical_slice.candidate_created"
SKILL_CV_UPLOADED = "recruitment.vertical_slice.cv_uploaded"
SKILL_CV_PARSED = "recruitment.vertical_slice.cv_parsed"
SKILL_HARD_FILTER = "recruitment.vertical_slice.hard_filter"
SKILL_LIGHT_SCORING = "recruitment.vertical_slice.light_scoring"
SKILL_DEEP_SCORING = "recruitment.vertical_slice.deep_scoring"
SKILL_QUESTIONNAIRE_STAGE = "recruitment.vertical_slice.questionnaire_stage"


def _event_trigger(name: str) -> str:
    return f"event:{name}"


def _system_actor(envelope: EventEnvelope) -> StateActor:
    actor_id = envelope.metadata.actor_id if envelope.metadata else None
    return StateActor(actor_type=DecisionActorType.SYSTEM, actor_id=actor_id)


def _human_override(envelope: EventEnvelope) -> bool:
    if envelope.extensions and envelope.extensions.get("human_override") is True:
        return True
    if envelope.payload and envelope.payload.get("human_override") is True:
        return True
    return False


def _skill_input(
    *,
    planner_path: str,
    envelope: EventEnvelope,
    extras: Optional[Dict[str, Any]] = None,
) -> SkillInputEnvelope:
    payload: Dict[str, Any] = {
        "vertical_slice.planner_path": planner_path,
        "ingested_event_id": str(envelope.event_id),
        "ingested_event_type": envelope.event_type,
    }
    if extras:
        payload.update(extras)
    return SkillInputEnvelope(payload=payload)


class VerticalSlicePlanner:
    """
    First runnable recruiter vertical-slice :class:`OrchestrationStepPlanner`.

    Implements a conservative subset of pipeline progression aligned with
    ``default_pipeline_registry()`` edges in ``state_machine.transition_engine``.

    **Scoring**: light completion advances ``hard_filter_passed`` → ``light_scored``;
    deep completion advances ``questionnaire_completed`` → ``deep_scored`` (not
    directly to ``shortlisted``). **Questionnaire**: explicit events advance
    ``light_scored`` → ``questionnaire_pending`` → ``questionnaire_sent`` →
    ``questionnaire_completed`` per the default registry.
    """

    def plan(
        self,
        *,
        state: OrchestrationState,
        envelope: EventEnvelope,
        delivery: DeliveryContext,
    ) -> OrchestrationPlan:
        _ = delivery  # Accepted for protocol symmetry; deterministic slice ignores it today.
        et = envelope.event_type
        phase = state.pipeline.phase

        if et == "candidate_created":
            return self._plan_candidate_created(phase, envelope)
        if et == "cv_uploaded":
            return self._plan_cv_uploaded(phase, envelope)
        if et == "cv_parsed":
            return self._plan_cv_parsed(phase, envelope)
        if et == "hard_filter_passed":
            return self._plan_hard_filter_passed(phase, envelope)
        if et == "hard_filter_failed":
            return self._plan_hard_filter_failed(phase, envelope)
        if et == "light_scoring_completed":
            return self._plan_light_scoring_completed(phase, envelope, planner_path="light_scoring_completed")
        if et == "questionnaire_requested":
            return self._plan_questionnaire_requested(phase, envelope)
        if et == "questionnaire_sent":
            return self._plan_questionnaire_sent(phase, envelope)
        if et == "questionnaire_completed":
            return self._plan_questionnaire_completed(phase, envelope)
        if et == "deep_scoring_completed":
            return self._plan_deep_scoring_completed(phase, envelope, planner_path="deep_scoring_completed")
        if et == "scoring_completed":
            if phase == PipelinePhase.HARD_FILTER_PASSED:
                return self._plan_light_scoring_completed(
                    phase, envelope, planner_path="scoring_completed(disambiguated_light)"
                )
            if phase == PipelinePhase.QUESTIONNAIRE_COMPLETED:
                return self._plan_deep_scoring_completed(
                    phase, envelope, planner_path="scoring_completed(disambiguated_deep)"
                )
            return OrchestrationPlan()

        return OrchestrationPlan()

    def _plan_candidate_created(
        self, phase: PipelinePhase, envelope: EventEnvelope
    ) -> OrchestrationPlan:
        if phase != PipelinePhase.NEW:
            return OrchestrationPlan()
        return OrchestrationPlan(
            skills=(
                SkillInvocationSpec(
                    skill_name=SKILL_CANDIDATE_CREATED,
                    input=_skill_input(planner_path="candidate_created", envelope=envelope),
                    required=False,
                ),
            ),
        )

    def _plan_cv_uploaded(self, phase: PipelinePhase, envelope: EventEnvelope) -> OrchestrationPlan:
        if phase != PipelinePhase.NEW:
            return OrchestrationPlan()
        return OrchestrationPlan(
            proposed_transition=ProposedTransition(
                state_domain=StateDomain.PIPELINE,
                from_state=PipelinePhase.NEW.value,
                to_state=PipelinePhase.CV_RECEIVED.value,
                trigger=_event_trigger("cv_uploaded"),
                human_override=_human_override(envelope),
                transition_actor=_system_actor(envelope),
            ),
            skills=(
                SkillInvocationSpec(
                    skill_name=SKILL_CV_UPLOADED,
                    input=_skill_input(planner_path="cv_uploaded", envelope=envelope),
                    required=True,
                ),
            ),
        )

    def _plan_cv_parsed(self, phase: PipelinePhase, envelope: EventEnvelope) -> OrchestrationPlan:
        if phase != PipelinePhase.CV_RECEIVED:
            return OrchestrationPlan()
        return OrchestrationPlan(
            proposed_transition=ProposedTransition(
                state_domain=StateDomain.PIPELINE,
                from_state=PipelinePhase.CV_RECEIVED.value,
                to_state=PipelinePhase.CV_PARSED.value,
                trigger=_event_trigger("cv_parsed"),
                human_override=_human_override(envelope),
                transition_actor=_system_actor(envelope),
            ),
            skills=(
                SkillInvocationSpec(
                    skill_name=SKILL_CV_PARSED,
                    input=_skill_input(planner_path="cv_parsed", envelope=envelope),
                    required=True,
                ),
            ),
        )

    def _plan_hard_filter_passed(self, phase: PipelinePhase, envelope: EventEnvelope) -> OrchestrationPlan:
        if phase != PipelinePhase.CV_PARSED:
            return OrchestrationPlan()
        return OrchestrationPlan(
            proposed_transition=ProposedTransition(
                state_domain=StateDomain.PIPELINE,
                from_state=PipelinePhase.CV_PARSED.value,
                to_state=PipelinePhase.HARD_FILTER_PASSED.value,
                trigger=_event_trigger("hard_filter_passed"),
                human_override=_human_override(envelope),
                transition_actor=_system_actor(envelope),
            ),
            skills=(
                SkillInvocationSpec(
                    skill_name=SKILL_HARD_FILTER,
                    input=_skill_input(
                        planner_path="hard_filter_passed",
                        envelope=envelope,
                        extras={"outcome": "passed"},
                    ),
                    required=False,
                ),
            ),
        )

    def _plan_hard_filter_failed(self, phase: PipelinePhase, envelope: EventEnvelope) -> OrchestrationPlan:
        if phase != PipelinePhase.CV_PARSED:
            return OrchestrationPlan()
        # Semantic event is ``hard_filter_failed``; the default pipeline registry only
        # authorizes ``manual_inactive`` / ``event:candidate_rejected`` for the ``*`` ->
        # inactive edge. We use ``manual_inactive`` as a deterministic control-plane alias
        # for slice closure (registry extension / typed trigger mapping is deferred).
        return OrchestrationPlan(
            proposed_transition=ProposedTransition(
                state_domain=StateDomain.PIPELINE,
                from_state=PipelinePhase.CV_PARSED.value,
                to_state=PipelinePhase.INACTIVE.value,
                trigger="manual_inactive",
                human_override=_human_override(envelope),
                transition_actor=_system_actor(envelope),
            ),
            skills=(
                SkillInvocationSpec(
                    skill_name=SKILL_HARD_FILTER,
                    input=_skill_input(
                        planner_path="hard_filter_failed",
                        envelope=envelope,
                        extras={"outcome": "failed"},
                    ),
                    required=False,
                ),
            ),
        )

    def _plan_light_scoring_completed(
        self, phase: PipelinePhase, envelope: EventEnvelope, *, planner_path: str
    ) -> OrchestrationPlan:
        if phase != PipelinePhase.HARD_FILTER_PASSED:
            return OrchestrationPlan()
        emissions: Tuple[OrchestrationEmissionDraft, ...] = (
            OrchestrationEmissionDraft(
                event_type="questionnaire_requested",
                payload={"reason": "post_light_scoring_gate"},
                subject_id=envelope.subject_id,
                subject_kind=envelope.subject_kind or "candidate",
            ),
        )
        return OrchestrationPlan(
            proposed_transition=ProposedTransition(
                state_domain=StateDomain.PIPELINE,
                from_state=PipelinePhase.HARD_FILTER_PASSED.value,
                to_state=PipelinePhase.LIGHT_SCORED.value,
                trigger=_event_trigger("light_scoring_completed"),
                human_override=_human_override(envelope),
                transition_actor=_system_actor(envelope),
            ),
            skills=(
                SkillInvocationSpec(
                    skill_name=SKILL_LIGHT_SCORING,
                    input=_skill_input(planner_path=planner_path, envelope=envelope),
                    required=True,
                ),
            ),
            emissions=emissions,
        )

    def _plan_questionnaire_requested(
        self, phase: PipelinePhase, envelope: EventEnvelope
    ) -> OrchestrationPlan:
        """
        Registry: ``light_scored_to_questionnaire_pending``
        (``light_scored`` → ``questionnaire_pending``).
        """
        if phase != PipelinePhase.LIGHT_SCORED:
            return OrchestrationPlan()
        return OrchestrationPlan(
            proposed_transition=ProposedTransition(
                state_domain=StateDomain.PIPELINE,
                from_state=PipelinePhase.LIGHT_SCORED.value,
                to_state=PipelinePhase.QUESTIONNAIRE_PENDING.value,
                trigger=_event_trigger("questionnaire_requested"),
                human_override=_human_override(envelope),
                transition_actor=_system_actor(envelope),
            ),
            skills=(
                SkillInvocationSpec(
                    skill_name=SKILL_QUESTIONNAIRE_STAGE,
                    input=_skill_input(planner_path="questionnaire_requested", envelope=envelope),
                    required=False,
                ),
            ),
        )

    def _plan_questionnaire_sent(
        self, phase: PipelinePhase, envelope: EventEnvelope
    ) -> OrchestrationPlan:
        """
        Registry: ``questionnaire_pending_to_sent``
        (``questionnaire_pending`` → ``questionnaire_sent``).
        """
        if phase != PipelinePhase.QUESTIONNAIRE_PENDING:
            return OrchestrationPlan()
        return OrchestrationPlan(
            proposed_transition=ProposedTransition(
                state_domain=StateDomain.PIPELINE,
                from_state=PipelinePhase.QUESTIONNAIRE_PENDING.value,
                to_state=PipelinePhase.QUESTIONNAIRE_SENT.value,
                trigger=_event_trigger("questionnaire_sent"),
                human_override=_human_override(envelope),
                transition_actor=_system_actor(envelope),
            ),
            skills=(
                SkillInvocationSpec(
                    skill_name=SKILL_QUESTIONNAIRE_STAGE,
                    input=_skill_input(planner_path="questionnaire_sent", envelope=envelope),
                    required=False,
                ),
            ),
        )

    def _plan_questionnaire_completed(
        self, phase: PipelinePhase, envelope: EventEnvelope
    ) -> OrchestrationPlan:
        """
        Registry: ``questionnaire_sent_to_completed``
        (``questionnaire_sent`` → ``questionnaire_completed``).

        This snapshot is the prerequisite for ``deep_scoring_completed``
        (``questionnaire_completed_to_deep_scored``).
        """
        if phase != PipelinePhase.QUESTIONNAIRE_SENT:
            return OrchestrationPlan()
        return OrchestrationPlan(
            proposed_transition=ProposedTransition(
                state_domain=StateDomain.PIPELINE,
                from_state=PipelinePhase.QUESTIONNAIRE_SENT.value,
                to_state=PipelinePhase.QUESTIONNAIRE_COMPLETED.value,
                trigger=_event_trigger("questionnaire_completed"),
                human_override=_human_override(envelope),
                transition_actor=_system_actor(envelope),
            ),
            skills=(
                SkillInvocationSpec(
                    skill_name=SKILL_QUESTIONNAIRE_STAGE,
                    input=_skill_input(planner_path="questionnaire_completed", envelope=envelope),
                    required=False,
                ),
            ),
        )

    def _plan_deep_scoring_completed(
        self, phase: PipelinePhase, envelope: EventEnvelope, *, planner_path: str
    ) -> OrchestrationPlan:
        """
        Deep scoring **completion** in the slice: leave ``questionnaire_completed`` and
        enter ``deep_scored`` (see ``questionnaire_completed_to_deep_scored`` in the
        default pipeline registry).

        This is intentionally **not** the ``deep_scored`` → ``shortlisted`` hop; that
        progression is reserved for a separate explicit control-plane event in a
        fuller workflow.
        """
        if phase != PipelinePhase.QUESTIONNAIRE_COMPLETED:
            return OrchestrationPlan()
        return OrchestrationPlan(
            proposed_transition=ProposedTransition(
                state_domain=StateDomain.PIPELINE,
                from_state=PipelinePhase.QUESTIONNAIRE_COMPLETED.value,
                to_state=PipelinePhase.DEEP_SCORED.value,
                trigger=_event_trigger("deep_scoring_completed"),
                human_override=_human_override(envelope),
                transition_actor=_system_actor(envelope),
            ),
            skills=(
                SkillInvocationSpec(
                    skill_name=SKILL_DEEP_SCORING,
                    input=_skill_input(planner_path=planner_path, envelope=envelope),
                    required=True,
                ),
            ),
        )