"""
Recruitment application boundary (DDD-lite).

HTTP and runtime wiring live outside this package; use cases receive an injected runtime.
"""

from .exceptions import (
    CandidateNotFoundError,
    DemoRunPreconditionError,
    InvalidIngressEventError,
    RecruitmentUseCaseError,
)
from .projection import (
    CANDIDATE_VIEW_EVALUATION_SUMMARY_PLACEHOLDER,
    build_candidate_view,
    get_candidate_view_for_runtime,
    get_demo_candidate,
    get_state_summary,
    get_timeline,
)
from .use_cases import (
    EventIngressResult,
    publish_ingress_event,
    record_recruiter_decision,
    run_primary_demo_sequence,
    submit_cv,
)

__all__ = (
    "CANDIDATE_VIEW_EVALUATION_SUMMARY_PLACEHOLDER",
    "CandidateNotFoundError",
    "DemoRunPreconditionError",
    "EventIngressResult",
    "InvalidIngressEventError",
    "RecruitmentUseCaseError",
    "build_candidate_view",
    "get_candidate_view_for_runtime",
    "get_demo_candidate",
    "get_state_summary",
    "get_timeline",
    "publish_ingress_event",
    "record_recruiter_decision",
    "run_primary_demo_sequence",
    "submit_cv",
)
