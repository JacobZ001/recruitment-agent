"""API governance flags: ingress_in_progress vs orphan (R-013.1)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from integrations.api.app import create_app
from modules.recruitment.idempotency_store import IDEMPOTENCY_METHOD_PATH, InMemoryIdempotencyStore
from modules.recruitment.ingress import FIXED_CLOCK
from modules.recruitment.ingress_governance import ORPHAN_INGRESS_STALE_SECONDS
from modules.recruitment.state_init import initial_orchestration_state
from modules.recruitment.use_cases import ensure_candidate_record


@pytest.fixture
def client() -> TestClient:
    with TestClient(create_app(db_path="")) as c:
        yield c


def _seed_list_row(rt, cid) -> None:
    ensure_candidate_record(rt.candidate_store, cid, occurred_at=FIXED_CLOCK)
    snap = initial_orchestration_state(
        state_id=uuid4(), candidate_id=cid, occurred_at=FIXED_CLOCK
    )
    got = rt.bundle.store.create(snap)
    assert got.ok


def test_list_flags_fresh_in_progress_not_orphan(client: TestClient) -> None:
    rt = client.app.state.vertical_slice
    cid = uuid4()
    _seed_list_row(rt, cid)
    assert isinstance(rt.idempotency_store, InMemoryIdempotencyStore)
    rt.idempotency_store.upsert_in_progress(
        method_path=IDEMPOTENCY_METHOD_PATH,
        idempotency_key="gov-fresh",
        payload_fingerprint="fp",
        candidate_id=str(cid),
        created_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    resp = client.get("/candidates")
    assert resp.status_code == 200
    row = next(r for r in resp.json() if r["candidate_id"] == str(cid))
    flags = row["governance_flags"]
    assert flags["ingress_in_progress"] is True
    assert flags["orphan_ingress"] is False


def test_list_flags_stale_in_progress_is_orphan(client: TestClient) -> None:
    rt = client.app.state.vertical_slice
    cid = uuid4()
    _seed_list_row(rt, cid)
    assert isinstance(rt.idempotency_store, InMemoryIdempotencyStore)
    rt.idempotency_store.upsert_in_progress(
        method_path=IDEMPOTENCY_METHOD_PATH,
        idempotency_key="gov-stale",
        payload_fingerprint="fp",
        candidate_id=str(cid),
        created_at=datetime.now(timezone.utc)
        - timedelta(seconds=ORPHAN_INGRESS_STALE_SECONDS + 120),
    )
    resp = client.get("/candidates")
    assert resp.status_code == 200
    row = next(r for r in resp.json() if r["candidate_id"] == str(cid))
    flags = row["governance_flags"]
    assert flags["ingress_in_progress"] is False
    assert flags["orphan_ingress"] is True
