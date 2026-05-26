"""
LLM-backed light scoring against the active scoring context.

The model returns per-layer criterion scores only. Deterministic program logic
computes and persists the final aggregate score and confidence.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Final, Mapping, Optional
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
from schemas.state_schema import (
    CriterionScore,
    ScoringContext,
    ScoreLayerEvaluation,
)
from skills.llm.llm_provider import LLMProvider, LLMProviderError, build_llm_provider_from_env

SKILL_NAME: Final[str] = "recruitment.vertical_slice.cv_score_light"
SKILL_VERSION: Final[str] = "1.0.0"
_REFERENCE_TIME: Final[datetime] = datetime(2026, 5, 1, 0, 0, 0, tzinfo=timezone.utc)
_EXECUTION_ID_NAMESPACE: Final[UUID] = UUID("018f3e2a-7c9b-4a3d-8f0e-000000000022")
_L1_NAMES = ("communication", "ownership", "reliability", "thinking")

_SYSTEM_PROMPT: Final[str] = """
You are scoring a candidate CV against a bounded recruiter scoring context.
Return strict JSON only, no markdown.
Required top-level keys: l1_universal, l2_role_specific, l3_recruiter_preference, explanation.
Each layer must contain keys: summary, criteria.
Criteria values must be objects with score in [0,1], confidence in [0,1], and reason.
Use exactly the criterion names supplied in required_layers.
Do not compute overall score or final aggregate confidence; program logic handles that.
""".strip()


class _SkillModel(BaseModel):
    if _PYDANTIC_V2:
        model_config = ConfigDict(extra="forbid", validate_assignment=True)  # type: ignore[name-defined]
    else:  # pragma: no cover
        class Config:
            extra = "forbid"
            validate_assignment = True


class _LLMCriterion(_SkillModel):
    score: float = Field(..., ge=0.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str = Field(default="")


class _LLMLayer(_SkillModel):
    summary: str = Field(default="")
    criteria: Dict[str, _LLMCriterion]


class _LLMScoreResponse(_SkillModel):
    l1_universal: _LLMLayer
    l2_role_specific: _LLMLayer
    l3_recruiter_preference: _LLMLayer
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


def _validate_response(value: Any) -> _LLMScoreResponse:
    if hasattr(_LLMScoreResponse, "model_validate"):
        return _LLMScoreResponse.model_validate(value)
    return _LLMScoreResponse.parse_obj(value)


def _dump_model(model: Any) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return model.dict()


def _criterion_dict(criteria: Mapping[str, _LLMCriterion]) -> Dict[str, CriterionScore]:
    out: Dict[str, CriterionScore] = {}
    for key, item in criteria.items():
        out[str(key)] = CriterionScore(
            score=float(item.score),
            confidence=float(item.confidence),
            reason=str(item.reason or ""),
        )
    return out


def _layer_payload(layer: _LLMLayer) -> ScoreLayerEvaluation:
    return ScoreLayerEvaluation(
        summary=layer.summary,
        criteria=_criterion_dict(layer.criteria),
    )


class CvLlmScoreCandidateSkill:
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
            description="LLM job-aware light scoring from CV text plus scoring_context.",
            input_contract_version="1.0",
            output_contract_version="1.0",
            supports_dry_run=True,
            supports_replay=False,
            supports_idempotency=False,
            tags=["vertical_slice", "llm", "recruitment", "cv_score"],
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
            runtime="skills.llm.cv_llm_score_candidate",
            model_info={},
            extensions={"skill_version": SKILL_VERSION},
        )
        planner_path = str(payload.get("vertical_slice.planner_path") or "")
        if planner_path != "light_scoring_completed":
            return _fail(
                self.metadata,
                audit=audit,
                timing=timing,
                category=FailureCategory.VALIDATION_ERROR,
                code="cv_llm_score_candidate.validation.planner_path",
                message=f"unexpected planner_path {planner_path!r}",
            )
        raw_cv = payload.get("cv_text")
        if raw_cv is None or not str(raw_cv).strip():
            return _fail(
                self.metadata,
                audit=audit,
                timing=timing,
                category=FailureCategory.VALIDATION_ERROR,
                code="cv_llm_score_candidate.validation.cv_text",
                message="missing required payload key: cv_text",
            )
        raw_scoring_context = payload.get("scoring_context")
        if not isinstance(raw_scoring_context, Mapping):
            return _fail(
                self.metadata,
                audit=audit,
                timing=timing,
                category=FailureCategory.VALIDATION_ERROR,
                code="cv_llm_score_candidate.validation.scoring_context",
                message="missing required payload key: scoring_context",
            )
        try:
            if hasattr(ScoringContext, "model_validate"):
                scoring_context = ScoringContext.model_validate(raw_scoring_context)
            else:
                scoring_context = ScoringContext.parse_obj(raw_scoring_context)
        except ValidationError as exc:
            return _fail(
                self.metadata,
                audit=audit,
                timing=timing,
                category=FailureCategory.VALIDATION_ERROR,
                code="cv_llm_score_candidate.validation.scoring_context_invalid",
                message=f"invalid scoring_context payload: {exc}",
            )
        if (
            scoring_context.organization_context is None
            or scoring_context.recruiter_actor_context is None
            or scoring_context.job_context is None
        ):
            return _fail(
                self.metadata,
                audit=audit,
                timing=timing,
                category=FailureCategory.VALIDATION_ERROR,
                code="cv_llm_score_candidate.validation.scoring_context_components",
                message=(
                    "scoring_context must contain organization_context, recruiter_actor_context, "
                    "and job_context"
                ),
            )

        required_layers = {
            "l1_universal": list(_L1_NAMES),
            "l2_role_specific": list(scoring_context.derived_l2_criteria),
            "l3_recruiter_preference": list(scoring_context.derived_l3_criteria),
        }
        if not required_layers["l2_role_specific"] or not required_layers["l3_recruiter_preference"]:
            return _fail(
                self.metadata,
                audit=audit,
                timing=timing,
                category=FailureCategory.VALIDATION_ERROR,
                code="cv_llm_score_candidate.validation.materialized_criteria",
                message="scoring_context must contain persisted derived_l2_criteria and derived_l3_criteria",
            )

        user_payload = {
            "cv_text": str(raw_cv).strip(),
            "profile": payload.get("profile") or {},
            "scoring_context": _dump_model(scoring_context),
            "required_layers": required_layers,
        }
        if context.dry_run:
            return SkillExecutionResult(
                metadata=self.metadata,
                status=ExecutionStatus.SUCCEEDED,
                output=SkillOutputEnvelope(
                    payload={
                        "dry_run": True,
                        "required_layers": required_layers,
                    },
                    extensions={"dry_run": True},
                ),
                timing=timing,
                audit=audit,
            )
        try:
            provider = self._provider_or_error()
            raw_result = provider.generate_structured(
                system_prompt=_SYSTEM_PROMPT,
                user_prompt=json.dumps(user_payload, ensure_ascii=True),
            )
            parsed = _validate_response(raw_result)
            for name in required_layers["l1_universal"]:
                if name not in parsed.l1_universal.criteria:
                    raise ValueError(f"missing required L1 criterion: {name}")
            for name in required_layers["l2_role_specific"]:
                if name not in parsed.l2_role_specific.criteria:
                    raise ValueError(f"missing required L2 criterion: {name}")
            for name in required_layers["l3_recruiter_preference"]:
                if name not in parsed.l3_recruiter_preference.criteria:
                    raise ValueError(f"missing required L3 criterion: {name}")
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
                code="cv_llm_score_candidate.invalid_output",
                message=f"provider returned invalid layered output: {exc}",
            )

        return SkillExecutionResult(
            metadata=self.metadata,
            status=ExecutionStatus.SUCCEEDED,
            output=SkillOutputEnvelope(
                payload={
                    "evaluation": {
                        "light": {
                            "source": "system_llm",
                            "context_version": scoring_context.context_version,
                            "explanation": parsed.explanation,
                            "l1_universal": _dump_model(_layer_payload(parsed.l1_universal)),
                            "l2_role_specific": _dump_model(_layer_payload(parsed.l2_role_specific)),
                            "l3_recruiter_preference": _dump_model(
                                _layer_payload(parsed.l3_recruiter_preference)
                            ),
                        }
                    }
                },
                extensions={"interface_version": SkillInterfaceVersion.V1.value},
            ),
            timing=timing,
            audit=audit,
            metrics={
                "cv.char_count": float(len(user_payload["cv_text"])),
                "scoring_context.context_version": float(scoring_context.context_version),
                "layer.l2.criteria_count": float(len(required_layers["l2_role_specific"])),
                "layer.l3.criteria_count": float(len(required_layers["l3_recruiter_preference"])),
            },
        )
