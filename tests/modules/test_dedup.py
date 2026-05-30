"""Deterministic dedup evaluation (R-013)."""

from __future__ import annotations

from uuid import uuid4

from modules.recruitment.dedup import (
    DedupIngressSignals,
    DedupOutcome,
    evaluate_dedup,
    extract_ingress_signals_from_cv_text,
    normalize_email,
)
from runtime.persistence.in_memory_candidate_store import InMemoryCandidateStore
from schemas.candidate_schema import Candidate, DedupSignals, Identity, new_candidate


def test_extract_email_from_cv_text() -> None:
    sig = extract_ingress_signals_from_cv_text("Contact sam@hire.test for role")
    assert sig.normalized_email == "sam@hire.test"


def test_high_confidence_email_match() -> None:
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
    sig = extract_ingress_signals_from_cv_text("sam@hire.test\nPython engineer")
    ev = evaluate_dedup(store, sig)
    assert ev.outcome == DedupOutcome.HIGH_CONFIDENCE_DUPLICATE
    assert len(ev.matches) == 1


def test_fingerprint_only_is_suspected() -> None:
    store = InMemoryCandidateStore()
    cid = uuid4()
    fp = "abc123fingerprint"
    cand = new_candidate(cid)
    cand = cand.model_copy(update={"dedup_signals": DedupSignals(cv_content_fingerprint=fp)})
    store.create(cand)
    sig = DedupIngressSignals(
        normalized_email=None,
        normalized_phone=None,
        cv_content_fingerprint=fp,
    )
    ev = evaluate_dedup(store, sig)
    assert ev.outcome == DedupOutcome.SUSPECTED_FINGERPRINT
