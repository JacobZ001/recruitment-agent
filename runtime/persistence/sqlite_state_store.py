"""
SQLite implementation of the orchestration state snapshot store API.

Mirrors :class:`~runtime.in_memory_state_store.InMemoryStateStore` behavior and result
types; snapshot JSON is canonical—transition audit rows are a bounded convenience mirror.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, List, Optional
from uuid import UUID

from schemas.state_schema import OrchestrationState

from runtime.in_memory_state_store import (
    InMemoryStateStoreConfig,
    StateStoreFailure,
    StateStoreFailureCode,
    StateStoreResult,
    StateStoreSnapshotMeta,
    _candidate_ids_for_index,
    _state_deep_copy,
)


def _schema_sql() -> str:
    p = Path(__file__).resolve().parent / "sqlite_schema.sql"
    return p.read_text(encoding="utf-8")


def _iso(dt: Any) -> str:
    if hasattr(dt, "isoformat"):
        return dt.isoformat()
    return str(dt)


class SQLiteStateStore:
    """
    File-backed synchronous snapshot store (stdlib sqlite3 only).

    ``check_same_thread=False`` allows use under threaded servers (callers should still
    serialize if concurrent writes are possible).
    """

    def __init__(
        self,
        db_path: str,
        *,
        config: Optional[InMemoryStateStoreConfig] = None,
    ) -> None:
        self._db_path = db_path
        self._config = config or InMemoryStateStoreConfig()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_schema_sql())
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def _count_states(self) -> int:
        cur = self._conn.execute("SELECT COUNT(*) FROM orchestration_state")
        row = cur.fetchone()
        return int(row[0]) if row else 0

    def _persist_snapshot_and_indexes(
        self,
        *,
        state_id: UUID,
        snapshot: OrchestrationState,
        store_revision: int,
        created_at: str,
        updated_at: str,
    ) -> None:
        cids = _candidate_ids_for_index(snapshot)
        primary_cand = str(cids[0]) if cids else None
        payload = snapshot.model_dump_json()

        self._conn.execute("DELETE FROM orchestration_state_candidate WHERE state_id = ?", (str(state_id),))
        self._conn.execute("DELETE FROM state_transition_audit WHERE state_id = ?", (str(state_id),))

        self._conn.execute(
            """
            INSERT INTO orchestration_state (
                state_id, candidate_id, snapshot_json, created_at, updated_at, store_revision
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(state_id) DO UPDATE SET
                candidate_id = excluded.candidate_id,
                snapshot_json = excluded.snapshot_json,
                updated_at = excluded.updated_at,
                store_revision = excluded.store_revision
            """,
            (str(state_id), primary_cand, payload, created_at, updated_at, store_revision),
        )

        for cid in cids:
            self._conn.execute(
                "INSERT INTO orchestration_state_candidate (candidate_id, state_id) VALUES (?, ?)",
                (str(cid), str(state_id)),
            )

        for idx, tr in enumerate(snapshot.transitions):
            ex_raw = tr.extensions or {}
            ext_json = json.dumps(ex_raw, default=str) if ex_raw else None
            ev = str(tr.event_id) if tr.event_id else None
            atype = tr.actor.actor_type.value if tr.actor else None
            aid = tr.actor.actor_id if tr.actor else None
            self._conn.execute(
                """
                INSERT INTO state_transition_audit (
                    state_id, sequence_index, from_state, to_state, trigger,
                    event_id, actor_type, actor_id, extensions_json, recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(state_id),
                    idx,
                    tr.from_state,
                    tr.to_state,
                    tr.trigger,
                    ev,
                    atype,
                    aid,
                    ext_json,
                    _iso(tr.timestamp),
                ),
            )

    def exists(self, state_id: UUID) -> bool:
        cur = self._conn.execute(
            "SELECT 1 FROM orchestration_state WHERE state_id = ? LIMIT 1",
            (str(state_id),),
        )
        return cur.fetchone() is not None

    def has_candidate(self, candidate_id: UUID) -> bool:
        cur = self._conn.execute(
            "SELECT 1 FROM orchestration_state_candidate WHERE candidate_id = ? LIMIT 1",
            (str(candidate_id),),
        )
        return cur.fetchone() is not None

    def list_all_state_ids(self) -> List[UUID]:
        """Return all persisted orchestration state ids (deterministic sort order)."""
        cur = self._conn.execute(
            "SELECT state_id FROM orchestration_state ORDER BY state_id",
        )
        return [UUID(row[0]) for row in cur.fetchall()]

    def get(self, state_id: UUID, *, replay_run_id: Optional[UUID] = None) -> StateStoreResult:
        cur = self._conn.execute(
            "SELECT snapshot_json, store_revision FROM orchestration_state WHERE state_id = ?",
            (str(state_id),),
        )
        row = cur.fetchone()
        if row is None:
            return StateStoreResult(
                ok=False,
                failure=StateStoreFailure(
                    code=StateStoreFailureCode.NOT_FOUND,
                    message="No orchestration snapshot exists for the given state id",
                    details={"state_id": str(state_id)},
                ),
            )
        snap_json, rev = row
        raw = json.loads(snap_json)
        for legacy_key in ("links", "ingress_profile", "evaluation"):
            raw.pop(legacy_key, None)
        snap = OrchestrationState.model_validate(raw)
        now = self._config.clock()
        return StateStoreResult(
            ok=True,
            snapshot=_state_deep_copy(snap),
            meta=StateStoreSnapshotMeta(
                state_id=state_id,
                store_revision=int(rev),
                recorded_at=now,
                replay_run_id=replay_run_id,
            ),
        )

    def get_for_candidate(
        self, candidate_id: UUID, *, replay_run_id: Optional[UUID] = None
    ) -> StateStoreResult:
        cur = self._conn.execute(
            "SELECT state_id FROM orchestration_state_candidate WHERE candidate_id = ?",
            (str(candidate_id),),
        )
        row = cur.fetchone()
        if row is None:
            return StateStoreResult(
                ok=False,
                failure=StateStoreFailure(
                    code=StateStoreFailureCode.NOT_FOUND,
                    message="No orchestration snapshot is indexed for the given candidate id",
                    details={"candidate_id": str(candidate_id)},
                ),
            )
        return self.get(UUID(row[0]), replay_run_id=replay_run_id)

    def create(
        self,
        snapshot: OrchestrationState,
        *,
        replay_run_id: Optional[UUID] = None,
    ) -> StateStoreResult:
        sid = snapshot.id
        if self.exists(sid):
            return StateStoreResult(
                ok=False,
                failure=StateStoreFailure(
                    code=StateStoreFailureCode.ALREADY_EXISTS,
                    message="An orchestration snapshot already exists for this state id",
                    details={"state_id": str(sid)},
                ),
            )
        if self._count_states() >= self._config.limits.max_distinct_states:
            return StateStoreResult(
                ok=False,
                failure=StateStoreFailure(
                    code=StateStoreFailureCode.CAPACITY_EXCEEDED,
                    message="max_distinct_states reached",
                    details={"limit": self._config.limits.max_distinct_states},
                ),
            )

        frozen = _state_deep_copy(snapshot)
        now = self._config.clock()
        created = _iso(now)
        updated = created

        try:
            self._persist_snapshot_and_indexes(
                state_id=sid,
                snapshot=frozen,
                store_revision=1,
                created_at=created,
                updated_at=updated,
            )
            self._conn.commit()
        except Exception as exc:  # pragma: no cover - defensive
            self._conn.rollback()
            raise RuntimeError(f"sqlite create failed: {exc}") from exc

        now2 = self._config.clock()
        return StateStoreResult(
            ok=True,
            snapshot=_state_deep_copy(frozen),
            meta=StateStoreSnapshotMeta(
                state_id=sid,
                store_revision=1,
                recorded_at=now2,
                replay_run_id=replay_run_id,
            ),
        )

    def replace(
        self,
        state_id: UUID,
        snapshot: OrchestrationState,
        *,
        expected_store_revision: Optional[int] = None,
        replay_run_id: Optional[UUID] = None,
    ) -> StateStoreResult:
        if snapshot.id != state_id:
            return StateStoreResult(
                ok=False,
                failure=StateStoreFailure(
                    code=StateStoreFailureCode.STATE_ID_MISMATCH,
                    message="Snapshot id must match the state_id key",
                    details={"state_id": str(state_id), "snapshot_id": str(snapshot.id)},
                ),
            )

        cur = self._conn.execute(
            "SELECT store_revision, created_at FROM orchestration_state WHERE state_id = ?",
            (str(state_id),),
        )
        row = cur.fetchone()
        if row is None:
            return StateStoreResult(
                ok=False,
                failure=StateStoreFailure(
                    code=StateStoreFailureCode.NOT_FOUND,
                    message="Cannot replace: no existing snapshot for state id",
                    details={"state_id": str(state_id)},
                ),
            )

        rev = int(row[0])
        created_at_existing = row[1]

        if expected_store_revision is not None and expected_store_revision != rev:
            return StateStoreResult(
                ok=False,
                failure=StateStoreFailure(
                    code=StateStoreFailureCode.REVISION_MISMATCH,
                    message="Optimistic store revision mismatch",
                    details={
                        "state_id": str(state_id),
                        "expected": expected_store_revision,
                        "actual": rev,
                    },
                ),
            )

        new_rev = rev + 1
        frozen = _state_deep_copy(snapshot)
        now = self._config.clock()
        updated_at = _iso(now)

        try:
            self._conn.execute("DELETE FROM orchestration_state WHERE state_id = ?", (str(state_id),))
            self._persist_snapshot_and_indexes(
                state_id=state_id,
                snapshot=frozen,
                store_revision=new_rev,
                created_at=created_at_existing,
                updated_at=updated_at,
            )
            self._conn.commit()
        except Exception as exc:  # pragma: no cover
            self._conn.rollback()
            raise RuntimeError(f"sqlite replace failed: {exc}") from exc

        now2 = self._config.clock()
        return StateStoreResult(
            ok=True,
            snapshot=_state_deep_copy(frozen),
            meta=StateStoreSnapshotMeta(
                state_id=state_id,
                store_revision=new_rev,
                recorded_at=now2,
                replay_run_id=replay_run_id,
            ),
        )

    def audit_transition_count(self, state_id: UUID) -> int:
        """Test helper: rows in state_transition_audit for a state (non-authoritative)."""
        cur = self._conn.execute(
            "SELECT COUNT(*) FROM state_transition_audit WHERE state_id = ?",
            (str(state_id),),
        )
        r = cur.fetchone()
        return int(r[0]) if r else 0
