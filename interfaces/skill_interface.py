from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
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

    This module defines canonical contracts for bounded "skills" that can be executed
    by an orchestrator in a replayable, observable manner.

    Notes:
    - This file intentionally does NOT implement orchestration, routing, retries,
      state transitions, or skill behavior.
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


class SkillInterfaceVersion(str, Enum):
    V1 = "1.0"


class SkillKind(str, Enum):
    """
    High-level skill category used for governance and deterministic boundaries.
    """

    DETERMINISTIC = "deterministic"
    LLM = "llm"
    HYBRID = "hybrid"


class DeterminismClass(str, Enum):
    """
    Deterministic classification of the skill's execution behavior.

    This is used for deterministic-first orchestration, replay constraints,
    and governance policies (e.g., what must be re-validated vs. replayed).
    """

    PURE_DETERMINISTIC = "pure_deterministic"
    PROBABILISTIC = "probabilistic"
    HYBRID_GUARDED = "hybrid_guarded"


class ExecutionStatus(str, Enum):
    """
    Skill execution outcome status.
    """

    SUCCEEDED = "succeeded"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class FailureCategory(str, Enum):
    """
    Failure taxonomy for consistent handling and observability.
    """

    VALIDATION_ERROR = "validation_error"
    INPUT_MISSING = "input_missing"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    AUTHORIZATION = "authorization"
    TRANSIENT = "transient"
    PERMANENT = "permanent"
    UNKNOWN = "unknown"


class ConfidenceLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EvidenceKind(str, Enum):
    """
    Generic evidence vocabulary suitable beyond recruitment.
    """

    DOCUMENT = "document"
    MESSAGE = "message"
    TRANSCRIPT = "transcript"
    LINK = "link"
    STRUCTURED_RECORD = "structured_record"
    METRIC = "metric"
    OTHER = "other"


class DeterministicBoundary(_SchemaBase):
    """
    Declares the deterministic boundary contract for a skill.

    The orchestrator can use this structure to enforce deterministic-first policies
    without embedding orchestration logic into the skill.
    """

    determinism_class: DeterminismClass
    kind: SkillKind

    # For LLM/hybrid skills, record what must be captured for replay/audit.
    requires_input_snapshot: bool = Field(
        default=True,
        description="Whether input payload/context snapshots are required for audit/replay.",
    )
    requires_output_snapshot: bool = Field(
        default=True,
        description="Whether outputs (or references) are required for audit/replay.",
    )
    requires_model_capture: bool = Field(
        default=False,
        description="Whether model identifiers/parameters should be captured for auditability.",
    )

    extensions: Dict[str, Any] = Field(default_factory=dict)


class EvidenceRef(_SchemaBase):
    """
    Reference to evidence used or produced by a skill.

    Store references/keys/URIs rather than raw blobs to keep interfaces lightweight.
    """

    kind: EvidenceKind = Field(default=EvidenceKind.OTHER)
    ref: str = Field(..., min_length=1, description="Opaque storage key/URI/reference.")
    sha256: Optional[str] = Field(
        default=None, description="Optional content hash for integrity/deduplication."
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp for the evidence reference record (not necessarily the artifact).",
    )
    extensions: Dict[str, Any] = Field(default_factory=dict)


class ConfidenceReport(_SchemaBase):
    """
    Confidence reporting for explainability and governance.
    """

    score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    level: Optional[ConfidenceLevel] = Field(default=None)
    rationale_ref: Optional[str] = Field(
        default=None,
        description="Reference to stored explanation/rationale for the confidence assessment.",
    )
    extensions: Dict[str, Any] = Field(default_factory=dict)


class ExecutionTiming(_SchemaBase):
    """
    Timing info for observability and audit.
    """

    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: Optional[datetime] = Field(default=None)
    duration_ms: Optional[int] = Field(default=None, ge=0)
    extensions: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("ended_at")
    def _ended_at_not_before_started_at(cls, v, values=None, **_kwargs):  # type: ignore[override]
        started_at = None
        try:
            started_at = getattr(values, "data", None) and values.data.get("started_at")  # type: ignore[attr-defined]
        except Exception:
            pass
        if started_at is None and isinstance(values, dict):
            started_at = values.get("started_at")
        if v is not None and started_at is not None and v < started_at:
            raise ValueError("ended_at cannot be before started_at")
        return v


class RetryAwareness(_SchemaBase):
    """
    Retry awareness (signal only). This does not encode retry policy logic.
    """

    attempt: int = Field(default=1, ge=1, description="1-based attempt count.")
    max_attempts: Optional[int] = Field(
        default=None, ge=1, description="Upper bound, if provided by orchestrator."
    )
    is_retry: bool = Field(default=False)
    previous_execution_id: Optional[UUID] = Field(
        default=None, description="Execution id of the previous attempt (if any)."
    )
    extensions: Dict[str, Any] = Field(default_factory=dict)


class ExecutionContext(_SchemaBase):
    """
    Canonical execution context passed into all skills.

    The orchestrator is responsible for populating these fields.
    """

    interface_version: str = Field(default=SkillInterfaceVersion.V1.value)

    # Traceability / replay / event-driven compatibility (generic identifiers)
    trace_id: Optional[str] = Field(default=None, description="Distributed tracing id.")
    request_id: Optional[str] = Field(default=None, description="Inbound request id.")
    correlation_id: Optional[UUID] = Field(
        default=None, description="Groups related executions/events in a workflow."
    )
    causation_id: Optional[UUID] = Field(
        default=None, description="Parent event/execution that caused this execution."
    )
    event_id: Optional[UUID] = Field(
        default=None, description="Associated event id (if execution is event-driven)."
    )

    # Domain identifiers (optional to keep this interface reusable outside recruitment)
    subject_id: Optional[UUID] = Field(
        default=None,
        description="Primary entity id being processed (e.g., candidate_id).",
    )
    subject_kind: Optional[str] = Field(
        default=None, description="Entity kind for `subject_id` (e.g., 'candidate')."
    )

    # Governance / human-compatibility
    actor_id: Optional[str] = Field(
        default=None,
        description="Operator/service identifier initiating the execution (for audit).",
    )
    run_reason: Optional[str] = Field(
        default=None, description="Human-readable reason code/string (audit-friendly)."
    )

    # Replayability knobs (signals only)
    replay_mode: bool = Field(
        default=False, description="True when running in replay/backfill mode."
    )
    dry_run: bool = Field(
        default=False,
        description="True when outputs should be produced without side effects (if supported).",
    )

    # Deadlines / scheduling (signal only; no policy logic)
    scheduled_at: Optional[datetime] = Field(default=None)
    deadline_at: Optional[datetime] = Field(default=None)

    retry: RetryAwareness = Field(default_factory=RetryAwareness)

    tags: List[str] = Field(default_factory=list)
    extensions: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("subject_kind")
    def _subject_kind_non_empty_if_present(cls, v):  # type: ignore[override]
        if v is not None and not v.strip():
            raise ValueError("subject_kind must be non-empty if provided")
        return v


class SkillMetadata(_SchemaBase):
    """
    Canonical skill metadata.

    The orchestrator can use this for registration, governance, observability,
    and deterministic boundary enforcement.
    """

    interface_version: str = Field(default=SkillInterfaceVersion.V1.value)

    skill_name: str = Field(
        ...,
        min_length=1,
        description="Stable, import-friendly identifier (e.g. 'skills.deterministic.hard_filter').",
    )
    skill_version: str = Field(
        ...,
        min_length=1,
        description="Skill implementation version (semver recommended, e.g. '1.2.0').",
    )

    kind: SkillKind
    boundary: DeterministicBoundary

    description: Optional[str] = Field(default=None)
    owner: Optional[str] = Field(
        default=None, description="Owning team/component identifier."
    )

    # Contract versioning for IO schemas (not necessarily Python classes).
    input_contract_version: str = Field(default="1.0", min_length=1)
    output_contract_version: str = Field(default="1.0", min_length=1)

    # Capability flags (signals only; no orchestration logic).
    supports_dry_run: bool = Field(default=False)
    supports_replay: bool = Field(default=True)
    supports_idempotency: bool = Field(default=True)

    tags: List[str] = Field(default_factory=list)
    extensions: Dict[str, Any] = Field(default_factory=dict)


class SkillInputEnvelope(_SchemaBase):
    """
    Canonical skill input contract.

    The payload is intentionally generic to support a wide range of domains.
    """

    payload: Dict[str, Any] = Field(default_factory=dict)
    evidence_refs: List[EvidenceRef] = Field(
        default_factory=list,
        description="References to evidence inputs used by the skill.",
    )
    input_snapshot_ref: Optional[str] = Field(
        default=None,
        description="Optional reference to a persisted full input snapshot for replay/audit.",
    )
    extensions: Dict[str, Any] = Field(default_factory=dict)


class SkillOutputEnvelope(_SchemaBase):
    """
    Canonical skill output contract.

    Prefer storing large content externally and referencing it here.
    """

    payload: Dict[str, Any] = Field(default_factory=dict)
    evidence_refs: List[EvidenceRef] = Field(
        default_factory=list,
        description="References to evidence produced by the skill (outputs/artifacts).",
    )
    explanation_ref: Optional[str] = Field(
        default=None,
        description="Reference to stored explanation/rationale (explainability).",
    )
    confidence: Optional[ConfidenceReport] = Field(default=None)
    output_snapshot_ref: Optional[str] = Field(
        default=None,
        description="Optional reference to a persisted full output snapshot for replay/audit.",
    )
    extensions: Dict[str, Any] = Field(default_factory=dict)


class SkillFailure(_SchemaBase):
    """
    Canonical failure structure for skills.
    """

    category: FailureCategory = Field(default=FailureCategory.UNKNOWN)
    message: str = Field(..., min_length=1, description="Human-readable error summary.")
    code: Optional[str] = Field(
        default=None, description="Stable error code for analytics/handling."
    )
    details_ref: Optional[str] = Field(
        default=None,
        description="Reference to stored structured error details/stack traces.",
    )
    is_retryable: Optional[bool] = Field(
        default=None,
        description="Signal only; the orchestrator decides retry policy.",
    )
    evidence_refs: List[EvidenceRef] = Field(
        default_factory=list, description="Evidence references relevant to the failure."
    )
    extensions: Dict[str, Any] = Field(default_factory=dict)


class ExecutionAudit(_SchemaBase):
    """
    Audit fields for execution traceability.
    """

    execution_id: UUID = Field(..., description="Unique execution id.")
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Capture environment in a generic way (avoid coupling to specific vendors).
    runtime: Optional[str] = Field(default=None, description="Runtime identifier.")
    host: Optional[str] = Field(default=None, description="Host/worker identifier.")

    # For LLM/hybrid skills: capture model info (if available) without enforcing shape.
    model_info: Dict[str, Any] = Field(
        default_factory=dict,
        description="Model identifiers/parameters for auditability (when applicable).",
    )
    extensions: Dict[str, Any] = Field(default_factory=dict)


class SkillExecutionResult(_SchemaBase):
    """
    Canonical execution result contract for all skills.

    Partial execution:
    - `status=partial_success` indicates the skill produced a usable output while also
      recording an issue/failure signal for auditability and downstream handling.

    Skipped execution:
    - `status=skipped` indicates the skill was intentionally not executed (e.g., due to
      gating/preconditions handled by the orchestrator). No output is produced.
    - `failure` is optional and, when present, should be treated as an audit signal
      rather than a directive for routing/retry policy.

    Cancelled execution:
    - `status=cancelled` indicates the skill did not complete (e.g., operator/system abort).
      No output is produced.
    - `failure` is optional and should remain descriptive/audit-focused.

    - This contract does not define any orchestration policy; it only provides a
      validation-friendly shape for bounded execution.
    """

    metadata: SkillMetadata
    status: ExecutionStatus

    output: Optional[SkillOutputEnvelope] = Field(default=None)
    failure: Optional[SkillFailure] = Field(default=None)

    timing: ExecutionTiming = Field(default_factory=ExecutionTiming)
    audit: ExecutionAudit

    # Observability hooks (references only; avoid logging raw blobs here).
    log_refs: List[str] = Field(
        default_factory=list, description="References/keys to stored logs."
    )
    metrics: Dict[str, float] = Field(
        default_factory=dict,
        description="Lightweight numeric metrics emitted by the skill (timings, counts).",
    )
    extensions: Dict[str, Any] = Field(default_factory=dict)

    if _PYDANTIC_V2:

        @model_validator(mode="after")
        def _validate_status_invariants(self):  # type: ignore[override]
            """
            Enforce cross-field invariants independent of field parse order.

            No orchestration behavior is encoded here; these are correctness constraints
            for the execution contract.
            """

            if self.status == ExecutionStatus.SUCCEEDED:
                if self.output is None:
                    raise ValueError("status=succeeded requires output to be present")
                if self.failure is not None:
                    raise ValueError("status=succeeded forbids failure")

            if self.status in (ExecutionStatus.FAILED, ExecutionStatus.TIMEOUT):
                if self.failure is None:
                    raise ValueError("status indicates failure/timeout requires failure to be present")
                if self.output is not None:
                    raise ValueError("status indicates failure/timeout forbids output")

            if self.status == ExecutionStatus.PARTIAL_SUCCESS:
                if self.output is None:
                    raise ValueError("status=partial_success requires output to be present")
                # `failure` is allowed for auditability; it must not be required.

            if self.status in (ExecutionStatus.SKIPPED, ExecutionStatus.CANCELLED):
                if self.output is not None:
                    raise ValueError("status indicates skipped/cancelled forbids output")
                # `failure` is optional for auditability; it must not be required.

            return self

    else:

        @root_validator
        def _validate_status_invariants(cls, values):  # type: ignore[override]
            status = values.get("status")
            output = values.get("output")
            failure = values.get("failure")

            if status == ExecutionStatus.SUCCEEDED:
                if output is None:
                    raise ValueError("status=succeeded requires output to be present")
                if failure is not None:
                    raise ValueError("status=succeeded forbids failure")

            if status in (ExecutionStatus.FAILED, ExecutionStatus.TIMEOUT):
                if failure is None:
                    raise ValueError("status indicates failure/timeout requires failure to be present")
                if output is not None:
                    raise ValueError("status indicates failure/timeout forbids output")

            if status == ExecutionStatus.PARTIAL_SUCCESS:
                if output is None:
                    raise ValueError("status=partial_success requires output to be present")
                # `failure` is allowed for auditability; it must not be required.

            if status in (ExecutionStatus.SKIPPED, ExecutionStatus.CANCELLED):
                if output is not None:
                    raise ValueError("status indicates skipped/cancelled forbids output")
                # `failure` is optional for auditability; it must not be required.

            return values


InputT = TypeVar("InputT", bound=SkillInputEnvelope)
OutputT = TypeVar("OutputT", bound=SkillOutputEnvelope)


class Skill(Protocol, Generic[InputT, OutputT]):
    """
    Canonical executable contract for all system skills.

    Implementations should:
    - Validate input using Pydantic models
    - Produce `SkillExecutionResult` with references for evidence/explanations/logs
    - Avoid embedding orchestration logic, state transitions, routing, or retry policy
    """

    metadata: SkillMetadata

    def execute(self, skill_input: InputT, context: ExecutionContext) -> SkillExecutionResult: ...

