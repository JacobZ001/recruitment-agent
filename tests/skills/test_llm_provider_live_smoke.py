from __future__ import annotations

import os

import pytest

from skills.llm.llm_provider import build_llm_provider_from_env


def test_live_provider_smoke() -> None:
    if os.environ.get("RUN_LLM_PROVIDER_LIVE_SMOKE") != "1":
        pytest.skip("Set RUN_LLM_PROVIDER_LIVE_SMOKE=1 to enable live provider smoke test")

    provider_name = (os.environ.get("LLM_PROVIDER") or "").strip().lower()
    if provider_name not in {"openai", "openrouter"}:
        pytest.skip("Set LLM_PROVIDER=openai or LLM_PROVIDER=openrouter for live smoke")

    provider = build_llm_provider_from_env()
    result = provider.generate_structured(
        system_prompt=(
            "Return a JSON object with keys profile, criteria, and explanation. "
            "Criteria must include communication, ownership, reliability, and thinking."
        ),
        user_prompt=(
            "Candidate: 6 years as a Python backend engineer building APIs in SaaS. "
            "Uses FastAPI, PostgreSQL, Docker, and CI. Led small projects and wrote design docs."
        ),
    )
    assert set(result.keys()) >= {"profile", "criteria", "explanation"}
    assert set(result["criteria"].keys()) >= {
        "communication",
        "ownership",
        "reliability",
        "thinking",
    }
