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
                "raw_text": (
                    "BlueOcean is a recruitment company. The Talent Ops team operates in a "
                    "fast-moving operations environment. The organization values clear "
                    "communication and structured follow-through."
                ),
                "source_ref": "test://organization",
            },
        )
        assert org.status_code == 200, org.text
        assert org.json()["status"] == "collecting"
        assert org.json()["organization_authoring_text"]
        assert org.json()["organization_context"] is None

        recruiter = client.post(
            "/scoring-context/recruiter-actor",
            json={
                "raw_text": (
                    "Recruiter route-recruiter is a lead recruiter focused on ownership and "
                    "operator-ready execution. The recruiter values ownership and stakeholder "
                    "communication, and avoids unclear updates."
                ),
                "source_ref": "test://recruiter",
            },
        )
        assert recruiter.status_code == 200, recruiter.text
        assert recruiter.json()["status"] == "collecting"
        assert recruiter.json()["recruiter_actor_authoring_text"]
        assert recruiter.json()["recruiter_actor_context"] is None

        job = client.post(
            "/scoring-context/job/text",
            json={
                "raw_text": (
                    "We are hiring for a Recruiting Operations Specialist. Must-have signals "
                    "include stakeholder communication and process ownership. Preferred signals "
                    "include ATS familiarity. Success in the role means keeping candidate flow "
                    "organized. Responsibilities include coordinating interviews and surfacing "
                    "blockers early."
                ),
                "source_ref": "test://job",
            },
        )
        assert job.status_code == 200, job.text
        assert job.json()["status"] == "collecting"
        assert job.json()["job_authoring_text"]
        assert job.json()["job_context"] is None

        ready = client.post("/scoring-context/refresh")
        assert ready.status_code == 200, ready.text
        assert ready.json()["status"] == "ready"
        assert ready.json()["job_context"]["title"] == "Recruiting Operations Specialist"
        assert ready.json()["organization_context"]["company_name"] == "BlueOcean"
        assert ready.json()["recruiter_actor_context"]["actor_id"] == "route-recruiter"
        assert ready.json()["derived_l2_criteria"]
        assert ready.json()["derived_l3_criteria"]

        get_ready = client.get("/scoring-context")
        assert get_ready.status_code == 200
        assert get_ready.json()["status"] == "ready"
        assert get_ready.json()["organization_authoring_text"]


def test_scoring_context_structured_authoring_routes_and_refresh() -> None:
    with TestClient(create_app(db_path="")) as client:
        org = client.post(
            "/scoring-context/organization/structured",
            json={
                "company_name": "BlueOcean Recruitment",
                "industry": "Recruitment",
                "team_name": "Talent Ops",
                "environment_signals": ["Fast-paced recruiter workflow"],
                "preference_signals": ["Clear communication", "Structured follow-through"],
                "summary": "Boutique recruitment firm focused on ops excellence.",
                "source_ref": "form://organization",
            },
        )
        assert org.status_code == 200, org.text
        payload = org.json()
        assert payload["status"] == "collecting"
        assert payload["organization_authoring_text"]
        assert payload["organization_context"] is not None
        assert payload["organization_context"]["company_name"] == "BlueOcean Recruitment"
        assert "form://organization" in (payload.get("source_refs") or [])

        recruiter = client.post(
            "/scoring-context/recruiter-actor/structured",
            json={
                "actor_id": "Jane-recruiter",
                "actor_role": "Lead Recruiter",
                "preference_signals": ["Ownership"],
                "avoid_signals": ["Unclear communication"],
                "source_ref": "form://recruiter_actor",
            },
        )
        assert recruiter.status_code == 200, recruiter.text
        payload = recruiter.json()
        assert payload["status"] == "collecting"
        assert payload["recruiter_actor_authoring_text"]
        assert payload["recruiter_actor_context"] is not None
        assert payload["recruiter_actor_context"]["actor_id"] == "Jane-recruiter"
        assert "form://recruiter_actor" in (payload.get("source_refs") or [])

        job = client.post(
            "/scoring-context/job/structured",
            json={
                "role_title": "Recruiting Operations Specialist",
                "must_haves_answer": "Stakeholder communication\nProcess ownership",
                "preferred_answer": "ATS familiarity",
                "success_answer": "Keep candidate flow organized",
                "responsibilities_answer": "Coordinate interviews\nSurface blockers early",
                "source_ref": "form://job",
            },
        )
        assert job.status_code == 200, job.text
        payload = job.json()
        assert payload["status"] == "collecting"
        assert payload["job_authoring_text"]
        assert "form://job" in (payload.get("source_refs") or [])

        ready = client.post("/scoring-context/refresh")
        assert ready.status_code == 200, ready.text
        payload = ready.json()
        assert payload["status"] == "ready"
        assert payload["organization_context"]["company_name"] == "BlueOcean Recruitment"
        assert payload["recruiter_actor_context"]["actor_id"] == "Jane-recruiter"
        assert payload["job_context"]["title"] == "Recruiting Operations Specialist"
        assert payload["derived_l2_criteria"]
        assert payload["derived_l3_criteria"]


def test_scoring_context_refresh_rejects_insufficient_derivation_signals() -> None:
    with TestClient(create_app(db_path="")) as client:
        client.post(
            "/scoring-context/organization",
            json={
                "raw_text": "BlueOcean is a recruitment company with a fast-moving operations environment.",
            },
        )
        client.post(
            "/scoring-context/recruiter-actor",
            json={
                "raw_text": "Recruiter route-recruiter is a lead recruiter.",
            },
        )
        client.post(
            "/scoring-context/job/text",
            json={
                "raw_text": (
                    "We are hiring for a Recruiting Operations Specialist. Must-have signals "
                    "include stakeholder communication. Success in the role means keeping "
                    "candidate flow organized."
                ),
            },
        )

        ready = client.post("/scoring-context/refresh")
        assert ready.status_code == 422
        assert ready.json()["detail"]["code"] == "invalid_scoring_context"

        current = client.get("/scoring-context")
        assert current.status_code == 200
        assert current.json()["status"] == "collecting"
        assert current.json()["derived_l2_criteria"] == []
        assert current.json()["derived_l3_criteria"] == []


def test_job_context_pdf_route_success_and_failure() -> None:
    with TestClient(create_app(db_path="")) as client:
        good = client.post(
            "/scoring-context/job/pdf",
            json={
                "file_name": "job_context.pdf",
                "pdf_base64": _build_pdf_base64(
                    "We are hiring for a Recruiting Operations Specialist. Must-have signals include communication and ownership. Success in the role means keeping candidate flow organized."
                ),
            },
        )
        assert good.status_code == 200, good.text
        assert "Recruiting Operations Specialist" in good.json()["job_authoring_text"]

        bad = client.post(
            "/scoring-context/job/pdf",
            json={
                "file_name": "blank_job.pdf",
                "pdf_base64": _build_pdf_base64(None),
            },
        )
        assert bad.status_code == 422
        assert bad.json()["detail"]["code"] == "invalid_pdf_cv"
