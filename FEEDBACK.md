# FEEDBACK — R-011.2

## Round ID + Status

- **Round:** R-011.2 (corrective minor, parent R-011)
- **Status:** `done`

## Step Completion Mapping

| PLAN step | Status | Notes |
|-----------|--------|-------|
| 1. Inventory & absorb `candidate_aggregate.py` | done | Logic split: writes/dual-write → `use_cases.py` + `bootstrap.py`; snapshot finalize/ref → `projection.py` |
| 2. Delete `candidate_aggregate.py` + fix refs | done | File deleted; all imports retargeted |
| 3. Delete `runtime/demo_candidate_fixture.py` + fix tests | done | File deleted; boundary test updated; planner doc points to `modules.recruitment.fixtures` |
| 4. Remove legacy `OrchestrationState` fields | done | Removed `links`, `ingress_profile`, `evaluation`; removed `StateLink` class |
| 5. Clean legacy runtime reads | done | Planner, inspection explainer, tests updated; no `state.links` / `ingress_profile` / `evaluation` reads remain |
| 6. Minimal test fixes | done | Persistence, ingestion, scoring, inspection tests adjusted |
| 7. Verification matrix | done | See below |
| 8. Overwrite FEEDBACK.md | done | This file |

## File Change Summary

| Path | Change |
|------|--------|
| `modules/recruitment/candidate_aggregate.py` | D |
| `runtime/demo_candidate_fixture.py` | D |
| `schemas/state_schema.py` | M |
| `modules/recruitment/projection.py` | M |
| `modules/recruitment/use_cases.py` | M |
| `modules/recruitment/bootstrap.py` | M |
| `modules/recruitment/runtime.py` | M |
| `modules/recruitment/state_init.py` | M |
| `orchestrator/vertical_slice_planner.py` | M |
| `runtime/in_memory_state_store.py` | M |
| `runtime/inspection/decision_explainer.py` | M |
| `tests/modules/test_candidate_snapshot_sync.py` | M |
| `tests/modules/test_recruitment_boundary.py` | M |
| `tests/modules/test_cv_ingestion.py` | M |
| `tests/modules/test_cv_pdf_ingestion.py` | M |
| `tests/modules/test_scoring_context.py` | M |
| `tests/persistence/test_sqlite_state_store.py` | M |
| `tests/persistence/test_sqlite_cv_extensions.py` | M |
| `tests/inspection/test_decision_evidence_navigation.py` | M |
| `FEEDBACK.md` | M |

## Logic Absorption Map

| Former `candidate_aggregate` concern | New owner |
|--------------------------------------|-----------|
| `ensure_candidate_record`, `find_candidate_ids_by_dedup_signals`, `persist_candidate_and_snapshot_with_reconcile` | `modules/recruitment/use_cases.py` |
| `apply_skill_results_to_candidate` (+ parse/merge helpers) | `modules/recruitment/bootstrap.py` |
| `finalize_orchestration_snapshot`, `evaluation_status_ref_from_evaluation`, `evaluation_ref_lags_candidate`, `evaluation_from_candidate` | `modules/recruitment/projection.py` |

## Test Commands & Results

```text
python -m pytest -q
→ 180 passed, 2 skipped

cd frontend && npm test -- --run
→ 3 files, 7 tests passed

cd frontend && npm run build
→ success

API smoke (TestClient lifespan): GET /health, /candidate/{id}, /candidates → 200
```

## Risks, Deviations, Blockers

- **No blockers.**
- **Deviation:** None material; scope stayed within PLAN.
- **Residual risk:** Existing SQLite rows may still contain stripped JSON keys from older snapshots; in-memory/test paths are clean. Full local DB delete + reseed recommended if a persistent dev DB shows stale deserialization warnings (not required for test matrix pass).

## Debt Handling

- **TD-PERSISTENCE-008 + Candidate/snapshot write ownership still split across transitional helpers** — **partial close:** transitional `candidate_aggregate.py` removed; dual-write and ensure-record live in `use_cases`, skill merge in `bootstrap`, finalize/ref projection in `projection`. Residual: write paths still span bootstrap subscriber + use_cases (by design for this round).
- **TD-DX-002 + Demo-era fixture/profile assumptions still leak into runtime path** — **partial close:** `runtime/demo_candidate_fixture.py` deleted; demo merge remains on `modules/recruitment/fixtures` only. Full demo phase-out still deferred (`R-019`).

## Suggested Next Round

- **Routing:** `advance-major` → open **R-012** (hard-filter capability per roadmap).
- Residual TD-PERSISTENCE-008 ownership consolidation can be revisited only if PM prioritizes further write-path unification before R-012.
