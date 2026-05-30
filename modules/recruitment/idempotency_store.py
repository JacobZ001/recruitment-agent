"""
HTTP idempotency persistence for bounded ingress (R-012: POST /candidates/cv/pdf only).
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional


IDEMPOTENCY_METHOD_PATH = "POST:/candidates/cv/pdf"
IDEMPOTENCY_TTL = timedelta(hours=24)


class IdempotencyRecordStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    SUCCEEDED = "succeeded"


@dataclass(frozen=True)
class IdempotencyRecord:
    method_path: str
    idempotency_key: str
    status: IdempotencyRecordStatus
    payload_fingerprint: str
    candidate_id: Optional[str]
    response_status_code: Optional[int]
    response_body_json: Optional[str]
    created_at: datetime


class InMemoryIdempotencyStore:
    def __init__(self) -> None:
        self._rows: Dict[tuple[str, str], IdempotencyRecord] = {}
        self._lock = threading.Lock()

    def purge_expired(self, *, now: Optional[datetime] = None) -> int:
        cutoff = (now or datetime.now(timezone.utc)) - IDEMPOTENCY_TTL
        removed = 0
        with self._lock:
            stale = [k for k, r in self._rows.items() if r.created_at < cutoff]
            for k in stale:
                del self._rows[k]
                removed += 1
        return removed

    def get(self, method_path: str, idempotency_key: str) -> Optional[IdempotencyRecord]:
        with self._lock:
            row = self._rows.get((method_path, idempotency_key))
            return row

    def upsert_in_progress(
        self,
        *,
        method_path: str,
        idempotency_key: str,
        payload_fingerprint: str,
        candidate_id: str,
        created_at: Optional[datetime] = None,
    ) -> IdempotencyRecord:
        ts = created_at or datetime.now(timezone.utc)
        record = IdempotencyRecord(
            method_path=method_path,
            idempotency_key=idempotency_key,
            status=IdempotencyRecordStatus.IN_PROGRESS,
            payload_fingerprint=payload_fingerprint,
            candidate_id=candidate_id,
            response_status_code=None,
            response_body_json=None,
            created_at=ts,
        )
        with self._lock:
            self._rows[(method_path, idempotency_key)] = record
        return record

    def mark_succeeded(
        self,
        *,
        method_path: str,
        idempotency_key: str,
        response_status_code: int,
        response_body: Dict[str, Any],
    ) -> IdempotencyRecord:
        with self._lock:
            prev = self._rows.get((method_path, idempotency_key))
            if prev is None:
                raise KeyError(f"idempotency record missing: {idempotency_key!r}")
            record = IdempotencyRecord(
                method_path=method_path,
                idempotency_key=idempotency_key,
                status=IdempotencyRecordStatus.SUCCEEDED,
                payload_fingerprint=prev.payload_fingerprint,
                candidate_id=prev.candidate_id,
                response_status_code=response_status_code,
                response_body_json=json.dumps(response_body, separators=(",", ":"), sort_keys=True),
                created_at=prev.created_at,
            )
            self._rows[(method_path, idempotency_key)] = record
        return record

    def clear_all(self) -> None:
        with self._lock:
            self._rows.clear()


class SQLiteIdempotencyStore:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ingress_idempotency (
                method_path TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                status TEXT NOT NULL,
                payload_fingerprint TEXT NOT NULL,
                candidate_id TEXT,
                response_status_code INTEGER,
                response_body_json TEXT,
                created_at TEXT NOT NULL,
                PRIMARY KEY (method_path, idempotency_key)
            )
            """
        )
        self._conn.commit()
        self._lock = threading.Lock()

    def close(self) -> None:
        self._conn.close()

    def purge_expired(self, *, now: Optional[datetime] = None) -> int:
        cutoff = (now or datetime.now(timezone.utc)) - IDEMPOTENCY_TTL
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM ingress_idempotency WHERE created_at < ?",
                (cutoff.isoformat(),),
            )
            self._conn.commit()
            return int(cur.rowcount)

    def get(self, method_path: str, idempotency_key: str) -> Optional[IdempotencyRecord]:
        row = self._conn.execute(
            """
            SELECT status, payload_fingerprint, candidate_id, response_status_code,
                   response_body_json, created_at
            FROM ingress_idempotency
            WHERE method_path = ? AND idempotency_key = ?
            """,
            (method_path, idempotency_key),
        ).fetchone()
        if row is None:
            return None
        status_s, fingerprint, candidate_id, status_code, body_json, created_s = row
        return IdempotencyRecord(
            method_path=method_path,
            idempotency_key=idempotency_key,
            status=IdempotencyRecordStatus(status_s),
            payload_fingerprint=fingerprint,
            candidate_id=candidate_id,
            response_status_code=status_code,
            response_body_json=body_json,
            created_at=datetime.fromisoformat(created_s),
        )

    def upsert_in_progress(
        self,
        *,
        method_path: str,
        idempotency_key: str,
        payload_fingerprint: str,
        candidate_id: str,
        created_at: Optional[datetime] = None,
    ) -> IdempotencyRecord:
        ts = created_at or datetime.now(timezone.utc)
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO ingress_idempotency (
                    method_path, idempotency_key, status, payload_fingerprint,
                    candidate_id, response_status_code, response_body_json, created_at
                ) VALUES (?, ?, ?, ?, ?, NULL, NULL, ?)
                ON CONFLICT(method_path, idempotency_key) DO UPDATE SET
                    status = excluded.status,
                    payload_fingerprint = excluded.payload_fingerprint,
                    candidate_id = excluded.candidate_id,
                    response_status_code = NULL,
                    response_body_json = NULL,
                    created_at = excluded.created_at
                """,
                (
                    method_path,
                    idempotency_key,
                    IdempotencyRecordStatus.IN_PROGRESS.value,
                    payload_fingerprint,
                    candidate_id,
                    ts.isoformat(),
                ),
            )
            self._conn.commit()
        return self.get(method_path, idempotency_key)  # type: ignore[return-value]

    def mark_succeeded(
        self,
        *,
        method_path: str,
        idempotency_key: str,
        response_status_code: int,
        response_body: Dict[str, Any],
    ) -> IdempotencyRecord:
        body_json = json.dumps(response_body, separators=(",", ":"), sort_keys=True)
        with self._lock:
            self._conn.execute(
                """
                UPDATE ingress_idempotency
                SET status = ?, response_status_code = ?, response_body_json = ?
                WHERE method_path = ? AND idempotency_key = ?
                """,
                (
                    IdempotencyRecordStatus.SUCCEEDED.value,
                    response_status_code,
                    body_json,
                    method_path,
                    idempotency_key,
                ),
            )
            self._conn.commit()
        got = self.get(method_path, idempotency_key)
        if got is None:
            raise KeyError(f"idempotency record missing after succeed: {idempotency_key!r}")
        return got

    def clear_all(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM ingress_idempotency")
            self._conn.commit()
