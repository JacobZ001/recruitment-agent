from __future__ import annotations

import io
import json
import os
from urllib import error

import pytest

from integrations.api.app import _load_local_env_file
from skills.llm.llm_provider import (
    LLMProviderError,
    OpenAICompatibleProvider,
    StubLLMProvider,
    build_llm_provider_from_env,
)


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        return None


def test_build_provider_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(LLMProviderError) as excinfo:
        build_llm_provider_from_env()
    assert excinfo.value.code == "llm_provider.not_configured"
    assert excinfo.value.category == "dependency_unavailable"


def test_build_provider_openai_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(LLMProviderError) as excinfo:
        build_llm_provider_from_env()
    assert excinfo.value.code == "openai.missing_api_key"
    assert excinfo.value.category == "authorization"


def test_build_provider_openrouter_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(LLMProviderError) as excinfo:
        build_llm_provider_from_env()
    assert excinfo.value.code == "openrouter.missing_api_key"
    assert excinfo.value.category == "authorization"


def test_openai_provider_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = OpenAICompatibleProvider(
        base_url="https://api.openai.com/v1",
        model="gpt-4.1-mini",
        api_key="k",
        provider_name="openai",
    )

    def _boom(req, timeout):  # noqa: ANN001
        raise error.URLError("offline")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    with pytest.raises(LLMProviderError) as excinfo:
        provider.generate_structured(system_prompt="sys", user_prompt="user")
    assert excinfo.value.code == "openai.network_error"
    assert excinfo.value.category == "dependency_unavailable"


def test_openrouter_provider_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = OpenAICompatibleProvider(
        base_url="https://openrouter.ai/api/v1",
        model="openai/gpt-4.1-mini",
        api_key="k",
        provider_name="openrouter",
    )

    def _boom(req, timeout):  # noqa: ANN001
        raise error.HTTPError(
            url=str(req.full_url),
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=io.BytesIO(b'{"error":"bad key"}'),
        )

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    with pytest.raises(LLMProviderError) as excinfo:
        provider.generate_structured(system_prompt="sys", user_prompt="user")
    assert excinfo.value.code == "openrouter.http_error"
    assert excinfo.value.category == "dependency_unavailable"


def test_provider_invalid_response(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = OpenAICompatibleProvider(
        base_url="https://api.openai.com/v1",
        model="gpt-4.1-mini",
        api_key="k",
        provider_name="openai",
    )

    def _ok(req, timeout):  # noqa: ANN001
        return _FakeResponse({"choices": [{"message": {"content": "not-json"}}]})

    monkeypatch.setattr("urllib.request.urlopen", _ok)
    with pytest.raises(LLMProviderError) as excinfo:
        provider.generate_structured(system_prompt="sys", user_prompt="user")
    assert excinfo.value.code == "openai.invalid_response"
    assert excinfo.value.category == "permanent"


def test_provider_successful_json_parse(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = OpenAICompatibleProvider(
        base_url="https://api.openai.com/v1",
        model="gpt-4.1-mini",
        api_key="k",
        provider_name="openai",
    )

    payload = {
        "profile": {
            "years_experience": 5,
            "seniority": "mid",
            "roles": ["developer"],
            "skills": ["python"],
            "industries": [],
            "summary": "test summary",
        },
        "criteria": {
            "communication": {"score": 0.5, "confidence": 0.5, "reason": "r"},
            "ownership": {"score": 0.5, "confidence": 0.5, "reason": "r"},
            "reliability": {"score": 0.5, "confidence": 0.5, "reason": "r"},
            "thinking": {"score": 0.5, "confidence": 0.5, "reason": "r"},
        },
        "explanation": "ok",
    }

    def _ok(req, timeout):  # noqa: ANN001
        return _FakeResponse({"choices": [{"message": {"content": json.dumps(payload)}}]})

    monkeypatch.setattr("urllib.request.urlopen", _ok)
    result = provider.generate_structured(system_prompt="sys", user_prompt="user")
    assert result["profile"]["seniority"] == "mid"
    assert result["criteria"]["communication"]["score"] == 0.5


def test_stub_provider_returns_expected_shape() -> None:
    result = StubLLMProvider().generate_structured(
        system_prompt="Required top-level keys: profile, explanation.",
        user_prompt="Senior Python developer with 9 years experience in SaaS.",
    )
    assert "profile" in result
    assert "criteria" not in result
    assert result["profile"]["seniority"] == "senior"


def test_load_local_env_file_sets_missing_values_only(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "LLM_PROVIDER=openai\nVERTICAL_SLICE_DB_PATH=tmp.db\nLLM_MODEL='gpt-test'\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("VERTICAL_SLICE_DB_PATH", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    loaded = _load_local_env_file(str(env_file))
    assert loaded == str(env_file)
    assert os.environ["LLM_PROVIDER"] == "stub"
    assert os.environ["VERTICAL_SLICE_DB_PATH"] == "tmp.db"
    assert os.environ["LLM_MODEL"] == "gpt-test"
