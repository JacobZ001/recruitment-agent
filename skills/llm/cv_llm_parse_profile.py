"""
LLM-backed candidate profile parsing for ``cv_submitted`` ingress.

This skill extracts bounded profile fields only. It does not score the candidate.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Final, Literal, Optional
from uuid import UUID, uuid5

from pydantic import BaseModel, Field, ValidationError

try:  # Pydantic v2
    from pydantic import ConfigDict

    _PYDANTIC_V2 = True
except Exception:  # pragma: no cover
    _PYDANTIC_V2 = False

from interfaces.skill_interface import (
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
import hashlib

from schemas.state_schema import IngressProfile
from skills.llm.llm_provider import LLMProvider, LLMProviderError, build_llm_provider_from_env

SKILL_NAME: Final[str] = "recruitment.vertical_slice.cv_parse_profile"
SKILL_VERSION: Final[str] = "1.0.0"
_REFERENCE_TIME: Final[datetime] = datetime(2026, 5, 1, 0, 0, 0, tzinfo=timezone.utc)
_EXECUTION_ID_NAMESPACE: Final[UUID] = UUID("018f3e2a-7c9b-4a3d-8f0e-000000000021")

_SYSTEM_PROMPT: Final[str] = """
You are extracting structured recruiter intake profile data from a submitted CV.
Return strict JSON only, no markdown.
Required top-level keys: profile, explanation.
Profile keys: full_name, headline, years_experience, seniority, roles, skills, industries, summary.
Optional: primary_email, primary_phone.
Seniority must be junior, mid, senior, or null.
Do not include raw CV text in the response.
""".strip()


class _SkillModel(BaseModel):
    if _PYDANTIC_V2:
        model_config = ConfigDict(extra="forbid", validate_assignment=True)  # type: ignore[name-defined]
    else:  # pragma: no cover
        class Config:
            extra = "forbid"
            validate_assignment = True


class _LLMProfile(_SkillModel):
    full_name: Optional[str] = Field(default=None)
    headline: Optional[str] = Field(default=None)
    primary_email: Optional[str] = Field(default=None)
    primary_phone: Optional[str] = Field(default=None)
    years_experience: Optional[int] = Field(default=None, ge=0, le=80)
    seniority: Optional[Literal["junior", "mid", "senior"]] = Field(default=None)
    roles: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    summary: str = Field(default="")


class _LLMParseResponse(_SkillModel):
    profile: _LLMProfile
    explanation: str = Field(default="")


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


def _fail(
    metadata: SkillMetadata,
    *,
    audit: ExecutionAudit,
    timing: ExecutionTiming,
    category: FailureCategory,
    code: str,
    message: str,
) -> SkillExecutionResult:
    return SkillExecutionResult(
        metadata=metadata,
        status=ExecutionStatus.FAILED,
        failure=SkillFailure(
            category=category,
            message=message,
            code=code,
            is_retryable=category in (FailureCategory.TRANSIENT, FailureCategory.TIMEOUT),
        ),
        timing=timing,
        audit=audit,
    )


def _dump_model(model: Any) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return model.dict()


def _validate_response(value: Any) -> _LLMParseResponse:
    if hasattr(_LLMParseResponse, "model_validate"):
        return _LLMParseResponse.model_validate(value)
    return _LLMParseResponse.parse_obj(value)


class CvLlmParseProfileSkill:
    metadata: SkillMetadata

    def __init__(
        self,
        *,
        provider: Optional[LLMProvider] = None,
        provider_factory=build_llm_provider_from_env,
    ) -> None:
        self._provider = provider
        self._provider_factory = provider_factory
        self.metadata = SkillMetadata(
            skill_name=SKILL_NAME,
            skill_version=SKILL_VERSION,
            kind=SkillKind.LLM,
            boundary=DeterministicBoundary(
                determinism_class=DeterminismClass.PROBABILISTIC,
                kind=SkillKind.LLM,
                requires_input_snapshot=False,
                requires_output_snapshot=False,
                requires_model_capture=True,
            ),
            description="LLM candidate-profile parsing from submitted CV text.",
            input_contract_version="1.0",
            output_contract_version="1.0",
            supports_dry_run=True,
            supports_replay=False,
            supports_idempotency=False,
            tags=["vertical_slice", "llm", "recruitment", "cv_parse"],
        )

    def _provider_or_error(self) -> LLMProvider:
        if self._provider is not None:
            return self._provider
        return self._provider_factory()

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
            runtime="skills.llm.cv_llm_parse_profile",
            model_info={},
            extensions={"skill_version": SKILL_VERSION},
        )
        planner_path = str(payload.get("vertical_slice.planner_path") or "")
        if planner_path != "cv_submitted":
            return _fail(
                self.metadata,
                audit=audit,
                timing=timing,
                category=FailureCategory.VALIDATION_ERROR,
                code="cv_llm_parse_profile.validation.planner_path",
                message=f"unexpected planner_path {planner_path!r}",
            )
        raw_cv = payload.get("cv_text")
        if raw_cv is None or not str(raw_cv).strip():
            return _fail(
                self.metadata,
                audit=audit,
                timing=timing,
                category=FailureCategory.VALIDATION_ERROR,
                code="cv_llm_parse_profile.validation.cv_text",
                message="missing required payload key: cv_text",
            )
        cv_text = str(raw_cv).strip()
        if len(cv_text) > 16_000:
            return _fail(
                self.metadata,
                audit=audit,
                timing=timing,
                category=FailureCategory.VALIDATION_ERROR,
                code="cv_llm_parse_profile.validation.cv_text_too_long",
                message="cv_text exceeds max supported length",
            )
        if context.dry_run:
            return SkillExecutionResult(
                metadata=self.metadata,
                status=ExecutionStatus.SUCCEEDED,
                output=SkillOutputEnvelope(
                    payload={"dry_run": True, "would_parse_profile": True},
                    extensions={"dry_run": True},
                ),
                timing=timing,
                audit=audit,
            )
        try:
            provider = self._provider_or_error()
            raw_result = provider.generate_structured(
                system_prompt=_SYSTEM_PROMPT,
                user_prompt=cv_text,
            )
            parsed = _validate_response(raw_result)
        except LLMProviderError as exc:
            category_map = {
                "dependency_unavailable": FailureCategory.DEPENDENCY_UNAVAILABLE,
                "authorization": FailureCategory.AUTHORIZATION,
                "transient": FailureCategory.TRANSIENT,
                "permanent": FailureCategory.PERMANENT,
            }
            return _fail(
                self.metadata,
                audit=audit,
                timing=timing,
                category=category_map.get(exc.category, FailureCategory.UNKNOWN),
                code=exc.code,
                message=str(exc),
            )
        except ValidationError as exc:
            return _fail(
                self.metadata,
                audit=audit,
                timing=timing,
                category=FailureCategory.PERMANENT,
                code="cv_llm_parse_profile.invalid_output",
                message=f"provider returned invalid structured output: {exc}",
            )

        profile = IngressProfile(
            years_experience=parsed.profile.years_experience,
            seniority=parsed.profile.seniority,
            roles=list(parsed.profile.roles),
            skills=list(parsed.profile.skills),
            industries=list(parsed.profile.industries),
            summary=parsed.profile.summary,
        )
        aggregate_profile = {
            "full_name": parsed.profile.full_name,
            "headline": parsed.profile.headline or (parsed.profile.roles[0] if parsed.profile.roles else None),
            "primary_email": parsed.profile.primary_email,
            "primary_phone": parsed.profile.primary_phone,
            "years_experience": parsed.profile.years_experience,
            "seniority": parsed.profile.seniority,
            "roles": list(parsed.profile.roles),
            "skills": list(parsed.profile.skills),
            "industries": list(parsed.profile.industries),
            "summary": parsed.profile.summary,
        }
        return SkillExecutionResult(
            metadata=self.metadata,
            status=ExecutionStatus.SUCCEEDED,
            output=SkillOutputEnvelope(
                payload={
                    "profile": aggregate_profile,
                    "ingress_profile": _dump_model(profile),
                    "profile_explanation": parsed.explanation,
                    "cv_content_fingerprint": hashlib.sha256(
                        " ".join(
                            ln.strip().lower() for ln in cv_text.splitlines() if ln.strip()
                        ).encode("utf-8")
                    ).hexdigest(),
                },
                extensions={"interface_version": SkillInterfaceVersion.V1.value},
            ),
            timing=timing,
            audit=audit,
            metrics={"cv.char_count": float(len(cv_text))},
        )
