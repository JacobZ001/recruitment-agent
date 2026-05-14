"""
Deterministic orchestration runtime core.

Purpose
-------
Coordinate a **single-process, synchronous** control-plane loop:

    ingest event → validate plan invariants → validate transition → run skills
    → commit structured state change → emit derived events

This module is the **deterministic orchestration layer**: it wires the event bus
contract, transition engine, state schemas, and skill execution interfaces. It
does **not** decide *which* transition or skills apply for a given domain event;
that policy lives behind :class:`OrchestrationStepPlanner` (implemented as pure
deterministic code outside this module).

Boundaries
----------
- **In scope**: bounded sequencing, validation, audit records, trace metadata,
  replay signal propagation into the transition engine, structured failure
  taxonomy, optional publishing of immutable envelopes.
- **Out of scope**: LLM-driven routing, autonomous agents, retry schedulers,
  queues/brokers, persistence/repositories, async concurrency, distributed
  execution, ranking/scoring heuristics, microservice choreography.

Invariants
----------
- State is never mutated in-place; a successful run returns a new
  :class:`~schemas.state_schema.OrchestrationState` instance.
- State changes occur only after transition validation succeeds and, when the
  plan requires skills, required skills complete without hard failure.
- Transition validation always goes through :class:`state_machine.transition_engine.TransitionEngine`
  (no bypass).
- Replay flags on the delivery context are forwarded to
  :class:`state_machine.transition_engine.TransitionContext` so structural replay
  can remain deterministic (see ``ReplayValidationMode`` in the engine).

Replay expectations
-------------------
Replay is **signal-driven**, not a storage implementation. Callers set
``DeliveryContext.replay`` consistently with ``TransitionReplayContext`` rules
(e.g. ``replay_run_id`` required when ``replay_mode`` is true). The orchestrator
does not load historical streams; it interprets the supplied envelope + state
snapshot deterministically.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Protocol, Sequence, Tuple
from uuid import UUID, uuid5

# Namespace for stable orchestration correlation IDs (replay harness / deterministic runs).
# IDs derive from the ingested envelope and structural indices — no ambient randomness.
_ORCHESTRATION_ID_NS = UUID("018f3e2a-7c9b-4a3d-8f0e-a11b00c0ff02")


def _run_id_for_ingested_event(envelope_event_id: UUID) -> UUID:
    return uuid5(_ORCHESTRATION_ID_NS, f"orch_run:{envelope_event_id}")


def _skill_execution_id_for(envelope_event_id: UUID, skill_index: int, skill_name: str) -> UUID:
    return uuid5(_ORCHESTRATION_ID_NS, f"skill_exec:{envelope_event_id}:{skill_index}:{skill_name}")


def _emission_event_id_for(causation_id: UUID, emission_index: int, event_type: str) -> UUID:
    return uuid5(_ORCHESTRATION_ID_NS, f"emit:{causation_id}:{emission_index}:{event_type}")

from pydantic import BaseModel, Field

try:  # Pydantic v2
    from pydantic import ConfigDict, model_validator

    _PYDANTIC_V2 = True
except Exception:  # Pydantic v1 fallback
    from pydantic import root_validator  # type: ignore

    _PYDANTIC_V2 = False

from interfaces.event_bus_interface import (
    AckDecision,
    DeliveryContext,
    DeliveryStatus,
    EventBusFailure,
    EventEnvelope,
    EventEnvelopeMetadata,
    EventPublisher,
    FailureCategory,
    HandleAudit,
    HandleResult,
    PublishAudit,
    PublishResult,
)
from interfaces.skill_interface import (
    ExecutionContext,
    ExecutionStatus,
    Skill,
    SkillExecutionResult,
    SkillInputEnvelope,
    SkillInterfaceVersion,
)
from schemas.state_schema import (
    CommunicationStatus,
    DecisionOutcome,
    OrchestrationState,
    PipelinePhase,
    StateActor,
    StateDomain,
    StateTransitionRecord,
)
from state_machine.transition_engine import (
    ReplayValidationMode,
    TransitionContext,
    TransitionEngine,
    TransitionReplayContext,
    TransitionValidationResult,
)


class _OrchestratorBase(BaseModel):
    if _PYDANTIC_V2:
        model_config = ConfigDict(
            extra="forbid",
            validate_assignment=True,
            populate_by_name=True,
        )
    else:

        class Config:  # pragma: no cover
            extra = "forbid"
            validate_assignment = True
            allow_population_by_field_name = True


class OrchestrationFailureCode(str, Enum):
    """
    Layer-local failure taxonomy for orchestration runs.

    Intentionally separate from bus/skill failure enums (see tech-debt: future
    consolidation). Values are stable strings for audit logs and harness tests.
    """

    PLAN_INVALID = "plan_invalid"
    BOUNDS_EXCEEDED = "bounds_exceeded"
    STATE_MISMATCH = "state_mismatch"
    TRANSITION_REJECTED = "transition_rejected"
    SKILL_NOT_REGISTERED = "skill_not_registered"
    SKILL_EXECUTION_REJECTED = "skill_execution_rejected"
    EVENT_PUBLISH_FAILED = "event_publish_failed"
    INTERNAL_INVARIANT = "internal_invariant"


class OrchestrationFailure(_OrchestratorBase):
    """Structured orchestration failure (audit-friendly, no stack traces by default)."""

    code: OrchestrationFailureCode
    message: str = Field(..., min_length=1)
    details: Dict[str, Any] = Field(default_factory=dict)


class OrchestrationDecisionKind(str, Enum):
    """High-level decision categories recorded for explainability."""

    PLAN_ACCEPTED = "plan_accepted"
    TRANSITION_VALIDATED = "transition_validated"
    SKILL_DISPATCHED = "skill_dispatched"
    STATE_COMMITTED = "state_committed"
    EMISSION_SCHEDULED = "emission_scheduled"
    NOOP = "noop"
    REJECTED = "rejected"
    RUN_COMPLETED = "run_completed"


class OrchestrationDecisionRecord(_OrchestratorBase):
    """
    Append-only style decision log entry for a single orchestration run.

    These records explain *what the control plane decided* (and why), without
    embedding domain scoring heuristics. Domain meaning lives in planner/skills.
    """

    kind: OrchestrationDecisionKind
    message: str = Field(..., min_length=1)
    code: Optional[str] = Field(
        default=None, description="Optional stable sub-code (e.g. engine rejection code)."
    )
    evidence_refs: List[str] = Field(default_factory=list)
    extensions: Dict[str, Any] = Field(default_factory=dict)


class OrchestrationTraceMeta(_OrchestratorBase):
    """
    Trace metadata for one orchestration invocation.

    Links the ingested envelope to skill executions and emissions. Callers should
    persist this alongside state/event timelines for audit/replay tooling.
    """

    orchestration_execution_id: UUID
    ingested_event_id: UUID
    correlation_id: Optional[UUID] = None
    causation_id: Optional[UUID] = None
    replay_mode: bool = False
    replay_run_id: Optional[UUID] = None
    replay_sequence: Optional[int] = None
    rule_set_id: Optional[str] = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: Optional[datetime] = None
    extensions: Dict[str, Any] = Field(default_factory=dict)


class OrchestrationBoundedLimits(_OrchestratorBase):
    """Hard caps to keep orchestration work bounded per event."""

    max_skills_per_event: int = Field(default=16, ge=0)
    max_emissions_per_event: int = Field(default=32, ge=0)


class ProposedTransition(_OrchestratorBase):
    """
    A single validated state change request produced by deterministic policy code.

    ``from_state`` / ``to_state`` are validated against the current aggregate and
    the transition engine; this model does not interpret domain semantics.
    """

    state_domain: StateDomain
    from_state: str = Field(..., min_length=1)
    to_state: str = Field(..., min_length=1)
    trigger: str = Field(..., min_length=1)
    human_override: bool = False
    transition_actor: StateActor
    record_extensions: Dict[str, Any] = Field(
        default_factory=dict,
        description="Merged into StateTransitionRecord.extensions after validation (audit metadata).",
    )


class SkillInvocationSpec(_OrchestratorBase):
    """Declarative skill dispatch instruction."""

    skill_name: str = Field(..., min_length=1)
    input: SkillInputEnvelope
    required: bool = Field(
        default=True,
        description="If false, non-success skill statuses do not fail the run (audit only).",
    )


class OrchestrationEmissionDraft(_OrchestratorBase):
    """
    Request to emit a new immutable envelope after successful commit.

    The orchestrator assigns fresh ``event_id`` values; planners must not reuse ids.
    """

    event_type: str = Field(..., min_length=1)
    payload: Dict[str, Any] = Field(default_factory=dict)
    subject_id: Optional[UUID] = None
    subject_kind: Optional[str] = None
    schema_version: Optional[str] = None


class OrchestrationPlan(_OrchestratorBase):
    """
    Deterministic execution plan for one ingested envelope.

    Produced exclusively by :class:`OrchestrationStepPlanner` implementations
    (deterministic code). Empty plan means explicit no-op (no transition, skills,
    or emissions).
    """

    proposed_transition: Optional[ProposedTransition] = None
    secondary_proposed_transition: Optional[ProposedTransition] = Field(
        default=None,
        description=(
            "Optional second pipeline commit for the same ingested envelope, validated "
            "after the primary transition commits (e.g. light/deep scoring + immediate ranking)."
        ),
    )
    skills: Tuple[SkillInvocationSpec, ...] = Field(default_factory=tuple)
    emissions: Tuple[OrchestrationEmissionDraft, ...] = Field(default_factory=tuple)


class OrchestrationExecutionResult(_OrchestratorBase):
    """Outcome of one orchestration invocation."""

    ok: bool
    failure: Optional[OrchestrationFailure] = None
    transition_result: Optional[TransitionValidationResult] = None

    new_state: Optional[OrchestrationState] = None
    skill_results: List[SkillExecutionResult] = Field(default_factory=list)
    publish_results: List[PublishResult] = Field(default_factory=list)
    produced_event_ids: List[UUID] = Field(default_factory=list)

    decisions: Tuple[OrchestrationDecisionRecord, ...] = Field(default_factory=tuple)
    trace: OrchestrationTraceMeta

    if _PYDANTIC_V2:

        @model_validator(mode="after")
        def _ok_invariants(self):  # type: ignore[override]
            if self.ok and self.failure is not None:
                raise ValueError("ok=true forbids failure")
            if not self.ok and self.failure is None:
                raise ValueError("ok=false requires failure")
            if self.ok and self.new_state is None:
                raise ValueError("ok=true requires new_state")
            if not self.ok and self.new_state is not None:
                raise ValueError("ok=false forbids new_state")
            return self

    else:

        @root_validator
        def _ok_invariants(cls, values):  # type: ignore[override]
            ok = values.get("ok")
            if ok and values.get("failure") is not None:
                raise ValueError("ok=true forbids failure")
            if not ok and values.get("failure") is None:
                raise ValueError("ok=false requires failure")
            if ok and values.get("new_state") is None:
                raise ValueError("ok=true requires new_state")
            if not ok and values.get("new_state") is not None:
                raise ValueError("ok=false forbids new_state")
            return values


@dataclass(frozen=True)
class OrchestrationContext:
    """
    Frozen runtime dependencies for :class:`Orchestrator`.

    Keeps orchestration wiring explicit: engine, planner, skill registry, optional
    publisher, and audit knobs (``rule_set_id``) used for replay alignment.
    """

    transition_engine: TransitionEngine
    planner: "OrchestrationStepPlanner"
    skills: Mapping[str, Skill]
    publisher: Optional[EventPublisher[EventEnvelope]] = None
    rule_set_id: Optional[str] = None
    limits: OrchestrationBoundedLimits = dc_field(default_factory=OrchestrationBoundedLimits)
    updated_by: str = "orchestrator"

    def __post_init__(self) -> None:
        if not self.updated_by or not self.updated_by.strip():
            object.__setattr__(self, "updated_by", "orchestrator")


class OrchestrationStepPlanner(Protocol):
    """
    Deterministic policy port: maps (state, envelope, delivery) → :class:`OrchestrationPlan`.

    Implementations live outside this module (e.g. vertical-slice wiring). They
    must be pure deterministic Python: **no LLM calls** for routing decisions.
    """

    def plan(
        self,
        *,
        state: OrchestrationState,
        envelope: EventEnvelope,
        delivery: DeliveryContext,
    ) -> OrchestrationPlan:
        ...


def _model_copy(model: BaseModel, **kwargs: Any) -> BaseModel:
    if _PYDANTIC_V2:
        return model.model_copy(update=kwargs, deep=True)
    return model.copy(update=kwargs, deep=True)  # type: ignore[call-arg]


def _pydantic_dump(model: BaseModel) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _current_domain_snapshot(state: OrchestrationState, domain: StateDomain) -> str:
    if domain == StateDomain.PIPELINE:
        return state.pipeline.phase.value
    if domain == StateDomain.DECISION:
        return state.decision.current_outcome.value
    if domain == StateDomain.COMMUNICATION:
        return state.communication.status.value
    raise ValueError(f"Unsupported state domain: {domain!r}")


def _build_transition_replay(delivery: DeliveryContext) -> TransitionReplayContext:
    r = delivery.replay
    mode = ReplayValidationMode.STRICT
    if r.extensions:
        raw = r.extensions.get("transition_replay_validation_mode")
        if raw == ReplayValidationMode.SKIP_GUARDS.value:
            mode = ReplayValidationMode.SKIP_GUARDS
    return TransitionReplayContext(
        replay_mode=r.replay_mode,
        replay_run_id=r.replay_run_id,
        validation_mode=mode,
        extensions=r.extensions or {},
    )


def _build_execution_context(
    *,
    envelope: EventEnvelope,
    delivery: DeliveryContext,
    execution_id: UUID,
) -> ExecutionContext:
    meta = envelope.metadata
    return ExecutionContext(
        interface_version=SkillInterfaceVersion.V1.value,
        trace_id=meta.trace_id,
        request_id=meta.request_id,
        correlation_id=meta.correlation_id or envelope.subject_id,
        causation_id=meta.causation_id or envelope.event_id,
        event_id=envelope.event_id,
        subject_id=envelope.subject_id,
        subject_kind=envelope.subject_kind,
        actor_id=meta.actor_id,
        run_reason="orchestrator.dispatch",
        replay_mode=delivery.replay.replay_mode,
        extensions={
            "orchestrator_skill_execution_id": str(execution_id),
            "delivery_id": str(delivery.delivery_id) if delivery.delivery_id else None,
            "subscriber_id": delivery.subscriber_id,
        },
    )


def _touch_audit(
    state: OrchestrationState,
    *,
    updated_by: str,
    occurred_at: datetime,
) -> OrchestrationState:
    new_audit = _model_copy(state.audit, updated_at=occurred_at, updated_by=updated_by)
    return _model_copy(state, audit=new_audit)  # type: ignore[return-value]


def _commit_transition(
    state: OrchestrationState,
    *,
    envelope: EventEnvelope,
    proposed: ProposedTransition,
    matched_rule_id: str,
    updated_by: str,
    occurred_at: datetime,
    snapshot_extensions: Optional[Dict[str, Any]] = None,
) -> OrchestrationState:
    ext: Dict[str, Any] = {"matched_rule_id": matched_rule_id}
    if proposed.record_extensions:
        ext = {**ext, **proposed.record_extensions}
    if snapshot_extensions:
        ext = {**ext, **snapshot_extensions}
    record = StateTransitionRecord(
        state_domain=proposed.state_domain,
        from_state=proposed.from_state,
        to_state=proposed.to_state,
        trigger=proposed.trigger,
        timestamp=occurred_at,
        actor=proposed.transition_actor,
        event_id=envelope.event_id,
        extensions=ext,
    )
    new_transitions: List[StateTransitionRecord] = list(state.transitions) + [record]
    new_audit = _model_copy(state.audit, updated_at=occurred_at, updated_by=updated_by)
    inactive_from_record: Dict[str, Any] = {}
    ranking_from_record: Dict[str, Any] = {}
    if proposed.record_extensions:
        inactive_from_record = {
            k: v
            for k, v in proposed.record_extensions.items()
            if isinstance(k, str) and k.startswith("inactive.")
        }
        ranking_from_record = {
            k: v
            for k, v in proposed.record_extensions.items()
            if isinstance(k, str) and k.startswith("ranking.")
        }
    new_snap_ext = dict(state.extensions)
    for k, v in inactive_from_record.items():
        if v is None:
            new_snap_ext.pop(k, None)
        else:
            new_snap_ext[k] = v
    for k, v in ranking_from_record.items():
        new_snap_ext[k] = v
    if snapshot_extensions:
        new_snap_ext = {**new_snap_ext, **snapshot_extensions}

    if proposed.state_domain == StateDomain.PIPELINE:
        new_pipeline = _model_copy(
            state.pipeline,
            phase=PipelinePhase(proposed.to_state),
            last_event_id=envelope.event_id,
            last_transition_at=occurred_at,
        )
        return _model_copy(
            state,
            pipeline=new_pipeline,  # type: ignore[arg-type]
            transitions=new_transitions,
            audit=new_audit,  # type: ignore[arg-type]
            extensions=new_snap_ext,  # type: ignore[arg-type]
        )

    if proposed.state_domain == StateDomain.DECISION:
        new_decision = _model_copy(
            state.decision,
            current_outcome=DecisionOutcome(proposed.to_state),
        )
        return _model_copy(
            state,
            decision=new_decision,  # type: ignore[arg-type]
            transitions=new_transitions,
            audit=new_audit,  # type: ignore[arg-type]
            extensions=new_snap_ext,  # type: ignore[arg-type]
        )

    new_comm = _model_copy(
        state.communication,
        status=CommunicationStatus(proposed.to_state),
    )
    return _model_copy(
        state,
        communication=new_comm,  # type: ignore[arg-type]
        transitions=new_transitions,
        audit=new_audit,  # type: ignore[arg-type]
        extensions=new_snap_ext,  # type: ignore[arg-type]
    )


def _build_emission_envelope(
    *,
    draft: OrchestrationEmissionDraft,
    causation_id: UUID,
    correlation_id: Optional[UUID],
    trace_id: Optional[str],
    request_id: Optional[str],
    actor_id: Optional[str],
    emission_index: int,
    occurred_at: datetime,
) -> EventEnvelope:
    eid = _emission_event_id_for(causation_id, emission_index, draft.event_type)
    meta = EventEnvelopeMetadata(
        trace_id=trace_id,
        request_id=request_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        actor_id=actor_id,
    )
    return EventEnvelope(
        event_id=eid,
        event_type=draft.event_type,
        occurred_at=occurred_at,
        subject_id=draft.subject_id,
        subject_kind=draft.subject_kind,
        payload=dict(draft.payload),
        metadata=meta,
        schema_version=draft.schema_version,
    )


def orchestration_to_handle_result(
    result: OrchestrationExecutionResult,
    *,
    handling_id: Optional[UUID] = None,
) -> HandleResult:
    """
    Map a structured orchestration outcome to a bus :class:`HandleResult`.

    ``ack_decision`` is a **signal** only; brokers/persistence interpret it in
    infrastructure layers outside this orchestrator.
    """

    hid = handling_id or uuid5(
        _ORCHESTRATION_ID_NS,
        f"handle:{result.trace.ingested_event_id}",
    )
    recorded_at = result.trace.ended_at or result.trace.started_at
    if recorded_at is None:
        recorded_at = datetime.now(timezone.utc)
    audit = HandleAudit(handling_id=hid, recorded_at=recorded_at)
    if result.ok:
        return HandleResult(
            status=DeliveryStatus.ACCEPTED,
            ack_decision=AckDecision.ACK,
            failure=None,
            audit=audit,
            produced_event_ids=list(result.produced_event_ids),
        )

    assert result.failure is not None
    f = result.failure
    if f.code in (
        OrchestrationFailureCode.PLAN_INVALID,
        OrchestrationFailureCode.STATE_MISMATCH,
        OrchestrationFailureCode.BOUNDS_EXCEEDED,
    ):
        status = DeliveryStatus.REJECTED
        ack: AckDecision = AckDecision.DROP
    elif f.code == OrchestrationFailureCode.EVENT_PUBLISH_FAILED:
        status = DeliveryStatus.FAILED
        ack = AckDecision.NACK
    else:
        status = DeliveryStatus.REJECTED
        ack = AckDecision.NACK

    bus_failure = EventBusFailure(
        category=FailureCategory.PERMANENT,
        message=f.message,
        code=f.code.value,
        details_ref=None,
        is_retryable=False,
        extensions=dict(f.details),
    )
    return HandleResult(
        status=status,
        ack_decision=ack,
        failure=bus_failure,
        audit=audit,
        produced_event_ids=[],
    )


class Orchestrator:
    """
    Synchronous orchestration runtime.

    Call :meth:`handle_event` with the current ``OrchestrationState`` snapshot and
    the ingested :class:`EventEnvelope`. The orchestrator never persists; callers
    own storage and timeline reconstruction.
    """

    def __init__(self, context: OrchestrationContext) -> None:
        self._ctx = context

    def handle_event(
        self,
        *,
        state: OrchestrationState,
        envelope: EventEnvelope,
        delivery: DeliveryContext,
    ) -> OrchestrationExecutionResult:
        run_id = _run_id_for_ingested_event(envelope.event_id)
        trace = OrchestrationTraceMeta(
            orchestration_execution_id=run_id,
            ingested_event_id=envelope.event_id,
            correlation_id=envelope.metadata.correlation_id,
            causation_id=envelope.metadata.causation_id,
            replay_mode=delivery.replay.replay_mode,
            replay_run_id=delivery.replay.replay_run_id,
            replay_sequence=delivery.replay.sequence,
            rule_set_id=self._ctx.rule_set_id,
            started_at=envelope.occurred_at,
        )
        decisions: List[OrchestrationDecisionRecord] = []
        skill_results: List[SkillExecutionResult] = []
        publish_results: List[PublishResult] = []
        produced_ids: List[UUID] = []

        def _fail(
            code: OrchestrationFailureCode,
            message: str,
            *,
            details: Optional[Dict[str, Any]] = None,
            transition_result: Optional[TransitionValidationResult] = None,
        ) -> OrchestrationExecutionResult:
            ended = envelope.occurred_at
            trace_done = _model_copy(trace, ended_at=ended)
            decisions.append(
                OrchestrationDecisionRecord(
                    kind=OrchestrationDecisionKind.REJECTED,
                    message=message,
                    code=code.value,
                )
            )
            return OrchestrationExecutionResult(
                ok=False,
                failure=OrchestrationFailure(code=code, message=message, details=details or {}),
                transition_result=transition_result,
                new_state=None,
                skill_results=skill_results,
                publish_results=publish_results,
                produced_event_ids=produced_ids,
                decisions=tuple(decisions),
                trace=trace_done,  # type: ignore[arg-type]
            )

        plan = self._ctx.planner.plan(state=state, envelope=envelope, delivery=delivery)

        if len(plan.skills) > self._ctx.limits.max_skills_per_event:
            return _fail(
                OrchestrationFailureCode.BOUNDS_EXCEEDED,
                "OrchestrationPlan exceeds max_skills_per_event",
                details={"limit": self._ctx.limits.max_skills_per_event, "requested": len(plan.skills)},
            )
        if len(plan.emissions) > self._ctx.limits.max_emissions_per_event:
            return _fail(
                OrchestrationFailureCode.BOUNDS_EXCEEDED,
                "OrchestrationPlan exceeds max_emissions_per_event",
                details={"limit": self._ctx.limits.max_emissions_per_event, "requested": len(plan.emissions)},
            )

        decisions.append(
            OrchestrationDecisionRecord(
                kind=OrchestrationDecisionKind.PLAN_ACCEPTED,
                message="Planner produced a bounded orchestration plan",
                code="plan",
                extensions={
                    "skills": len(plan.skills),
                    "emissions": len(plan.emissions),
                    "has_transition": plan.proposed_transition is not None,
                    "has_secondary_transition": plan.secondary_proposed_transition is not None,
                },
            )
        )

        tv: Optional[TransitionValidationResult] = None
        tv_secondary: Optional[TransitionValidationResult] = None
        if plan.proposed_transition is not None:
            pt = plan.proposed_transition
            current = _current_domain_snapshot(state, pt.state_domain)
            if current != pt.from_state:
                return _fail(
                    OrchestrationFailureCode.STATE_MISMATCH,
                    "Plan from_state does not match current aggregate snapshot",
                    details={
                        "domain": pt.state_domain.value,
                        "expected_from": pt.from_state,
                        "actual": current,
                    },
                )

            tctx = TransitionContext(
                state_domain=pt.state_domain,
                from_state=pt.from_state,
                to_state=pt.to_state,
                trigger=pt.trigger,
                actor=pt.transition_actor,
                event_id=envelope.event_id,
                human_override=pt.human_override,
                rule_set_id=self._ctx.rule_set_id,
                replay=_build_transition_replay(delivery),
            )
            tv = self._ctx.transition_engine.validate(tctx)
            if not tv.ok:
                return _fail(
                    OrchestrationFailureCode.TRANSITION_REJECTED,
                    "Transition engine rejected proposed transition",
                    details={"rejections": [_pydantic_dump(r) for r in tv.rejections]},
                    transition_result=tv,
                )

            decisions.append(
                OrchestrationDecisionRecord(
                    kind=OrchestrationDecisionKind.TRANSITION_VALIDATED,
                    message="Transition engine accepted proposed transition",
                    code=tv.matched_rule_id,
                )
            )

        for skill_index, spec in enumerate(plan.skills):
            skill = self._ctx.skills.get(spec.skill_name)
            if skill is None:
                return _fail(
                    OrchestrationFailureCode.SKILL_NOT_REGISTERED,
                    f"Skill not registered: {spec.skill_name!r}",
                    details={"skill_name": spec.skill_name},
                    transition_result=tv,
                )

            execution_id = _skill_execution_id_for(envelope.event_id, skill_index, spec.skill_name)
            exc_ctx = _build_execution_context(
                envelope=envelope,
                delivery=delivery,
                execution_id=execution_id,
            )
            result = skill.execute(spec.input, exc_ctx)
            skill_results.append(result)

            decisions.append(
                OrchestrationDecisionRecord(
                    kind=OrchestrationDecisionKind.SKILL_DISPATCHED,
                    message=f"Executed skill {spec.skill_name!r}",
                    code=result.status.value,
                )
            )

            if spec.required and result.status not in (
                ExecutionStatus.SUCCEEDED,
                ExecutionStatus.PARTIAL_SUCCESS,
                ExecutionStatus.SKIPPED,
            ):
                return _fail(
                    OrchestrationFailureCode.SKILL_EXECUTION_REJECTED,
                    f"Required skill {spec.skill_name!r} returned status {result.status.value}",
                    details={"skill_name": spec.skill_name, "status": result.status.value},
                    transition_result=tv,
                )

        decision_snapshot_extensions: Dict[str, Any] = {}
        if plan.skills:
            from orchestrator.vertical_slice_planner import merge_vertical_slice_decision_snapshot_extensions

            decision_snapshot_extensions = merge_vertical_slice_decision_snapshot_extensions(
                plan.skills, skill_results, prior_extensions=dict(state.extensions)
            )

        occurred_at = envelope.occurred_at
        if plan.proposed_transition is None:
            new_state = _touch_audit(state, updated_by=self._ctx.updated_by, occurred_at=occurred_at)
            if decision_snapshot_extensions:
                new_state = _model_copy(
                    new_state,
                    extensions={**new_state.extensions, **decision_snapshot_extensions},  # type: ignore[arg-type]
                )
            if not plan.skills and not plan.emissions:
                decisions.append(
                    OrchestrationDecisionRecord(
                        kind=OrchestrationDecisionKind.NOOP,
                        message="Empty plan: deterministic no-op",
                        code="noop",
                    )
                )
        else:
            assert tv is not None and tv.ok and tv.matched_rule_id is not None
            new_state = _commit_transition(
                state,
                envelope=envelope,
                proposed=plan.proposed_transition,
                matched_rule_id=tv.matched_rule_id,
                updated_by=self._ctx.updated_by,
                occurred_at=occurred_at,
                snapshot_extensions=decision_snapshot_extensions or None,
            )
            decisions.append(
                OrchestrationDecisionRecord(
                    kind=OrchestrationDecisionKind.STATE_COMMITTED,
                    message="Committed validated transition to orchestration state snapshot",
                    code=plan.proposed_transition.to_state,
                )
            )

            if plan.secondary_proposed_transition is not None:
                pt2 = plan.secondary_proposed_transition
                current2 = _current_domain_snapshot(new_state, pt2.state_domain)
                if current2 != pt2.from_state:
                    return _fail(
                        OrchestrationFailureCode.STATE_MISMATCH,
                        "Secondary plan from_state does not match post-primary aggregate snapshot",
                        details={
                            "domain": pt2.state_domain.value,
                            "expected_from": pt2.from_state,
                            "actual": current2,
                        },
                        transition_result=tv,
                    )
                tctx2 = TransitionContext(
                    state_domain=pt2.state_domain,
                    from_state=pt2.from_state,
                    to_state=pt2.to_state,
                    trigger=pt2.trigger,
                    actor=pt2.transition_actor,
                    event_id=envelope.event_id,
                    human_override=pt2.human_override,
                    rule_set_id=self._ctx.rule_set_id,
                    replay=_build_transition_replay(delivery),
                )
                tv_secondary = self._ctx.transition_engine.validate(tctx2)
                if not tv_secondary.ok:
                    return _fail(
                        OrchestrationFailureCode.TRANSITION_REJECTED,
                        "Transition engine rejected secondary proposed transition",
                        details={"rejections": [_pydantic_dump(r) for r in tv_secondary.rejections]},
                        transition_result=tv_secondary,
                    )
                decisions.append(
                    OrchestrationDecisionRecord(
                        kind=OrchestrationDecisionKind.TRANSITION_VALIDATED,
                        message="Transition engine accepted secondary proposed transition",
                        code=tv_secondary.matched_rule_id,
                    )
                )
                assert tv_secondary.matched_rule_id is not None
                new_state = _commit_transition(
                    new_state,
                    envelope=envelope,
                    proposed=pt2,
                    matched_rule_id=tv_secondary.matched_rule_id,
                    updated_by=self._ctx.updated_by,
                    occurred_at=occurred_at,
                    snapshot_extensions=None,
                )
                decisions.append(
                    OrchestrationDecisionRecord(
                        kind=OrchestrationDecisionKind.STATE_COMMITTED,
                        message="Committed secondary validated transition to orchestration state snapshot",
                        code=pt2.to_state,
                    )
                )
                tv = tv_secondary

        if self._ctx.publisher is not None:
            for emission_index, draft in enumerate(plan.emissions):
                out = _build_emission_envelope(
                    draft=draft,
                    causation_id=envelope.event_id,
                    correlation_id=envelope.metadata.correlation_id,
                    trace_id=envelope.metadata.trace_id,
                    request_id=envelope.metadata.request_id,
                    actor_id=envelope.metadata.actor_id,
                    emission_index=emission_index,
                    occurred_at=occurred_at,
                )
                decisions.append(
                    OrchestrationDecisionRecord(
                        kind=OrchestrationDecisionKind.EMISSION_SCHEDULED,
                        message=f"Publishing derived event {out.event_type!r}",
                        code=out.event_type,
                    )
                )
                pr = self._ctx.publisher.publish(out)
                publish_results.append(pr)
                if pr.status not in (DeliveryStatus.ACCEPTED, DeliveryStatus.SKIPPED):
                    assert pr.failure is not None
                    return _fail(
                        OrchestrationFailureCode.EVENT_PUBLISH_FAILED,
                        "Event publisher rejected or failed an emission",
                        details={
                            "publish_status": pr.status.value,
                            "failure": _pydantic_dump(pr.failure),
                            "event_type": out.event_type,
                        },
                        transition_result=tv,
                    )
                produced_ids.append(out.event_id)

        trace_done = _model_copy(trace, ended_at=occurred_at)
        decisions.append(
            OrchestrationDecisionRecord(
                kind=OrchestrationDecisionKind.RUN_COMPLETED,
                message="Orchestration run completed successfully",
                code="complete",
            )
        )
        return OrchestrationExecutionResult(
            ok=True,
            failure=None,
            transition_result=tv,
            new_state=new_state,  # type: ignore[arg-type]
            skill_results=skill_results,
            publish_results=publish_results,
            produced_event_ids=produced_ids,
            decisions=tuple(decisions),
            trace=trace_done,  # type: ignore[arg-type]
        )

