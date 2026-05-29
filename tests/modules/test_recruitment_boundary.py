"""Recruitment module boundary and policy smoke tests."""

from __future__ import annotations

import ast
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import integrations.api.session as api_session_module
from integrations.api.app import create_app
from modules.recruitment import policies
from modules.recruitment.runtime import VerticalSliceApiRuntime
from modules.recruitment.use_cases import publish_recruitment_event, record_recruiter_decision, submit_cv
import modules.recruitment.bootstrap as recruitment_bootstrap
import modules.recruitment.fixtures as recruitment_fixtures
import modules.recruitment.ranking as recruitment_ranking
import runtime.bootstrap_vertical_slice as runtime_bootstrap_shim
import runtime.demo_candidate_fixture as runtime_fixture_shim
import runtime.vertical_slice_ranking as runtime_ranking_shim
from modules.recruitment.bootstrap import (
    VERTICAL_SLICE_DEFAULT_CANDIDATE_ID,
    drive_vertical_slice_primary_sequence,
    wire_vertical_slice_runtime,
)
from modules.recruitment.policies import VERTICAL_SLICE_INGRESS_EVENT_TYPES
from modules.recruitment.fixtures import TESTING_DESKTOP_CANDIDATE_ID, merge_demo_profile_into_skill_payload
from modules.recruitment.ranking import resolve_ranking_branch
from schemas.governance_schema import GOVERNANCE_EVENT_TYPES


@pytest.fixture
def client() -> TestClient:
    with TestClient(create_app(db_path="")) as c:
        yield c


def _assert_shim_only(path: Path, *, forbidden_substrings: tuple[str, ...]) -> None:
    text = path.read_text(encoding="utf-8")
    for frag in forbidden_substrings:
        assert frag not in text, f"{path.name} must not contain {frag!r}"


def test_runtime_bootstrap_shim_reexports_canonical_symbols() -> None:
    _assert_shim_only(
        Path(__file__).resolve().parents[2] / "runtime" / "bootstrap_vertical_slice.py",
        forbidden_substrings=("def wire_vertical_slice_runtime", "class VerticalSliceRuntimeBundle"),
    )
    assert runtime_bootstrap_shim.VERTICAL_SLICE_DEFAULT_CANDIDATE_ID == recruitment_bootstrap.VERTICAL_SLICE_DEFAULT_CANDIDATE_ID
    assert runtime_bootstrap_shim.VERTICAL_SLICE_INGRESS_EVENT_TYPES == recruitment_bootstrap.VERTICAL_SLICE_INGRESS_EVENT_TYPES
    assert runtime_bootstrap_shim.wire_vertical_slice_runtime is recruitment_bootstrap.wire_vertical_slice_runtime
    assert runtime_bootstrap_shim.drive_vertical_slice_primary_sequence is recruitment_bootstrap.drive_vertical_slice_primary_sequence


def test_runtime_fixture_and_ranking_shims() -> None:
    _assert_shim_only(
        Path(__file__).resolve().parents[2] / "runtime" / "demo_candidate_fixture.py",
        forbidden_substrings=("def merge_demo_profile_into_skill_payload",),
    )
    _assert_shim_only(
        Path(__file__).resolve().parents[2] / "runtime" / "vertical_slice_ranking.py",
        forbidden_substrings=("def resolve_ranking_branch", "TOP_K ="),
    )
    assert runtime_fixture_shim.merge_demo_profile_into_skill_payload is merge_demo_profile_into_skill_payload
    assert runtime_fixture_shim.TESTING_DESKTOP_CANDIDATE_ID == TESTING_DESKTOP_CANDIDATE_ID
    assert runtime_ranking_shim.resolve_ranking_branch is recruitment_ranking.resolve_ranking_branch


def test_bootstrap_module_does_not_import_fastapi() -> None:
    path = Path(__file__).resolve().parents[2] / "modules" / "recruitment" / "bootstrap.py"
    text = path.read_text(encoding="utf-8").lower()
    assert "fastapi" not in text
    assert "httpexception" not in text


def test_runtime_module_does_not_import_registry() -> None:
    path = Path(__file__).resolve().parents[2] / "modules" / "recruitment" / "runtime.py"
    text = path.read_text(encoding="utf-8")
    assert "registry" not in text


def test_bootstrap_subscriber_does_not_import_registry() -> None:
    path = Path(__file__).resolve().parents[2] / "modules" / "recruitment" / "bootstrap.py"
    text = path.read_text(encoding="utf-8")
    assert "from .registry" not in text
    assert "CandidateRegistry" not in text
    assert "get_for_candidate" in text


def test_ranking_module_is_pure_policy() -> None:
    path = Path(__file__).resolve().parents[2] / "modules" / "recruitment" / "ranking.py"
    text = path.read_text(encoding="utf-8")
    assert "from runtime" not in text
    assert "from orchestrator" not in text
    assert resolve_ranking_branch(payload={}, stage="light") == "mid_m"


def test_api_session_module_is_shim_only() -> None:
    path = Path(__file__).resolve().parents[2] / "integrations" / "api" / "session.py"
    text = path.read_text(encoding="utf-8")
    assert "class VerticalSliceApiRuntime" not in text
    assert "class DevResetResult" not in text
    assert api_session_module.VerticalSliceApiRuntime is VerticalSliceApiRuntime
    assert api_session_module.DevResetResult is not None


def test_recruitment_module_does_not_import_integrations_api() -> None:
    root = Path(__file__).resolve().parents[2] / "modules" / "recruitment"
    forbidden = "integrations.api"
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert forbidden not in alias.name, f"{path.name} imports {alias.name}"
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert forbidden not in node.module, f"{path.name} imports from {node.module}"


def test_governance_payload_not_merged_with_bootstrap_fields() -> None:
    with TestClient(create_app(db_path="")) as client:
        rt = client.app.state.vertical_slice
        payload = {
            "actor_id": "boundary-test",
            "actor_type": "recruiter",
            "reason": "governance boundary test",
            "evidence_refs": ["artifact://test/boundary"],
        }
        result = record_recruiter_decision(
            rt,
            VERTICAL_SLICE_DEFAULT_CANDIDATE_ID,
            "recruiter_schedule_interview",
            payload,
        )
        assert result.ingress_accepted is True
        bus = rt.bundle.bus
        last = bus.recorded_envelopes[-1]
        pl = last.payload
        assert pl.get("bootstrap") is not True
        assert "api_sequence" not in pl
        assert pl["actor_id"] == "boundary-test"


@pytest.mark.parametrize("event_type", list(GOVERNANCE_EVENT_TYPES[:3]))
def test_is_governance_event(event_type: str) -> None:
    assert policies.is_governance_event(event_type)


def test_invalid_candidate_id_via_api_404(client: TestClient) -> None:
    r = client.get(f"/candidate/{uuid4()}")
    assert r.status_code == 404


def test_allowed_ingress_matches_policies_allowlist() -> None:
    assert tuple(policies.ALLOWED_INGRESS_EVENT_TYPES) == VERTICAL_SLICE_INGRESS_EVENT_TYPES
    assert policies.allowed_ingress_event_types() == VERTICAL_SLICE_INGRESS_EVENT_TYPES
    assert recruitment_bootstrap.VERTICAL_SLICE_INGRESS_EVENT_TYPES == VERTICAL_SLICE_INGRESS_EVENT_TYPES
    assert callable(merge_demo_profile_into_skill_payload)
    assert TESTING_DESKTOP_CANDIDATE_ID is not None


def _module_imports_bootstrap(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module in (".bootstrap", "modules.recruitment.bootstrap"):
                return True
            if node.module.endswith(".bootstrap"):
                return True
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in ("modules.recruitment.bootstrap",):
                    return True
    return "from .bootstrap" in text or "from modules.recruitment.bootstrap" in text


def test_bootstrap_docstring_declares_minimal_role() -> None:
    text = Path(__file__).resolve().parents[2] / "modules" / "recruitment" / "bootstrap.py"
    body = text.read_text(encoding="utf-8")
    assert "**Allowed**" in body
    assert "**Forbidden**" in body
    assert "Import rule:" in body


def test_recruitment_layers_do_not_import_bootstrap() -> None:
    root = Path(__file__).resolve().parents[2] / "modules" / "recruitment"
    for name in ("use_cases.py", "projection.py", "policies.py"):
        assert not _module_imports_bootstrap(root / name), f"{name} must not import bootstrap"
    inspection = root / "inspection"
    for path in inspection.rglob("*.py"):
        assert not _module_imports_bootstrap(path), f"{path.relative_to(root)} must not import bootstrap"


def test_inspection_catalog_is_merge_only() -> None:
    path = Path(__file__).resolve().parents[2] / "modules" / "recruitment" / "inspection" / "catalog.py"
    text = path.read_text(encoding="utf-8")
    assert "from ..policies" not in text
    assert "from ..ranking" not in text
    assert "PRIMARY_VERTICAL_SLICE_EVENT_TYPES" not in text
    assert "build_ingress_envelope" not in text
    assert "resolve_vertical_slice_inspection_catalog" in text


def test_bootstrap_imported_only_by_runtime_api_and_shims() -> None:
    root = Path(__file__).resolve().parents[2]
    allowed_files = {
        root / "modules" / "recruitment" / "bootstrap.py",
        root / "modules" / "recruitment" / "runtime.py",
        root / "runtime" / "bootstrap_vertical_slice.py",
        root / "tests" / "modules" / "test_recruitment_boundary.py",
    }
    allowed_prefixes = (root / "integrations" / "api",)
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        if path in allowed_files:
            continue
        if any(str(path).startswith(str(prefix)) for prefix in allowed_prefixes):
            continue
        if _module_imports_bootstrap(path):
            offenders.append(str(path.relative_to(root)))
    assert offenders == [], f"unexpected bootstrap imports: {offenders}"


def test_submit_cv_publishes_cv_submitted(establish_ready_scoring_context) -> None:
    rt = VerticalSliceApiRuntime()
    establish_ready_scoring_context(rt)
    cid = uuid4()
    publish_recruitment_event(rt, cid, "candidate_created", {})
    result = submit_cv(rt, cid, "Python developer\n5 years experience\npython django")
    assert result.ingress_accepted is True
    assert result.event_type == "cv_submitted"


def test_api_lifespan_initializes_runtime_and_demo_run(client: TestClient) -> None:
    rt = client.app.state.vertical_slice
    assert isinstance(rt, VerticalSliceApiRuntime)
    assert client.get("/health").status_code == 200
    assert client.post("/demo/run").status_code == 200


def test_admin_reset_restores_new_phase(client: TestClient) -> None:
    assert client.post("/demo/run").status_code == 200
    reset = client.post("/admin/reset")
    assert reset.status_code == 200
    body = reset.json()
    assert body["pipeline_phase"] == "new"
    assert body["status"] == "ok"


def test_non_governance_merge_adds_api_sequence() -> None:
    merged = policies.merge_non_governance_publish_payload(
        {"bootstrap": True, "sequence": 1},
        {"extra": "field"},
        seq=7,
    )
    assert merged["api_sequence"] == 7
    assert merged["extra"] == "field"
    assert merged["bootstrap"] is True
