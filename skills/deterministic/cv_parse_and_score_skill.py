"""
Deterministic CV parse-and-score skill for MVP ``cv_submitted`` ingress.

Reads ``cv_text`` from skill payload; emits minimal keys for snapshot merge.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Final
from uuid import UUID, uuid5

from interfaces.skill_interface import (
    ConfidenceLevel,
    ConfidenceReport,
    DeterminismClass,
    DeterministicBoundary,
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

from skills.deterministic.cv_heuristics import bound_cv_text, extract_signals, score_signals

SKILL_NAME: Final[str] = "recruitment.vertical_slice.cv_parse_and_score"
SKILL_VERSION: Final[str] = "1.0.0"

_REFERENCE_TIME: Final[datetime] = datetime(2026, 5, 1, 0, 0, 0, tzinfo=timezone.utc)
_EXECUTION_ID_NAMESPACE: Final[UUID] = UUID("018f3e2a-7c9b-4a3d-8f0e-000000000010")


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


def _confidence_level(score: float) -> ConfidenceLevel:
    if score < 0.4:
        return ConfidenceLevel.LOW
    if score < 0.7:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.HIGH


class CvParseAndScoreSkill:
    """Parse raw CV text and compute a basic light-tier score (deterministic)."""

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
                "MVP CV ingress: heuristic extraction and basic scoring from cv_text payload."
            ),
            input_contract_version="1.0",
            output_contract_version="1.0",
            supports_dry_run=True,
            supports_replay=True,
            supports_idempotency=True,
            tags=["vertical_slice", "deterministic", "recruitment", "cv"],
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
            runtime="skills.deterministic.cv_parse_and_score",
            model_info={},
            extensions={"skill_version": SKILL_VERSION},
        )

        planner_path = str(payload.get("vertical_slice.planner_path") or "")
        if planner_path != "cv_submitted":
            return SkillExecutionResult(
                metadata=self.metadata,
                status=ExecutionStatus.FAILED,
                failure=SkillFailure(
                    category=FailureCategory.VALIDATION_ERROR,
                    message=f"unexpected planner_path {planner_path!r}",
                    code="cv_parse_and_score.validation.planner_path",
                    is_retryable=False,
                ),
                timing=timing,
                audit=audit,
            )

        raw_cv = payload.get("cv_text")
        if raw_cv is None or not str(raw_cv).strip():
            return SkillExecutionResult(
                metadata=self.metadata,
                status=ExecutionStatus.FAILED,
                failure=SkillFailure(
                    category=FailureCategory.VALIDATION_ERROR,
                    message="missing required payload key: cv_text",
                    code="cv_parse_and_score.validation.cv_text",
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
                    payload={"dry_run": True, "would_parse": True},
                    extensions={"dry_run": True},
                ),
                timing=timing,
                audit=audit,
            )

        try:
            cv_bounded = bound_cv_text(str(raw_cv))
            signals = extract_signals(cv_bounded)
            normalized_score, confidence_score = score_signals(signals)
        except ValueError as exc:
            return SkillExecutionResult(
                metadata=self.metadata,
                status=ExecutionStatus.FAILED,
                failure=SkillFailure(
                    category=FailureCategory.VALIDATION_ERROR,
                    message=str(exc),
                    code="cv_parse_and_score.validation",
                    is_retryable=False,
                ),
                timing=timing,
                audit=audit,
            )

        confidence = ConfidenceReport(
            score=confidence_score,
            level=_confidence_level(confidence_score),
        )
        return SkillExecutionResult(
            metadata=self.metadata,
            status=ExecutionStatus.SUCCEEDED,
            output=SkillOutputEnvelope(
                payload={
                    "cv.raw_text": cv_bounded,
                    "cv.signals": signals,
                    "scoring.normalized_score": normalized_score,
                    "scoring.confidence_score": confidence_score,
                },
                confidence=confidence,
                extensions={
                    "interface_version": SkillInterfaceVersion.V1.value,
                },
            ),
            timing=timing,
            audit=audit,
            metrics={
                "cv.char_count": float(len(cv_bounded)),
                "cv.keyword_hits": float(len(signals.get("matched_keywords") or [])),
                "scoring.normalized_score": normalized_score,
            },
        )
