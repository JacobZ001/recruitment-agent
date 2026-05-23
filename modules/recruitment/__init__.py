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
    build_candidate_list_item,
    build_candidate_view,
    get_candidate_view_for_runtime,
    get_demo_candidate,
    get_state_summary,
    get_state_summary_for_candidate,
    get_timeline,
    get_timeline_for_candidate,
)
from .registry import get_state_id
from .policies import ALLOWED_INGRESS_EVENT_TYPES, allowed_ingress_event_types
from .runtime import DevResetResult, VerticalSliceApiRuntime
from .use_cases import (
    EventIngressResult,
    publish_ingress_event,
    publish_recruitment_event,
    record_recruiter_decision,
    list_candidates,
    run_primary_demo_sequence,
    submit_cv,
)

__all__ = (
    "ALLOWED_INGRESS_EVENT_TYPES",
    "CANDIDATE_VIEW_EVALUATION_SUMMARY_PLACEHOLDER",
    "CandidateNotFoundError",
    "DemoRunPreconditionError",
    "DevResetResult",
    "EventIngressResult",
    "InvalidIngressEventError",
    "RecruitmentUseCaseError",
    "build_candidate_list_item",
    "build_candidate_view",
    "get_candidate_view_for_runtime",
    "get_demo_candidate",
    "get_state_id",
    "get_state_summary",
    "get_state_summary_for_candidate",
    "get_timeline",
    "allowed_ingress_event_types",
    "list_candidates",
    "publish_ingress_event",
    "publish_recruitment_event",
    "record_recruiter_decision",
    "run_primary_demo_sequence",
    "submit_cv",
    "VerticalSliceApiRuntime",
)
