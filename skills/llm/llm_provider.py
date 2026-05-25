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


class StubLLMProvider:
    """
    Deterministic local provider used in tests.

    This is not a fallback chain. It is selected explicitly by
    ``LLM_PROVIDER=stub`` or injected into the skill in tests.
    """

    def generate_structured(self, *, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        _ = system_prompt
        cv_text = user_prompt
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

        richness = min(len(cv_text.strip()) / 400.0, 1.0)
        years_score = 0.0 if years is None else min(float(years) / 10.0, 1.0)
        skill_score = min(len(skills) / 8.0, 1.0)
        summary_score = _clamp01((richness * 0.4) + (skill_score * 0.6))

        communication = _clamp01((richness * 0.7) + 0.15)
        ownership = _clamp01((years_score * 0.7) + 0.15)
        reliability = _clamp01((summary_score * 0.6) + (years_score * 0.2) + 0.1)
        thinking = _clamp01((skill_score * 0.6) + (richness * 0.2) + 0.1)

        def _criterion(score: float, reason: str) -> Dict[str, Any]:
            confidence = _clamp01(0.45 + (score * 0.45))
            return {
                "score": round(score, 6),
                "confidence": round(confidence, 6),
                "reason": reason,
            }

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

        return {
            "profile": {
                "years_experience": years,
                "seniority": seniority,
                "roles": roles,
                "skills": skills,
                "industries": industries,
                "summary": summary,
            },
            "criteria": {
                "communication": _criterion(communication, "Estimated from writing clarity and CV completeness."),
                "ownership": _criterion(ownership, "Estimated from experience level and role progression cues."),
                "reliability": _criterion(reliability, "Estimated from consistency and evidence density in the CV."),
                "thinking": _criterion(thinking, "Estimated from technical breadth and structured problem-solving signals."),
            },
            "explanation": (
                "Stub provider deterministic evaluation from the submitted CV text. "
                "Used for tests and local development only."
            ),
        }


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
