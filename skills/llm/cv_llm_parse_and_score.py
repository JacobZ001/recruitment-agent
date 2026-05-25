"""
LLM-backed CV parse-and-score skill for ``cv_submitted`` ingress.

The skill never persists raw CV text. It validates the LLM response into typed
snapshot write payloads: ``profile`` and ``evaluation.light``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Final, Literal, Mapping, Optional
from uuid import UUID, uuid5

from pydantic import BaseModel, Field, ValidationError

try:  # Pydantic v2
    from pydantic import ConfigDict

    _PYDANTIC_V2 = True
except Exception:  # pragma: no cover - runtime-selected by Pydantic major version
    _PYDANTIC_V2 = False

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
from modules.recruitment.scoring_context_service import build_score_evaluation
from schemas.state_schema import CriterionScore, IngressProfile, ScoreEvaluation
from skills.llm.llm_provider import LLMProvider, LLMProviderError, build_llm_provider_from_env

SKILL_NAME: Final[str] = "recruitment.vertical_slice.cv_parse_and_score"
SKILL_VERSION: Final[str] = "2.0.0"

_REFERENCE_TIME: Final[datetime] = datetime(2026, 5, 1, 0, 0, 0, tzinfo=timezone.utc)
_EXECUTION_ID_NAMESPACE: Final[UUID] = UUID("018f3e2a-7c9b-4a3d-8f0e-000000000011")
_CRITERION_WEIGHTS: Final[Dict[str, float]] = {
    "communication": 0.25,
    "ownership": 0.25,
    "reliability": 0.30,
    "thinking": 0.20,
}

_SYSTEM_PROMPT: Final[str] = """
You are extracting structured recruiter intake data from a submitted CV.
Return strict JSON only, no markdown.
Required top-level keys: profile, criteria, explanation.
Required criteria keys: communication, ownership, reliability, thinking.
Each criterion needs score in [0,1], confidence in [0,1], and reason.
Profile keys: years_experience, seniority, roles, skills, industries, summary.
Seniority must be junior, mid, senior, or null.
Do not include raw CV text in the response.
""".strip()


class _SkillModel(BaseModel):
    if _PYDANTIC_V2:
        model_config = ConfigDict(extra="forbid", validate_assignment=True)  # type: ignore[name-defined]
    else:  # pragma: no cover - runtime-selected by Pydantic major version
        class Config:
            extra = "forbid"
            validate_assignment = True


class _LLMProfile(_SkillModel):
    years_experience: Optional[int] = Field(default=None, ge=0, le=80)
    seniority: Optional[Literal["junior", "mid", "senior"]] = Field(default=None)
    roles: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    summary: str = Field(default="")


class _LLMCriterion(_SkillModel):
    score: float = Field(..., ge=0.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str = Field(default="")


class _LLMResponse(_SkillModel):
    profile: _LLMProfile
    criteria: Dict[str, _LLMCriterion]
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


def _confidence_level(score: float) -> ConfidenceLevel:
    if score < 0.4:
        return ConfidenceLevel.LOW
    if score < 0.7:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.HIGH


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


def _criterion_dict(criteria: Mapping[str, _LLMCriterion]) -> Dict[str, CriterionScore]:
    out: Dict[str, CriterionScore] = {}
    for key in _CRITERION_WEIGHTS:
        item = criteria[key]
        out[key] = CriterionScore(
            score=float(item.score),
            confidence=float(item.confidence),
            reason=str(item.reason or ""),
        )
    return out


def _mean_confidence(criteria: Mapping[str, CriterionScore]) -> float:
    vals = [float(v.confidence) for v in criteria.values()]
    if not vals:
        return 0.0
    return round(sum(vals) / float(len(vals)), 6)


def _weighted_score(criteria: Mapping[str, CriterionScore]) -> float:
    total = 0.0
    for key, weight in _CRITERION_WEIGHTS.items():
        total += float(criteria[key].score) * weight
    return round(total, 6)


def _dump_model(model: Any) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return model.dict()


def _validate_response(value: Any) -> _LLMResponse:
    if hasattr(_LLMResponse, "model_validate"):
        return _LLMResponse.model_validate(value)
    return _LLMResponse.parse_obj(value)


class CvLlmParseAndScoreSkill:
    """LLM skill that extracts ingress profile and light evaluation from raw CV text."""

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
            description="LLM CV ingress: structured profile extraction plus bounded light evaluation.",
            input_contract_version="2.0",
            output_contract_version="2.0",
            supports_dry_run=True,
            supports_replay=False,
            supports_idempotency=False,
            tags=["vertical_slice", "llm", "recruitment", "cv"],
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
            runtime="skills.llm.cv_llm_parse_and_score",
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
                code="cv_llm_parse_and_score.validation.planner_path",
                message=f"unexpected planner_path {planner_path!r}",
            )

        raw_cv = payload.get("cv_text")
        if raw_cv is None or not str(raw_cv).strip():
            return _fail(
                self.metadata,
                audit=audit,
                timing=timing,
                category=FailureCategory.VALIDATION_ERROR,
                code="cv_llm_parse_and_score.validation.cv_text",
                message="missing required payload key: cv_text",
            )
        cv_text = str(raw_cv).strip()
        if len(cv_text) > 16_000:
            return _fail(
                self.metadata,
                audit=audit,
                timing=timing,
                category=FailureCategory.VALIDATION_ERROR,
                code="cv_llm_parse_and_score.validation.cv_text_too_long",
                message="cv_text exceeds max supported length",
            )

        if context.dry_run:
            return SkillExecutionResult(
                metadata=self.metadata,
                status=ExecutionStatus.SUCCEEDED,
                output=SkillOutputEnvelope(
                    payload={"dry_run": True, "would_evaluate": True},
                    extensions={"dry_run": True},
                ),
                timing=timing,
                audit=audit,
            )

        try:
            provider = self._provider_or_error()
            raw_result = provider.generate_structured(system_prompt=_SYSTEM_PROMPT, user_prompt=cv_text)
            parsed = _validate_response(raw_result)
            for key in _CRITERION_WEIGHTS:
                if key not in parsed.criteria:
                    raise ValueError(f"missing required criterion: {key}")
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
        except (ValidationError, ValueError) as exc:
            return _fail(
                self.metadata,
                audit=audit,
                timing=timing,
                category=FailureCategory.PERMANENT,
                code="cv_llm_parse_and_score.invalid_output",
                message=f"provider returned invalid structured output: {exc}",
            )

        criteria = _criterion_dict(parsed.criteria)
        normalized_score = _weighted_score(criteria)
        confidence_score = _mean_confidence(criteria)

        profile = IngressProfile(
            years_experience=parsed.profile.years_experience,
            seniority=parsed.profile.seniority,
            roles=list(parsed.profile.roles),
            skills=list(parsed.profile.skills),
            industries=list(parsed.profile.industries),
            summary=parsed.profile.summary,
        )
        light = build_score_evaluation(
            source="system_llm",
            explanation=parsed.explanation,
            context_version=1,
            l1_universal=criteria,
            l2_role_specific={},
            l3_recruiter_preference={},
            evidence_refs=[],
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
                    "profile": _dump_model(profile),
                    "evaluation": {"light": _dump_model(light)},
                },
                confidence=confidence,
                extensions={"interface_version": SkillInterfaceVersion.V1.value},
            ),
            timing=timing,
            audit=audit,
            metrics={
                "cv.char_count": float(len(cv_text)),
                "evaluation.light.normalized_score": normalized_score,
                "evaluation.light.confidence": confidence_score,
            },
        )
