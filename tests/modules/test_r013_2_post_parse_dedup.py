"""R-013.2 post-parse high-confidence dedup and SQLite cutover."""

from __future__ import annotations

from uuid import uuid4

from modules.recruitment.dedup import (
    DedupIngressSignals,
    DedupMatch,
    DedupOutcome,
    merge_dedup_matches,
    normalize_email,
)
from modules.recruitment.use_cases import (
    _evaluate_post_parse_high_confidence_dedup,
    _mark_candidate_post_ingress_duplicate,
)
from runtime.persistence.in_memory_candidate_store import InMemoryCandidateStore
from runtime.persistence.sqlite_candidate_store import SQLiteCandidateStore
from schemas.candidate_schema import DedupSignals, Identity, new_candidate
from modules.recruitment.dedup import evaluate_dedup_high_confidence_from_ingress_signals


def _seed_indexed_email(store: InMemoryCandidateStore, email: str):
    cid = uuid4()
    cand = new_candidate(cid)
    cand = cand.model_copy(
        update={
            "identity": Identity(primary_email=email, full_name="Existing"),
            "dedup_signals": DedupSignals(normalized_email=normalize_email(email)),
        }
    )
    store.create(cand)
    return cid


def test_sqlite_store_has_no_runtime_dedup_migration() -> None:
    assert not hasattr(SQLiteCandidateStore, "_migrate_dedup_columns")
    assert not hasattr(SQLiteCandidateStore, "_backfill_dedup_columns")


def test_post_parse_marks_post_ingress_duplicate() -> None:
    store = InMemoryCandidateStore()
    existing = _seed_indexed_email(store, "post.parse@hire.test")
    new_id = uuid4()
    cand = new_candidate(new_id)
    cand = cand.model_copy(
        update={
            "dedup_signals": DedupSignals(
                normalized_email=normalize_email("post.parse@hire.test"),
            ),
        }
    )
    store.create(cand)
    ev = _evaluate_post_parse_high_confidence_dedup(
        _FakeRuntime(store), new_id
    )
    assert ev is not None
    assert ev.outcome == DedupOutcome.HIGH_CONFIDENCE_DUPLICATE
    rt = _FakeRuntime(store)
    _mark_candidate_post_ingress_duplicate(rt, new_id, ev)
    got = store.get(new_id)
    assert got.ok and got.candidate is not None
    dedup = got.candidate.extensions["dedup"]
    assert dedup["status"] == "post_ingress_duplicate"
    assert dedup["pending_resolution"] is True
    match_ids = {m["candidate_id"] for m in dedup["matches"]}
    assert str(existing) in match_ids


def test_post_parse_fills_gap_when_pre_create_had_no_email() -> None:
    store = InMemoryCandidateStore()
    existing = _seed_indexed_email(store, "gap.only@hire.test")
    new_id = uuid4()
    store.create(new_candidate(new_id))
    cand = store.get(new_id).candidate.model_copy(
        update={
            "dedup_signals": DedupSignals(
                normalized_email=normalize_email("gap.only@hire.test"),
            ),
        }
    )
    store.replace(cand, expected_store_revision=1)
    ev = _evaluate_post_parse_high_confidence_dedup(_FakeRuntime(store), new_id)
    assert ev is not None and ev.outcome == DedupOutcome.HIGH_CONFIDENCE_DUPLICATE
    _mark_candidate_post_ingress_duplicate(_FakeRuntime(store), new_id, ev)
    dedup = store.get(new_id).candidate.extensions["dedup"]
    assert dedup["status"] == "post_ingress_duplicate"
    assert str(existing) in {m["candidate_id"] for m in dedup["matches"]}


def test_suspected_plus_post_parse_merges_matches() -> None:
    store = InMemoryCandidateStore()
    email_id = _seed_indexed_email(store, "merge@hire.test")
    fp_id = uuid4()
    fp = "deadbeef" * 8
    cand_fp = new_candidate(fp_id)
    cand_fp = cand_fp.model_copy(
        update={"dedup_signals": DedupSignals(cv_content_fingerprint=fp)}
    )
    store.create(cand_fp)
    new_id = uuid4()
    store.create(new_candidate(new_id))
    cand = store.get(new_id).candidate.model_copy(
        update={
            "dedup_signals": DedupSignals(
                normalized_email=normalize_email("merge@hire.test"),
                cv_content_fingerprint=fp,
            ),
        }
    )
    store.replace(cand, expected_store_revision=1)
    from modules.recruitment.dedup import evaluate_dedup_fingerprint_suspected_from_ingress_signals

    rt = _FakeRuntime(store)
    suspected = evaluate_dedup_fingerprint_suspected_from_ingress_signals(
        store,
        DedupIngressSignals(None, None, fp),
        exclude_candidate_ids=[new_id],
    )
    post = _evaluate_post_parse_high_confidence_dedup(rt, new_id)
    assert post is not None and post.outcome == DedupOutcome.HIGH_CONFIDENCE_DUPLICATE
    _mark_candidate_post_ingress_duplicate(
        rt, new_id, post, extra_matches=suspected.matches
    )
    dedup = store.get(new_id).candidate.extensions["dedup"]
    assert dedup["status"] == "post_ingress_duplicate"
    by_cid = {m["candidate_id"]: set(m["match_kinds"]) for m in dedup["matches"]}
    assert "cv_content_fingerprint" in by_cid[str(fp_id)]
    assert "normalized_email" in by_cid[str(email_id)]


def test_post_parse_mark_is_idempotent() -> None:
    store = InMemoryCandidateStore()
    _seed_indexed_email(store, "idem@hire.test")
    new_id = uuid4()
    cand = new_candidate(new_id)
    cand = cand.model_copy(
        update={
            "dedup_signals": DedupSignals(
                normalized_email=normalize_email("idem@hire.test"),
            ),
        }
    )
    store.create(cand)
    rt = _FakeRuntime(store)
    ev = _evaluate_post_parse_high_confidence_dedup(rt, new_id)
    assert ev is not None
    _mark_candidate_post_ingress_duplicate(rt, new_id, ev)
    rev1 = store.get(new_id).meta.store_revision
    audit_len_1 = len(store.get(new_id).candidate.extensions["dedup"]["audit"])
    _mark_candidate_post_ingress_duplicate(rt, new_id, ev)
    rev2 = store.get(new_id).meta.store_revision
    audit_len_2 = len(store.get(new_id).candidate.extensions["dedup"]["audit"])
    assert rev1 == rev2
    assert audit_len_1 == audit_len_2


def test_merge_dedup_matches_unions_kinds() -> None:
    a = DedupMatch(uuid4(), ["normalized_email"], "A")
    b = DedupMatch(a.candidate_id, ["cv_content_fingerprint"], "A")
    merged = merge_dedup_matches([a], [b])
    assert len(merged) == 1
    assert set(merged[0].match_kinds) == {"normalized_email", "cv_content_fingerprint"}


class _FakeRuntime:
    def __init__(self, store: InMemoryCandidateStore) -> None:
        self.candidate_store = store
