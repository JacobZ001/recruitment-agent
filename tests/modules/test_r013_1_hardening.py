"""R-013.1 corrective minor: dedup governance hardening."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from modules.recruitment.dedup import (
    DedupIngressSignals,
    DedupOutcome,
    evaluate_dedup_from_ingress_signals,
    normalize_email,
)
from modules.recruitment.idempotency_store import (
    IDEMPOTENCY_METHOD_PATH,
    IdempotencyRecord,
    IdempotencyRecordStatus,
    InMemoryIdempotencyStore,
)
from modules.recruitment.ingress_governance import (
    ORPHAN_INGRESS_STALE_SECONDS,
    ingress_governance_by_candidate_id,
)
from modules.recruitment.use_cases import _dedup_audit_entry, link_candidate_dedup
from modules.recruitment.runtime import VerticalSliceApiRuntime
from runtime.persistence.in_memory_candidate_store import InMemoryCandidateStore
from schemas.candidate_schema import DedupSignals, Identity, new_candidate


def test_dedup_audit_uses_real_utc_clock() -> None:
    fixed_demo = "2026-05-12T14:00:00+00:00"
    e1 = _dedup_audit_entry(action="link", actor_id="r1", reason="first")
    time.sleep(0.02)
    e2 = _dedup_audit_entry(action="link", actor_id="r1", reason="second")
    assert e1["recorded_at"] != fixed_demo
    assert e2["recorded_at"] != fixed_demo
    assert e1["recorded_at"] != e2["recorded_at"]


def test_ingress_in_progress_vs_orphan_mutually_exclusive() -> None:
    now = datetime.now(timezone.utc)
    fresh_cid = uuid4()
    stale_cid = uuid4()
    fresh = IdempotencyRecord(
        method_path=IDEMPOTENCY_METHOD_PATH,
        idempotency_key="fresh-key",
        status=IdempotencyRecordStatus.IN_PROGRESS,
        payload_fingerprint="fp1",
        candidate_id=str(fresh_cid),
        response_status_code=None,
        response_body_json=None,
        created_at=now - timedelta(seconds=120),
    )
    stale = IdempotencyRecord(
        method_path=IDEMPOTENCY_METHOD_PATH,
        idempotency_key="stale-key",
        status=IdempotencyRecordStatus.IN_PROGRESS,
        payload_fingerprint="fp2",
        candidate_id=str(stale_cid),
        response_status_code=None,
        response_body_json=None,
        created_at=now - timedelta(seconds=ORPHAN_INGRESS_STALE_SECONDS + 60),
    )
    flags = ingress_governance_by_candidate_id(
        [fresh, stale],
        now=now,
        stale_seconds=ORPHAN_INGRESS_STALE_SECONDS,
    )
    assert flags[fresh_cid].ingress_in_progress is True
    assert flags[fresh_cid].orphan_ingress is False
    assert flags[stale_cid].ingress_in_progress is False
    assert flags[stale_cid].orphan_ingress is True


def test_link_audit_recorded_at_not_demo_fixed_clock() -> None:
    rt = VerticalSliceApiRuntime()
    cid_a = uuid4()
    cid_b = uuid4()
    from modules.recruitment.use_cases import ensure_candidate_record
    from modules.recruitment.ingress import FIXED_CLOCK

    ensure_candidate_record(rt.candidate_store, cid_a, occurred_at=FIXED_CLOCK)
    ensure_candidate_record(rt.candidate_store, cid_b, occurred_at=FIXED_CLOCK)
    flags = link_candidate_dedup(
        rt,
        cid_a,
        cid_b,
        actor_id="tester",
        reason="same person",
    )
    assert flags.get("dedup_status") == "linked"
    got = rt.candidate_store.get(cid_a)
    assert got.ok and got.candidate is not None
    audit = (got.candidate.extensions.get("dedup") or {}).get("audit") or []
    assert audit
    assert audit[-1]["recorded_at"] != FIXED_CLOCK.isoformat()


def test_indexed_dedup_matches_prior_semantics() -> None:
    store = InMemoryCandidateStore()
    cid = uuid4()
    cand = new_candidate(cid)
    cand = cand.model_copy(
        update={
            "identity": Identity(primary_email="sam@hire.test"),
            "dedup_signals": DedupSignals(normalized_email=normalize_email("sam@hire.test")),
        }
    )
    store.create(cand)
    sig = DedupIngressSignals(
        normalized_email="sam@hire.test",
        normalized_phone=None,
        cv_content_fingerprint=None,
    )
    ev = evaluate_dedup_from_ingress_signals(store, sig)
    assert ev.outcome == DedupOutcome.HIGH_CONFIDENCE_DUPLICATE


def test_sqlite_dedup_email_index_lookup(tmp_path) -> None:
    from runtime.persistence.sqlite_candidate_store import SQLiteCandidateStore

    db = tmp_path / "candidates.db"
    store = SQLiteCandidateStore(str(db))
    cid = uuid4()
    cand = new_candidate(cid)
    cand = cand.model_copy(
        update={"dedup_signals": DedupSignals(normalized_email="indexed@hire.test")}
    )
    store.create(cand)
    found = store.find_candidate_ids_by_normalized_email("indexed@hire.test")
    assert found == [cid]
