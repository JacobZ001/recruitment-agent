"""API: POST /candidates/cv/pdf create+upload with idempotency (R-012)."""

from __future__ import annotations

import base64
import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from integrations.api.app import create_app
from tests.api.test_cv_pdf_ingest import _build_pdf_base64


@pytest.fixture
def client() -> TestClient:
    with TestClient(create_app(db_path="")) as c:
        yield c


def test_create_cv_pdf_requires_idempotency_key(
    client: TestClient,
    establish_ready_scoring_context,
) -> None:
    establish_ready_scoring_context(client.app.state.vertical_slice)
    r = client.post(
        "/candidates/cv/pdf",
        json={"pdf_base64": _build_pdf_base64("Engineer CV"), "file_name": "cv.pdf"},
    )
    assert r.status_code == 422
    detail = r.json()["detail"]
    if isinstance(detail, dict):
        assert detail["code"] == "idempotency_key_required"
    else:
        assert any(
            item.get("type") == "missing"
            and "idempotency-key" in [str(part).lower() for part in item.get("loc", [])]
            for item in detail
        )


def test_create_cv_pdf_rejects_when_context_not_ready(client: TestClient) -> None:
    r = client.post(
        "/candidates/cv/pdf",
        headers={"Idempotency-Key": str(uuid4())},
        json={"pdf_base64": _build_pdf_base64("Engineer CV"), "file_name": "cv.pdf"},
    )
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "scoring_context_not_ready"


def test_create_cv_pdf_happy_path(
    client: TestClient,
    establish_ready_scoring_context,
) -> None:
    establish_ready_scoring_context(client.app.state.vertical_slice)
    key = str(uuid4())
    body = {"pdf_base64": _build_pdf_base64("Backend dev\n5 years Python"), "file_name": "cv.pdf"}
    r = client.post("/candidates/cv/pdf", headers={"Idempotency-Key": key}, json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["candidate_id"]
    assert data["ingress_accepted"] is True
    assert data["event_type"] == "cv_submitted"
    cid = data["candidate_id"]
    view = client.get(f"/candidate/{cid}")
    assert view.status_code == 200


def test_create_cv_pdf_idempotency_replay(
    client: TestClient,
    establish_ready_scoring_context,
) -> None:
    establish_ready_scoring_context(client.app.state.vertical_slice)
    key = str(uuid4())
    body = {"pdf_base64": _build_pdf_base64("Replay test CV"), "file_name": "cv.pdf"}
    h = {"Idempotency-Key": key}
    r1 = client.post("/candidates/cv/pdf", headers=h, json=body)
    assert r1.status_code == 200
    r2 = client.post("/candidates/cv/pdf", headers=h, json=body)
    assert r2.status_code == 200
    assert r2.content == r1.content


def test_create_cv_pdf_idempotency_conflict(
    client: TestClient,
    establish_ready_scoring_context,
) -> None:
    establish_ready_scoring_context(client.app.state.vertical_slice)
    key = str(uuid4())
    h = {"Idempotency-Key": key}
    r1 = client.post(
        "/candidates/cv/pdf",
        headers=h,
        json={"pdf_base64": _build_pdf_base64("First PDF"), "file_name": "a.pdf"},
    )
    assert r1.status_code == 200
    r2 = client.post(
        "/candidates/cv/pdf",
        headers=h,
        json={"pdf_base64": _build_pdf_base64("Different PDF"), "file_name": "b.pdf"},
    )
    assert r2.status_code == 409
    assert r2.json()["detail"]["code"] == "idempotency_key_conflict"


def test_admin_reset_clears_idempotency_replay(
    client: TestClient,
    establish_ready_scoring_context,
) -> None:
    establish_ready_scoring_context(client.app.state.vertical_slice)
    key = str(uuid4())
    body = {"pdf_base64": _build_pdf_base64("Reset test"), "file_name": "cv.pdf"}
    h = {"Idempotency-Key": key}
    r1 = client.post("/candidates/cv/pdf", headers=h, json=body)
    assert r1.status_code == 200
    cid1 = r1.json()["candidate_id"]
    client.post("/admin/reset")
    establish_ready_scoring_context(client.app.state.vertical_slice)
    r2 = client.post("/candidates/cv/pdf", headers=h, json=body)
    assert r2.status_code == 200
    cid2 = r2.json()["candidate_id"]
    assert cid2 != cid1


def test_clear_organization_context(
    client: TestClient,
    establish_ready_scoring_context,
) -> None:
    establish_ready_scoring_context(client.app.state.vertical_slice)
    ctx = client.get("/scoring-context").json()
    assert ctx["status"] == "ready"
    cleared = client.delete("/scoring-context/organization")
    assert cleared.status_code == 200
    body = cleared.json()
    assert body["organization_authoring_text"] == ""
    assert body["organization_context"] is None
    assert body["status"] in ("stale", "collecting")
