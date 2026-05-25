"""
Canonical persistence for the single active scoring context.

This remains intentionally small in R-004: one active scoring context per runtime,
persisted separately from candidate workflow snapshots so the shape can later grow
into requisition-level context without duplicating it onto every candidate row.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

from schemas.state_schema import ScoringContext

_ACTIVE_CONTEXT_KEY = "active"


class InMemoryScoringContextStore:
    def __init__(self) -> None:
        self._current: Optional[ScoringContext] = None

    def get(self) -> Optional[ScoringContext]:
        if self._current is None:
            return None
        if hasattr(self._current, "model_copy"):
            return self._current.model_copy(deep=True)
        return self._current.copy(deep=True)

    def replace(self, context: ScoringContext) -> ScoringContext:
        if hasattr(context, "model_copy"):
            self._current = context.model_copy(deep=True)
            return context.model_copy(deep=True)
        self._current = context.copy(deep=True)
        return context.copy(deep=True)

    def clear(self) -> None:
        self._current = None


class SQLiteScoringContextStore:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scoring_context_state (
                context_key TEXT PRIMARY KEY,
                context_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def get(self) -> Optional[ScoringContext]:
        row = self._conn.execute(
            "SELECT context_json FROM scoring_context_state WHERE context_key = ?",
            (_ACTIVE_CONTEXT_KEY,),
        ).fetchone()
        if row is None:
            return None
        payload = row[0]
        if hasattr(ScoringContext, "model_validate_json"):
            return ScoringContext.model_validate_json(payload)
        return ScoringContext.parse_raw(payload)

    def replace(self, context: ScoringContext) -> ScoringContext:
        payload = context.model_dump_json() if hasattr(context, "model_dump_json") else context.json()
        updated_at = str(context.updated_at.isoformat())
        self._conn.execute(
            """
            INSERT INTO scoring_context_state (context_key, context_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(context_key) DO UPDATE SET
                context_json = excluded.context_json,
                updated_at = excluded.updated_at
            """,
            (_ACTIVE_CONTEXT_KEY, payload, updated_at),
        )
        self._conn.commit()
        return self.get() or context

    def clear(self) -> None:
        self._conn.execute("DELETE FROM scoring_context_state WHERE context_key = ?", (_ACTIVE_CONTEXT_KEY,))
        self._conn.commit()
