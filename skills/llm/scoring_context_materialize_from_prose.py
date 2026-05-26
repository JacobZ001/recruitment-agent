"""
LLM-backed prose normalization for scoring-context authoring.

This skill converts bounded freeform authoring prose into normalized typed
context plus persisted derived criteria candidates. It does not mutate state.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Final, List, Optional
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
)
from schemas.state_schema import JobContext, OrganizationContext, RecruiterActorContext
from skills.llm.llm_provider import LLMProvider, LLMProviderError, build_llm_provider_from_env

SKILL_NAME: Final[str] = "recruitment.scoring_context.materialize_from_prose"
SKILL_VERSION: Final[str] = "1.0.0"
_REFERENCE_TIME: Final[datetime] = datetime(2026, 5, 1, 0, 0, 0, tzinfo=timezone.utc)
_EXECUTION_ID_NAMESPACE: Final[UUID] = UUID("018f3e2a-7c9b-4a3d-8f0e-000000000023")

_SYSTEM_PROMPT: Final[str] = """
You are normalizing recruiter-authored prose into a bounded scoring context.
Return strict JSON only, no markdown.
Required top-level keys: organization_context, recruiter_actor_context, job_context, derived_l2_criteria, derived_l3_criteria, explanation.
organization_context must contain: company_name, industry, team_name, environment_signals, preference_signals, summary, source_refs.
recruiter_actor_context must contain: actor_id, actor_role, hiring_focus, preference_signals, avoid_signals, summary, source_refs.
job_context must contain: title, summary, responsibilities, hard_requirements, preferred_requirements, success_signals, source_refs.
derived_l2_criteria and derived_l3_criteria must be bounded string lists suitable for later scoring.
Do not add workflow state or routing decisions.
""".strip()


class _SkillModel(BaseModel):
    if _PYDANTIC_V2:
        model_config = ConfigDict(extra="forbid", validate_assignment=True)  # type: ignore[name-defined]
    else:  # pragma: no cover
        class Config:
            extra = "forbid"
            validate_assignment = True


class _LLMResponse(_SkillModel):
    organization_context: OrganizationContext
    recruiter_actor_context: RecruiterActorContext
    job_context: JobContext
    derived_l2_criteria: List[str] = Field(default_factory=list)
    derived_l3_criteria: List[str] = Field(default_factory=list)
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


def _validate_response(value: Any) -> _LLMResponse:
    if hasattr(_LLMResponse, "model_validate"):
        return _LLMResponse.model_validate(value)
    return _LLMResponse.parse_obj(value)


class ScoringContextMaterializeFromProseSkill:
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
            description="LLM prose normalization for scoring_context materialization.",
            input_contract_version="1.0",
            output_contract_version="1.0",
            supports_dry_run=True,
            supports_replay=False,
            supports_idempotency=False,
            tags=["recruitment", "llm", "scoring_context", "materialization"],
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
            runtime="skills.llm.scoring_context_materialize_from_prose",
            model_info={},
            extensions={"skill_version": SKILL_VERSION},
        )
        planner_path = str(payload.get("vertical_slice.planner_path") or "")
        if planner_path != "scoring_context_refresh":
            return _fail(
                self.metadata,
                audit=audit,
                timing=timing,
                category=FailureCategory.VALIDATION_ERROR,
                code="scoring_context_materialize.validation.planner_path",
                message=f"unexpected planner_path {planner_path!r}",
            )
        authored = {
            "organization_authoring_text": str(payload.get("organization_authoring_text") or "").strip(),
            "recruiter_actor_authoring_text": str(
                payload.get("recruiter_actor_authoring_text") or ""
            ).strip(),
            "job_authoring_text": str(payload.get("job_authoring_text") or "").strip(),
        }
        for key, value in authored.items():
            if not value:
                return _fail(
                    self.metadata,
                    audit=audit,
                    timing=timing,
                    category=FailureCategory.VALIDATION_ERROR,
                    code=f"scoring_context_materialize.validation.{key}",
                    message=f"missing required payload key: {key}",
                )
        if context.dry_run:
            return SkillExecutionResult(
                metadata=self.metadata,
                status=ExecutionStatus.SUCCEEDED,
                output=SkillOutputEnvelope(
                    payload={"dry_run": True, "would_materialize_scoring_context": True},
                    extensions={"dry_run": True},
                ),
                timing=timing,
                audit=audit,
            )
        try:
            provider = self._provider_or_error()
            raw_result = provider.generate_structured(
                system_prompt=_SYSTEM_PROMPT,
                user_prompt=json.dumps(authored, ensure_ascii=True),
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
                code="scoring_context_materialize.invalid_output",
                message=f"provider returned invalid structured output: {exc}",
            )

        return SkillExecutionResult(
            metadata=self.metadata,
            status=ExecutionStatus.SUCCEEDED,
            output=SkillOutputEnvelope(
                payload={
                    "organization_context": _dump_model(parsed.organization_context),
                    "recruiter_actor_context": _dump_model(parsed.recruiter_actor_context),
                    "job_context": _dump_model(parsed.job_context),
                    "derived_l2_criteria": list(parsed.derived_l2_criteria),
                    "derived_l3_criteria": list(parsed.derived_l3_criteria),
                    "explanation": parsed.explanation,
                },
            ),
            timing=timing,
            audit=audit,
        )
