"""API: bounded PDF CV ingress and recruiter read-surface reflection."""

from __future__ import annotations

import base64
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from integrations.api.app import create_app


@pytest.fixture
def client() -> TestClient:
    with TestClient(create_app(db_path="")) as c:
        yield c


def _build_pdf_bytes(text: str | None) -> bytes:
    if text is None:
        stream = b"BT\nET"
    else:
        safe = (
            text.replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
        )
        stream = f"BT\n/F1 12 Tf\n72 720 Td\n({safe}) Tj\nET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for idx, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{idx} 0 obj\n".encode())
        out.extend(obj)
        out.extend(b"\nendobj\n")
    xref_offset = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    out.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        out.extend(f"{offset:010d} 00000 n \n".encode())
    out.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode()
    )
    return bytes(out)


def _build_pdf_base64(text: str | None) -> str:
    return base64.b64encode(_build_pdf_bytes(text)).decode("ascii")


def test_pdf_cv_ingest_updates_state_and_recruiter_views(
    client: TestClient,
    establish_ready_scoring_context,
) -> None:
    establish_ready_scoring_context(client.app.state.vertical_slice)
    cid = str(uuid4())
    response = client.post(
        f"/candidates/{cid}/cv/pdf",
        json={
            "file_name": "candidate_cv.pdf",
            "pdf_base64": _build_pdf_base64(
                "Senior backend engineer\n8 years of experience\nPython FastAPI PostgreSQL Docker"
            ),
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["event_type"] == "cv_submitted"

    state = client.get(f"/state/{cid}")
    assert state.status_code == 200, state.text
    assert state.json()["pipeline_phase"] == "questionnaire_pending"

    view = client.get(f"/candidate/{cid}")
    assert view.status_code == 200, view.text
    payload = view.json()
    assert payload["profile"]["summary"]
    assert payload["evaluation"]["light"]["source"] == "system_llm"
    assert payload["scoring_context"]["status"] == "ready"
    assert payload["scores"]["overall_score"]["type"] == "light"
    assert payload["scores"]["overall_score"]["value"] is not None

    listing = client.get("/candidates")
    assert listing.status_code == 200, listing.text
    rows = listing.json()
    row = next(item for item in rows if item["candidate_id"] == cid)
    assert row["overall_score"]["type"] == "light"
    assert row["overall_score"]["value"] == payload["scores"]["overall_score"]["value"]
    assert row["rank"] == 1
    assert row["total_candidates"] >= 1


def test_pdf_cv_ingest_empty_pdf_returns_422(client: TestClient) -> None:
    cid = str(uuid4())
    response = client.post(
        f"/candidates/{cid}/cv/pdf",
        json={
            "file_name": "blank_cv.pdf",
            "pdf_base64": _build_pdf_base64(None),
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_pdf_cv"
    assert "empty text" in response.json()["detail"]["message"]


def test_pdf_cv_ingest_requires_ready_scoring_context(client: TestClient) -> None:
    cid = str(uuid4())
    response = client.post(
        f"/candidates/{cid}/cv/pdf",
        json={
            "file_name": "candidate_cv.pdf",
            "pdf_base64": _build_pdf_base64("Recruiter operations coordinator"),
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "scoring_context_not_ready"


def test_pdf_cv_ingest_rejects_collecting_context_with_weak_derivation_signals(
    client: TestClient,
) -> None:
    client.post(
        "/scoring-context/organization",
        json={
            "company_name": "BlueOcean",
            "environment_signals": ["fast-moving operations"],
            "preference_signals": [],
        },
    )
    client.post(
        "/scoring-context/recruiter-actor",
        json={
            "actor_id": "route-recruiter",
            "preference_signals": [],
            "avoid_signals": [],
        },
    )
    client.post(
        "/scoring-context/job/recruiter-answers",
        json={
            "role_title": "Recruiting Operations Specialist",
            "must_haves_answer": "stakeholder communication",
            "preferred_answer": "",
            "success_answer": "keep candidate flow organized",
            "responsibilities_answer": "coordinate interviews",
        },
    )

    cid = str(uuid4())
    response = client.post(
        f"/candidates/{cid}/cv/pdf",
        json={
            "file_name": "candidate_cv.pdf",
            "pdf_base64": _build_pdf_base64("Recruiter operations coordinator"),
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "scoring_context_not_ready"


def test_pdf_cv_ingest_provider_not_configured_returns_502(
    monkeypatch: pytest.MonkeyPatch,
    establish_ready_scoring_context,
) -> None:
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    with TestClient(create_app(db_path="")) as client:
        establish_ready_scoring_context(client.app.state.vertical_slice)
        cid = str(uuid4())
        response = client.post(
            f"/candidates/{cid}/cv/pdf",
            json={
                "file_name": "candidate_cv.pdf",
                "pdf_base64": _build_pdf_base64(
                    "Senior Python developer with 9 years experience"
                ),
            },
        )
    assert response.status_code == 502
    assert response.json()["detail"] == {"status": "failed", "error": "scoring_failed"}


def test_pdf_cv_ingest_uses_provider_from_env_file(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    establish_ready_scoring_context,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("LLM_PROVIDER=stub\nLLM_MODEL=stub-cv\n", encoding="utf-8")
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.setenv("VERTICAL_SLICE_ENV_FILE", str(env_file))

    with TestClient(create_app(db_path="")) as client:
        establish_ready_scoring_context(client.app.state.vertical_slice)
        cid = str(uuid4())
        response = client.post(
            f"/candidates/{cid}/cv/pdf",
            json={
                "file_name": "candidate_cv.pdf",
                "pdf_base64": _build_pdf_base64(
                    "Python backend engineer with 6 years experience and FastAPI"
                ),
            },
        )
    assert response.status_code == 200, response.text
    assert response.json()["publish_status"] == "accepted"


def test_pdf_cv_ingest_live_provider_smoke(establish_ready_scoring_context) -> None:
    if os.environ.get("RUN_LLM_PROVIDER_LIVE_SMOKE") != "1":
        pytest.skip("Set RUN_LLM_PROVIDER_LIVE_SMOKE=1 to enable live provider smoke test")
    provider_name = (os.environ.get("LLM_PROVIDER") or "").strip().lower()
    if provider_name not in {"openai", "openrouter"}:
        pytest.skip("Set LLM_PROVIDER=openai or LLM_PROVIDER=openrouter for live smoke")

    with TestClient(create_app(db_path="")) as client:
        establish_ready_scoring_context(client.app.state.vertical_slice)
        cid = str(uuid4())
        response = client.post(
            f"/candidates/{cid}/cv/pdf",
            json={
                "file_name": "candidate_cv.pdf",
                "pdf_base64": _build_pdf_base64(
                    "Candidate: 6 years building backend APIs in SaaS with Python, FastAPI, "
                    "PostgreSQL, Docker, CI, and design docs."
                ),
            },
        )
    assert response.status_code == 200, response.text
    assert response.json()["publish_status"] == "accepted"
