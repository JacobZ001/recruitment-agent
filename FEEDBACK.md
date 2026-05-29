# FEEDBACK — R-011.1 (Corrective Minor)

## Round

- **Round ID:** R-011.1
- **Status:** `done`

## PLAN step mapping

| Step | Status | Notes |
|------|--------|-------|
| 1. Consolidate transitional modules | done | Writes + dual-write → `candidate_aggregate.py`; read convergence → `projection.py` |
| 2. Delete `candidate_writes.py` / `candidate_sync.py` | done | `git` deletes; no shim re-exports |
| 3. Full-repo tail legacy semantics | done | `schemas/state_schema.py` field descriptions aligned with R-011 |
| 4. Remove `DEMO_CANDIDATE_DISPLAY` | done | `fixtures.py` skill-only defaults; demo routes use canonical store |
| 5. Minimal projection/DTO | done | `get_demo_candidate` returns `_profile_dto` from store |
| 6. DB reset/reseed | done | Stopped port 8000 holder, deleted `data/app.db`, seed OK |
| 7. Verification matrix | done | see below |
| 8. FEEDBACK | done | this file |

## File changes

| Path | Change |
|------|--------|
| `modules/recruitment/candidate_aggregate.py` | A |
| `modules/recruitment/candidate_writes.py` | D |
| `modules/recruitment/candidate_sync.py` | D |
| `modules/recruitment/projection.py` | M |
| `modules/recruitment/bootstrap.py` | M |
| `modules/recruitment/use_cases.py` | M |
| `modules/recruitment/runtime.py` | M |
| `modules/recruitment/fixtures.py` | M |
| `orchestrator/vertical_slice_planner.py` | M |
| `integrations/api/demo_page.py` | M |
| `runtime/demo_candidate_fixture.py` | M |
| `schemas/state_schema.py` | M |
| `tests/modules/test_candidate_snapshot_sync.py` | M |
| `tests/modules/test_recruitment_boundary.py` | M |
| `tests/api/test_demo_recruiter_surface.py` | M |
| `FEEDBACK.md` | M |

## Module ownership (post-consolidation)

| Concern | Module |
|---------|--------|
| Skill merge, finalize snapshot, ensure record, dual-write reconcile | `candidate_aggregate.py` |
| Recruiter read load + snapshot convergence | `projection.py` |
| Demo skill payload defaults (no display fixture) | `fixtures.py` |

## Tests

```text
python -m pytest -q
→ 180 passed, 2 skipped

cd frontend && npm test
→ 7 passed

cd frontend && npm run build
→ OK
```

## DB reset / reseed (required gate)

1. Stopped process bound to port 8000 (SQLite lock).
2. Deleted `data/app.db`.
3. `python scripts/seed_testing_candidate_from_pdf.py` → `21024f7f-e639-580f-aae6-d4d2776f910e`, `questionnaire_pending`.
4. TestClient smoke on `data/app.db`: `GET /candidates` + `GET /candidate/{id}` OK with profile keys.

**Restart Uvicorn** after pull: `python -m uvicorn integrations.api.app:app --host 127.0.0.1 --port 8000`

## Acceptance criteria

- [x] Transitional logic consolidated; behavior preserved (pytest green).
- [x] `candidate_writes.py` / `candidate_sync.py` deleted.
- [x] Read/write paths remain `candidate_id` + Candidate canonical (no links/ingress fallback).
- [x] DB delete + reseed executed with evidence.
- [x] `DEMO_CANDIDATE_DISPLAY` removed; demo uses store-backed profile.
- [x] Recruiter API contract stable (demo tests updated for canonical profile shape).

## Debt

- **TD-PERSISTENCE-008 Evaluation precedence semantics** — partial (unchanged; Candidate + ref semantics preserved).
- **TD-DX-002 Compatibility shim sprawl and demo-first residue** — partial close: display fixture removed; `runtime/demo_candidate_fixture.py` still shims `merge_demo_profile_into_skill_payload` only.
- **TD-PERSISTENCE-012**, **TD-ORCHESTRATOR-012**, **TD-INSPECTION-003** — deferred per PLAN.

## Risks / deviations

- Demo HTML no longer shows fictional “Alex Morgan” block; shows canonical store fields (may be sparse before `demo/run`).
- `merge_demo_profile_into_skill_payload` retained for deterministic demo skill inputs (not a display fixture).

## Suggested next-round focus

- PM routing: **`advance-major`** to **R-012** (hard-filter restoration) if R-011 major objectives accepted.
- Optional: further shrink `runtime/demo_candidate_fixture.py` shim after PM confirms no external importers.
