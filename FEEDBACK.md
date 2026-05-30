# FEEDBACK — R-013.1

## Round ID + Status

- **Round:** R-013.1 (minor, parent R-013)
- **Status:** `done`

## Step Completion Mapping

| PLAN step | Status | Notes |
|-----------|--------|-------|
| 1. Dedup audit UTC timestamps | done | `_dedup_audit_entry`, `detected_at` use `datetime.now(timezone.utc)` |
| 2. Orphan vs ingress_in_progress | done | `ingress_governance.py`, 24h `ORPHAN_INGRESS_STALE_SECONDS` |
| 3. API/projection/frontend flags | done | `ingress_in_progress` + distinct UI copy |
| 4. Indexed dedup lookup | done | SQLite columns/indexes + in-memory indexes; `evaluate_dedup_from_ingress_signals` |
| 5. Regression tests + verify | done | `test_r013_1_hardening.py`, `test_candidate_governance_r013_1.py` |
| 6. FEEDBACK | done | This file |

## File Change Summary

| Path | Change |
|------|--------|
| `modules/recruitment/dedup.py` | M |
| `modules/recruitment/ingress_governance.py` | A |
| `modules/recruitment/use_cases.py` | M |
| `modules/recruitment/projection.py` | M |
| `runtime/persistence/candidate_store_dedup.py` | A |
| `runtime/persistence/sqlite_candidate_schema.sql` | M |
| `runtime/persistence/sqlite_candidate_store.py` | M |
| `runtime/persistence/in_memory_candidate_store.py` | M |
| `integrations/api/schemas_http.py` | M |
| `frontend/src/api/types.ts` | M |
| `frontend/src/components/recruiter/CandidateGovernancePanel.tsx` | M |
| `tests/modules/test_r013_1_hardening.py` | A |
| `tests/api/test_candidate_governance_r013_1.py` | A |
| `FEEDBACK.md` | M |

## Test Commands & Results

```text
python -m pytest -q
→ 199 passed, 2 skipped

cd frontend && npm test -- --run
→ 7 passed

cd frontend && npm run build
→ success
```

## Risks, Deviations, Blockers

- **No blockers.**
- **Note:** Existing SQLite DBs get `ALTER TABLE` + backfill on store open; no separate migration runner.
- **Note:** `ORPHAN_INGRESS_STALE_SECONDS` is a module constant (tests override via `ingress_governance_by_candidate_id(stale_seconds=...)`).

## Debt Handling

- **TD-API-016 + Candidate deduplication, merge/link, and orphan governance** — **partial close:** real audit timestamps; orphan only after stale threshold; indexed dedup lookups.
- **TD-API-004 + Candidate list is store-driven** — **partial close:** `ingress_in_progress` vs `orphan_ingress` on list/detail.
- **TD-API-011 + HTTP ingress idempotency** — **deferred** (global extension → R-015 per PLAN).
- **TD-API-012 + API boundary coupling to bootstrap helpers** — **deferred** (R-015 per PLAN).

## Suggested Next Round

- **Routing:** `advance-major` → **R-014** (timeline / inspection productization) per prior R-013 closeout, unless PM prioritizes **R-015** API hardening.
- Architect: reconcile `ROADMAP.md` / `tech_debt.md` for TD-API-016 partial close from R-013 + R-013.1.
