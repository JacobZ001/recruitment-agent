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
_CLAUSE_SPLIT_RE = re.compile(r"[\n;,]+|\band\b", flags=re.IGNORECASE)
_SENTENCE_SPLIT_RE = re.compile(r"[\r\n]+|(?<=[.!?])\s+")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _clean_text(value: str, *, limit: int = 400) -> str:
    return " ".join(value.split())[:limit].strip()


def _clean_authored_text(value: str, *, limit: int = 2_000) -> str:
    lines = [" ".join(str(line).split()).strip() for line in str(value).splitlines()]
    cleaned = "\n".join(line for line in lines if line)
    return cleaned[:limit].strip()


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


def _split_items_loose(raw: str) -> List[str]:
    return _bounded_items(part for part in _CLAUSE_SPLIT_RE.split(raw or ""))


def _split_sentences(raw: str) -> List[str]:
    return _bounded_items(part for part in _SENTENCE_SPLIT_RE.split(raw or ""))


def _strip_leading_article(value: str) -> str:
    return re.sub(r"^(?:a|an|the)\s+", "", value.strip(), flags=re.IGNORECASE)


def _extract_first_match(raw_text: str, patterns: Sequence[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, raw_text, flags=re.IGNORECASE | re.MULTILINE)
        if match is None:
            continue
        value = _clean_text(match.group(1), limit=160)
        if value:
            return value
    return ""


def _extract_items_after_markers(raw_text: str, markers: Sequence[str]) -> List[str]:
    out: List[str] = []
    for marker in markers:
        pattern = rf"{marker}\s*[:\-]?\s*([^\n.]+)"
        match = re.search(pattern, raw_text, flags=re.IGNORECASE)
        if match is None:
            continue
        out.extend(_split_items_loose(match.group(1)))
    return _bounded_items(out)


def _sentences_with_keywords(raw_text: str, keywords: Sequence[str], *, limit: int = 2) -> List[str]:
    lowered_keywords = [item.lower() for item in keywords]
    out: List[str] = []
    for sentence in _split_sentences(raw_text):
        lowered = sentence.lower()
        if not any(keyword in lowered for keyword in lowered_keywords):
            continue
        out.append(sentence)
        if len(out) >= limit:
            break
    return _bounded_items(out)


def organization_context_to_authoring_text(context: OrganizationContext) -> str:
    lines = [f"Company: {context.company_name}"]
    if context.industry:
        lines.append(f"Industry: {context.industry}")
    if context.team_name:
        lines.append(f"Team: {context.team_name}")
    if context.environment_signals:
        lines.append(f"Environment: {', '.join(context.environment_signals)}")
    if context.preference_signals:
        lines.append(f"Preferences: {', '.join(context.preference_signals)}")
    if context.summary:
        lines.append(f"Summary: {context.summary}")
    return _clean_authored_text("\n".join(lines))


def recruiter_actor_context_to_authoring_text(context: RecruiterActorContext) -> str:
    lines = [f"Recruiter: {context.actor_id}"]
    if context.actor_role:
        lines.append(f"Role: {context.actor_role}")
    if context.hiring_focus:
        lines.append(f"Hiring focus: {', '.join(context.hiring_focus)}")
    if context.preference_signals:
        lines.append(f"Preferences: {', '.join(context.preference_signals)}")
    if context.avoid_signals:
        lines.append(f"Avoid: {', '.join(context.avoid_signals)}")
    if context.summary:
        lines.append(f"Summary: {context.summary}")
    return _clean_authored_text("\n".join(lines))


def job_context_to_authoring_text(context: JobContext) -> str:
    lines = [f"Role: {context.title}"]
    if context.hard_requirements:
        lines.append(f"Must have: {', '.join(context.hard_requirements)}")
    if context.preferred_requirements:
        lines.append(f"Preferred: {', '.join(context.preferred_requirements)}")
    if context.success_signals:
        lines.append(f"Success: {', '.join(context.success_signals)}")
    if context.responsibilities:
        lines.append(f"Responsibilities: {', '.join(context.responsibilities)}")
    if context.summary:
        lines.append(f"Summary: {context.summary}")
    return _clean_authored_text("\n".join(lines))


def recruiter_answers_to_job_authoring_text(
    *,
    role_title: str,
    must_haves_answer: str,
    preferred_answer: str,
    success_answer: str,
    responsibilities_answer: str,
) -> str:
    parts = [f"We are hiring for {role_title.strip()}."]
    if must_haves_answer.strip():
        parts.append(f"Must-have signals include {must_haves_answer.strip()}.")
    if preferred_answer.strip():
        parts.append(f"Preferred signals include {preferred_answer.strip()}.")
    if success_answer.strip():
        parts.append(f"Success in the role means {success_answer.strip()}.")
    if responsibilities_answer.strip():
        parts.append(f"Responsibilities include {responsibilities_answer.strip()}.")
    return _clean_authored_text("\n".join(parts))


def _job_context_has_required_signals(job: JobContext) -> bool:
    return bool(job.title.strip()) and bool(
        job.hard_requirements or job.preferred_requirements or job.success_signals or job.responsibilities
    )


def _organization_context_has_required_signals(org: OrganizationContext) -> bool:
    return bool(org.company_name.strip()) and bool(org.environment_signals) and bool(org.preference_signals)


def _recruiter_actor_context_has_required_signals(recruiter: RecruiterActorContext) -> bool:
    return bool(recruiter.actor_id.strip()) and bool(
        recruiter.preference_signals or recruiter.avoid_signals
    )


def normalize_organization_context_from_text(
    raw_text: str,
    *,
    source_refs: Optional[Sequence[str]] = None,
) -> OrganizationContext:
    authored = _clean_authored_text(raw_text)
    if not authored:
        raise ValueError("organization_context text must be non-empty")
    company_name = _extract_first_match(
        authored,
        (
            r"company\s*:\s*([^\n.]+)",
            r"organization\s*:\s*([^\n.]+)",
            r"^\s*([A-Z][A-Za-z0-9&' /-]{1,80}?)\s+(?:is|runs|operates|builds)\b",
        ),
    )
    if not company_name:
        raise ValueError("organization_context prose must identify a company_name")
    industry = _extract_first_match(
        authored,
        (
            r"industry\s*:\s*([^\n.]+)",
            r"\b(recruitment|saas|fintech|healthcare|ecommerce|education|consulting)\b",
        ),
    )
    team_name = _extract_first_match(
        authored,
        (
            r"team\s*:\s*([^\n.]+)",
            r"([A-Z][A-Za-z0-9&' /-]{1,80} team)\b",
        ),
    ).removesuffix(" team").strip()
    environment_signals = _extract_items_after_markers(
        authored,
        (
            "environment",
            "operating environment",
            "pace",
            "workflow",
            "team works in",
        ),
    ) or _sentences_with_keywords(
        authored,
        ("environment", "pace", "workflow", "operations", "coordination", "cross-functional"),
    )
    preference_signals = _extract_items_after_markers(
        authored,
        ("values", "value", "prefers", "prefer", "looks for", "cares about", "care about"),
    ) or _sentences_with_keywords(
        authored,
        ("values", "prefer", "looks for", "care", "communication", "follow-through"),
    )
    return OrganizationContext(
        company_name=company_name,
        industry=industry,
        team_name=team_name,
        environment_signals=environment_signals,
        preference_signals=preference_signals,
        summary=_clean_text(authored, limit=260),
        source_refs=_bounded_items(source_refs or ()),
    )


def normalize_recruiter_actor_context_from_text(
    raw_text: str,
    *,
    source_refs: Optional[Sequence[str]] = None,
) -> RecruiterActorContext:
    authored = _clean_authored_text(raw_text)
    if not authored:
        raise ValueError("recruiter_actor_context text must be non-empty")
    actor_id = _extract_first_match(
        authored,
        (
            r"recruiter\s*:\s*([^\n.]+)",
            r"actor\s*:\s*([^\n.]+)",
            r"^\s*([A-Z][A-Za-z0-9&' /-]{1,80}?)\s+is\b",
        ),
    )
    actor_id = re.sub(r"^recruiter\s+", "", actor_id, flags=re.IGNORECASE).strip()
    if not actor_id:
        raise ValueError("recruiter_actor_context prose must identify an actor_id")
    actor_role = _extract_first_match(
        authored,
        (
            r"role\s*:\s*([^\n.]+)",
            r"\bis\s+(?:the\s+)?([a-z][a-z0-9 /-]{2,60}?)(?:[.,]|\s+who\b|\s+focused\b|\s+with\b)",
        ),
    )
    hiring_focus = _extract_items_after_markers(
        authored,
        ("hiring focus", "focused on", "focuses on", "focus", "cares most about"),
    ) or _sentences_with_keywords(
        authored,
        ("focus", "hiring", "execution", "delivery"),
    )
    preference_signals = _extract_items_after_markers(
        authored,
        ("values", "prefers", "preference", "looks for", "wants"),
    ) or _sentences_with_keywords(
        authored,
        ("values", "prefers", "looks for", "ownership", "communication"),
    )
    avoid_signals = _extract_items_after_markers(
        authored,
        ("avoid", "avoids", "dislikes", "should not", "watch out for"),
    )
    return RecruiterActorContext(
        actor_id=actor_id,
        actor_role=actor_role,
        hiring_focus=hiring_focus,
        preference_signals=preference_signals,
        avoid_signals=avoid_signals,
        summary=_clean_text(authored, limit=260),
        source_refs=_bounded_items(source_refs or ()),
    )


def _validate_materialized_payload(
    *,
    organization_context: Optional[OrganizationContext],
    recruiter_actor_context: Optional[RecruiterActorContext],
    job_context: Optional[JobContext],
    derived_l2_criteria: Sequence[str],
    derived_l3_criteria: Sequence[str],
) -> tuple[List[str], List[str]]:
    org = organization_context
    recruiter = recruiter_actor_context
    job = job_context
    if org is None or not _organization_context_has_required_signals(org):
        raise ValueError(
            "organization_context must include non-empty company_name plus bounded "
            "environment_signals and preference_signals before ready"
        )
    if recruiter is None or not _recruiter_actor_context_has_required_signals(recruiter):
        raise ValueError(
            "recruiter_actor_context must include actor_id plus at least one recruiter "
            "preference or avoid signal before ready"
        )
    if job is None or not _job_context_has_required_signals(job):
        raise ValueError(
            "job_context must include title plus bounded role signals before ready"
        )
    l2 = _bounded_items(derived_l2_criteria)[:3]
    l3 = _bounded_items(derived_l3_criteria)[:3]
    if not l2:
        raise ValueError("materialized L2 criteria must be non-empty before ready")
    if not l3:
        raise ValueError("materialized L3 criteria must be non-empty before ready")
    return l2, l3


def scoring_context_is_ready(context: ScoringContext) -> bool:
    if context.status != ScoringContextStatus.READY:
        return False
    try:
        l2, l3 = _validate_materialized_payload(
            organization_context=context.organization_context,
            recruiter_actor_context=context.recruiter_actor_context,
            job_context=context.job_context,
            derived_l2_criteria=context.derived_l2_criteria,
            derived_l3_criteria=context.derived_l3_criteria,
        )
    except ValueError:
        return False
    return list(context.derived_l2_criteria) == list(l2) and list(context.derived_l3_criteria) == list(l3)


def refresh_scoring_context(
    existing: Optional[ScoringContext],
    *,
    organization_context: Optional[OrganizationContext] = None,
    recruiter_actor_context: Optional[RecruiterActorContext] = None,
    job_context: Optional[JobContext] = None,
    derived_l2_criteria: Optional[Sequence[str]] = None,
    derived_l3_criteria: Optional[Sequence[str]] = None,
) -> ScoringContext:
    base = existing or ScoringContext()
    next_organization = organization_context if organization_context is not None else base.organization_context
    next_recruiter = (
        recruiter_actor_context
        if recruiter_actor_context is not None
        else base.recruiter_actor_context
    )
    next_job = job_context if job_context is not None else base.job_context
    next_l2 = (
        list(derived_l2_criteria)
        if derived_l2_criteria is not None
        else list(base.derived_l2_criteria)
    )
    next_l3 = (
        list(derived_l3_criteria)
        if derived_l3_criteria is not None
        else list(base.derived_l3_criteria)
    )
    try:
        l2, l3 = _validate_materialized_payload(
            organization_context=next_organization,
            recruiter_actor_context=next_recruiter,
            job_context=next_job,
            derived_l2_criteria=next_l2,
            derived_l3_criteria=next_l3,
        )
    except ValueError:
        return _copy_context(
            base,
            organization_context=next_organization,
            recruiter_actor_context=next_recruiter,
            job_context=next_job,
            status=ScoringContextStatus.COLLECTING,
            updated_at=_now_utc(),
            ready_at=None,
            derived_l2_criteria=[],
            derived_l3_criteria=[],
        )
    now = _now_utc()
    return _copy_context(
        base,
        organization_context=next_organization,
        recruiter_actor_context=next_recruiter,
        job_context=next_job,
        status=ScoringContextStatus.READY,
        updated_at=now,
        ready_at=now,
        stale_at=None,
        derived_l2_criteria=l2,
        derived_l3_criteria=l3,
    )


def _clear_dimension_status(existing: ScoringContext) -> tuple[ScoringContextStatus, Optional[datetime]]:
    if existing.status == ScoringContextStatus.READY:
        return ScoringContextStatus.STALE, _now_utc()
    return ScoringContextStatus.COLLECTING, existing.stale_at


def clear_organization_from_scoring_context(
    existing: Optional[ScoringContext],
) -> ScoringContext:
    now = _now_utc()
    if existing is None:
        return ScoringContext(created_at=now, updated_at=now, status=ScoringContextStatus.COLLECTING)
    next_status, stale_at = _clear_dimension_status(existing)
    return _copy_context(
        existing,
        context_version=int(existing.context_version) + 1,
        organization_authoring_text="",
        organization_context=None,
        status=next_status,
        updated_at=now,
        ready_at=None,
        stale_at=stale_at,
        derived_l2_criteria=[],
        derived_l3_criteria=[],
    )


def clear_recruiter_actor_from_scoring_context(
    existing: Optional[ScoringContext],
) -> ScoringContext:
    now = _now_utc()
    if existing is None:
        return ScoringContext(created_at=now, updated_at=now, status=ScoringContextStatus.COLLECTING)
    next_status, stale_at = _clear_dimension_status(existing)
    return _copy_context(
        existing,
        context_version=int(existing.context_version) + 1,
        recruiter_actor_authoring_text="",
        recruiter_actor_context=None,
        status=next_status,
        updated_at=now,
        ready_at=None,
        stale_at=stale_at,
        derived_l2_criteria=[],
        derived_l3_criteria=[],
    )


def clear_job_from_scoring_context(
    existing: Optional[ScoringContext],
) -> ScoringContext:
    now = _now_utc()
    if existing is None:
        return ScoringContext(created_at=now, updated_at=now, status=ScoringContextStatus.COLLECTING)
    next_status, stale_at = _clear_dimension_status(existing)
    return _copy_context(
        existing,
        context_version=int(existing.context_version) + 1,
        job_authoring_text="",
        job_context=None,
        status=next_status,
        updated_at=now,
        ready_at=None,
        stale_at=stale_at,
        derived_l2_criteria=[],
        derived_l3_criteria=[],
    )


def update_scoring_context(
    existing: Optional[ScoringContext],
    *,
    organization_authoring_text: Optional[str] = None,
    recruiter_actor_authoring_text: Optional[str] = None,
    job_authoring_text: Optional[str] = None,
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
        organization_authoring_text=(
            _clean_authored_text(organization_authoring_text)
            if organization_authoring_text is not None
            else context.organization_authoring_text
        ),
        recruiter_actor_authoring_text=(
            _clean_authored_text(recruiter_actor_authoring_text)
            if recruiter_actor_authoring_text is not None
            else context.recruiter_actor_authoring_text
        ),
        job_authoring_text=(
            _clean_authored_text(job_authoring_text)
            if job_authoring_text is not None
            else context.job_authoring_text
        ),
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
        ready_at=None if next_status != ScoringContextStatus.READY else context.ready_at,
        derived_l2_criteria=[],
        derived_l3_criteria=[],
        source_refs=next_source_refs,
    )


def normalize_job_context_from_text(raw_text: str, *, source_refs: Optional[Sequence[str]] = None) -> JobContext:
    authored = _clean_authored_text(raw_text)
    lines = [line.strip() for line in authored.splitlines() if line.strip()]
    if not lines:
        raise ValueError("job_context text must be non-empty")

    title = ""
    responsibilities: List[str] = []
    hard_requirements: List[str] = []
    preferred_requirements: List[str] = []
    success_signals: List[str] = []

    for index, line in enumerate(lines):
        lowered = line.lower()
        if lowered.startswith(("title:", "role:", "position:")):
            title = _clean_text(line.split(":", 1)[1], limit=120)
            continue
        if lowered.startswith(("must:", "must_have:", "requirements:", "hard_requirements:", "must have:")):
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
            if lowered.startswith(("we are hiring", "hiring ", "role is", "position is")):
                continue
            title = _clean_text(line, limit=120)
        else:
            responsibilities.append(_clean_text(line, limit=_MAX_ITEM_LEN))

    if not title:
        title = _strip_leading_article(
            _extract_first_match(
            authored,
            (
                r"(?:hiring for|hiring an|hiring a|role is|position is)\s+([^\n.]+)",
                r"(?:we are hiring for|we need)\s+([^\n.]+)",
            ),
        )
        )
    if not hard_requirements:
        hard_requirements.extend(
            _extract_items_after_markers(
                authored,
                ("must have", "must-have signals include", "requires", "needs"),
            )
        )
    if not preferred_requirements:
        preferred_requirements.extend(
            _extract_items_after_markers(
                authored,
                ("preferred", "nice to have", "bonus", "ideally"),
            )
        )
    if not success_signals:
        success_signals.extend(
            _extract_items_after_markers(
                authored,
                ("success", "success means", "successful in the role means", "you will succeed by"),
            )
        )
    if not responsibilities:
        responsibilities.extend(
            _extract_items_after_markers(
                authored,
                ("responsibilities include", "you will", "responsibility"),
            )
        )

    job = JobContext(
        title=_strip_leading_article(title) or "Untitled role",
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
    return _bounded_items(
        list(job_context.hard_requirements[:2])
        + list(job_context.preferred_requirements[:1])
        + [f"Operate effectively in {signal}" for signal in organization_context.environment_signals[:1]]
        + list(job_context.success_signals[:1])
    )[:3]


def derive_l3_labels(
    organization_context: OrganizationContext,
    recruiter_actor_context: RecruiterActorContext,
) -> List[str]:
    return _bounded_items(
        list(recruiter_actor_context.preference_signals[:2])
        + list(organization_context.preference_signals[:1])
        + [f"Avoid: {item}" for item in recruiter_actor_context.avoid_signals[:1]]
    )[:3]


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
