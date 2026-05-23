"""
First runnable deterministic recruiter vertical-slice integration bootstrap.

Orchestration bootstrap philosophy
-----------------------------------
This module is a **deliberately simple wiring harness**: it composes the transition
engine, default pipeline registry, :class:`~orchestrator.vertical_slice_planner.VerticalSlicePlanner`,
:class:`~orchestrator.orchestrator.Orchestrator`, in-memory bus/store, and bounded fake
skills to prove the **event → validate → skills → state → emit** loop end-to-end. It is
not a deployment entrypoint—no databases, brokers, LLMs, or async (see ``AGENTS.md``).

Module boundary (wiring only)
------------------------------
**Allowed** — this module may only:

- Wire the vertical-slice runtime (bus, store, orchestrator, skills, subscriptions)
- Drive the scripted demo / primary sequence (:func:`drive_vertical_slice_primary_sequence`)
- Re-export symbols for backward compatibility (thin shims to :mod:`modules.recruitment.policies`,
  :mod:`modules.recruitment.ingress`, :mod:`modules.recruitment.inspection`)

**Forbidden** — do not add here:

- Business rules, ingress allowlists, or governance policy (see :mod:`modules.recruitment.policies`)
- Ranking logic (see :mod:`modules.recruitment.ranking`)
- Candidate/read-model projection (see :mod:`modules.recruitment.projection`)
- Ingress envelope builders or scripted envelope sequences (see :mod:`modules.recruitment.ingress`)
- Inspection catalogs or timeline rendering (see :mod:`modules.recruitment.inspection`)
- Reusable helpers that other modules could depend on (move to the owning module instead)

Import rule: only :mod:`modules.recruitment.runtime` and :mod:`integrations.api` (plus
``runtime/*`` compatibility shims) should import this module directly.

Deterministic integration semantics
-------------------------------------
Fake and stub skills are **pure and synchronous**; the orchestrator remains the sole
authority for validated transitions. Orchestrator emissions are captured by a small
**collector publisher** so state can be committed **before** derived envelopes hit the
bus—avoiding nested-dispatch seeing a stale store snapshot (see orchestrator ordering in
``docs/architecture/tech_debt.md``). After each successful run, collected emissions are
published to the in-memory bus in declaration order.

Replay-safe workflow validation
-------------------------------
Callers may set ``ReplayContext`` on deliveries for replay harnesses; this bootstrap uses
live-mode replay flags by default. State snapshots are deep-copied via
:class:`~runtime.in_memory_state_store.InMemoryStateStore` so each successful orchestration
commit replaces the snapshot explicitly.

Why fake (and stub) skills exist
---------------------------------
Fake skills validate **control-plane wiring** and contracts before real cognition layers.
Stub skills here cover planner slots not yet backed by dedicated fake modules
(``candidate_created``, ``cv_parsed``, ``questionnaire_stage``) with minimal **audit-safe**
success envelopes so the slice remains runnable without expanding scope.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, List, Mapping, Optional, Sequence, Tuple, Union
from uuid import UUID, uuid4, uuid5

from interfaces.event_bus_interface import (
    AckDecision,
    DeliveryContext,
    DeliveryStatus,
    EventBusFailure,
    EventEnvelope,
    EventEnvelopeMetadata,
    FailureCategory,
    HandleAudit,
    HandleResult,
    PublishAudit,
    PublishResult,
    ReplayContext,
    SubscriptionSelector,
    SubscriptionSpec,
)
from interfaces.skill_interface import (
    DeterminismClass,
    DeterministicBoundary,
    EvidenceKind,
    EvidenceRef,
    ExecutionAudit,
    ExecutionContext,
    ExecutionStatus,
    ExecutionTiming,
    Skill,
    SkillExecutionResult,
    SkillInputEnvelope,
    SkillKind,
    SkillMetadata,
    SkillOutputEnvelope,
)
from orchestrator.orchestrator import (
    OrchestrationContext,
    OrchestrationExecutionResult,
    Orchestrator,
    orchestration_to_handle_result,
)
from orchestrator.vertical_slice_planner import (
    SKILL_CANDIDATE_CREATED,
    SKILL_CV_PARSED,
    SKILL_CV_UPLOADED,
    SKILL_QUESTIONNAIRE_STAGE,
    VerticalSlicePlanner,
)
from runtime.in_memory_event_bus import InMemoryEventBus, SimpleEventSubscription
from runtime.in_memory_state_store import (
    InMemoryStateStore,
    InMemoryStateStoreConfig,
    StateStoreFailureCode,
)
from runtime.persistence.sqlite_state_store import SQLiteStateStore
from schemas.state_schema import (
    OrchestrationState,
    PipelinePhase,
    PipelineState,
    StateAudit,
    StateLink,
)
from skills.deterministic.fake_cv_uploaded_skill import FakeCvUploadedSkill
from skills.deterministic.fake_deep_scoring_skill import FakeDeepScoringSkill
from skills.deterministic.fake_hard_filter_skill import FakeHardFilterSkill
from skills.deterministic.fake_light_scoring_skill import FakeLightScoringSkill
from state_machine.transition_engine import TransitionEngine, default_pipeline_registry

from .ingress import BOOT_NS as _BOOT_NS
from .ingress import FIXED_CLOCK as _FIXED_CLOCK
from .ingress import build_ingress_envelope as _envelope
from .ingress import vertical_slice_primary_ingress_envelopes
from .inspection.catalog import resolve_vertical_slice_inspection_catalog
from .policies import PRIMARY_VERTICAL_SLICE_EVENT_TYPES, VERTICAL_SLICE_INGRESS_EVENT_TYPES
from .state_init import initial_orchestration_state as _initial_state
_STUB_AUDIT_TIME = datetime(2026, 5, 1, 0, 0, 0, tzinfo=timezone.utc)

# Stable ids for the reference vertical slice (bootstrap + API ingress).
VERTICAL_SLICE_DEFAULT_CANDIDATE_ID = uuid5(_BOOT_NS, "vertical_slice.candidate_subject")


def _state_id_for_candidate(candidate_id: UUID) -> UUID:
    return uuid5(_BOOT_NS, f"candidate:{candidate_id}")


VERTICAL_SLICE_DEFAULT_STATE_ID = _state_id_for_candidate(VERTICAL_SLICE_DEFAULT_CANDIDATE_ID)


def _state_id() -> UUID:
    return _state_id_for_candidate(_candidate_id())


def _candidate_id() -> UUID:
    return uuid5(_BOOT_NS, "vertical_slice.candidate_subject")


def _dump_state_summary(state: OrchestrationState) -> str:
    if hasattr(state, "model_dump"):
        d = state.model_dump()
    else:
        d = state.dict()
    return (
        f"pipeline.phase={d.get('pipeline', {}).get('phase')} "
        f"transitions={len(d.get('transitions', []))} "
        f"state_id={d.get('id')}"
    )


def _summarize_skill_result(res: SkillExecutionResult) -> str:
    meta = res.metadata
    base = f"{meta.skill_name} status={res.status.value}"
    if res.output and res.output.payload:
        p = res.output.payload
        if "scoring.deep.normalized_score" in p:
            return f"{base} deep_score={p.get('scoring.deep.normalized_score')}"
        if "scoring.normalized_score" in p:
            return f"{base} score={p.get('scoring.normalized_score')}"
        if "filter.decision" in p:
            return f"{base} filter={p.get('filter.decision')}"
        if p.get("stub"):
            return f"{base} stub_path={p.get('planner_path')}"
    return base


class _EmissionCollector:
    """
    Captures orchestrator draft emissions synchronously.

    The real bus is fed **after** the subscriber commits ``OrchestrationState`` so
    downstream handlers observe the post-transition snapshot.
    """

    def __init__(self) -> None:
        self._pending: List[EventEnvelope] = []

    def publish(self, envelope: EventEnvelope) -> PublishResult:
        self._pending.append(envelope)
        pid = uuid5(_BOOT_NS, f"collector_publish:{envelope.event_id}")
        audit = PublishAudit(publish_id=pid, recorded_at=envelope.occurred_at, runtime="bootstrap.collector")
        return PublishResult(status=DeliveryStatus.ACCEPTED, failure=None, audit=audit)

    def drain(self) -> List[EventEnvelope]:
        out = list(self._pending)
        self._pending.clear()
        return out


class _StubVerticalSliceSkill:
    """Minimal deterministic success skill for planner slots without dedicated fakes yet."""

    metadata: SkillMetadata
    _runtime_label: str

    def __init__(self, *, skill_name: str, runtime_label: str) -> None:
        self._runtime_label = runtime_label
        self.metadata = SkillMetadata(
            skill_name=skill_name,
            skill_version="1.0.0",
            kind=SkillKind.DETERMINISTIC,
            boundary=DeterministicBoundary(
                determinism_class=DeterminismClass.PURE_DETERMINISTIC,
                kind=SkillKind.DETERMINISTIC,
                requires_input_snapshot=False,
                requires_output_snapshot=False,
                requires_model_capture=False,
            ),
            description="Vertical-slice bootstrap stub (deterministic noop body).",
            supports_dry_run=True,
            supports_replay=True,
            supports_idempotency=True,
            tags=["vertical_slice", "stub"],
        )

    def execute(
        self, skill_input: SkillInputEnvelope, context: ExecutionContext
    ) -> SkillExecutionResult:
        raw = (context.extensions or {}).get("orchestrator_skill_execution_id")
        exec_id = UUID(str(raw)) if raw else uuid5(_BOOT_NS, f"{self.metadata.skill_name}|stub")
        timing = ExecutionTiming(
            started_at=_STUB_AUDIT_TIME,
            ended_at=_STUB_AUDIT_TIME,
            duration_ms=0,
        )
        audit = ExecutionAudit(
            execution_id=exec_id,
            recorded_at=_STUB_AUDIT_TIME,
            runtime=self._runtime_label,
            model_info={},
            extensions={"stub_skill": True},
        )
        return SkillExecutionResult(
            metadata=self.metadata,
            status=ExecutionStatus.SUCCEEDED,
            output=SkillOutputEnvelope(
                payload={
                    "stub": True,
                    "ingested_event_id": skill_input.payload.get("ingested_event_id"),
                    "planner_path": skill_input.payload.get("vertical_slice.planner_path"),
                },
                evidence_refs=[
                    EvidenceRef(
                        kind=EvidenceKind.STRUCTURED_RECORD,
                        ref=f"structured://stub/{self.metadata.skill_name}",
                        created_at=_STUB_AUDIT_TIME,
                    )
                ],
            ),
            timing=timing,
            audit=audit,
            metrics={"stub.executed": 1.0},
        )


def _skill_registry() -> Dict[str, Skill]:
    return {
        SKILL_CANDIDATE_CREATED: _StubVerticalSliceSkill(
            skill_name=SKILL_CANDIDATE_CREATED,
            runtime_label="runtime.stub.candidate_created",
        ),
        SKILL_CV_UPLOADED: FakeCvUploadedSkill(),
        SKILL_CV_PARSED: _StubVerticalSliceSkill(
            skill_name=SKILL_CV_PARSED,
            runtime_label="runtime.stub.cv_parsed",
        ),
        FakeHardFilterSkill().metadata.skill_name: FakeHardFilterSkill(),
        FakeLightScoringSkill().metadata.skill_name: FakeLightScoringSkill(),
        FakeDeepScoringSkill().metadata.skill_name: FakeDeepScoringSkill(),
        SKILL_QUESTIONNAIRE_STAGE: _StubVerticalSliceSkill(
            skill_name=SKILL_QUESTIONNAIRE_STAGE,
            runtime_label="runtime.stub.questionnaire_stage",
        ),
    }


StateStoreLike = Union[InMemoryStateStore, SQLiteStateStore]


@dataclass
class VerticalSliceRuntimeBundle:
    """Wired transition engine + orchestrator + bus/store for integration and replay tests."""

    bus: InMemoryEventBus
    store: StateStoreLike
    state_id: UUID
    candidate_id: UUID
    correlation_id: UUID
    subscriber: _OrchestrationSubscriber


def wire_vertical_slice_runtime(
    *,
    bus: Optional[InMemoryEventBus] = None,
    clock: Optional[Callable[[], datetime]] = None,
    skills: Optional[Mapping[str, Skill]] = None,
    planner: Optional[VerticalSlicePlanner] = None,
    store: Optional[StateStoreLike] = None,
) -> VerticalSliceRuntimeBundle:
    """
    Compose the same runtime as :func:`run_vertical_slice_bootstrap` without publishing events.

    ``clock`` bounds state-store revision timestamps when creating the default
    :class:`~runtime.in_memory_state_store.InMemoryStateStore`; ingress envelopes use
    :data:`_FIXED_CLOCK` via :func:`_envelope`.

    Pass ``store`` to use :class:`~runtime.persistence.sqlite_state_store.SQLiteStateStore`
    or a preconfigured in-memory store; when set, ``clock`` is ignored for store creation
    (the store's own config supplies the clock).

    Pass ``skills`` and/or ``planner`` to exercise alternate registries or planner policy
    in harness tests (defaults match the CLI vertical slice).
    """
    state_id = _state_id()
    candidate_id = _candidate_id()
    correlation_id = candidate_id

    registry = default_pipeline_registry()
    engine = TransitionEngine(registry)
    use_planner = planner if planner is not None else VerticalSlicePlanner()
    use_bus = bus or InMemoryEventBus()
    collector = _EmissionCollector()
    tick = clock or (lambda: _FIXED_CLOCK)
    if store is not None:
        use_store = store
    else:
        use_store = InMemoryStateStore(
            InMemoryStateStoreConfig(clock=tick),
        )

    skill_map: Dict[str, Skill] = dict(skills) if skills is not None else _skill_registry()

    ctx = OrchestrationContext(
        transition_engine=engine,
        planner=use_planner,
        skills=skill_map,
        publisher=collector,
        rule_set_id="default_pipeline_registry",
        updated_by="bootstrap_vertical_slice",
    )
    orchestrator = Orchestrator(ctx)

    sub = _OrchestrationSubscriber(
        orchestrator=orchestrator,
        store=use_store,
        state_id=state_id,
        bus=use_bus,
        collector=collector,
    )
    use_bus.register_subscription(
        SimpleEventSubscription(
            spec=SubscriptionSpec(
                subscriber_id="vertical_slice.orchestrator",
                subscription_id="bootstrap.vertical_slice.orchestrator",
                selector=SubscriptionSelector(subject_kind="candidate"),
            ),
            handler=sub,
        )
    )

    init = _initial_state(state_id=state_id, candidate_id=candidate_id, occurred_at=_FIXED_CLOCK)
    created = use_store.create(init)
    if not created.ok:
        if (
            created.failure is not None
            and created.failure.code == StateStoreFailureCode.ALREADY_EXISTS
        ):
            got = use_store.get(state_id)
            if not got.ok or got.snapshot is None:
                raise RuntimeError(
                    f"state store already_exists but get failed: {got.failure}"
                )
            # Persisted file (e.g. SQLite): same deterministic aggregate id across restarts.
        else:
            raise RuntimeError(f"state store create failed: {created.failure}")
    
    return VerticalSliceRuntimeBundle(
        bus=use_bus,
        store=use_store,
        state_id=state_id,
        candidate_id=candidate_id,
        correlation_id=correlation_id,
        subscriber=sub,
    )


def drive_vertical_slice_primary_sequence(
    bundle: VerticalSliceRuntimeBundle,
    *,
    verbose: bool = False,
    print_timeline: bool = False,
    timeline_envelopes: Optional[Sequence[EventEnvelope]] = None,
) -> OrchestrationState:
    """
    Publish :data:`PRIMARY_VERTICAL_SLICE_EVENT_TYPES` in order (same as the CLI bootstrap).

    When ``print_timeline`` is true, append a human-readable inspection timeline (see
    :func:`vertical_slice_timeline_text`). If ``timeline_envelopes`` is omitted, the
    timeline uses :func:`resolve_vertical_slice_inspection_catalog` so a recording bus
    (when present) enriches labels for runtime-emitted ingests (e.g.
    ``questionnaire_requested``).
    """
    state_id = bundle.state_id
    bus = bundle.bus
    sub = bundle.subscriber
    store = bundle.store

    if verbose:
        cur0 = store.get(state_id)
        if cur0.ok and cur0.snapshot is not None:
            print("=== BlueOcean vertical slice bootstrap (deterministic) ===")
            print(f"initial {_dump_state_summary(cur0.snapshot)}")

    history_offset = 0
    for env in vertical_slice_primary_ingress_envelopes(bundle):
        pr = bus.publish(env)
        if verbose:
            print(f"\n-- publish {env.event_type!r} status={pr.status.value} event_id={env.event_id}")

        if pr.status != DeliveryStatus.ACCEPTED:
            raise RuntimeError(f"publish failed for {env.event_type!r}: {pr.failure}")

        snap = store.get(state_id)
        if not snap.ok or snap.snapshot is None:
            raise RuntimeError("state missing after publish")
        if verbose:
            print(f"   state {_dump_state_summary(snap.snapshot)}")

        new_runs = sub.run_history[history_offset:]
        history_offset = len(sub.run_history)
        if verbose and new_runs:
            for idx, lr in enumerate(new_runs, start=1):
                tag = f"orchestration_run[{idx}/{len(new_runs)}]"
                print(f"   --- {tag} ok={lr.ok} ---")
                if lr.decisions:
                    for d in lr.decisions[-6:]:
                        print(f"   decision {d.kind.value}: {d.message} code={d.code}")
                if lr.skill_results:
                    print("   skills:")
                    for sr in lr.skill_results:
                        print(f"      {_summarize_skill_result(sr)}")
                if lr.produced_event_ids:
                    print(f"   emitted_event_ids: {[str(x) for x in lr.produced_event_ids]}")

    final = store.get(state_id)
    if not final.ok or final.snapshot is None:
        raise RuntimeError("final state missing")
    if verbose:
        print("\n=== final snapshot ===")
        print(_dump_state_summary(final.snapshot))
        print(f"terminal pipeline phase: {final.snapshot.pipeline.phase.value!r}")
        if final.snapshot.pipeline.phase != PipelinePhase.SHORTLISTED:
            print("WARNING: expected shortlisted; check planner/registry alignment.")
    if print_timeline:
        if timeline_envelopes is not None:
            print(vertical_slice_timeline_text(bundle, timeline_envelopes))
        else:
            print(vertical_slice_timeline_text(bundle))
    return final.snapshot


def _reject_handle(message: str) -> HandleResult:
    audit = HandleAudit(handling_id=uuid4(), recorded_at=_FIXED_CLOCK, runtime="bootstrap_vertical_slice")
    return HandleResult(
        status=DeliveryStatus.REJECTED,
        ack_decision=AckDecision.DROP,
        failure=EventBusFailure(
            category=FailureCategory.VALIDATION_ERROR,
            message=message,
            code="bootstrap_vertical_slice.store_precondition",
        ),
        audit=audit,
    )


def _fail_handle(message: str) -> HandleResult:
    audit = HandleAudit(handling_id=uuid4(), recorded_at=_FIXED_CLOCK, runtime="bootstrap_vertical_slice")
    return HandleResult(
        status=DeliveryStatus.FAILED,
        ack_decision=AckDecision.NACK,
        failure=EventBusFailure(
            category=FailureCategory.PERMANENT,
            message=message,
            code="bootstrap_vertical_slice.store_commit",
        ),
        audit=audit,
    )


@dataclass
class _OrchestrationSubscriber:
    """Invokes orchestrator, commits state, then fans out collected emissions to the bus."""

    orchestrator: Orchestrator
    store: StateStoreLike
    state_id: UUID
    bus: InMemoryEventBus
    collector: _EmissionCollector
    last_run: Optional[OrchestrationExecutionResult] = field(default=None, repr=False)
    run_history: List[OrchestrationExecutionResult] = field(default_factory=list, repr=False)

    def handle(self, envelope: EventEnvelope, context: DeliveryContext) -> HandleResult:
        cur = self.store.get_for_candidate(envelope.subject_id)
        if not cur.ok or cur.snapshot is None or cur.meta is None:
            return _reject_handle("orchestration snapshot missing before handle")

        state_id = cur.meta.state_id
        result = self.orchestrator.handle_event(
            state=cur.snapshot,
            envelope=envelope,
            delivery=context,
        )
        self.last_run = result
        self.run_history.append(result)

        if result.ok and result.new_state is not None:
            rep = self.store.replace(
                state_id,
                result.new_state,
                expected_store_revision=cur.meta.store_revision,
            )
            if not rep.ok:
                return _fail_handle(f"state store replace failed: {rep.failure}")

            for em in self.collector.drain():
                pr = self.bus.publish(em)
                if pr.status != DeliveryStatus.ACCEPTED:
                    return _fail_handle(f"emission publish failed for {em.event_type!r}")

        return orchestration_to_handle_result(result)


def run_vertical_slice_bootstrap(
    *,
    verbose: bool = True,
    print_timeline: bool = False,
    timeline_envelopes: Optional[Sequence[EventEnvelope]] = None,
) -> OrchestrationState:
    """
    Wire bus + store + orchestrator and drive the default recruiter slice through ``shortlisted``.

    Publishes the primary ingress sequence; ranking after light and deep scoring is applied
    inside the planner on the same ingest (no separate ``ranking_completed`` publish).
    """
    bundle = wire_vertical_slice_runtime()
    return drive_vertical_slice_primary_sequence(
        bundle,
        verbose=verbose,
        print_timeline=print_timeline,
        timeline_envelopes=timeline_envelopes,
    )


if __name__ == "__main__":
    '''leave print_timeline=True for timeline inspection'''
    run_vertical_slice_bootstrap(verbose=True, print_timeline=True)


def vertical_slice_timeline_text(
    bundle: VerticalSliceRuntimeBundle,
    envelope_catalog: Optional[Sequence[EventEnvelope]] = None,
    *,
    include_operator_navigation: bool = True,
) -> str:
    """Compatibility entry; implementation lives in :mod:`modules.recruitment.inspection.timeline`."""
    from .inspection.timeline import vertical_slice_timeline_text as _render

    return _render(
        bundle,
        envelope_catalog,
        include_operator_navigation=include_operator_navigation,
    )


__all__ = (
    "PRIMARY_VERTICAL_SLICE_EVENT_TYPES",
    "VERTICAL_SLICE_DEFAULT_CANDIDATE_ID",
    "VERTICAL_SLICE_DEFAULT_STATE_ID",
    "VERTICAL_SLICE_INGRESS_EVENT_TYPES",
    "VerticalSliceRuntimeBundle",
    "_initial_state",
    "_skill_registry",
    "drive_vertical_slice_primary_sequence",
    "resolve_vertical_slice_inspection_catalog",
    "run_vertical_slice_bootstrap",
    "vertical_slice_primary_ingress_envelopes",
    "vertical_slice_timeline_text",
    "wire_vertical_slice_runtime",
)
