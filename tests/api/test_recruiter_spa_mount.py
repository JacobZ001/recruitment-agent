"""Recruiter SPA static mount at /app."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_api_mod = importlib.import_module("integrations.api.app")
create_app = _api_mod.create_app


def test_demo_route_unaffected_without_frontend_dist(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")
    monkeypatch.setenv("VERTICAL_SLICE_ENV_FILE", str(env_file))
    monkeypatch.setenv("VERTICAL_SLICE_DB_PATH", "")
    monkeypatch.setattr(_api_mod, "_frontend_dist_dir", lambda: None)

    with TestClient(create_app(db_path="")) as client:
        assert client.get("/demo").status_code == 200
        assert "text/html" in client.get("/demo").headers.get("content-type", "")


def test_spa_served_when_frontend_dist_exists(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")
    monkeypatch.setenv("VERTICAL_SLICE_ENV_FILE", str(env_file))
    monkeypatch.setenv("VERTICAL_SLICE_DB_PATH", "")

    fake_dist = tmp_path / "dist"
    fake_dist.mkdir(parents=True, exist_ok=True)
    index = fake_dist / "index.html"
    index.write_text("<!doctype html><html><body>recruiter spa</body></html>", encoding="utf-8")

    monkeypatch.setattr(_api_mod, "_frontend_dist_dir", lambda: fake_dist)

    with TestClient(create_app(db_path="")) as client:
        root = client.get("/", follow_redirects=False)
        assert root.status_code == 307
        assert root.headers.get("location") == "/app/"

        spa = client.get("/app/")
        assert spa.status_code == 200
        assert "recruiter spa" in spa.text

        assert client.get("/demo").status_code == 200
