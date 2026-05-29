# FEEDBACK — R-011 (Major)

## Round

- **Round ID:** R-011
- **Status:** `done`

## PLAN step mapping

| Step | Status | Notes |
|------|--------|-------|
| 1. Remove active `links` binding dependency | done | `projection`, `use_cases`, `state_init`, stores |
| 2. Contract legacy snapshot branches | done | `finalize_orchestration_snapshot` clears `links`; removed `legacy_ingress_profile_from_candidate` |
| 3. Calibrate read/write paths | done | Canonical Candidate + explicit `candidate_id` only |
| 4. SQLite / in-memory index alignment | done | `_candidate_ids_for_index`; no links fallback |
| 5. API projection/DTO | skipped | No contract change required |
| 6. Balanced verification | done | see below |
| 7. FEEDBACK + R-011.1 entry | done | this file |

## File changes

| Path | Change |
|------|--------|
| `modules/recruitment/state_init.py` | M |
| `modules/recruitment/candidate_writes.py` | M |
| `modules/recruitment/projection.py` | M |
| `modules/recruitment/use_cases.py` | M |
| `modules/recruitment/bootstrap.py` | M |
| `runtime/in_memory_state_store.py` | M |
| `runtime/persistence/sqlite_state_store.py` | M |
| `tests/persistence/test_sqlite_state_store.py` | M |
| `tests/modules/test_list_candidates.py` | M |
| `FEEDBACK.md` | M |

## Tests

```text
python -m pytest -q
→ 180 passed, 2 skipped

cd frontend && npm test
→ 7 passed

cd frontend && npm run build
→ OK
```

New: `test_sqlite_candidate_index_requires_explicit_candidate_id` — links-only snapshots are not indexed.

## DB reset / seed

- Attempted delete of `data/app.db` while Uvicorn held the file (file in use); seed script still ran against existing DB.
- **Recommendation:** stop API, delete `data/app.db`, run `python scripts/seed_testing_candidate_from_pdf.py`, restart Uvicorn so all rows have explicit `candidate_id` and canonical candidate rows.

## Acceptance criteria

- [x] `candidate_id` is the only active binding path; no `links` fallback in list/projection/store index.
- [x] No active-flow legacy `ingress_profile` helper; snapshot finalize strips legacy owned fields.
- [x] Recruiter surfaces unchanged at API contract level (no schema changes).
- [x] Persistence index uses `_candidate_ids_for_index` (`candidate_id` only).
- [x] Balanced test matrix green.

## Debt

- **TD-PERSISTENCE-008 Evaluation precedence semantics** — partial: list/detail still use evaluation from Candidate + `evaluation_status_ref` on snapshot for overall when needed; no links/ingress fallback reintroduced.
- **TD-PERSISTENCE-012**, **TD-ORCHESTRATOR-012**, **TD-INSPECTION-003** — deferred per PLAN.

## Risks / deviations

- Legacy SQLite rows with **only** `links` and no `candidate_id` will not appear in list or `get_for_candidate` until DB reset/migration.
- `candidate_sync` / `candidate_writes` module consolidation deferred to **R-011.1** per PLAN.

## R-011.1 entry conditions (suggested)

- R-011 baseline accepted on PM smoke (list/detail/action).
- Consolidate or absorb `candidate_sync` + `candidate_writes` write-path duplication.
- Optional: repo-wide cleanup of stale `StateLink` documentation in `tech_debt.md` (not required for Builder this round).

## Suggested next-round focus

- **R-011.1 (corrective-minor):** write/sync consolidation and any remaining transition helpers after linkage cutover.
