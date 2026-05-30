"""Application-layer errors for recruitment use cases (mapped to HTTP in integrations/api)."""

from __future__ import annotations


class RecruitmentUseCaseError(Exception):
    """Base for recruitment application errors."""


class CandidateNotFoundError(RecruitmentUseCaseError):
    """Single-tenant runtime has no state for the given candidate id."""


class InvalidIngressEventError(RecruitmentUseCaseError):
    """Event type is not allowed or does not match the intended use case."""


class InvalidCvPdfError(RecruitmentUseCaseError):
    """Uploaded or encoded PDF CV failed validation or text extraction guards."""


class InvalidScoringContextError(RecruitmentUseCaseError):
    """Scoring-context authoring or normalization failed bounded validation."""


class ScoringContextNotReadyError(RecruitmentUseCaseError):
    """Candidate CV ingress is forbidden until the active scoring context is ready."""


class DemoRunPreconditionError(RecruitmentUseCaseError):
    """Scripted primary sequence cannot run safely on the current pipeline snapshot."""


class InvalidCandidateActionError(RecruitmentUseCaseError):
    """Action key is not allowed for the candidate's current pipeline phase."""


class InvalidRecruiterActionPayloadError(RecruitmentUseCaseError):
    """Recruiter action payload failed deterministic validation before publish."""


class ScoringFailedError(RecruitmentUseCaseError):
    """A required scoring/evaluation step failed during ingress processing."""


class CandidateStoreUnavailableError(RecruitmentUseCaseError):
    """Canonical Candidate store cannot be read for recruiter surfaces (fail-fast; no legacy fallback)."""


class CandidateCanonicalMissingError(RecruitmentUseCaseError):
    """Orchestration state exists but canonical Candidate row is absent (fail-fast; no legacy fallback)."""


class IdempotencyKeyRequiredError(RecruitmentUseCaseError):
    """POST /candidates/cv/pdf requires an Idempotency-Key header."""


class IdempotencyKeyConflictError(RecruitmentUseCaseError):
    """Same idempotency key was used with a different payload fingerprint."""


class IdempotencyKeyInProgressError(RecruitmentUseCaseError):
    """Another in-flight request holds the same idempotency key."""


class IdempotencyReplayError(RecruitmentUseCaseError):
    """Carries stored HTTP replay response (status + body) for idempotent success replay."""

    def __init__(self, *, status_code: int, body: dict) -> None:
        self.status_code = status_code
        self.body = body
        super().__init__("idempotency_http_replay")
