from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _configure_stub_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    if "LLM_PROVIDER" not in os.environ:
        monkeypatch.setenv("LLM_PROVIDER", "stub")
    if "LLM_MODEL" not in os.environ:
        monkeypatch.setenv("LLM_MODEL", "stub-cv")
