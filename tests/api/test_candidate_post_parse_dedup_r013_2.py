"""API wiring: post-parse duplicate flag on create+upload (R-013.2)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from integrations.api.app import create_app
from skills.llm.cv_llm_parse_profile import SKILL_NAME as SKILL_CV_PARSE_PROFILE
from modules.recruitment.dedup import normalize_email
from runtime.persistence.in_memory_candidate_store import InMemoryCandidateStore
from schemas.candidate_schema import DedupSignals, Identity, new_candidate
from skills.llm.llm_provider import StubLLMProvider
from tests.api.test_cv_pdf_ingest import _build_pdf_base64


@pytest.fixture
def client() -> TestClient:
    with TestClient(create_app(db_path="")) as c:
        yield c


def test_create_cv_pdf_post_parse_duplicate_visible_on_detail(
    client: TestClient,
    establish_ready_scoring_context,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PDF has no @ (pre-create skip); stub injects email matching seeded candidate."""
    parsed_email = "post.parse.api@hire.test"
    rt = client.app.state.vertical_slice
    establish_ready_scoring_context(rt)

    store: InMemoryCandidateStore = rt.candidate_store
    existing = uuid4()
    cand = new_candidate(existing)
    cand = cand.model_copy(
        update={
            "identity": Identity(primary_email=parsed_email, full_name="Existing"),
            "dedup_signals": DedupSignals(normalized_email=normalize_email(parsed_email)),
        }
    )
    store.create(cand)
    from modules.recruitment.use_cases import _ensure_candidate_state

    _ensure_candidate_state(rt, existing)

    class _InjectEmailStub(StubLLMProvider):
        def generate_structured(self, *, system_prompt: str, user_prompt: str):
            result = super().generate_structured(
                system_prompt=system_prompt, user_prompt=user_prompt
            )
            if "l1_universal" not in system_prompt and isinstance(
                result.get("profile"), dict
            ):
                profile = dict(result["profile"])
                profile["primary_email"] = parsed_email
                result = {**result, "profile": profile}
            return result

    inject_stub = _InjectEmailStub()
    rt.bundle.subscriber.orchestrator._ctx.skills[SKILL_CV_PARSE_PROFILE]._provider = (
        inject_stub
    )

    pdf_text = "Backend developer\n8 years Python django fastapi"
    r = client.post(
        "/candidates/cv/pdf",
        headers={"Idempotency-Key": str(uuid4())},
        json={"pdf_base64": _build_pdf_base64(pdf_text), "file_name": "cv.pdf"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("dedup", {}).get("status") == "post_ingress_duplicate"
    cid = body["candidate_id"]
    detail = client.get(f"/candidate/{cid}")
    assert detail.status_code == 200
    flags = detail.json()["governance_flags"]
    assert flags["dedup_status"] == "post_ingress_duplicate"
    assert flags["dedup_pending_resolution"] is True
