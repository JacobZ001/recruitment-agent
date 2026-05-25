"""
Deterministic scoring-context authoring, normalization, and aggregation helpers.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

from schemas.state_schema import (
    CriterionScore,
    JobContext,
    OrganizationContext,
    RecruiterActorContext,
    ScoreEvaluation,
    ScoreLayerEvaluation,
    ScoringContext,
    ScoringContextStatus,
)

_MAX_ITEMS = 8
_MAX_ITEM_LEN = 120
_L1_UNIVERSAL_NAMES = ("communication", "ownership", "reliability", "thinking")
_LAYER_WEIGHTS = {
    "l1_universal": 0.40,
    "l2_role_specific": 0.40,
    "l3_recruiter_preference": 0.20,
}
_TEXT_SPLIT_RE = re.compile(r"[\n;,]+")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _clean_text(value: str, *, limit: int = 400) -> str:
    return " ".join(value.split())[:limit].strip()


def _bounded_items(values: Iterable[str]) -> List[str]:
    out: List[str] = []
    for raw in values:
        item = _clean_text(str(raw), limit=_MAX_ITEM_LEN)
        if not item:
            continue
        if item not in out:
            out.append(item)
        if len(out) >= _MAX_ITEMS:
            break
    return out


def _split_items(raw: str) -> List[str]:
    return _bounded_items(part for part in _TEXT_SPLIT_RE.split(raw or ""))


def _job_context_has_required_signals(job: JobContext) -> bool:
    return bool(job.title.strip()) and bool(
        job.hard_requirements or job.preferred_requirements or job.success_signals or job.responsibilities
    )


def scoring_context_is_ready(context: ScoringContext) -> bool:
    return (
        context.organization_context is not None
        and context.recruiter_actor_context is not None
        and context.job_context is not None
        and _job_context_has_required_signals(context.job_context)
    )


def refresh_scoring_context(existing: Optional[ScoringContext]) -> ScoringContext:
    base = existing or ScoringContext()
    if not scoring_context_is_ready(base):
        return _copy_context(
            base,
            status=ScoringContextStatus.COLLECTING,
            updated_at=_now_utc(),
        )
    now = _now_utc()
    return _copy_context(
        base,
        status=ScoringContextStatus.READY,
        updated_at=now,
        ready_at=now,
        stale_at=None,
    )


def update_scoring_context(
    existing: Optional[ScoringContext],
    *,
    organization_context: Optional[OrganizationContext] = None,
    recruiter_actor_context: Optional[RecruiterActorContext] = None,
    job_context: Optional[JobContext] = None,
    source_refs: Optional[Sequence[str]] = None,
) -> ScoringContext:
    now = _now_utc()
    if existing is None:
        context = ScoringContext(created_at=now, updated_at=now)
    else:
        context = _copy_context(existing)
    next_version = 1 if existing is None else int(existing.context_version) + 1
    next_source_refs = _bounded_items(list(context.source_refs) + list(source_refs or ()))
    next_status = ScoringContextStatus.COLLECTING
    stale_at = context.stale_at
    if existing is not None and existing.status == ScoringContextStatus.READY:
        next_status = ScoringContextStatus.STALE
        stale_at = now
    return _copy_context(
        context,
        context_version=next_version,
        organization_context=organization_context if organization_context is not None else context.organization_context,
        recruiter_actor_context=(
            recruiter_actor_context
            if recruiter_actor_context is not None
            else context.recruiter_actor_context
        ),
        job_context=job_context if job_context is not None else context.job_context,
        status=next_status,
        updated_at=now,
        stale_at=stale_at,
        source_refs=next_source_refs,
    )


def normalize_job_context_from_text(raw_text: str, *, source_refs: Optional[Sequence[str]] = None) -> JobContext:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    if not lines:
        raise ValueError("job_context text must be non-empty")

    title = ""
    responsibilities: List[str] = []
    hard_requirements: List[str] = []
    preferred_requirements: List[str] = []
    success_signals: List[str] = []

    for index, line in enumerate(lines):
        lowered = line.lower()
        if lowered.startswith(("title:", "role:")):
            title = _clean_text(line.split(":", 1)[1], limit=120)
            continue
        if lowered.startswith(("must:", "must_have:", "requirements:", "hard_requirements:")):
            hard_requirements.extend(_split_items(line.split(":", 1)[1]))
            continue
        if lowered.startswith(("prefer:", "preferred:", "nice_to_have:", "preferred_requirements:")):
            preferred_requirements.extend(_split_items(line.split(":", 1)[1]))
            continue
        if lowered.startswith(("success:", "success_signals:", "outcomes:")):
            success_signals.extend(_split_items(line.split(":", 1)[1]))
            continue
        if lowered.startswith(("responsibilities:", "responsibility:")):
            responsibilities.extend(_split_items(line.split(":", 1)[1]))
            continue
        if index == 0 and not title:
            title = _clean_text(line, limit=120)
        else:
            responsibilities.append(_clean_text(line, limit=_MAX_ITEM_LEN))

    job = JobContext(
        title=title or "Untitled role",
        summary=_clean_text(" ".join(lines), limit=260),
        responsibilities=_bounded_items(responsibilities),
        hard_requirements=_bounded_items(hard_requirements or responsibilities[:3]),
        preferred_requirements=_bounded_items(preferred_requirements),
        success_signals=_bounded_items(success_signals or responsibilities[:2]),
        source_refs=_bounded_items(source_refs or ()),
    )
    if not _job_context_has_required_signals(job):
        raise ValueError("job_context requires a title and at least one bounded role signal")
    return job


def normalize_job_context_from_answers(
    *,
    role_title: str,
    must_haves_answer: str,
    preferred_answer: str,
    success_answer: str,
    responsibilities_answer: str,
    source_refs: Optional[Sequence[str]] = None,
) -> JobContext:
    title = _clean_text(role_title, limit=120)
    if not title:
        raise ValueError("role_title must be non-empty")
    job = JobContext(
        title=title,
        summary=_clean_text(
            " ".join(
                filter(
                    None,
                    [
                        role_title,
                        must_haves_answer,
                        preferred_answer,
                        success_answer,
                        responsibilities_answer,
                    ],
                )
            ),
            limit=260,
        ),
        hard_requirements=_split_items(must_haves_answer),
        preferred_requirements=_split_items(preferred_answer),
        success_signals=_split_items(success_answer),
        responsibilities=_split_items(responsibilities_answer),
        source_refs=_bounded_items(source_refs or ()),
    )
    if not _job_context_has_required_signals(job):
        raise ValueError("normalized recruiter answers did not yield a valid job_context")
    return job


def derive_l2_labels(job_context: JobContext, organization_context: OrganizationContext) -> List[str]:
    labels = _bounded_items(
        list(job_context.hard_requirements[:2])
        + list(job_context.preferred_requirements[:1])
        + [f"Operate effectively in {signal}" for signal in organization_context.environment_signals[:1]]
        + list(job_context.success_signals[:1])
    )
    if not labels:
        labels = [f"Fit for role: {job_context.title}"]
    return labels[:3]


def derive_l3_labels(
    organization_context: OrganizationContext,
    recruiter_actor_context: RecruiterActorContext,
) -> List[str]:
    labels = _bounded_items(
        list(recruiter_actor_context.preference_signals[:2])
        + list(organization_context.preference_signals[:1])
        + [f"Avoid: {item}" for item in recruiter_actor_context.avoid_signals[:1]]
    )
    if not labels:
        labels = ["General recruiter/operator preference alignment"]
    return labels[:3]


def build_score_evaluation(
    *,
    source: str,
    explanation: str,
    context_version: int,
    l1_universal: Mapping[str, CriterionScore],
    l2_role_specific: Mapping[str, CriterionScore],
    l3_recruiter_preference: Mapping[str, CriterionScore],
    evidence_refs: Optional[Sequence[str]] = None,
) -> ScoreEvaluation:
    layer_models = {
        "l1_universal": ScoreLayerEvaluation(
            summary="Universal competencies for bounded recruiter evaluation.",
            criteria=dict(l1_universal),
        ),
        "l2_role_specific": ScoreLayerEvaluation(
            summary="Role-specific fit criteria derived from job and organization context.",
            criteria=dict(l2_role_specific),
        ),
        "l3_recruiter_preference": ScoreLayerEvaluation(
            summary="Preference-alignment criteria derived from recruiter and organization context.",
            criteria=dict(l3_recruiter_preference),
        ),
    }
    layer_scores: Dict[str, float] = {}
    layer_confidence: Dict[str, float] = {}
    for layer_name, layer_model in layer_models.items():
        criteria = list(layer_model.criteria.values())
        if not criteria:
            layer_scores[layer_name] = 0.0
            layer_confidence[layer_name] = 0.0
            continue
        layer_scores[layer_name] = round(sum(float(item.score) for item in criteria) / len(criteria), 6)
        layer_confidence[layer_name] = round(
            sum(float(item.confidence) for item in criteria) / len(criteria), 6
        )

    normalized_score = round(
        sum(layer_scores[name] * _LAYER_WEIGHTS[name] for name in _LAYER_WEIGHTS),
        6,
    )
    confidence = round(
        sum(layer_confidence[name] * _LAYER_WEIGHTS[name] for name in _LAYER_WEIGHTS),
        6,
    )
    return ScoreEvaluation(
        normalized_score=normalized_score,
        confidence=confidence,
        explanation=explanation,
        source=source,
        context_version=context_version,
        stale=False,
        l1_universal=layer_models["l1_universal"],
        l2_role_specific=layer_models["l2_role_specific"],
        l3_recruiter_preference=layer_models["l3_recruiter_preference"],
        evidence_refs=[str(item) for item in list(evidence_refs or ())],
    )


def mark_evaluation_stale(
    evaluation: Optional[ScoreEvaluation],
    *,
    active_context_version: int,
) -> Optional[ScoreEvaluation]:
    if evaluation is None:
        return None
    if evaluation.context_version >= active_context_version:
        return evaluation
    return _copy_score_evaluation(evaluation, stale=True)


def _copy_context(context: ScoringContext, **updates) -> ScoringContext:
    if hasattr(context, "model_copy"):
        return context.model_copy(update=updates, deep=True)
    return context.copy(update=updates, deep=True)


def _copy_score_evaluation(evaluation: ScoreEvaluation, **updates) -> ScoreEvaluation:
    if hasattr(evaluation, "model_copy"):
        return evaluation.model_copy(update=updates, deep=True)
    return evaluation.copy(update=updates, deep=True)
