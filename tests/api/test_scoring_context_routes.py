"""API coverage for scoring-context authoring and readiness lifecycle."""

from __future__ import annotations

import base64

from fastapi.testclient import TestClient

from integrations.api.app import create_app


def _build_pdf_bytes(text: str | None) -> bytes:
    if text is None:
        stream = b"BT\nET"
    else:
        safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
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


def test_scoring_context_authoring_routes_and_refresh() -> None:
    with TestClient(create_app(db_path="")) as client:
        org = client.post(
            "/scoring-context/organization",
            json={
                "company_name": "BlueOcean",
                "industry": "recruitment",
                "environment_signals": ["fast-moving operations"],
                "preference_signals": ["clear communication"],
            },
        )
        assert org.status_code == 200, org.text
        assert org.json()["status"] == "collecting"

        recruiter = client.post(
            "/scoring-context/recruiter-actor",
            json={
                "actor_id": "route-recruiter",
                "preference_signals": ["ownership"],
                "avoid_signals": ["unclear updates"],
            },
        )
        assert recruiter.status_code == 200, recruiter.text
        assert recruiter.json()["status"] == "collecting"

        job = client.post(
            "/scoring-context/job/recruiter-answers",
            json={
                "role_title": "Recruiting Operations Specialist",
                "must_haves_answer": "stakeholder communication\nprocess ownership",
                "preferred_answer": "ATS familiarity",
                "success_answer": "keep candidate flow organized",
                "responsibilities_answer": "coordinate interviews\nsurface blockers early",
            },
        )
        assert job.status_code == 200, job.text
        assert job.json()["status"] == "collecting"
        assert job.json()["job_context"]["title"] == "Recruiting Operations Specialist"

        ready = client.post("/scoring-context/refresh")
        assert ready.status_code == 200, ready.text
        assert ready.json()["status"] == "ready"
        assert ready.json()["job_context"]["title"] == "Recruiting Operations Specialist"

        get_ready = client.get("/scoring-context")
        assert get_ready.status_code == 200
        assert get_ready.json()["status"] == "ready"


def test_job_context_pdf_route_success_and_failure() -> None:
    with TestClient(create_app(db_path="")) as client:
        good = client.post(
            "/scoring-context/job/pdf",
            json={
                "file_name": "job_context.pdf",
                "pdf_base64": _build_pdf_base64(
                    "Role: Recruiting Operations Specialist\nMust: communication, ownership\nSuccess: keep candidate flow organized"
                ),
            },
        )
        assert good.status_code == 200, good.text
        assert good.json()["job_context"]["title"] == "Recruiting Operations Specialist"

        bad = client.post(
            "/scoring-context/job/pdf",
            json={
                "file_name": "blank_job.pdf",
                "pdf_base64": _build_pdf_base64(None),
            },
        )
        assert bad.status_code == 422
        assert bad.json()["detail"]["code"] == "invalid_pdf_cv"
