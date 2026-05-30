"""SQLite-backed canonical Candidate aggregate store (R-009)."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import List, Optional, Sequence
from uuid import UUID

from schemas.candidate_schema import Candidate

from runtime.persistence.candidate_store_dedup import dedup_index_triple, filter_excluded


def _schema_sql() -> str:
    p = Path(__file__).resolve().parent / "sqlite_candidate_schema.sql"
    return p.read_text(encoding="utf-8")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CandidateStoreFailureCode(str, Enum):
    NOT_FOUND = "not_found"
    ALREADY_EXISTS = "already_exists"
    REVISION_MISMATCH = "revision_mismatch"
    VALIDATION_ERROR = "validation_error"


@dataclass(frozen=True)
class CandidateStoreFailure:
    code: CandidateStoreFailureCode
    message: str


@dataclass
class CandidateStoreMeta:
    store_revision: int
    created_at: str
    updated_at: str


@dataclass
class CandidateStoreResult:
    ok: bool
    candidate: Optional[Candidate] = None
    meta: Optional[CandidateStoreMeta] = None
    failure: Optional[CandidateStoreFailure] = None


class SQLiteCandidateStore:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_schema_sql())
        self._migrate_dedup_columns()
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def _migrate_dedup_columns(self) -> None:
        cur = self._conn.execute("PRAGMA table_info(candidate)")
        cols = {row[1] for row in cur.fetchall()}
        if "dedup_email" not in cols:
            self._conn.execute("ALTER TABLE candidate ADD COLUMN dedup_email TEXT")
        if "dedup_phone" not in cols:
            self._conn.execute("ALTER TABLE candidate ADD COLUMN dedup_phone TEXT")
        if "dedup_cv_fingerprint" not in cols:
            self._conn.execute("ALTER TABLE candidate ADD COLUMN dedup_cv_fingerprint TEXT")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_candidate_dedup_email ON candidate(dedup_email)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_candidate_dedup_phone ON candidate(dedup_phone)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_candidate_dedup_cv_fingerprint "
            "ON candidate(dedup_cv_fingerprint)"
        )
        self._backfill_dedup_columns()

    def _backfill_dedup_columns(self) -> None:
        cur = self._conn.execute(
            "SELECT candidate_id, candidate_json FROM candidate "
            "WHERE dedup_email IS NULL AND dedup_phone IS NULL AND dedup_cv_fingerprint IS NULL"
        )
        rows = cur.fetchall()
        for cid, payload in rows:
            try:
                cand = Candidate.model_validate_json(payload)
            except Exception:
                continue
            email, phone, fp = dedup_index_triple(cand)
            self._conn.execute(
                """
                UPDATE candidate
                SET dedup_email = ?, dedup_phone = ?, dedup_cv_fingerprint = ?
                WHERE candidate_id = ?
                """,
                (email, phone, fp, cid),
            )

    def get(self, candidate_id: UUID) -> CandidateStoreResult:
        cur = self._conn.execute(
            "SELECT candidate_json, store_revision, created_at, updated_at FROM candidate WHERE candidate_id = ?",
            (str(candidate_id),),
        )
        row = cur.fetchone()
        if row is None:
            return CandidateStoreResult(
                ok=False,
                failure=CandidateStoreFailure(
                    code=CandidateStoreFailureCode.NOT_FOUND,
                    message="candidate not found",
                ),
            )
        try:
            cand = Candidate.model_validate_json(row[0])
        except Exception as exc:
            return CandidateStoreResult(
                ok=False,
                failure=CandidateStoreFailure(
                    code=CandidateStoreFailureCode.VALIDATION_ERROR,
                    message=str(exc),
                ),
            )
        return CandidateStoreResult(
            ok=True,
            candidate=cand,
            meta=CandidateStoreMeta(
                store_revision=int(row[1]),
                created_at=str(row[2]),
                updated_at=str(row[3]),
            ),
        )

    def create(self, candidate: Candidate) -> CandidateStoreResult:
        cid = str(candidate.candidate_id)
        if self._exists(cid):
            return CandidateStoreResult(
                ok=False,
                failure=CandidateStoreFailure(
                    code=CandidateStoreFailureCode.ALREADY_EXISTS,
                    message="candidate already exists",
                ),
            )
        now = _utc_now_iso()
        payload = candidate.model_dump_json()
        email, phone, fp = dedup_index_triple(candidate)
        self._conn.execute(
            """
            INSERT INTO candidate (
                candidate_id, candidate_json, store_revision, created_at, updated_at,
                dedup_email, dedup_phone, dedup_cv_fingerprint
            )
            VALUES (?, ?, 1, ?, ?, ?, ?, ?)
            """,
            (cid, payload, now, now, email, phone, fp),
        )
        self._conn.commit()
        return CandidateStoreResult(
            ok=True,
            candidate=candidate,
            meta=CandidateStoreMeta(store_revision=1, created_at=now, updated_at=now),
        )

    def replace(
        self,
        candidate: Candidate,
        *,
        expected_store_revision: int,
    ) -> CandidateStoreResult:
        cid = str(candidate.candidate_id)
        cur = self._conn.execute(
            "SELECT store_revision FROM candidate WHERE candidate_id = ?",
            (cid,),
        )
        row = cur.fetchone()
        if row is None:
            return CandidateStoreResult(
                ok=False,
                failure=CandidateStoreFailure(
                    code=CandidateStoreFailureCode.NOT_FOUND,
                    message="candidate not found",
                ),
            )
        current_rev = int(row[0])
        if current_rev != expected_store_revision:
            return CandidateStoreResult(
                ok=False,
                failure=CandidateStoreFailure(
                    code=CandidateStoreFailureCode.REVISION_MISMATCH,
                    message=f"expected revision {expected_store_revision}, got {current_rev}",
                ),
            )
        now = _utc_now_iso()
        next_rev = current_rev + 1
        payload = candidate.model_dump_json()
        email, phone, fp = dedup_index_triple(candidate)
        self._conn.execute(
            """
            UPDATE candidate SET
                candidate_json = ?, store_revision = ?, updated_at = ?,
                dedup_email = ?, dedup_phone = ?, dedup_cv_fingerprint = ?
            WHERE candidate_id = ?
            """,
            (payload, next_rev, now, email, phone, fp, cid),
        )
        self._conn.commit()
        got = self.get(candidate.candidate_id)
        return got

    def list_candidate_ids(self) -> List[UUID]:
        cur = self._conn.execute("SELECT candidate_id FROM candidate ORDER BY candidate_id")
        return [UUID(row[0]) for row in cur.fetchall()]

    def find_candidate_ids_by_normalized_email(
        self,
        email: str,
        *,
        exclude_candidate_ids: Optional[Sequence[UUID]] = None,
    ) -> List[UUID]:
        cur = self._conn.execute(
            "SELECT candidate_id FROM candidate WHERE dedup_email = ?",
            (email,),
        )
        ids = [UUID(row[0]) for row in cur.fetchall()]
        return filter_excluded(ids, exclude_candidate_ids=exclude_candidate_ids)

    def find_candidate_ids_by_normalized_phone(
        self,
        phone: str,
        *,
        exclude_candidate_ids: Optional[Sequence[UUID]] = None,
    ) -> List[UUID]:
        cur = self._conn.execute(
            "SELECT candidate_id FROM candidate WHERE dedup_phone = ?",
            (phone,),
        )
        ids = [UUID(row[0]) for row in cur.fetchall()]
        return filter_excluded(ids, exclude_candidate_ids=exclude_candidate_ids)

    def find_candidate_ids_by_cv_fingerprint(
        self,
        fingerprint: str,
        *,
        exclude_candidate_ids: Optional[Sequence[UUID]] = None,
    ) -> List[UUID]:
        cur = self._conn.execute(
            "SELECT candidate_id FROM candidate WHERE dedup_cv_fingerprint = ?",
            (fingerprint,),
        )
        ids = [UUID(row[0]) for row in cur.fetchall()]
        return filter_excluded(ids, exclude_candidate_ids=exclude_candidate_ids)

    def clear_all(self) -> None:
        self._conn.execute("DELETE FROM candidate")
        self._conn.commit()

    def _exists(self, candidate_id: str) -> bool:
        cur = self._conn.execute(
            "SELECT 1 FROM candidate WHERE candidate_id = ? LIMIT 1",
            (candidate_id,),
        )
        return cur.fetchone() is not None
