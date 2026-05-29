"""R-009.1 candidate/snapshot consistency and fail-fast read paths."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from integrations.api.app import create_app
from modules.recruitment.candidate_sync import (
    evaluation_ref_lags_candidate,
    load_candidate_and_snapshot_for_read,
    persist_candidate_and_snapshot_with_reconcile,
)
from modules.recruitment.candidate_writes import ensure_candidate_record
from modules.recruitment.ingress import FIXED_CLOCK
from modules.recruitment.registry import get_state_id
from modules.recruitment.state_init import initial_orchestration_state
from modules.recruitment.projection import get_candidate_view_for_runtime
from modules.recruitment.runtime import VerticalSliceApiRuntime
from modules.recruitment.use_cases import list_candidates, publish_recruitment_event
from runtime.in_memory_state_store import (
    InMemoryStateStore,
    StateStoreFailure,
    StateStoreFailureCode,
    StateStoreResult,
)
from runtime.persistence.in_memory_candidate_store import InMemoryCandidateStore
from runtime.persistence.sqlite_candidate_store import (
    CandidateStoreFailure,
    CandidateStoreFailureCode,
    CandidateStoreResult,
)
from schemas.state_schema import OrchestrationState


@dataclass
class _FlakySnapshotReplaceStore:
    """Delegate to inner store; fail snapshot replace N times then succeed."""

    inner: InMemoryStateStore
    failures_remaining: int

    def get(self, state_id: UUID) -> Any:
        return self.inner.get(state_id)

    def get_for_candidate(self, candidate_id: UUID) -> Any:
        return self.inner.get_for_candidate(candidate_id)

    def replace(
        self,
        state_id: UUID,
        snapshot: OrchestrationState,
        *,
        expected_store_revision: int,
    ) -> StateStoreResult:
        if self.failures_remaining > 0:
            self.failures_remaining -= 1
            return StateStoreResult(
                ok=False,
                failure=StateStoreFailure(
                    code=StateStoreFailureCode.REVISION_MISMATCH,
                    message="simulated snapshot replace failure",
                ),
            )
        return self.inner.replace(state_id, snapshot, expected_store_revision=expected_store_revision)

    def list_all_state_ids(self) -> Any:
        return self.inner.list_all_state_ids()

    def create(self, *args: Any, **kwargs: Any) -> Any:
        return self.inner.create(*args, **kwargs)


def test_persist_dual_write_recovers_after_transient_snapshot_failure() -> None:
    inner = InMemoryStateStore()
    flaky = _FlakySnapshotReplaceStore(inner, failures_remaining=1)
    cand_store = InMemoryCandidateStore()
    cid = uuid4()
    sid = get_state_id(cid)
    snap0 = initial_orchestration_state(state_id=sid, candidate_id=cid, occurred_at=FIXED_CLOCK)
    flaky.create(snap0)
    got = flaky.get_for_candidate(cid)
    assert got.ok and got.snapshot is not None and got.meta is not None
    cand = ensure_candidate_record(cand_store, cid, occurred_at=FIXED_CLOCK)
    cand = cand.model_copy(update={"evaluation_revision": cand.evaluation_revision + 1})
    outcome = persist_candidate_and_snapshot_with_reconcile(
        candidate_store=cand_store,
        orchestration_store=flaky,
        state_id=got.meta.state_id,
        candidate_id=cid,
        workflow_snapshot=got.snapshot,
        candidate=cand,
        expected_snapshot_revision=got.meta.store_revision,
    )
    assert outcome.ok
    got2 = flaky.get_for_candidate(cid)
    assert got2.ok and got2.snapshot is not None
    ref = got2.snapshot.evaluation_status_ref
    assert ref is not None
    assert ref.revision == cand.evaluation_revision


def test_read_time_convergence_when_evaluation_ref_lags() -> None:
    rt = VerticalSliceApiRuntime()
    cid = uuid4()
    publish_recruitment_event(rt, cid, "candidate_created", {})
    got_c = rt.candidate_store.get(cid)
    assert got_c.ok and got_c.candidate is not None and got_c.meta is not None
    cand = got_c.candidate.model_copy(update={"evaluation_revision": got_c.candidate.evaluation_revision + 5})
    rt.candidate_store.replace(cand, expected_store_revision=got_c.meta.store_revision)
    got_s = rt.bundle.store.get_for_candidate(cid)
    assert got_s.ok and got_s.snapshot is not None
    assert evaluation_ref_lags_candidate(got_s.snapshot, cand)
    view = get_candidate_view_for_runtime(rt, cid)
    assert view["scores"]["overall_score"]["value"] is not None or view["stage"]
    got_s2 = rt.bundle.store.get_for_candidate(cid)
    assert got_s2.ok and got_s2.snapshot is not None
    ref = got_s2.snapshot.evaluation_status_ref
    assert ref is not None
    assert ref.revision == cand.evaluation_revision


def test_list_candidates_reflects_converged_score_ref() -> None:
    rt = VerticalSliceApiRuntime()
    cid = uuid4()
    publish_recruitment_event(rt, cid, "candidate_created", {})
    got_c = rt.candidate_store.get(cid)
    assert got_c.ok and got_c.candidate is not None and got_c.meta is not None
    cand = got_c.candidate.model_copy(update={"evaluation_revision": got_c.candidate.evaluation_revision + 3})
    rt.candidate_store.replace(cand, expected_store_revision=got_c.meta.store_revision)
    rows = list_candidates(rt)
    row = next(r for r in rows if r["candidate_id"] == str(cid))
    got_s = rt.bundle.store.get_for_candidate(cid)
    assert got_s.ok and got_s.snapshot is not None
    ref = got_s.snapshot.evaluation_status_ref
    assert ref is not None
    assert ref.revision == cand.evaluation_revision


@pytest.fixture
def client() -> TestClient:
    with TestClient(create_app(db_path="")) as c:
        yield c


def test_api_returns_503_when_candidate_store_unavailable(client: TestClient) -> None:
    rt = client.app.state.vertical_slice
    cid = rt.candidate_id

    def _broken_get(_: UUID) -> CandidateStoreResult:
        return CandidateStoreResult(
            ok=False,
            failure=CandidateStoreFailure(
                code=CandidateStoreFailureCode.VALIDATION_ERROR,
                message="simulated outage",
            ),
        )

    with patch.object(rt.candidate_store, "get", side_effect=_broken_get):
        r = client.get(f"/candidate/{cid}")
    assert r.status_code == 503
    body = r.json()
    assert body["detail"]["code"] == "candidate_store_unavailable"
    assert body["detail"]["diagnostic"] == "fail_fast_no_legacy_snapshot_fallback"


def test_load_candidate_and_snapshot_for_read_converges_ref() -> None:
    rt = VerticalSliceApiRuntime()
    cid = uuid4()
    publish_recruitment_event(rt, cid, "candidate_created", {})
    got_c = rt.candidate_store.get(cid)
    assert got_c.ok and got_c.candidate is not None and got_c.meta is not None
    cand = got_c.candidate.model_copy(update={"evaluation_revision": 99})
    rt.candidate_store.replace(cand, expected_store_revision=got_c.meta.store_revision)
    candidate, snapshot = load_candidate_and_snapshot_for_read(rt, cid)
    assert snapshot.evaluation_status_ref is not None
    assert snapshot.evaluation_status_ref.revision == candidate.evaluation_revision
