# FEEDBACK — R-014

## Round ID + Status

- **Round:** R-014 (major)
- **Status:** `done`

## Step Completion Mapping

| PLAN step | Status | Notes |
|-----------|--------|-------|
| 1. Backend: remove context `stale` / `stale_at`, legacy normalize, fingerprint + version semantics, force/clear evaluation stale, `materialization_blockers` | done | `ScoringContextStatus` only `collecting` \| `ready`; `last_ready_materialized_fingerprint`; author/clear from `ready` → `collecting` without version bump |
| 2. Frontend: `ScoringContextIngress` state machine, Confirm/Delete/Job PDF, refresh gating, invalidate order | done | `empty_locked` / `editing` / `saved_locked`; POST → optional refresh → `finally` invalidate; amber blockers + green PDF hint via `pdf://` on top-level `source_refs` |
| 3. `CandidateListPage` layout | done | Title → Create PDF → filters → table → ingress → processed panel |
| 4. Tests + build + FEEDBACK | done | Scoring-context module tests rewritten; API clear-status assertion updated |
| 5. PM manual acceptance checklist | done | See below (`LLM_PROVIDER=stub`) |

## Acceptance Criteria Traceability

| PLAN acceptance criterion | Verification |
|---------------------------|--------------|
| Third Confirm triggers refresh; `ready`; Processed updates without full reload | PM manual #3–5; `tests/modules/test_scoring_context.py`; ingress integration via API tests |
| Single Confirm: green success; incomplete third dim → amber | PM manual #4; frontend build + manual |
| No context `stale`; only `collecting` / `ready` | `tests/modules/test_scoring_context.py`; `pytest -q` |
| Edit from `ready` → `collecting`, eval stale, no version bump until new ready | `test_*` edit/collecting paths in `test_scoring_context.py`; PM manual #7 |
| Same fingerprint refresh: version unchanged, stale cleared | `test_idempotent_refresh_does_not_bump_version`; PM manual #8 |
| Different fingerprint ready: `context_version +1` | `test_scoring_context.py` refresh/changed materialize assertions; PM manual #7–8 |
| No `stale_at` field | schema tests + grep; PM ops note delete `app.db` |
| `materialization_blockers` readable when collecting / refresh fails | API/GET tests; PM manual #10 |
| Saved_locked hydrate; Job PDF green hint | PM manual #9; frontend manual |
| Create PDF above filters | PM manual #3 |
| Tests and build pass | `python -m pytest -q` (208 passed); `npm test`; `npm run build` |

## File Change Summary

| Path | Change |
|------|--------|
| `modules/recruitment/scoring_context_fingerprint.py` | A |
| `schemas/state_schema.py` | M |
| `modules/recruitment/scoring_context_service.py` | M |
| `modules/recruitment/use_cases.py` | M |
| `integrations/api/schemas_http.py` | M |
| `integrations/api/app.py` | M |
| `tests/modules/test_scoring_context.py` | M |
| `tests/api/test_candidates_cv_pdf_create.py` | M |
| `frontend/src/api/types.ts` | M |
| `frontend/src/components/recruiter/ScoringContextIngress.tsx` | M |
| `frontend/src/components/recruiter/ScoringContextPanel.tsx` | M |
| `frontend/src/pages/CandidateListPage.tsx` | M |
| `FEEDBACK.md` | M |

## Test Commands & Results

```text
python -m pytest -q
→ 208 passed, 2 skipped

cd frontend && npm test -- --run
→ 7 passed

cd frontend && npm run build
→ success
```

## Risks, Deviations, Blockers

- **No blockers.**
- **Build fix:** `scoring_context_service` imported nonexistent `EvaluationStatus`; corrected to `EvaluationState`. `state_schema` legacy normalizer missing `Mapping` import.
- **Test alignment:** Edit-after-ready + refresh with changed materialized content now asserts `context_version == 2` and evaluations remain stale (per PM fingerprint rules); idempotent same-fingerprint path covered by `test_idempotent_refresh_does_not_bump_version`.
- **Ops:** Delete `data/app.db` (+ WAL/SHM) after pulling R-014 if local JSON still has removed fields or legacy context `stale`.
- **Accepted risk:** Real LLM materialize may drift fingerprint → version bump; use stub for deterministic QA.

## PM Manual Acceptance (stub LLM)

1. In API terminal: `$env:LLM_PROVIDER = "stub"` (PowerShell) or `export LLM_PROVIDER=stub`; restart uvicorn.
2. Optional: delete `data/app.db` for clean cutover.
3. List page: Create PDF block **above** filters; scoring ingress below table.
4. Per dimension: Create → Confirm → green success; incomplete third dimension → amber warning (not red).
5. After third Confirm with all prose on server: auto refresh → `ready`; Processed panel updates without full page reload.
6. PDF create enabled when `ready`; disabled when `collecting`.
7. Edit from `ready`: status `collecting`, evaluations stale, version unchanged until new distinct ready refresh.
8. Repeat refresh without prose/material change: version unchanged, evaluation stale cleared.
9. Job PDF Confirm: top-level `source_refs` contains `pdf://…` → green PDF hint above disabled job textarea.
10. Refresh failure: amber lists `materialization_blockers` from GET (and refresh error detail when applicable).

**Builder verification used:** `LLM_PROVIDER=stub` (pytest autouse in `tests/conftest.py`).

## Debt Handling

- **TD-PERSISTENCE-009 — Requisition-scoped scoring context** — **partial** (fingerprint + `last_ready_materialized_fingerprint` on global context; full requisition scope still deferred).
- **TD-API-001 — Single-process shared scoring context** — **partial** (unchanged deployment model; ingress UX + blockers improve operability).
- **TD-CONTRACTS-015 / TD-INSPECTION-*** / **TD-API-011/012/015** — **deferred** per PLAN → R-015 / R-016.

## Roadmap Updates

- **R-014** removed from Upcoming; posture and capability notes reconciled in `docs/architecture/ROADMAP.md` (Architect closeout).

## Suggested Next Round

- **PM routing (confirmed):** **`corrective-minor`** → **R-014.1** (List scoring-context ingress UX).
- **PM UAT specifics (2026-05-30, stub):** materialization blocker readability; Cancel in editing; per-dimension inline status; label copy; Job PDF Confirm missing (Confirm only on job text row in `editing`); sidebar drawer + readiness checklist above Create PDF — frozen in root `PLAN.md`.
- **After R-014.1:** **`advance-major`** → **R-015** unless further corrective needed.
