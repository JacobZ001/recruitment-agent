"""
Deterministic vertical-slice workflow policy for recruiter orchestration.

Maps bus :class:`~interfaces.event_bus_interface.EventEnvelope` records and the current
:class:`~schemas.state_schema.OrchestrationState` into an :class:`OrchestrationPlan`.
Policy only: no execution, persistence, or transition validation (orchestrator + engine).

**System path**: CV intake through hard filter and scoring; **ranking** after light and deep
scoring is a **direct planner decision** (chained pipeline transition in the same ingest;
``runtime.vertical_slice_ranking.resolve_ranking_branch``). No ``ranking_completed`` bus event.

**Human path**: interview scheduling/completion, ``recruiter_send_offer`` from post-evaluation
phases only (see ``_SEND_OFFER_FROM_PHASES``), candidate offer accept/decline, recruiter reject and
reconsider out of ``inactive``. ``hired`` is terminal; ``inactive`` is recoverable.

**Inactive metadata**: ``inactive.*`` keys on :class:`ProposedTransition.record_extensions`
merge into aggregate ``OrchestrationState.extensions`` on commit (see orchestrator).
"""

from __future__ import annotations

from typing import Any, Dict, FrozenSet, List, Optional, Sequence, Tuple

from pydantic import ValidationError

from interfaces.event_bus_interface import DeliveryContext, EventEnvelope

from .orchestrator import (
    OrchestrationPlan,
    ProposedTransition,
    SkillInvocationSpec,
)
from interfaces.skill_interface import (
    ConfidenceLevel,
    ExecutionStatus,
    SkillExecutionResult,
    SkillInputEnvelope,
)
from schemas.governance_schema import (
    governance_record_extensions,
    parse_governance_ingress,
    parse_governance_override_ingress,
)
from schemas.state_schema import DecisionActorType, OrchestrationState, PipelinePhase, StateActor, StateDomain

from modules.recruitment.fixtures import merge_demo_profile_into_skill_payload
from modules.recruitment.ranking import resolve_ranking_branch


# Stable skill identifiers — must match keys in the orchestrator skill registry wiring.
SKILL_CANDIDATE_CREATED = "recruitment.vertical_slice.candidate_created"
SKILL_CV_UPLOADED = "recruitment.vertical_slice.cv_uploaded"
SKILL_CV_PARSED = "recruitment.vertical_slice.cv_parsed"
SKILL_HARD_FILTER = "recruitment.vertical_slice.hard_filter"
SKILL_LIGHT_SCORING = "recruitment.vertical_slice.light_scoring"
SKILL_DEEP_SCORING = "recruitment.vertical_slice.deep_scoring"
SKILL_QUESTIONNAIRE_STAGE = "recruitment.vertical_slice.questionnaire_stage"

# Bounded whitelist: explicit governance transitions must match default_pipeline_registry edges.
_ALLOWED_GOVERNANCE_OVERRIDE_TRIPLES: FrozenSet[Tuple[str, str, str]] = frozenset(
    {
        (
            PipelinePhase.DEEP_SCORED.value,
            PipelinePhase.SHORTLISTED.value,
            "manual_recruiter_shortlist_candidate",
        ),
        (
            PipelinePhase.DEEP_SCORED.value,
            PipelinePhase.SHORTLISTED.value,
            "manual_recruiter_approve",
        ),
        (
            PipelinePhase.SHORTLISTED.value,
            PipelinePhase.INTERVIEW_PENDING.value,
            "manual_recruiter_schedule_interview",
        ),
        (
            PipelinePhase.INTERVIEW_COMPLETED.value,
            PipelinePhase.INTERVIEW_PENDING.value,
            "manual_recruiter_schedule_interview",
        ),
    }
)

# Phases where ``manual_recruiter_send_offer`` may advance to ``offer_sent`` (registry-aligned).
_SEND_OFFER_FROM_PHASES: FrozenSet[PipelinePhase] = frozenset(
    {
        PipelinePhase.DEEP_SCORED,
        PipelinePhase.SHORTLISTED,
        PipelinePhase.INTERVIEW_PENDING,
        PipelinePhase.INTERVIEW_COMPLETED,
    }
)


def ranking_record_extensions(*, stage: str, branch: str) -> Dict[str, Any]:
    """Audit/snapshot keys for deterministic ranking branch (vertical slice)."""
    return {"ranking.stage": stage, "ranking.branch": branch}


def inactive_snapshot_extensions(
    *,
    reason: str,
    source_phase: str,
    event_type: str,
    governance_reason: Optional[str] = None,
) -> Dict[str, Any]:
    """Keys merged into orchestration snapshot ``extensions`` on inactive transitions."""
    out: Dict[str, Any] = {
        "inactive.reason": reason,
        "inactive.source_phase": source_phase,
        "inactive.event_type": event_type,
    }
    if governance_reason is not None:
        out["inactive.governance_reason"] = governance_reason
    return out


def _event_trigger(name: str) -> str:
    return f"event:{name}"


def _system_actor(envelope: EventEnvelope) -> StateActor:
    actor_id = envelope.metadata.actor_id if envelope.metadata else None
    return StateActor(actor_type=DecisionActorType.SYSTEM, actor_id=actor_id)


def _human_actor_from_governance(actor_id: str) -> StateActor:
    return StateActor(actor_type=DecisionActorType.HUMAN, actor_id=actor_id)


def _human_override(envelope: EventEnvelope) -> bool:
    if envelope.extensions and envelope.extensions.get("human_override") is True:
        return True
    if envelope.payload and envelope.payload.get("human_override") is True:
        return True
    return False


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

    def __init__(self, *, demo_skill_context: bool = False) -> None:
        """
        When ``demo_skill_context`` is True, merge :mod:`runtime.demo_candidate_fixture`
        keys into every skill input (``setdefault``) for recruiter-visible demos.
        Bootstrap/replay should keep the default False so historical payloads stay equal.
        """
        self._demo_skill_context = demo_skill_context

    def _skill_input(
        self,
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
        if self._demo_skill_context:
            merge_demo_profile_into_skill_payload(payload)
        return SkillInputEnvelope(payload=payload)

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
        if et == "recruiter_approve_candidate":
            return self._plan_recruiter_shortlist_candidate(phase, envelope, legacy_event_type=True)
        if et == "recruiter_shortlist_candidate":
            return self._plan_recruiter_shortlist_candidate(phase, envelope, legacy_event_type=False)
        if et == "recruiter_reject_candidate":
            return self._plan_recruiter_reject_candidate(phase, envelope)
        if et == "candidate_rejected":
            return self._plan_candidate_rejected(phase, envelope)
        if et == "recruiter_schedule_interview":
            return self._plan_recruiter_schedule_interview(phase, envelope)
        if et == "recruiter_complete_interview":
            return self._plan_recruiter_complete_interview(phase, envelope)
        if et == "recruiter_send_offer":
            return self._plan_recruiter_send_offer(phase, envelope)
        if et == "recruiter_mark_hired":
            return self._plan_recruiter_mark_hired(phase, envelope)
        if et == "candidate_accept_offer":
            return self._plan_candidate_accept_offer(phase, envelope)
        if et == "candidate_decline_offer":
            return self._plan_candidate_decline_offer(phase, envelope)
        if et == "recruiter_reconsider_candidate":
            return self._plan_recruiter_reconsider_candidate(phase, envelope)
        if et == "recruiter_override_transition":
            return self._plan_recruiter_override_transition(phase, envelope, force_human_override=False)
        if et == "recruiter_force_transition":
            return self._plan_recruiter_override_transition(phase, envelope, force_human_override=True)
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
                    input=self._skill_input(planner_path="candidate_created", envelope=envelope),
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
                    input=self._skill_input(planner_path="cv_uploaded", envelope=envelope),
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
                    input=self._skill_input(planner_path="cv_parsed", envelope=envelope),
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
                    input=self._skill_input(
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
        src = phase.value
        return OrchestrationPlan(
            proposed_transition=ProposedTransition(
                state_domain=StateDomain.PIPELINE,
                from_state=PipelinePhase.CV_PARSED.value,
                to_state=PipelinePhase.INACTIVE.value,
                trigger=_event_trigger("hard_filter_failed"),
                human_override=_human_override(envelope),
                transition_actor=_system_actor(envelope),
                record_extensions=inactive_snapshot_extensions(
                    reason="hard_filter_failed",
                    source_phase=src,
                    event_type="hard_filter_failed",
                ),
            ),
            skills=(
                SkillInvocationSpec(
                    skill_name=SKILL_HARD_FILTER,
                    input=self._skill_input(
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
        payload = dict(envelope.payload or {})
        branch = resolve_ranking_branch(payload=payload, stage="light")
        actor = _system_actor(envelope)
        skills_list: List[SkillInvocationSpec] = [
            SkillInvocationSpec(
                skill_name=SKILL_LIGHT_SCORING,
                input=self._skill_input(planner_path=planner_path, envelope=envelope),
                required=True,
            ),
        ]
        if branch == "mid_m":
            skills_list.append(
                SkillInvocationSpec(
                    skill_name=SKILL_QUESTIONNAIRE_STAGE,
                    input=self._skill_input(
                        planner_path="light_scoring_completed(mid_m_ranking)",
                        envelope=envelope,
                    ),
                    required=False,
                ),
            )
        secondary: ProposedTransition
        if branch == "top_k":
            secondary = ProposedTransition(
                state_domain=StateDomain.PIPELINE,
                from_state=PipelinePhase.LIGHT_SCORED.value,
                to_state=PipelinePhase.SHORTLISTED.value,
                trigger="system_ranking_top_k",
                human_override=False,
                transition_actor=actor,
                record_extensions=ranking_record_extensions(stage="light", branch="top_k"),
            )
        elif branch == "mid_m":
            secondary = ProposedTransition(
                state_domain=StateDomain.PIPELINE,
                from_state=PipelinePhase.LIGHT_SCORED.value,
                to_state=PipelinePhase.QUESTIONNAIRE_PENDING.value,
                trigger="system_ranking_mid_m",
                human_override=False,
                transition_actor=actor,
                record_extensions=ranking_record_extensions(stage="light", branch="mid_m"),
            )
        else:
            secondary = ProposedTransition(
                state_domain=StateDomain.PIPELINE,
                from_state=PipelinePhase.LIGHT_SCORED.value,
                to_state=PipelinePhase.INACTIVE.value,
                trigger="system_ranking_reject",
                human_override=False,
                transition_actor=actor,
                record_extensions={
                    **ranking_record_extensions(stage="light", branch="reject"),
                    **inactive_snapshot_extensions(
                        reason="ranking_reject_after_light_scoring",
                        source_phase=PipelinePhase.LIGHT_SCORED.value,
                        event_type="light_scoring_completed",
                    ),
                },
            )
        return OrchestrationPlan(
            proposed_transition=ProposedTransition(
                state_domain=StateDomain.PIPELINE,
                from_state=PipelinePhase.HARD_FILTER_PASSED.value,
                to_state=PipelinePhase.LIGHT_SCORED.value,
                trigger=_event_trigger("light_scoring_completed"),
                human_override=_human_override(envelope),
                transition_actor=actor,
            ),
            secondary_proposed_transition=secondary,
            skills=tuple(skills_list),
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
                    input=self._skill_input(planner_path="questionnaire_requested", envelope=envelope),
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
                    input=self._skill_input(planner_path="questionnaire_sent", envelope=envelope),
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
                    input=self._skill_input(planner_path="questionnaire_completed", envelope=envelope),
                    required=False,
                ),
            ),
        )

    def _plan_deep_scoring_completed(
        self, phase: PipelinePhase, envelope: EventEnvelope, *, planner_path: str
    ) -> OrchestrationPlan:
        if phase != PipelinePhase.QUESTIONNAIRE_COMPLETED:
            return OrchestrationPlan()
        payload = dict(envelope.payload or {})
        branch = resolve_ranking_branch(payload=payload, stage="deep")
        if branch == "mid_m":
            branch = "top_k"
        actor = _system_actor(envelope)
        if branch == "top_k":
            secondary = ProposedTransition(
                state_domain=StateDomain.PIPELINE,
                from_state=PipelinePhase.DEEP_SCORED.value,
                to_state=PipelinePhase.SHORTLISTED.value,
                trigger="system_ranking_top_k",
                human_override=False,
                transition_actor=actor,
                record_extensions=ranking_record_extensions(stage="deep", branch="top_k"),
            )
        else:
            secondary = ProposedTransition(
                state_domain=StateDomain.PIPELINE,
                from_state=PipelinePhase.DEEP_SCORED.value,
                to_state=PipelinePhase.INACTIVE.value,
                trigger="system_ranking_reject",
                human_override=False,
                transition_actor=actor,
                record_extensions={
                    **ranking_record_extensions(stage="deep", branch="reject"),
                    **inactive_snapshot_extensions(
                        reason="ranking_reject_after_deep_scoring",
                        source_phase=PipelinePhase.DEEP_SCORED.value,
                        event_type="deep_scoring_completed",
                    ),
                },
            )
        return OrchestrationPlan(
            proposed_transition=ProposedTransition(
                state_domain=StateDomain.PIPELINE,
                from_state=PipelinePhase.QUESTIONNAIRE_COMPLETED.value,
                to_state=PipelinePhase.DEEP_SCORED.value,
                trigger=_event_trigger("deep_scoring_completed"),
                human_override=_human_override(envelope),
                transition_actor=actor,
            ),
            secondary_proposed_transition=secondary,
            skills=(
                SkillInvocationSpec(
                    skill_name=SKILL_DEEP_SCORING,
                    input=self._skill_input(planner_path=planner_path, envelope=envelope),
                    required=True,
                ),
            ),
        )

    def _plan_recruiter_shortlist_candidate(
        self, phase: PipelinePhase, envelope: EventEnvelope, *, legacy_event_type: bool
    ) -> OrchestrationPlan:
        try:
            gov = parse_governance_ingress(dict(envelope.payload or {}))
        except ValidationError:
            return OrchestrationPlan()
        if phase != PipelinePhase.DEEP_SCORED:
            return OrchestrationPlan()
        et = "recruiter_approve_candidate" if legacy_event_type else "recruiter_shortlist_candidate"
        trig = "manual_recruiter_approve" if legacy_event_type else "manual_recruiter_shortlist_candidate"
        dc = "GOVERNANCE_APPROVE_CANDIDATE_LEGACY" if legacy_event_type else "GOVERNANCE_SHORTLIST_CANDIDATE"
        return OrchestrationPlan(
            proposed_transition=ProposedTransition(
                state_domain=StateDomain.PIPELINE,
                from_state=PipelinePhase.DEEP_SCORED.value,
                to_state=PipelinePhase.SHORTLISTED.value,
                trigger=trig,
                human_override=False,
                transition_actor=_human_actor_from_governance(gov.actor_id),
                record_extensions=governance_record_extensions(
                    event_type=et,
                    gov=gov,
                    decision_code=dc,
                ),
            ),
        )

    def _plan_recruiter_reject_candidate(
        self, phase: PipelinePhase, envelope: EventEnvelope
    ) -> OrchestrationPlan:
        try:
            gov = parse_governance_ingress(dict(envelope.payload or {}))
        except ValidationError:
            return OrchestrationPlan()
        if phase == PipelinePhase.INACTIVE:
            return OrchestrationPlan()
        if phase == PipelinePhase.HIRED:
            return OrchestrationPlan()
        src = phase.value
        rec = governance_record_extensions(
            event_type="recruiter_reject_candidate",
            gov=gov,
            decision_code="GOVERNANCE_REJECT_CANDIDATE",
        )
        rec.update(
            inactive_snapshot_extensions(
                reason="recruiter_rejected",
                source_phase=src,
                event_type="recruiter_reject_candidate",
                governance_reason=gov.reason,
            )
        )
        return OrchestrationPlan(
            proposed_transition=ProposedTransition(
                state_domain=StateDomain.PIPELINE,
                from_state=phase.value,
                to_state=PipelinePhase.INACTIVE.value,
                trigger="manual_recruiter_reject",
                human_override=False,
                transition_actor=_human_actor_from_governance(gov.actor_id),
                record_extensions=rec,
            ),
        )

    def _governance_manual_pipeline_step(
        self,
        *,
        phase: PipelinePhase,
        envelope: EventEnvelope,
        from_phase: PipelinePhase,
        to_phase: PipelinePhase,
        trigger: str,
        event_type: str,
        decision_code: str,
        extra_record_extensions: Optional[Dict[str, Any]] = None,
    ) -> OrchestrationPlan:
        try:
            gov = parse_governance_ingress(dict(envelope.payload or {}))
        except ValidationError:
            return OrchestrationPlan()
        if phase != from_phase:
            return OrchestrationPlan()
        rec = governance_record_extensions(
            event_type=event_type,
            gov=gov,
            decision_code=decision_code,
        )
        if extra_record_extensions:
            rec = {**rec, **extra_record_extensions}
        return OrchestrationPlan(
            proposed_transition=ProposedTransition(
                state_domain=StateDomain.PIPELINE,
                from_state=from_phase.value,
                to_state=to_phase.value,
                trigger=trigger,
                human_override=False,
                transition_actor=_human_actor_from_governance(gov.actor_id),
                record_extensions=rec,
            ),
        )

    def _plan_recruiter_schedule_interview(
        self, phase: PipelinePhase, envelope: EventEnvelope
    ) -> OrchestrationPlan:
        first = self._governance_manual_pipeline_step(
            phase=phase,
            envelope=envelope,
            from_phase=PipelinePhase.SHORTLISTED,
            to_phase=PipelinePhase.INTERVIEW_PENDING,
            trigger="manual_recruiter_schedule_interview",
            event_type="recruiter_schedule_interview",
            decision_code="GOVERNANCE_SCHEDULE_INTERVIEW",
        )
        if first.proposed_transition is not None:
            return first
        return self._governance_manual_pipeline_step(
            phase=phase,
            envelope=envelope,
            from_phase=PipelinePhase.INTERVIEW_COMPLETED,
            to_phase=PipelinePhase.INTERVIEW_PENDING,
            trigger="manual_recruiter_schedule_interview",
            event_type="recruiter_schedule_interview",
            decision_code="GOVERNANCE_SCHEDULE_INTERVIEW_NEXT_ROUND",
        )

    def _plan_recruiter_complete_interview(
        self, phase: PipelinePhase, envelope: EventEnvelope
    ) -> OrchestrationPlan:
        """Registry: ``interview_pending_to_completed``."""
        return self._governance_manual_pipeline_step(
            phase=phase,
            envelope=envelope,
            from_phase=PipelinePhase.INTERVIEW_PENDING,
            to_phase=PipelinePhase.INTERVIEW_COMPLETED,
            trigger="manual_recruiter_complete_interview",
            event_type="recruiter_complete_interview",
            decision_code="GOVERNANCE_COMPLETE_INTERVIEW",
        )

    def _plan_recruiter_send_offer(
        self, phase: PipelinePhase, envelope: EventEnvelope
    ) -> OrchestrationPlan:
        if phase in (PipelinePhase.OFFER_SENT, PipelinePhase.HIRED):
            return OrchestrationPlan()
        if phase not in _SEND_OFFER_FROM_PHASES:
            return OrchestrationPlan()
        return self._governance_manual_pipeline_step(
            phase=phase,
            envelope=envelope,
            from_phase=phase,
            to_phase=PipelinePhase.OFFER_SENT,
            trigger="manual_recruiter_send_offer",
            event_type="recruiter_send_offer",
            decision_code="GOVERNANCE_SEND_OFFER",
        )

    def _plan_recruiter_mark_hired(
        self, phase: PipelinePhase, envelope: EventEnvelope
    ) -> OrchestrationPlan:
        """Legacy governance path; prefer ``candidate_accept_offer`` + ``event:offer_accepted``."""
        return self._governance_manual_pipeline_step(
            phase=phase,
            envelope=envelope,
            from_phase=PipelinePhase.OFFER_SENT,
            to_phase=PipelinePhase.HIRED,
            trigger="manual_recruiter_mark_hired",
            event_type="recruiter_mark_hired",
            decision_code="GOVERNANCE_MARK_HIRED_LEGACY",
        )

    def _plan_candidate_accept_offer(
        self, phase: PipelinePhase, envelope: EventEnvelope
    ) -> OrchestrationPlan:
        if phase != PipelinePhase.OFFER_SENT:
            return OrchestrationPlan()
        try:
            gov = parse_governance_ingress(dict(envelope.payload or {}))
        except ValidationError:
            return OrchestrationPlan()
        rec = governance_record_extensions(
            event_type="candidate_accept_offer",
            gov=gov,
            decision_code="CANDIDATE_ACCEPT_OFFER",
        )
        return OrchestrationPlan(
            proposed_transition=ProposedTransition(
                state_domain=StateDomain.PIPELINE,
                from_state=PipelinePhase.OFFER_SENT.value,
                to_state=PipelinePhase.HIRED.value,
                trigger=_event_trigger("offer_accepted"),
                human_override=False,
                transition_actor=_human_actor_from_governance(gov.actor_id),
                record_extensions=rec,
            ),
        )

    def _plan_candidate_decline_offer(
        self, phase: PipelinePhase, envelope: EventEnvelope
    ) -> OrchestrationPlan:
        if phase != PipelinePhase.OFFER_SENT:
            return OrchestrationPlan()
        try:
            gov = parse_governance_ingress(dict(envelope.payload or {}))
        except ValidationError:
            return OrchestrationPlan()
        rec = governance_record_extensions(
            event_type="candidate_decline_offer",
            gov=gov,
            decision_code="CANDIDATE_DECLINE_OFFER",
        )
        rec.update(
            inactive_snapshot_extensions(
                reason="offer_declined",
                source_phase=PipelinePhase.OFFER_SENT.value,
                event_type="candidate_decline_offer",
                governance_reason=gov.reason,
            )
        )
        return OrchestrationPlan(
            proposed_transition=ProposedTransition(
                state_domain=StateDomain.PIPELINE,
                from_state=PipelinePhase.OFFER_SENT.value,
                to_state=PipelinePhase.INACTIVE.value,
                trigger=_event_trigger("offer_declined"),
                human_override=False,
                transition_actor=_human_actor_from_governance(gov.actor_id),
                record_extensions=rec,
            ),
        )

    def _plan_recruiter_reconsider_candidate(
        self, phase: PipelinePhase, envelope: EventEnvelope
    ) -> OrchestrationPlan:
        return self._governance_manual_pipeline_step(
            phase=phase,
            envelope=envelope,
            from_phase=PipelinePhase.INACTIVE,
            to_phase=PipelinePhase.SHORTLISTED,
            trigger="manual_recruiter_reconsider",
            event_type="recruiter_reconsider_candidate",
            decision_code="GOVERNANCE_RECONSIDER_CANDIDATE",
            extra_record_extensions={
                "inactive.reason": None,
                "inactive.source_phase": None,
                "inactive.event_type": None,
                "inactive.governance_reason": None,
            },
        )

    def _plan_candidate_rejected(self, phase: PipelinePhase, envelope: EventEnvelope) -> OrchestrationPlan:
        if phase in (PipelinePhase.INACTIVE, PipelinePhase.HIRED):
            return OrchestrationPlan()
        src = phase.value
        return OrchestrationPlan(
            proposed_transition=ProposedTransition(
                state_domain=StateDomain.PIPELINE,
                from_state=phase.value,
                to_state=PipelinePhase.INACTIVE.value,
                trigger=_event_trigger("candidate_rejected"),
                human_override=False,
                transition_actor=_system_actor(envelope),
                record_extensions=inactive_snapshot_extensions(
                    reason="recruiter_rejected",
                    source_phase=src,
                    event_type="candidate_rejected",
                ),
            ),
        )

    def _plan_recruiter_override_transition(
        self, phase: PipelinePhase, envelope: EventEnvelope, *, force_human_override: bool
    ) -> OrchestrationPlan:
        """
        Bounded explicit transition requests; still validated by the transition engine.

        ``recruiter_force_transition`` sets ``human_override=True`` for audit/replay
        (terminal escape semantics when applicable).
        """
        try:
            gov = parse_governance_override_ingress(dict(envelope.payload or {}))
        except ValidationError:
            return OrchestrationPlan()
        triple = (gov.requested_from_phase, gov.requested_to_phase, gov.trigger)
        if triple not in _ALLOWED_GOVERNANCE_OVERRIDE_TRIPLES:
            return OrchestrationPlan()
        ho = force_human_override or gov.force_human_override
        et = "recruiter_force_transition" if force_human_override else "recruiter_override_transition"
        return OrchestrationPlan(
            proposed_transition=ProposedTransition(
                state_domain=StateDomain.PIPELINE,
                from_state=gov.requested_from_phase,
                to_state=gov.requested_to_phase,
                trigger=gov.trigger,
                human_override=ho,
                transition_actor=_human_actor_from_governance(gov.actor_id),
                record_extensions=governance_record_extensions(
                    event_type=et,
                    gov=gov,
                    decision_code="GOVERNANCE_OVERRIDE_TRANSITION",
                    extra={
                        "governance.force_human_override": ho,
                        "governance.requested_trigger": gov.trigger,
                    },
                ),
            ),
        )


_MAX_PERSISTED_DECISION_EVIDENCE_REFS = 48


def _evidence_ref_strings_from_skill_result(res: SkillExecutionResult) -> List[str]:
    out = res.output
    if out is None or not out.evidence_refs:
        return []
    return [str(r.ref) for r in out.evidence_refs[:_MAX_PERSISTED_DECISION_EVIDENCE_REFS]]


def _confidence_numeric_from_skill_result(
    res: SkillExecutionResult, *, prefer_deep_payload_score: bool
) -> Optional[float]:
    out = res.output
    if out is None:
        return None
    pl = out.payload or {}
    if prefer_deep_payload_score and pl.get("scoring.deep.confidence_score") is not None:
        return float(pl["scoring.deep.confidence_score"])
    c = out.confidence
    if c is not None and c.score is not None:
        return float(c.score)
    if c is not None and c.level is not None:
        lv = c.level
        if lv == ConfidenceLevel.LOW:
            return 0.25
        if lv == ConfidenceLevel.MEDIUM:
            return 0.5
        if lv == ConfidenceLevel.HIGH:
            return 0.75
    return None


def skill_result_to_vertical_slice_decision_extensions(
    skill_name: str, res: SkillExecutionResult
) -> Dict[str, Any]:
    """
    Flat ``OrchestrationState.extensions`` keys for vertical-slice scoring skills.

    Called by the orchestrator after skills execute so values reflect
    :class:`~interfaces.skill_interface.SkillExecutionResult` outputs.
    """
    out: Dict[str, Any] = {}
    if res.status not in (ExecutionStatus.SUCCEEDED, ExecutionStatus.PARTIAL_SUCCESS):
        return out
    if res.output is None:
        return out
    pl = res.output.payload or {}

    if skill_name == SKILL_HARD_FILTER:
        if "filter.computed_pass" in pl:
            out["decision.hard_filter_pass"] = bool(pl["filter.computed_pass"])
        refs = _evidence_ref_strings_from_skill_result(res)
        if refs:
            out["_evidence_refs_partial"] = refs
        return out

    if skill_name == SKILL_LIGHT_SCORING:
        if "scoring.normalized_score" in pl:
            out["decision.light_score"] = float(pl["scoring.normalized_score"])
        cn = _confidence_numeric_from_skill_result(res, prefer_deep_payload_score=False)
        if cn is not None:
            out["decision.light_confidence"] = cn
        refs = _evidence_ref_strings_from_skill_result(res)
        if refs:
            out["_evidence_refs_partial"] = refs
        return out

    if skill_name == SKILL_DEEP_SCORING:
        if "scoring.deep.normalized_score" in pl:
            out["decision.deep_score"] = float(pl["scoring.deep.normalized_score"])
        cn = _confidence_numeric_from_skill_result(res, prefer_deep_payload_score=True)
        if cn is not None:
            out["decision.deep_confidence"] = cn
        refs = _evidence_ref_strings_from_skill_result(res)
        if refs:
            out["_evidence_refs_partial"] = refs
        return out

    return out


def merge_vertical_slice_decision_snapshot_extensions(
    skills: Sequence[SkillInvocationSpec],
    skill_results: Sequence[SkillExecutionResult],
    *,
    prior_extensions: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Merge per-skill decision keys into one dict for ``OrchestrationState.extensions``.

    Evidence refs from prior snapshot extensions are preserved (dedupe, cap), then
    refs from this plan's skills are appended.
    """
    merged: Dict[str, Any] = {}
    evidence_ordered: List[str] = []

    prior = prior_extensions or {}
    prev_refs = prior.get("decision.evidence_refs")
    if isinstance(prev_refs, list):
        for r in prev_refs:
            s = str(r)
            if s not in evidence_ordered:
                evidence_ordered.append(s)

    for spec, res in zip(skills, skill_results):
        part = skill_result_to_vertical_slice_decision_extensions(spec.skill_name, res)
        refs = part.pop("_evidence_refs_partial", None)
        if isinstance(refs, list):
            for r in refs:
                if r not in evidence_ordered:
                    evidence_ordered.append(r)
        merged.update(part)

    if evidence_ordered:
        merged["decision.evidence_refs"] = evidence_ordered[:_MAX_PERSISTED_DECISION_EVIDENCE_REFS]
    return merged