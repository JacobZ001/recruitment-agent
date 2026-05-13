-- Canonical orchestration snapshot row (snapshot_json is source of truth).
CREATE TABLE IF NOT EXISTS orchestration_state (
    state_id TEXT PRIMARY KEY,
    candidate_id TEXT,
    snapshot_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    store_revision INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_orchestration_state_candidate
ON orchestration_state(candidate_id);

-- Maps each candidate link id -> state_id (matches InMemoryStateStore candidate index).
CREATE TABLE IF NOT EXISTS orchestration_state_candidate (
    candidate_id TEXT NOT NULL PRIMARY KEY,
    state_id TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_osc_state ON orchestration_state_candidate(state_id);

-- Non-authoritative mirror of snapshot.transitions (snapshot_json remains canonical).
CREATE TABLE IF NOT EXISTS state_transition_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    state_id TEXT NOT NULL,
    sequence_index INTEGER NOT NULL,
    from_state TEXT NOT NULL,
    to_state TEXT NOT NULL,
    trigger TEXT NOT NULL,
    event_id TEXT,
    actor_type TEXT,
    actor_id TEXT,
    extensions_json TEXT,
    recorded_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_transition_audit_state
ON state_transition_audit(state_id);
