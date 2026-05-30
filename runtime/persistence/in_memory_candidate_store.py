"""In-memory canonical Candidate store for tests and ephemeral runtimes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Set, Tuple
from uuid import UUID

from schemas.candidate_schema import Candidate

from runtime.persistence.candidate_store_dedup import dedup_index_triple, filter_excluded
from runtime.persistence.sqlite_candidate_store import (
    CandidateStoreFailure,
    CandidateStoreFailureCode,
    CandidateStoreMeta,
    CandidateStoreResult,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class InMemoryCandidateStore:
    def __init__(self) -> None:
        self._rows: Dict[str, Tuple[Candidate, int, str, str]] = {}
        self._by_email: Dict[str, Set[str]] = {}
        self._by_phone: Dict[str, Set[str]] = {}
        self._by_fp: Dict[str, Set[str]] = {}

    def get(self, candidate_id: UUID) -> CandidateStoreResult:
        row = self._rows.get(str(candidate_id))
        if row is None:
            return CandidateStoreResult(
                ok=False,
                failure=CandidateStoreFailure(
                    code=CandidateStoreFailureCode.NOT_FOUND,
                    message="candidate not found",
                ),
            )
        cand, rev, created, updated = row
        return CandidateStoreResult(
            ok=True,
            candidate=cand.model_copy(deep=True),
            meta=CandidateStoreMeta(store_revision=rev, created_at=created, updated_at=updated),
        )

    def create(self, candidate: Candidate) -> CandidateStoreResult:
        cid = str(candidate.candidate_id)
        if cid in self._rows:
            return CandidateStoreResult(
                ok=False,
                failure=CandidateStoreFailure(
                    code=CandidateStoreFailureCode.ALREADY_EXISTS,
                    message="candidate already exists",
                ),
            )
        now = _utc_now_iso()
        self._rows[cid] = (candidate.model_copy(deep=True), 1, now, now)
        self._index_add(cid, candidate)
        return self.get(candidate.candidate_id)

    def replace(
        self,
        candidate: Candidate,
        *,
        expected_store_revision: int,
    ) -> CandidateStoreResult:
        cid = str(candidate.candidate_id)
        row = self._rows.get(cid)
        if row is None:
            return CandidateStoreResult(
                ok=False,
                failure=CandidateStoreFailure(
                    code=CandidateStoreFailureCode.NOT_FOUND,
                    message="candidate not found",
                ),
            )
        prev_cand, rev, created, _ = row
        if rev != expected_store_revision:
            return CandidateStoreResult(
                ok=False,
                failure=CandidateStoreFailure(
                    code=CandidateStoreFailureCode.REVISION_MISMATCH,
                    message=f"expected revision {expected_store_revision}, got {rev}",
                ),
            )
        self._index_remove(cid, prev_cand)
        now = _utc_now_iso()
        self._rows[cid] = (candidate.model_copy(deep=True), rev + 1, created, now)
        self._index_add(cid, candidate)
        return self.get(candidate.candidate_id)

    def list_candidate_ids(self) -> List[UUID]:
        return [UUID(k) for k in sorted(self._rows.keys())]

    def find_candidate_ids_by_normalized_email(
        self,
        email: str,
        *,
        exclude_candidate_ids: Optional[Sequence[UUID]] = None,
    ) -> List[UUID]:
        ids = [UUID(x) for x in sorted(self._by_email.get(email, ()))]
        return filter_excluded(ids, exclude_candidate_ids=exclude_candidate_ids)

    def find_candidate_ids_by_normalized_phone(
        self,
        phone: str,
        *,
        exclude_candidate_ids: Optional[Sequence[UUID]] = None,
    ) -> List[UUID]:
        ids = [UUID(x) for x in sorted(self._by_phone.get(phone, ()))]
        return filter_excluded(ids, exclude_candidate_ids=exclude_candidate_ids)

    def find_candidate_ids_by_cv_fingerprint(
        self,
        fingerprint: str,
        *,
        exclude_candidate_ids: Optional[Sequence[UUID]] = None,
    ) -> List[UUID]:
        ids = [UUID(x) for x in sorted(self._by_fp.get(fingerprint, ()))]
        return filter_excluded(ids, exclude_candidate_ids=exclude_candidate_ids)

    def clear_all(self) -> None:
        self._rows.clear()
        self._by_email.clear()
        self._by_phone.clear()
        self._by_fp.clear()

    def _index_add(self, cid: str, candidate: Candidate) -> None:
        email, phone, fp = dedup_index_triple(candidate)
        if email:
            self._by_email.setdefault(email, set()).add(cid)
        if phone:
            self._by_phone.setdefault(phone, set()).add(cid)
        if fp:
            self._by_fp.setdefault(fp, set()).add(cid)

    def _index_remove(self, cid: str, candidate: Candidate) -> None:
        email, phone, fp = dedup_index_triple(candidate)
        if email and email in self._by_email:
            self._by_email[email].discard(cid)
            if not self._by_email[email]:
                del self._by_email[email]
        if phone and phone in self._by_phone:
            self._by_phone[phone].discard(cid)
            if not self._by_phone[phone]:
                del self._by_phone[phone]
        if fp and fp in self._by_fp:
            self._by_fp[fp].discard(cid)
            if not self._by_fp[fp]:
                del self._by_fp[fp]
