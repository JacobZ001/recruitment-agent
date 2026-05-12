"""
Synchronous in-memory :class:`~interfaces.event_bus_interface.EventBus` runtime.

Purpose
-------
Provide the first **concrete** implementation of the canonical event bus contracts
for vertical-slice runs, local tests, deterministic workflow checks, and demos.
This module is **infrastructure-light**: no broker, no disk, no async, no retries.

Boundaries
----------
- **In scope**: ``publish``, subscription registry, deterministic subscriber ordering,
  selector-based fan-out, structured :class:`HandleResult` collection per dispatch,
  replay *signals* on :class:`DeliveryContext` (constructor-configured by default),
  and **runtime boundary isolation** around subscriber ``handle`` calls.
- **Out of scope**: distributed delivery, persistence/event store, at-least-once
  brokers, orchestration or transition logic, idempotent consumer dedupe (callers
  own higher layers).

Runtime boundary isolation philosophy
-------------------------------------
Subscribers are treated as **untrusted runtime execution units**: they may contain
application bugs, integration faults, or accidental raises. The bus **does not**
let uncaught exceptions abort ``publish()`` mid-fan-out; they become structured
:class:`HandleResult` failures so ordering remains defined and the dispatch trace
stays audit-complete. This preserves deterministic **dispatch** (who runs next)
even when a handler fails; it does not imply transactional rollback of handler
side effects (callers own compensation).

Deterministic dispatch philosophy
---------------------------------
Given the same registration set (subscription ids + specs + handlers) and the
same ``publish`` input envelope, dispatch order and match decisions are stable:

- Matched subscriptions are invoked in **lexicographic order of ``subscription_id``**
  (not registration order), so runs are reproducible across process restarts that
  re-register in a different order.
- Selector evaluation is a pure predicate over the envelope + spec (no I/O).
- **Handler failures do not stop the fan-out**: later subscribers still run in
  order; exceptions are converted to deterministic synthetic ``HandleResult`` rows
  with ``status=failed`` (see tech debt for re-entrancy if handlers call
  ``publish`` recursively).

Replay expectations
---------------------
Replay is **signal-only** (see ``ReplayContext`` / ``SubscriptionSpec.replay_enabled``
/ ``start_from_event_id``). This bus does not load historical streams.

- Optional ``dispatch_replay`` (set at bus construction) is **deep-copied** onto
  each :class:`DeliveryContext` so subscribers do not share a mutable replay object.
- If ``replay_enabled`` is false on a subscription, that subscription is skipped
  when ``dispatch_replay.replay_mode`` is true (deterministic no-dispatch).
- ``start_from_event_id`` gates delivery: until the bus observes an envelope whose
  ``event_id`` equals that anchor for a subscription, that subscription does not
  receive ``handle`` calls; once the anchor matches, ``seen_start_anchor`` is set and
  normal selector matching applies for subsequent publishes (replay/backfill
  positioning signal).

Relationship to contracts
---------------------------
Implements :class:`EventBus` and satisfies :class:`EventPublisher` for the same
``EventEnvelope`` type so orchestration code can pass the bus as ``publisher``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID, uuid4, uuid5

# Stable dispatch correlation IDs: derive from envelope + subscription (replay harness).
_BUS_DISPATCH_ID_NS = UUID("018f3e2a-7c9b-4a3d-8f0e-a11b00c0ff03")

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
    EventHandler,
    EventSubscription,
    FailureCategory,
    HandleAudit,
    HandleResult,
    PublishAudit,
    PublishResult,
    ReplayContext,
    SubscriptionSpec,
)


class _RuntimeBase(BaseModel):
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


class DispatchSkipReason(str, Enum):
    """Deterministic reasons a subscription did not run ``handle``."""

    REPLAY_DISABLED_FOR_SUBSCRIPTION = "replay_disabled_for_subscription"
    BEFORE_START_ANCHOR = "before_start_anchor"
    SELECTOR_MISMATCH = "selector_mismatch"


class SubscriberDispatchRecord(_RuntimeBase):
    """
    One row in the publish dispatch trace: match decision + optional handle outcome.

    Invariants:
    - ``handle_result`` is present iff ``dispatched`` is true.
    - ``skip_reason`` is present iff ``dispatched`` is false.
    """

    subscription_id: str = Field(..., min_length=1)
    subscriber_id: str = Field(..., min_length=1)
    delivery_id: UUID
    dispatched: bool
    skip_reason: Optional[DispatchSkipReason] = None
    handle_result: Optional[HandleResult] = None

    if _PYDANTIC_V2:

        @model_validator(mode="after")
        def _invariants(self):  # type: ignore[override]
            if self.dispatched:
                if self.handle_result is None:
                    raise ValueError("dispatched=true requires handle_result")
                if self.skip_reason is not None:
                    raise ValueError("dispatched=true forbids skip_reason")
            else:
                if self.skip_reason is None:
                    raise ValueError("dispatched=false requires skip_reason")
                if self.handle_result is not None:
                    raise ValueError("dispatched=false forbids handle_result")
            return self

    else:

        @root_validator
        def _invariants(cls, values):  # type: ignore[override]
            disp = values.get("dispatched")
            if disp:
                if values.get("handle_result") is None:
                    raise ValueError("dispatched=true requires handle_result")
                if values.get("skip_reason") is not None:
                    raise ValueError("dispatched=true forbids skip_reason")
            else:
                if values.get("skip_reason") is None:
                    raise ValueError("dispatched=false requires skip_reason")
                if values.get("handle_result") is not None:
                    raise ValueError("dispatched=false forbids handle_result")
            return values


class InMemoryDispatchTrace(_RuntimeBase):
    """Audit-safe summary for one ``publish`` call."""

    publish_id: UUID
    envelope_event_id: UUID
    envelope_event_type: str
    dispatch_records: Tuple[SubscriberDispatchRecord, ...] = Field(default_factory=tuple)
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    runtime_label: str = Field(default="runtime.in_memory_event_bus", min_length=1)


class InMemoryEventBusLimits(_RuntimeBase):
    """Hard caps to keep fan-out bounded per publish."""

    max_subscriptions_per_bus: int = Field(default=4096, ge=1)
    max_dispatch_per_publish: int = Field(default=256, ge=1)


class InMemoryEventBusConfig(_RuntimeBase):
    """
    Optional wiring for replay signals and observability.

    ``dispatch_replay`` is deep-copied for each delivery so subscribers cannot
    accidentally mutate shared replay state.
    """

    dispatch_replay: ReplayContext = Field(default_factory=ReplayContext)
    runtime_label: str = Field(default="runtime.in_memory_event_bus", min_length=1)
    host_label: Optional[str] = Field(default=None)
    limits: InMemoryEventBusLimits = Field(default_factory=InMemoryEventBusLimits)


@dataclass
class _SubscriptionEntry:
    spec: SubscriptionSpec
    handler: EventHandler[EventEnvelope]
    seen_start_anchor: bool = False


def _copy_replay(ctx: ReplayContext) -> ReplayContext:
    if _PYDANTIC_V2:
        return ctx.model_copy(deep=True)
    return ctx.copy(deep=True)  # type: ignore[call-arg]


def _selector_matches(envelope: EventEnvelope, spec: SubscriptionSpec) -> bool:
    sel = spec.selector
    if sel.event_types and envelope.event_type not in sel.event_types:
        return False
    if sel.subject_kind is not None:
        if envelope.subject_kind != sel.subject_kind:
            return False
    if sel.tags_any:
        meta_tags = set(envelope.metadata.tags or [])
        if not any(t in meta_tags for t in sel.tags_any):
            return False
    return True


def _aggregate_publish_status(results: List[HandleResult]) -> DeliveryStatus:
    if any(r.status == DeliveryStatus.FAILED for r in results):
        return DeliveryStatus.FAILED
    if any(r.status == DeliveryStatus.REJECTED for r in results):
        return DeliveryStatus.REJECTED
    if all(r.status == DeliveryStatus.SKIPPED for r in results):
        return DeliveryStatus.SKIPPED
    return DeliveryStatus.ACCEPTED


HANDLER_EXCEPTION_CODE = "in_memory_bus.handler_exception"


def _synthetic_handler_failure_result(
    exc: Exception,
    *,
    subscription_id: str,
    subscriber_id: str,
    delivery_id: UUID,
    runtime_label: str,
) -> HandleResult:
    """
    Deterministic contract-preserving outcome when ``handler.handle`` raises.

    Maps any ``Exception`` subclass to ``HandleResult`` with ``status=failed``,
    stable ``code``, and structured extensions for audit/replay tooling (no raw
    traceback embedded by default).
    """

    audit = HandleAudit(
        handling_id=uuid4(),
        recorded_at=datetime.now(timezone.utc),
        runtime=runtime_label,
    )
    exc_type = type(exc).__name__
    failure = EventBusFailure(
        category=FailureCategory.PERMANENT,
        message=f"Subscriber handler raised {exc_type}: {exc}",
        code=HANDLER_EXCEPTION_CODE,
        extensions={
            "exception_type": exc_type,
            "exception_module": getattr(type(exc), "__module__", ""),
            "subscription_id": subscription_id,
            "subscriber_id": subscriber_id,
            "delivery_id": str(delivery_id),
        },
    )
    return HandleResult(
        status=DeliveryStatus.FAILED,
        ack_decision=AckDecision.NACK,
        failure=failure,
        audit=audit,
        extensions={
            "handler_exception": True,
            "exception_type": exc_type,
            "synthetic_handle_result": True,
        },
    )


def _failure_for_status(status: DeliveryStatus, message: str) -> EventBusFailure:
    cat = FailureCategory.UNKNOWN
    if status == DeliveryStatus.REJECTED:
        cat = FailureCategory.VALIDATION_ERROR
    elif status == DeliveryStatus.FAILED:
        cat = FailureCategory.PERMANENT
    return EventBusFailure(category=cat, message=message, code=f"in_memory_bus.{status.value}")


def _dump_trace(trace: InMemoryDispatchTrace) -> Dict[str, Any]:
    if hasattr(trace, "model_dump"):
        return trace.model_dump()
    return trace.dict()


@dataclass(frozen=True)
class _PlannedSkip:
    subscription_id: str
    subscriber_id: str
    delivery_id: UUID
    reason: DispatchSkipReason


@dataclass(frozen=True)
class _PlannedDispatch:
    subscription_id: str
    subscriber_id: str
    delivery_id: UUID


def _build_publish_plan(
    *,
    ordered_ids: Tuple[str, ...],
    subs: Dict[str, _SubscriptionEntry],
    envelope: EventEnvelope,
    replay_base: ReplayContext,
) -> List[Union[_PlannedSkip, _PlannedDispatch]]:
    """
    Pure dry-run: does not call handlers or mutate ``_SubscriptionEntry.seen_start_anchor``.

    Uses a local anchor map mirroring per-subscription ``seen_start_anchor`` semantics.
    """

    anchor_map: Dict[str, bool] = {sid: subs[sid].seen_start_anchor for sid in ordered_ids}
    plan: List[Union[_PlannedSkip, _PlannedDispatch]] = []

    for sid in ordered_ids:
        entry = subs[sid]
        spec = entry.spec
        delivery_id = uuid5(_BUS_DISPATCH_ID_NS, f"delivery:{envelope.event_id}:{sid}")

        if replay_base.replay_mode and not spec.replay_enabled:
            plan.append(
                _PlannedSkip(
                    subscription_id=sid,
                    subscriber_id=spec.subscriber_id,
                    delivery_id=delivery_id,
                    reason=DispatchSkipReason.REPLAY_DISABLED_FOR_SUBSCRIPTION,
                )
            )
            continue

        if spec.start_from_event_id is not None and not anchor_map[sid]:
            if envelope.event_id != spec.start_from_event_id:
                plan.append(
                    _PlannedSkip(
                        subscription_id=sid,
                        subscriber_id=spec.subscriber_id,
                        delivery_id=delivery_id,
                        reason=DispatchSkipReason.BEFORE_START_ANCHOR,
                    )
                )
                continue
            anchor_map[sid] = True

        if not _selector_matches(envelope, spec):
            plan.append(
                _PlannedSkip(
                    subscription_id=sid,
                    subscriber_id=spec.subscriber_id,
                    delivery_id=delivery_id,
                    reason=DispatchSkipReason.SELECTOR_MISMATCH,
                )
            )
            continue

        plan.append(
            _PlannedDispatch(
                subscription_id=sid,
                subscriber_id=spec.subscriber_id,
                delivery_id=delivery_id,
            )
        )

    return plan


def _apply_anchor_progress(
    subs: Dict[str, _SubscriptionEntry],
    envelope: EventEnvelope,
    replay_base: ReplayContext,
    ordered_ids: Tuple[str, ...],
) -> None:
    """
    Mutate ``seen_start_anchor`` after handlers run.

    Mirrors dry-run semantics: crossing ``start_from_event_id`` flips the flag even
    if the selector did not match on that same envelope.
    """

    for sid in ordered_ids:
        entry = subs[sid]
        spec = entry.spec
        if replay_base.replay_mode and not spec.replay_enabled:
            continue
        if spec.start_from_event_id is not None and not entry.seen_start_anchor:
            if envelope.event_id == spec.start_from_event_id:
                entry.seen_start_anchor = True


@dataclass
class SimpleEventSubscription:
    """
    Concrete :class:`EventSubscription` for registry use.

    Handlers should treat ``envelope`` as read-only; the bus never mutates it.
    Handlers are **untrusted** at the runtime boundary: exceptions are isolated
    (see module docstring).
    """

    spec: SubscriptionSpec
    handler: EventHandler[EventEnvelope]


class InMemoryEventBus:
    """
    Synchronous in-memory event bus + publisher.

    Threading/asyncio are intentionally unsupported: callers must not invoke
    ``publish`` concurrently unless they enforce external locking.

    **Exception boundary**: each ``handle`` invocation is isolated; raises become
    synthetic ``HandleResult`` failures so ``publish()`` completes and remaining
    subscribers run in deterministic order. Recursive ``publish`` from within
    handlers is not governed here (see tech debt).
    """

    def __init__(self, config: Optional[InMemoryEventBusConfig] = None) -> None:
        self._config = config or InMemoryEventBusConfig()
        self._subs: Dict[str, _SubscriptionEntry] = {}

    def register_subscription(self, subscription: EventSubscription[EventEnvelope]) -> None:
        sid = subscription.spec.subscription_id
        if sid in self._subs:
            raise ValueError(f"subscription_id already registered: {sid!r}")
        if len(self._subs) >= self._config.limits.max_subscriptions_per_bus:
            raise ValueError("max_subscriptions_per_bus exceeded")
        self._subs[sid] = _SubscriptionEntry(spec=subscription.spec, handler=subscription.handler)

    def unregister_subscription(self, subscription_id: str) -> None:
        self._subs.pop(subscription_id, None)

    def publish(self, envelope: EventEnvelope) -> PublishResult:
        """
        Fan out to all registered subscriptions in deterministic ``subscription_id`` order.

        Each matched subscription receives a fresh :class:`DeliveryContext` with a
        unique ``delivery_id`` and a deep-copied replay payload from config.

        Uncaught handler exceptions (subclasses of :class:`Exception`) are converted
        to structured ``HandleResult`` failures and do not propagate out of
        ``publish``. ``BaseException`` subclasses outside ``Exception`` (e.g.
        ``KeyboardInterrupt``) are not caught and will abort the process as usual.
        """
        publish_id = uuid5(_BUS_DISPATCH_ID_NS, f"publish:{envelope.event_id}")
        audit = PublishAudit(
            publish_id=publish_id,
            recorded_at=envelope.occurred_at,
            runtime=self._config.runtime_label,
            host=self._config.host_label,
        )

        replay_base = self._config.dispatch_replay
        if replay_base.replay_mode and replay_base.replay_run_id is None:
            return PublishResult(
                status=DeliveryStatus.REJECTED,
                failure=EventBusFailure(
                    category=FailureCategory.VALIDATION_ERROR,
                    message="dispatch_replay requires replay_run_id when replay_mode is true",
                    code="in_memory_bus.replay_invariant",
                ),
                audit=audit,
                extensions={"trace": "dispatch_replay_invalid"},
            )

        ordered_ids = tuple(sorted(self._subs.keys()))
        plan = _build_publish_plan(
            ordered_ids=ordered_ids,
            subs=self._subs,
            envelope=envelope,
            replay_base=replay_base,
        )
        dispatch_steps = [p for p in plan if isinstance(p, _PlannedDispatch)]
        budget = self._config.limits.max_dispatch_per_publish
        if len(dispatch_steps) > budget:
            return PublishResult(
                status=DeliveryStatus.REJECTED,
                failure=EventBusFailure(
                    category=FailureCategory.PERMANENT,
                    message="max_dispatch_per_publish would be exceeded for this envelope",
                    code="in_memory_bus.bounds_exceeded",
                    extensions={"limit": budget, "requested_dispatches": len(dispatch_steps)},
                ),
                audit=audit,
                extensions={"planned_dispatch_count": len(dispatch_steps)},
            )

        records: List[SubscriberDispatchRecord] = []
        handle_results: List[HandleResult] = []

        for step in plan:
            if isinstance(step, _PlannedSkip):
                records.append(
                    SubscriberDispatchRecord(
                        subscription_id=step.subscription_id,
                        subscriber_id=step.subscriber_id,
                        delivery_id=step.delivery_id,
                        dispatched=False,
                        skip_reason=step.reason,
                    )
                )
                continue

            entry = self._subs[step.subscription_id]
            dctx = DeliveryContext(
                delivery_id=step.delivery_id,
                delivered_at=envelope.occurred_at,
                attempt=1,
                subscriber_id=step.subscriber_id,
                subscription_id=step.subscription_id,
                replay=_copy_replay(replay_base),
            )
            try:
                hr = entry.handler.handle(envelope, dctx)
            except Exception as exc:
                hr = _synthetic_handler_failure_result(
                    exc,
                    subscription_id=step.subscription_id,
                    subscriber_id=step.subscriber_id,
                    delivery_id=step.delivery_id,
                    runtime_label=self._config.runtime_label,
                )
            records.append(
                SubscriberDispatchRecord(
                    subscription_id=step.subscription_id,
                    subscriber_id=step.subscriber_id,
                    delivery_id=step.delivery_id,
                    dispatched=True,
                    handle_result=hr,
                )
            )
            handle_results.append(hr)

        _apply_anchor_progress(self._subs, envelope, replay_base, ordered_ids)

        trace = InMemoryDispatchTrace(
            publish_id=publish_id,
            envelope_event_id=envelope.event_id,
            envelope_event_type=envelope.event_type,
            dispatch_records=tuple(records),
            recorded_at=envelope.occurred_at,
            runtime_label=self._config.runtime_label,
        )

        if not handle_results:
            return PublishResult(
                status=DeliveryStatus.ACCEPTED,
                failure=None,
                audit=audit,
                extensions={"dispatch_trace": _dump_trace(trace)},
            )

        agg = _aggregate_publish_status(handle_results)
        if agg == DeliveryStatus.ACCEPTED:
            return PublishResult(
                status=DeliveryStatus.ACCEPTED,
                failure=None,
                audit=audit,
                extensions={"dispatch_trace": _dump_trace(trace)},
            )
        if agg == DeliveryStatus.SKIPPED:
            return PublishResult(
                status=DeliveryStatus.SKIPPED,
                failure=None,
                audit=audit,
                extensions={"dispatch_trace": _dump_trace(trace)},
            )

        fail = _failure_for_status(
            agg,
            "One or more subscribers returned a non-success delivery status",
        )
        return PublishResult(
            status=agg,
            failure=fail,
            audit=audit,
            extensions={
                "dispatch_trace": _dump_trace(trace),
                "subscriber_statuses": [h.status.value for h in handle_results],
            },
        )
