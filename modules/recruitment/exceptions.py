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
