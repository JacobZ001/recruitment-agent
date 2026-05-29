"""In-memory canonical Candidate store for tests and ephemeral runtimes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from schemas.candidate_schema import Candidate

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
        _, rev, created, _ = row
        if rev != expected_store_revision:
            return CandidateStoreResult(
                ok=False,
                failure=CandidateStoreFailure(
                    code=CandidateStoreFailureCode.REVISION_MISMATCH,
                    message=f"expected revision {expected_store_revision}, got {rev}",
                ),
            )
        now = _utc_now_iso()
        self._rows[cid] = (candidate.model_copy(deep=True), rev + 1, created, now)
        return self.get(candidate.candidate_id)

    def list_candidate_ids(self) -> List[UUID]:
        return [UUID(k) for k in sorted(self._rows.keys())]

    def clear_all(self) -> None:
        self._rows.clear()
