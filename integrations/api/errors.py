"""Map recruitment application exceptions to HTTP responses (integrations layer only)."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import HTTPException

from modules.recruitment.exceptions import (
    CandidateCanonicalMissingError,
    CandidateNotFoundError,
    DuplicateCandidateHighConfidenceError,
    InvalidDedupGovernanceError,
    CandidateStoreUnavailableError,
    DemoRunPreconditionError,
    IdempotencyKeyConflictError,
    IdempotencyKeyInProgressError,
    IdempotencyKeyRequiredError,
    IdempotencyReplayError,
    InvalidCvPdfError,
    InvalidCandidateActionError,
    InvalidIngressEventError,
    InvalidRecruiterActionPayloadError,
    InvalidScoringContextError,
    RecruitmentUseCaseError,
    ScoringContextNotReadyError,
    ScoringFailedError,
)


def recruitment_error_to_http(
    exc: RecruitmentUseCaseError,
    *,
    candidate_id: Optional[UUID] = None,
) -> HTTPException:
    """
    Convert a domain/application error into an HTTPException with a stable JSON body.

    Never re-raise the original exception to clients.
    """
    if isinstance(exc, CandidateNotFoundError):
        msg = str(exc)
        if "no orchestration state" in msg:
            return HTTPException(status_code=404, detail="no orchestration state for candidate")
        return HTTPException(
            status_code=404,
            detail={
                "code": "candidate_not_found",
                "message": msg,
                "candidate_id": str(candidate_id) if candidate_id is not None else None,
            },
        )
    if isinstance(exc, InvalidIngressEventError):
        return HTTPException(
            status_code=422,
            detail={
                "code": "invalid_ingress",
                "message": str(exc),
            },
        )
    if isinstance(exc, InvalidCvPdfError):
        return HTTPException(
            status_code=422,
            detail={
                "code": "invalid_pdf_cv",
                "message": str(exc),
            },
        )
    if isinstance(exc, InvalidScoringContextError):
        return HTTPException(
            status_code=422,
            detail={
                "code": "invalid_scoring_context",
                "message": str(exc),
            },
        )
    if isinstance(exc, ScoringContextNotReadyError):
        return HTTPException(
            status_code=409,
            detail={
                "code": "scoring_context_not_ready",
                "message": str(exc),
            },
        )
    if isinstance(exc, InvalidCandidateActionError):
        return HTTPException(
            status_code=422,
            detail={
                "code": "invalid_candidate_action",
                "message": str(exc),
            },
        )
    if isinstance(exc, InvalidRecruiterActionPayloadError):
        return HTTPException(
            status_code=422,
            detail={
                "code": "invalid_candidate_action_payload",
                "message": str(exc),
            },
        )
    if isinstance(exc, DemoRunPreconditionError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, ScoringFailedError):
        return HTTPException(
            status_code=502,
            detail={
                "status": "failed",
                "error": "scoring_failed",
            },
        )
    if isinstance(exc, CandidateStoreUnavailableError):
        return HTTPException(
            status_code=503,
            detail={
                "code": "candidate_store_unavailable",
                "message": str(exc),
                "diagnostic": "fail_fast_no_legacy_snapshot_fallback",
            },
        )
    if isinstance(exc, CandidateCanonicalMissingError):
        return HTTPException(
            status_code=503,
            detail={
                "code": "candidate_canonical_missing",
                "message": str(exc),
                "diagnostic": "fail_fast_no_legacy_snapshot_fallback",
            },
        )
    if isinstance(exc, IdempotencyKeyRequiredError):
        return HTTPException(
            status_code=422,
            detail={
                "code": "idempotency_key_required",
                "message": str(exc),
            },
        )
    if isinstance(exc, IdempotencyKeyConflictError):
        return HTTPException(
            status_code=409,
            detail={
                "code": "idempotency_key_conflict",
                "message": str(exc),
            },
        )
    if isinstance(exc, IdempotencyKeyInProgressError):
        return HTTPException(
            status_code=409,
            detail={
                "code": "idempotency_key_in_progress",
                "message": str(exc),
            },
        )
    if isinstance(exc, IdempotencyReplayError):
        return HTTPException(status_code=exc.status_code, detail=exc.body)
    if isinstance(exc, DuplicateCandidateHighConfidenceError):
        return HTTPException(
            status_code=409,
            detail={
                "code": "duplicate_candidate_high_confidence",
                "message": str(exc),
                "matches": exc.matches,
            },
        )
    if isinstance(exc, InvalidDedupGovernanceError):
        return HTTPException(
            status_code=422,
            detail={
                "code": "invalid_dedup_governance",
                "message": str(exc),
            },
        )
    return HTTPException(
        status_code=400,
        detail={
            "code": "recruitment_use_case_error",
            "message": str(exc),
        },
    )


def raise_recruitment_http(
    exc: RecruitmentUseCaseError,
    *,
    candidate_id: Optional[UUID] = None,
) -> None:
    """Raise the HTTPException mapped from ``exc``."""
    raise recruitment_error_to_http(exc, candidate_id=candidate_id) from exc
