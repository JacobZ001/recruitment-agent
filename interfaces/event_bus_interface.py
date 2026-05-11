from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import re
from typing import Any, Dict, Generic, List, Optional, Protocol, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field

try:  # Pydantic v2
    from pydantic import ConfigDict, field_validator, model_validator

    _PYDANTIC_V2 = True
except Exception:  # Pydantic v1 fallback
    from pydantic import root_validator, validator as field_validator  # type: ignore

    _PYDANTIC_V2 = False


class _SchemaBase(BaseModel):
    """
    Shared interface base (validation-focused only).

    Purpose:
    Define canonical contracts for the system event bus boundary so that:
    - orchestration remains deterministic (control-plane logic stays in programs)
    - events remain replay-safe and auditable (immutable facts)
    - observability is first-class (trace/correlation/causation links)

    Boundaries:
    - This file intentionally does NOT implement a broker, queue, persistence, retries,
      streaming infrastructure, routing, or orchestration logic.
    - Forward compatibility is achieved via explicit `extensions` fields.
    """

    if _PYDANTIC_V2:
        model_config = ConfigDict(
            extra="forbid",
            validate_assignment=True,
            populate_by_name=True,
        )
    else:

        class Config:  # pragma: no cover (runtime-selected by Pydantic major version)
            extra = "forbid"
            validate_assignment = True
            allow_population_by_field_name = True


class _ImmutableSchemaBase(_SchemaBase):
    """
    Immutable contract base.

    Use for envelopes/records that represent facts and should not be mutated in-place.
    """

    if _PYDANTIC_V2:
        model_config = ConfigDict(
            extra="forbid",
            validate_assignment=True,
            populate_by_name=True,
            frozen=True,
        )
    else:

        class Config:  # pragma: no cover (runtime-selected by Pydantic major version)
            extra = "forbid"
            validate_assignment = True
            allow_population_by_field_name = True
            allow_mutation = False


class EventBusInterfaceVersion(str, Enum):
    V1 = "1.0"


class DeliveryStatus(str, Enum):
    """
    Delivery status for publishing or consuming an event.

    Semantics:
    - `accepted`: the bus/handler accepted the operation.
    - `rejected`: the operation was rejected (validation/authorization/etc.).
    - `failed`: the operation failed to complete successfully.
    - `skipped`: the operation was intentionally not performed (e.g., deterministic gating).
      `skipped` is not an error state and must not carry a `failure`.
    """

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    FAILED = "failed"
    SKIPPED = "skipped"


class AckDecision(str, Enum):
    """
    Acknowledgment decision for a delivered event.

    Notes:
    - This is an execution contract signal, not a retry/routing policy.
    - The orchestrator/bus implementation may interpret these decisions differently,
      but that interpretation must remain deterministic and validated elsewhere.
    """

    ACK = "ack"
    NACK = "nack"
    DROP = "drop"


class FailureCategory(str, Enum):
    """
    Failure taxonomy aligned with deterministic-first, audit-first systems.
    """

    VALIDATION_ERROR = "validation_error"
    AUTHORIZATION = "authorization"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    TIMEOUT = "timeout"
    TRANSIENT = "transient"
    PERMANENT = "permanent"
    UNKNOWN = "unknown"


class EventBusFailure(_SchemaBase):
    category: FailureCategory = Field(default=FailureCategory.UNKNOWN)
    message: str = Field(..., min_length=1)
    code: Optional[str] = Field(default=None, description="Stable error code if available.")
    details_ref: Optional[str] = Field(
        default=None, description="Reference to stored structured error details/stack traces."
    )
    is_retryable: Optional[bool] = Field(
        default=None,
        description="Signal only; retry policy is owned by deterministic orchestration.",
    )
    extensions: Dict[str, Any] = Field(default_factory=dict)


class EventEnvelopeMetadata(_ImmutableSchemaBase):
    """
    Audit and tracing metadata attached to an event envelope.

    Prefer references/ids over raw content; keep this small and stable.
    """

    interface_version: str = Field(default=EventBusInterfaceVersion.V1.value)

    trace_id: Optional[str] = Field(default=None)
    request_id: Optional[str] = Field(default=None)

    correlation_id: Optional[UUID] = Field(
        default=None, description="Groups related events across a workflow."
    )
    causation_id: Optional[UUID] = Field(
        default=None, description="Parent event that caused this event (if known)."
    )

    idempotency_key: Optional[str] = Field(
        default=None, description="Optional external idempotency key."
    )

    actor_id: Optional[str] = Field(
        default=None,
        description="Actor/service identifier initiating the publish (audit).",
    )

    tags: List[str] = Field(default_factory=list)
    extensions: Dict[str, Any] = Field(default_factory=dict)


class EventEnvelope(_ImmutableSchemaBase):
    """
    Canonical event bus envelope.

    Immutable event philosophy:
    - Envelopes represent facts ("something happened") and must not be mutated.
    - Corrections are represented as new events, not in-place mutation.
    """

    interface_version: str = Field(default=EventBusInterfaceVersion.V1.value)

    event_id: UUID = Field(..., description="Unique event id.")
    event_type: str = Field(
        ...,
        min_length=1,
        description=(
            "Stable event type identifier. Must be either `snake_case` or "
            "`dot.namespace.style` (lowercase; digits/underscores allowed)."
        ),
    )

    occurred_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the event occurred (timezone-aware UTC recommended).",
    )

    # Domain identifiers kept generic to support non-recruitment systems.
    subject_id: Optional[UUID] = Field(default=None)
    subject_kind: Optional[str] = Field(default=None, description="Entity kind for subject_id.")

    # Payload is intentionally generic in v1 (see tech debt registry).
    payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="Event-specific data (prefer references/keys over raw blobs).",
    )
    metadata: EventEnvelopeMetadata = Field(default_factory=EventEnvelopeMetadata)

    schema_version: Optional[str] = Field(
        default=None,
        description="Optional schema version for the payload/envelope interpretation.",
    )

    extensions: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("subject_kind")
    def _subject_kind_non_empty_if_present(cls, v):  # type: ignore[override]
        if v is not None and not v.strip():
            raise ValueError("subject_kind must be non-empty if provided")
        return v

    @field_validator("event_type")
    def _event_type_naming_convention(cls, v: str):  # type: ignore[override]
        """
        Lightweight naming governance.

        This preserves flexible string-based event types without prematurely centralizing
        all names into enums, while enforcing stable, deterministic naming.
        """

        if not v or not v.strip():
            raise ValueError("event_type must be a non-empty string")
        if any(ch.isspace() for ch in v):
            raise ValueError("event_type must not contain whitespace")

        snake_case = re.compile(r"^[a-z][a-z0-9_]*$")
        dotted = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")

        if not (snake_case.match(v) or dotted.match(v)):
            raise ValueError(
                "event_type must be snake_case (e.g. 'cv_parsed') or dot.namespace.style "
                "(e.g. 'candidate.cv_parsed')"
            )
        return v

    @field_validator("occurred_at")
    def _occurred_at_timezone_aware(cls, v: datetime):  # type: ignore[override]
        if v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
            raise ValueError("occurred_at must be timezone-aware")
        return v


class ReplayContext(_SchemaBase):
    """
    Replay-aware execution context.

    This does not implement replay tooling; it captures signals/ids required to
    keep replay deterministic and auditable.
    """

    replay_mode: bool = Field(default=False)
    replay_run_id: Optional[UUID] = Field(
        default=None, description="Identifier for a replay/backfill run."
    )
    original_recorded_at: Optional[datetime] = Field(
        default=None, description="When the event was originally recorded (if known)."
    )
    sequence: Optional[int] = Field(
        default=None,
        ge=0,
        description="Optional monotonic sequence within a replay stream (if available).",
    )

    extensions: Dict[str, Any] = Field(default_factory=dict)

    if _PYDANTIC_V2:

        @model_validator(mode="after")
        def _replay_invariants(self):  # type: ignore[override]
            if self.replay_mode and self.replay_run_id is None:
                raise ValueError("replay_mode=true requires replay_run_id to be set")
            return self

    else:

        @root_validator
        def _replay_invariants(cls, values):  # type: ignore[override]
            if values.get("replay_mode") and values.get("replay_run_id") is None:
                raise ValueError("replay_mode=true requires replay_run_id to be set")
            return values


class DeliveryContext(_SchemaBase):
    """
    Context attached to an event delivery for handling/ack decisions.
    """

    interface_version: str = Field(default=EventBusInterfaceVersion.V1.value)

    delivery_id: Optional[UUID] = Field(
        default=None, description="Unique id for this delivery attempt (if provided)."
    )
    delivered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    attempt: int = Field(default=1, ge=1, description="1-based delivery attempt count.")

    subscriber_id: Optional[str] = Field(
        default=None, description="Identifier for the subscriber/consumer."
    )
    subscription_id: Optional[str] = Field(
        default=None, description="Identifier for the subscription specification."
    )

    replay: ReplayContext = Field(default_factory=ReplayContext)
    extensions: Dict[str, Any] = Field(default_factory=dict)


class PublishAudit(_SchemaBase):
    publish_id: UUID = Field(..., description="Unique publish operation id.")
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    runtime: Optional[str] = Field(default=None)
    host: Optional[str] = Field(default=None)
    extensions: Dict[str, Any] = Field(default_factory=dict)


class PublishResult(_SchemaBase):
    """
    Result of publishing an event to the bus boundary.

    Notes:
    - `status=skipped` is an explicit, non-error terminal outcome (no failure details).
    - This contract does not define routing, retry, persistence, or broker semantics.
    """

    status: DeliveryStatus
    failure: Optional[EventBusFailure] = Field(default=None)
    audit: PublishAudit

    # References only; avoid embedding logs.
    log_refs: List[str] = Field(default_factory=list)
    extensions: Dict[str, Any] = Field(default_factory=dict)

    if _PYDANTIC_V2:

        @model_validator(mode="after")
        def _publish_invariants(self):  # type: ignore[override]
            if self.status in (DeliveryStatus.FAILED, DeliveryStatus.REJECTED) and self.failure is None:
                raise ValueError("failed/rejected publish requires failure to be present")
            if self.status == DeliveryStatus.ACCEPTED and self.failure is not None:
                raise ValueError("accepted publish forbids failure")
            if self.status == DeliveryStatus.SKIPPED and self.failure is not None:
                raise ValueError("skipped publish forbids failure")
            return self

    else:

        @root_validator
        def _publish_invariants(cls, values):  # type: ignore[override]
            status = values.get("status")
            failure = values.get("failure")
            if status in (DeliveryStatus.FAILED, DeliveryStatus.REJECTED) and failure is None:
                raise ValueError("failed/rejected publish requires failure to be present")
            if status == DeliveryStatus.ACCEPTED and failure is not None:
                raise ValueError("accepted publish forbids failure")
            if status == DeliveryStatus.SKIPPED and failure is not None:
                raise ValueError("skipped publish forbids failure")
            return values


class HandleAudit(_SchemaBase):
    handling_id: UUID = Field(..., description="Unique handling operation id.")
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    runtime: Optional[str] = Field(default=None)
    host: Optional[str] = Field(default=None)
    extensions: Dict[str, Any] = Field(default_factory=dict)


class HandleResult(_SchemaBase):
    """
    Result of handling a delivered event.

    This contract is orchestration-neutral:
    - `ack_decision` indicates the handler's desired acknowledgment semantics.
    - Any routing, retry policy, or state transition behavior must be implemented
      deterministically elsewhere and validated by the harness.

    Notes:
    - `status=skipped` indicates deterministic no-op handling (no failure details).
    """

    status: DeliveryStatus
    ack_decision: AckDecision

    failure: Optional[EventBusFailure] = Field(default=None)
    audit: HandleAudit

    produced_event_ids: List[UUID] = Field(
        default_factory=list,
        description="Optional references to events produced as a result of handling.",
    )
    log_refs: List[str] = Field(default_factory=list)
    metrics: Dict[str, float] = Field(default_factory=dict)
    extensions: Dict[str, Any] = Field(default_factory=dict)

    if _PYDANTIC_V2:

        @model_validator(mode="after")
        def _handle_invariants(self):  # type: ignore[override]
            if self.status in (DeliveryStatus.FAILED, DeliveryStatus.REJECTED) and self.failure is None:
                raise ValueError("failed/rejected handle requires failure to be present")
            if self.status == DeliveryStatus.ACCEPTED and self.failure is not None:
                raise ValueError("accepted handle forbids failure")
            if self.status == DeliveryStatus.SKIPPED and self.failure is not None:
                raise ValueError("skipped handle forbids failure")
            return self

    else:

        @root_validator
        def _handle_invariants(cls, values):  # type: ignore[override]
            status = values.get("status")
            failure = values.get("failure")
            if status in (DeliveryStatus.FAILED, DeliveryStatus.REJECTED) and failure is None:
                raise ValueError("failed/rejected handle requires failure to be present")
            if status == DeliveryStatus.ACCEPTED and failure is not None:
                raise ValueError("accepted handle forbids failure")
            if status == DeliveryStatus.SKIPPED and failure is not None:
                raise ValueError("skipped handle forbids failure")
            return values


class SubscriptionSelector(_SchemaBase):
    """
    Declarative selection criteria for subscriptions.

    The bus/orchestrator may use additional deterministic routing rules; those rules
    are intentionally not encoded here.
    """

    event_types: List[str] = Field(default_factory=list, description="If empty, matches all.")
    subject_kind: Optional[str] = Field(
        default=None,
        description="Optional subject kind filter (generic; e.g., 'candidate').",
    )
    tags_any: List[str] = Field(
        default_factory=list,
        description="Optional tag match-any filter (advisory; deterministic routing lives elsewhere).",
    )
    extensions: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("event_types")
    def _event_types_non_empty_strings(cls, v: List[str]):  # type: ignore[override]
        for t in v:
            if not t or not t.strip():
                raise ValueError("event_types entries must be non-empty strings")
        return v

    @field_validator("subject_kind")
    def _subject_kind_non_empty_if_present(cls, v):  # type: ignore[override]
        if v is not None and not v.strip():
            raise ValueError("subject_kind must be non-empty if provided")
        return v


class SubscriptionSpec(_SchemaBase):
    """
    Subscription specification contract.
    """

    interface_version: str = Field(default=EventBusInterfaceVersion.V1.value)

    subscriber_id: str = Field(..., min_length=1, description="Stable subscriber identifier.")
    subscription_id: str = Field(
        ...,
        min_length=1,
        description="Stable identifier for this subscription (versionable independently).",
    )

    selector: SubscriptionSelector = Field(default_factory=SubscriptionSelector)

    # Replay/positioning is signal-only; no streaming engine is defined here.
    start_from_event_id: Optional[UUID] = Field(
        default=None, description="Optional starting position anchor for replay/backfill."
    )
    replay_enabled: bool = Field(default=True)

    tags: List[str] = Field(default_factory=list)
    extensions: Dict[str, Any] = Field(default_factory=dict)


EnvelopeT = TypeVar("EnvelopeT", bound=EventEnvelope)


class EventPublisher(Protocol, Generic[EnvelopeT]):
    """
    Canonical event publishing interface.
    """

    def publish(self, envelope: EnvelopeT) -> PublishResult: ...


class EventHandler(Protocol, Generic[EnvelopeT]):
    """
    Canonical event handler interface.
    """

    def handle(self, envelope: EnvelopeT, context: DeliveryContext) -> HandleResult: ...


class EventSubscription(Protocol, Generic[EnvelopeT]):
    """
    Subscription contract linking a spec to a handler.
    """

    spec: SubscriptionSpec
    handler: EventHandler[EnvelopeT]


class EventBus(Protocol, Generic[EnvelopeT]):
    """
    Canonical event bus boundary contract.

    This is an interface-only definition; implementations may be in-memory, database-backed,
    or backed by external brokers, as long as they respect:
    - immutability of envelopes
    - deterministic, validated routing in the orchestrator layer
    - replay-safe semantics and auditability
    """

    def publish(self, envelope: EnvelopeT) -> PublishResult: ...

    def register_subscription(self, subscription: EventSubscription[EnvelopeT]) -> None: ...

    def unregister_subscription(self, subscription_id: str) -> None: ...

