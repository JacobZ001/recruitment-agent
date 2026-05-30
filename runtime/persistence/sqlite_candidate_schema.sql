CREATE TABLE IF NOT EXISTS candidate (
    candidate_id TEXT PRIMARY KEY,
    candidate_json TEXT NOT NULL,
    store_revision INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    dedup_email TEXT,
    dedup_phone TEXT,
    dedup_cv_fingerprint TEXT
);

CREATE INDEX IF NOT EXISTS idx_candidate_updated ON candidate(updated_at);
CREATE INDEX IF NOT EXISTS idx_candidate_dedup_email ON candidate(dedup_email);
CREATE INDEX IF NOT EXISTS idx_candidate_dedup_phone ON candidate(dedup_phone);
CREATE INDEX IF NOT EXISTS idx_candidate_dedup_cv_fingerprint ON candidate(dedup_cv_fingerprint);
