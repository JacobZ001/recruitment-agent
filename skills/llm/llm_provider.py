"""
Minimal LLM provider abstraction for CV parsing/scoring.

Production providers use an OpenAI-compatible chat-completions endpoint.
Tests can select the deterministic ``stub`` provider via ``LLM_PROVIDER=stub``.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Protocol
from urllib import error, request

from modules.recruitment.scoring_context_service import (
    derive_l2_labels,
    derive_l3_labels,
    normalize_job_context_from_text,
    normalize_organization_context_from_text,
    normalize_recruiter_actor_context_from_text,
)


class LLMProvider(Protocol):
    def generate_structured(self, *, system_prompt: str, user_prompt: str) -> Dict[str, Any]: ...


@dataclass(frozen=True)
class LLMProviderError(Exception):
    code: str
    message: str
    category: str

    def __str__(self) -> str:
        return self.message


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _extract_years(cv_text: str) -> int | None:
    match = re.search(r"(\d{1,2})\s*\+?\s*years?", cv_text, flags=re.IGNORECASE)
    if match is None:
        return None
    try:
        years = int(match.group(1))
    except ValueError:
        return None
    return max(0, min(80, years))


def _extract_keywords(cv_text: str, *, pool: List[str]) -> List[str]:
    lowered = cv_text.lower()
    out: List[str] = []
    for item in pool:
        if item.lower() in lowered and item not in out:
            out.append(item)
    return out


def _criterion_payload(score: float, reason: str) -> Dict[str, Any]:
    confidence = _clamp01(0.45 + (score * 0.45))
    return {
        "score": round(score, 6),
        "confidence": round(confidence, 6),
        "reason": reason,
    }


def _payload_for_profile(cv_text: str) -> Dict[str, Any]:
    lowered = cv_text.lower()
    years = _extract_years(cv_text)
    role_pool = [
        "engineer",
        "developer",
        "manager",
        "architect",
        "analyst",
        "recruiter",
        "designer",
    ]
    skill_pool = [
        "python",
        "django",
        "fastapi",
        "sql",
        "postgresql",
        "docker",
        "git",
        "rest",
        "api",
        "testing",
        "javascript",
        "typescript",
        "react",
    ]
    industry_pool = [
        "fintech",
        "healthcare",
        "recruitment",
        "saas",
        "ecommerce",
    ]
    roles = _extract_keywords(lowered, pool=role_pool)
    skills = _extract_keywords(lowered, pool=skill_pool)
    industries = _extract_keywords(lowered, pool=industry_pool)

    seniority = None
    if years is not None:
        if years >= 8:
            seniority = "senior"
        elif years >= 4:
            seniority = "mid"
        else:
            seniority = "junior"

    cleaned = " ".join(line.strip() for line in cv_text.splitlines() if line.strip())
    summary = cleaned[:220].strip() or "Candidate profile extracted from submitted CV."
    headline = roles[0] if roles else None
    # Stub mode is UI/dev focused: keep a stable placeholder identity.
    full_name = "John Doe"
    return {
        "profile": {
            "full_name": full_name,
            "headline": headline,
            "years_experience": years,
            "seniority": seniority,
            "roles": roles,
            "skills": skills,
            "industries": industries,
            "summary": summary,
        },
        "explanation": "Stub provider deterministic profile extraction from submitted CV text.",
    }


def _token_overlap_score(label: str, cv_text: str) -> float:
    tokens = [tok for tok in re.split(r"[^a-z0-9]+", label.lower()) if tok and len(tok) > 2]
    if not tokens:
        return 0.45
    matches = sum(1 for tok in tokens if tok in cv_text.lower())
    return _clamp01(0.25 + (matches / len(tokens)) * 0.55)


def _payload_for_layered_score(user_prompt: str) -> Dict[str, Any]:
    try:
        payload = json.loads(user_prompt)
    except Exception:
        payload = {"cv_text": user_prompt, "required_layers": {}}

    cv_text = str(payload.get("cv_text") or "")
    profile = payload.get("profile") or {}
    required_layers = payload.get("required_layers") or {}
    years = _extract_years(cv_text)
    richness = min(len(cv_text.strip()) / 500.0, 1.0)
    years_score = 0.0 if years is None else min(float(years) / 10.0, 1.0)
    skills = list((profile.get("skills") or [])) if isinstance(profile, Mapping) else []
    skill_score = min(len(skills) / 8.0, 1.0)
    summary_score = _clamp01((richness * 0.4) + (skill_score * 0.6))

    l1_names = list(required_layers.get("l1_universal") or [])
    l2_names = list(required_layers.get("l2_role_specific") or [])
    l3_names = list(required_layers.get("l3_recruiter_preference") or [])

    l1_scores: Dict[str, Any] = {}
    for name in l1_names:
        lowered = str(name).lower()
        if lowered == "communication":
            score = _clamp01((richness * 0.7) + 0.15)
            reason = "Estimated from writing clarity and CV completeness."
        elif lowered == "ownership":
            score = _clamp01((years_score * 0.7) + 0.15)
            reason = "Estimated from experience level and role progression cues."
        elif lowered == "reliability":
            score = _clamp01((summary_score * 0.6) + (years_score * 0.2) + 0.1)
            reason = "Estimated from consistency and evidence density in the CV."
        else:
            score = _clamp01((skill_score * 0.6) + (richness * 0.2) + 0.1)
            reason = "Estimated from technical breadth and structured problem-solving signals."
        l1_scores[str(name)] = _criterion_payload(score, reason)

    l2_scores: Dict[str, Any] = {}
    for name in l2_names:
        base = _token_overlap_score(str(name), cv_text)
        score = _clamp01(0.25 + (base * 0.55) + (years_score * 0.10))
        l2_scores[str(name)] = _criterion_payload(
            score,
            "Estimated from overlap between candidate evidence and derived role/job requirements.",
        )

    l3_scores: Dict[str, Any] = {}
    for name in l3_names:
        base = _token_overlap_score(str(name), cv_text)
        if str(name).lower().startswith("avoid:"):
            score = _clamp01(0.9 - (base * 0.5))
            reason = "Estimated from limited presence of explicitly avoided preference signals."
        else:
            score = _clamp01(0.30 + (base * 0.45) + (richness * 0.15))
            reason = "Estimated from alignment with recruiter and organization preference signals."
        l3_scores[str(name)] = _criterion_payload(score, reason)

    return {
        "l1_universal": {
            "summary": "Universal competencies scored from candidate CV evidence.",
            "criteria": l1_scores,
        },
        "l2_role_specific": {
            "summary": "Role-specific fit scored against derived job and organization requirements.",
            "criteria": l2_scores,
        },
        "l3_recruiter_preference": {
            "summary": "Preference alignment scored against recruiter and organization context.",
            "criteria": l3_scores,
        },
        "explanation": (
            "Stub provider deterministic layered evaluation from submitted CV text "
            "and scoring context. Used for tests and local development only."
        ),
    }


def _payload_for_scoring_context_materialization(user_prompt: str) -> Dict[str, Any]:
    try:
        payload = json.loads(user_prompt)
    except Exception:
        payload = {}
    organization_text = str(payload.get("organization_authoring_text") or "")
    recruiter_text = str(payload.get("recruiter_actor_authoring_text") or "")
    job_text = str(payload.get("job_authoring_text") or "")

    organization_context = normalize_organization_context_from_text(
        organization_text,
        source_refs=["normalized://organization_authoring_text"],
    )
    recruiter_actor_context = normalize_recruiter_actor_context_from_text(
        recruiter_text,
        source_refs=["normalized://recruiter_actor_authoring_text"],
    )
    job_context = normalize_job_context_from_text(
        job_text,
        source_refs=["normalized://job_authoring_text"],
    )
    if hasattr(organization_context, "model_dump"):
        org_payload = organization_context.model_dump(mode="json")
        recruiter_payload = recruiter_actor_context.model_dump(mode="json")
        job_payload = job_context.model_dump(mode="json")
    else:  # pragma: no cover
        org_payload = organization_context.dict()
        recruiter_payload = recruiter_actor_context.dict()
        job_payload = job_context.dict()
    return {
        "organization_context": {**org_payload},
        "recruiter_actor_context": {**recruiter_payload},
        "job_context": {**job_payload},
        "derived_l2_criteria": derive_l2_labels(job_context, organization_context),
        "derived_l3_criteria": derive_l3_labels(organization_context, recruiter_actor_context),
        "explanation": (
            "Stub provider normalized recruiter-authored prose into typed scoring context "
            "fields and bounded derived criteria."
        ),
    }


class StubLLMProvider:
    """
    Deterministic local provider used in tests.

    This is not a fallback chain. It is selected explicitly by
    ``LLM_PROVIDER=stub`` or injected into the skill in tests.
    """

    def generate_structured(self, *, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        if "l1_universal" in system_prompt and "l2_role_specific" in system_prompt:
            return _payload_for_layered_score(user_prompt)
        if "derived_l2_criteria" in system_prompt and "organization_context" in system_prompt:
            return _payload_for_scoring_context_materialization(user_prompt)
        return _payload_for_profile(user_prompt)


class OpenAICompatibleProvider:
    def __init__(self, *, base_url: str, model: str, api_key: str, provider_name: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._provider_name = provider_name

    def generate_structured(self, *, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        body = {
            "model": self._model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        payload = json.dumps(body).encode("utf-8")
        req = request.Request(
            url=f"{self._base_url}/chat/completions",
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
        )
        if self._provider_name == "openrouter":
            req.add_header("HTTP-Referer", "https://cursor.sh")
            req.add_header("X-Title", "BlueOcean Recruitment Agent")

        try:
            with request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise LLMProviderError(
                code=f"{self._provider_name}.http_error",
                message=f"{self._provider_name} request failed: {exc.code} {detail}",
                category="dependency_unavailable",
            ) from exc
        except error.URLError as exc:
            raise LLMProviderError(
                code=f"{self._provider_name}.network_error",
                message=f"{self._provider_name} request failed: {exc.reason}",
                category="dependency_unavailable",
            ) from exc

        try:
            data = json.loads(raw)
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
        except Exception as exc:  # pragma: no cover - provider contract failure
            raise LLMProviderError(
                code=f"{self._provider_name}.invalid_response",
                message=f"{self._provider_name} returned invalid structured output",
                category="permanent",
            ) from exc

        if not isinstance(parsed, Mapping):
            raise LLMProviderError(
                code=f"{self._provider_name}.invalid_payload",
                message=f"{self._provider_name} returned a non-object JSON payload",
                category="permanent",
            )
        return dict(parsed)


def build_llm_provider_from_env() -> LLMProvider:
    provider = (os.environ.get("LLM_PROVIDER") or "").strip().lower()
    if provider == "stub":
        return StubLLMProvider()

    if provider == "openai":
        api_key = (os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY") or "").strip()
        model = (os.environ.get("LLM_MODEL") or "gpt-4.1-mini").strip()
        if not api_key:
            raise LLMProviderError(
                code="openai.missing_api_key",
                message="OPENAI_API_KEY or LLM_API_KEY must be set for LLM_PROVIDER=openai",
                category="authorization",
            )
        return OpenAICompatibleProvider(
            base_url="https://api.openai.com/v1",
            model=model,
            api_key=api_key,
            provider_name="openai",
        )

    if provider == "openrouter":
        api_key = (os.environ.get("OPENROUTER_API_KEY") or os.environ.get("LLM_API_KEY") or "").strip()
        model = (os.environ.get("LLM_MODEL") or "openai/gpt-4.1-mini").strip()
        if not api_key:
            raise LLMProviderError(
                code="openrouter.missing_api_key",
                message="OPENROUTER_API_KEY or LLM_API_KEY must be set for LLM_PROVIDER=openrouter",
                category="authorization",
            )
        return OpenAICompatibleProvider(
            base_url="https://openrouter.ai/api/v1",
            model=model,
            api_key=api_key,
            provider_name="openrouter",
        )

    raise LLMProviderError(
        code="llm_provider.not_configured",
        message="Set LLM_PROVIDER to one of: stub, openai, openrouter",
        category="dependency_unavailable",
    )
