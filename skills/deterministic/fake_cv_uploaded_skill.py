"""
Fake deterministic CV upload intake for vertical-slice orchestration validation.

Why fake skills exist
---------------------
Real ingestion (parsers, OCR, brokers) couples the control plane to IO, entropy, and
operational failure modes before the **event → state → skill → decision** loop is
proven. Fake skills exercise the orchestrator, skill registry, and audit envelopes
with **bounded**, **replay-friendly** semantics so deterministic policy and
transition validation stay testable in isolation (see ``docs/architecture/ADR.md``
ADR-001/002 and ``docs/architecture/ROADMAP.md`` Phase 2).

Deterministic simulation philosophy
------------------------------------
This module **does not** interpret CV bytes, call models, or score candidates. It
accepts explicit planner-shaped inputs and emits **derived metadata** using pure
functions of those inputs (plus ``ExecutionContext`` correlation fields). Same inputs
and context identifiers yield the same structured outputs, suitable for harness and
replay tooling that compares stable payloads rather than wall-clock timestamps.

Relationship to orchestrator / runtime
---------------------------------------
:class:`~orchestrator.vertical_slice_planner.VerticalSlicePlanner` dispatches
``recruitment.vertical_slice.cv_uploaded`` with a :class:`SkillInputEnvelope` payload.
The orchestrator supplies trace fields on :class:`ExecutionContext` and records skill
results; this skill **must not** mutate orchestration state, publish events, or embed
routing/scoring policy—only return a :class:`SkillExecutionResult`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Final, Mapping, Optional, Tuple
from uuid import UUID, uuid5

from interfaces.skill_interface import (
    DeterminismClass,
    DeterministicBoundary,
    EvidenceKind,
    EvidenceRef,
    ExecutionAudit,
    ExecutionContext,
    ExecutionStatus,
    ExecutionTiming,
    FailureCategory,
    SkillExecutionResult,
    SkillFailure,
    SkillInputEnvelope,
    SkillKind,
    SkillMetadata,
    SkillOutputEnvelope,
    SkillInterfaceVersion,
)

# Stable registry key — must match ``SKILL_CV_UPLOADED`` in
# ``orchestrator.vertical_slice_planner``.
SKILL_NAME: Final[str] = "recruitment.vertical_slice.cv_uploaded"
SKILL_VERSION: Final[str] = "1.0.0"

# Intentionally fixed "simulation clock" for timing/evidence records so repeated runs
# and replay comparisons do not depend on wall-clock (orchestrator still owns real
# envelope ``occurred_at`` on the event stream).
_REFERENCE_TIME: Final[datetime] = datetime(2026, 5, 1, 0, 0, 0, tzinfo=timezone.utc)

_MAX_DECLARED_BYTES: Final[int] = 50_000_000
_MAX_PAGES: Final[int] = 500
_MAX_WORD_ESTIMATE: Final[int] = 200_000

_EXECUTION_ID_NAMESPACE: Final[UUID] = UUID("018f3e2a-7c9b-7a3d-9f0e-recruitment00")


def _execution_id(context: ExecutionContext) -> UUID:
    raw = (context.extensions or {}).get("orchestrator_skill_execution_id")
    if raw:
        return UUID(str(raw))
    basis = "|".join(
        (
            str(context.event_id or ""),
            str(context.subject_id or ""),
            str(context.correlation_id or ""),
            SKILL_NAME,
        )
    )
    return uuid5(_EXECUTION_ID_NAMESPACE, basis)


def _require_non_empty_str(payload: Mapping[str, Any], key: str) -> str:
    raw = payload.get(key)
    if raw is None:
        raise ValueError(f"missing required payload key: {key!r}")
    s = str(raw).strip()
    if not s:
        raise ValueError(f"payload key {key!r} must be non-empty")
    return s


def _optional_int(payload: Mapping[str, Any], key: str) -> Optional[int]:
    raw = payload.get(key)
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError(f"payload key {key!r} must be an integral number if present")
    n = int(raw)
    return n


def _bounded_int(value: int, *, low: int, high: int) -> int:
    return max(low, min(high, value))


def _simulate_extraction(
    *,
    subject_id: Optional[UUID],
    ingested_event_id: str,
    file_name: str,
    content_type: str,
    byte_length: Optional[int],
) -> Tuple[Dict[str, Any], Dict[str, float]]:
    """
    Pure deterministic "metadata extraction" from declared artifact hints.

    Returns (output_payload_fragment, metrics).
    """
    bl = int(byte_length) if byte_length is not None else 24_000
    bl = _bounded_int(bl, low=1, high=_MAX_DECLARED_BYTES)

    # Deterministic page/word heuristics — not semantic document understanding.
    pages = _bounded_int(bl // 45_000 + 1, low=1, high=_MAX_PAGES)
    words = _bounded_int(bl // 6, low=50, high=_MAX_WORD_ESTIMATE)

    sub_key = str(subject_id) if subject_id else "unassigned"
    artifact_ref = f"artifact://cv/{sub_key}/{ingested_event_id}"
    mime_family = "pdf" if "pdf" in content_type.lower() else "document"

    out: Dict[str, Any] = {
        "intake.status": "accepted",
        "intake.simulation": True,
        "artifact.ref": artifact_ref,
        "artifact.declared_file_name": file_name,
        "artifact.declared_content_type": content_type,
        "artifact.declared_byte_length": bl,
        "extraction.mime_family": mime_family,
        "extraction.simulated_page_count": pages,
        "extraction.simulated_word_estimate": words,
        "extraction.determinism_note": (
            "Heuristic counts are bounded functions of declared byte_length only; "
            "not OCR or LLM output."
        ),
    }
    metrics: Dict[str, float] = {
        "simulated.bytes_considered": float(bl),
        "simulated.pages_estimated": float(pages),
        "simulated.words_estimated": float(words),
    }
    return out, metrics


class FakeCvUploadedSkill:
    """
    Deterministic stand-in for CV upload ingestion on the recruiter vertical slice.

    Implements :class:`Skill` for :class:`SkillInputEnvelope` I/O without async,
    network, LLM, or orchestration side effects.
    """

    metadata: SkillMetadata

    def __init__(self) -> None:
        self.metadata = SkillMetadata(
            skill_name=SKILL_NAME,
            skill_version=SKILL_VERSION,
            kind=SkillKind.DETERMINISTIC,
            boundary=DeterministicBoundary(
                determinism_class=DeterminismClass.PURE_DETERMINISTIC,
                kind=SkillKind.DETERMINISTIC,
                requires_input_snapshot=False,
                requires_output_snapshot=False,
                requires_model_capture=False,
            ),
            description=(
                "Fake CV upload intake: validates skill dispatch and emits bounded, "
                "explainable deterministic metadata (vertical slice only)."
            ),
            input_contract_version="1.0",
            output_contract_version="1.0",
            supports_dry_run=True,
            supports_replay=True,
            supports_idempotency=True,
            tags=["vertical_slice", "fake", "recruitment", "cv_intake"],
        )

    def execute(
        self, skill_input: SkillInputEnvelope, context: ExecutionContext
    ) -> SkillExecutionResult:
        payload = skill_input.payload or {}
        timing = ExecutionTiming(
            started_at=_REFERENCE_TIME,
            ended_at=_REFERENCE_TIME,
            duration_ms=0,
        )
        audit = ExecutionAudit(
            execution_id=_execution_id(context),
            recorded_at=_REFERENCE_TIME,
            runtime="skills.deterministic.fake_cv_uploaded",
            model_info={},
            extensions={"fake_skill": True, "skill_version": SKILL_VERSION},
        )

        sim = payload.get("simulation")
        if isinstance(sim, Mapping):
            forced = sim.get("outcome")
            if forced == "failed":
                return SkillExecutionResult(
                    metadata=self.metadata,
                    status=ExecutionStatus.FAILED,
                    failure=SkillFailure(
                        category=FailureCategory.PERMANENT,
                        message="Deterministic simulation requested failure (harness hook).",
                        code="fake_cv_uploaded.simulation.failed",
                        is_retryable=False,
                    ),
                    timing=timing,
                    audit=audit,
                    extensions={"simulation": "forced_failure"},
                )

        try:
            planner_path = _require_non_empty_str(payload, "vertical_slice.planner_path")
            if planner_path != "cv_uploaded":
                raise ValueError(
                    f"unexpected planner_path {planner_path!r} for {SKILL_NAME!r}"
                )
            ingested_event_id = _require_non_empty_str(payload, "ingested_event_id")
            ingested_event_type = _require_non_empty_str(payload, "ingested_event_type")
            if ingested_event_type != "cv_uploaded":
                raise ValueError(
                    f"ingested_event_type must be 'cv_uploaded', got {ingested_event_type!r}"
                )

            file_name = str(payload.get("artifact.file_name") or "cv.pdf").strip() or "cv.pdf"
            content_type = str(
                payload.get("artifact.content_type") or "application/pdf"
            ).strip() or "application/pdf"
            byte_length = _optional_int(payload, "artifact.byte_length")
            if byte_length is not None and (
                byte_length < 1 or byte_length > _MAX_DECLARED_BYTES
            ):
                raise ValueError(
                    f"artifact.byte_length out of bounds (1..{_MAX_DECLARED_BYTES})"
                )
        except ValueError as exc:
            return SkillExecutionResult(
                metadata=self.metadata,
                status=ExecutionStatus.FAILED,
                failure=SkillFailure(
                    category=FailureCategory.VALIDATION_ERROR,
                    message=str(exc),
                    code="fake_cv_uploaded.validation_error",
                    is_retryable=False,
                ),
                timing=timing,
                audit=audit,
            )

        if context.dry_run:
            return SkillExecutionResult(
                metadata=self.metadata,
                status=ExecutionStatus.SUCCEEDED,
                output=SkillOutputEnvelope(
                    payload={
                        "dry_run": True,
                        "would_accept": True,
                        "ingested_event_id": ingested_event_id,
                    },
                    extensions={"fake_skill": True},
                ),
                timing=timing,
                audit=audit,
                metrics={"simulated.dry_run": 1.0},
                extensions={"simulation": "dry_run"},
            )

        extracted, metrics = _simulate_extraction(
            subject_id=context.subject_id,
            ingested_event_id=ingested_event_id,
            file_name=file_name,
            content_type=content_type,
            byte_length=byte_length,
        )

        evidence_out = EvidenceRef(
            kind=EvidenceKind.DOCUMENT,
            ref=extracted["artifact.ref"],
            sha256=None,
            created_at=_REFERENCE_TIME,
            extensions={"role": "simulated_cv_artifact_ref"},
        )

        output_payload: Dict[str, Any] = {
            **extracted,
            "provenance.ingested_event_id": ingested_event_id,
            "provenance.planner_path": planner_path,
        }
        if context.event_id:
            output_payload["provenance.context_event_id"] = str(context.event_id)

        return SkillExecutionResult(
            metadata=self.metadata,
            status=ExecutionStatus.SUCCEEDED,
            output=SkillOutputEnvelope(
                payload=output_payload,
                evidence_refs=[evidence_out],
                extensions={
                    "fake_skill": True,
                    "interface_version": SkillInterfaceVersion.V1.value,
                },
            ),
            timing=timing,
            audit=audit,
            metrics=metrics,
            extensions={
                "execution.semantics": "deterministic_fake_cv_upload",
                "replay.note": (
                    "Timing fields use the module reference clock; correlate real "
                    "timelines via envelope ids in provenance.*"
                ),
            },
        )
