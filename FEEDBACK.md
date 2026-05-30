# FEEDBACK — R-012

## Round ID + Status

- **Round:** R-012 (major)
- **Status:** `done`

## Step Completion Mapping

| PLAN step | Status | Notes |
|-----------|--------|-------|
| 1. Inventory ingress call chains | done | Reused `submit_cv` / `submit_cv_pdf` / scoring-context author + refresh |
| 2. `POST /candidates/cv/pdf` create+upload API | done | Server-assigned `candidate_id`; response includes full ingress fields |
| 3. Atomic order ready → idempotency → write | done | Ready + replay/conflict before allocation; write via existing ingress |
| 4. Idempotency (TD-API-011 bounded) | done | SQLite + in-memory store; 24h lazy purge; dev_reset clears table |
| 5. Frontend PDF create button + idempotency UX | done | `CreateCandidatePdfUpload` with session key + retry/new session |
| 6. Scoring context text + job PDF ingress UI | done | `ScoringContextIngress` component |
| 7. Confirm → upsert/clear + auto refresh | done | Confirm triggers POST or DELETE then `POST /scoring-context/refresh` |
| 8. DELETE clear routes (3) + use cases | done | Clears authoring + structured + derived; returns full response |
| 9. Ready gating (backend + UI) | done | `ScoringContextStatus.READY` required; UI blocks upload when non-ready |
| 10. Full GET field visualization | done | `ScoringContextPanel` renders all `ScoringContextResponse` fields |
| 11. Regression tests | done | New API tests + existing suite green |
| 12. Verification + FEEDBACK | done | This file |

## File Change Summary

| Path | Change |
|------|--------|
| `modules/recruitment/idempotency_store.py` | A |
| `modules/recruitment/exceptions.py` | M |
| `modules/recruitment/use_cases.py` | M |
| `modules/recruitment/runtime.py` | M |
| `modules/recruitment/scoring_context_service.py` | M |
| `modules/recruitment/__init__.py` | M |
| `integrations/api/app.py` | M |
| `integrations/api/errors.py` | M |
| `integrations/api/schemas_http.py` | M |
| `runtime/persistence/sqlite_state_store.py` | M |
| `tests/api/test_candidates_cv_pdf_create.py` | A |
| `frontend/src/api/client.ts` | M |
| `frontend/src/api/types.ts` | M |
| `frontend/src/pages/CandidateListPage.tsx` | M |
| `frontend/src/components/recruiter/ScoringContextPanel.tsx` | M |
| `frontend/src/components/recruiter/ScoringContextIngress.tsx` | A |
| `frontend/src/components/recruiter/CreateCandidatePdfUpload.tsx` | A |
| `FEEDBACK.md` | M |

## Test Commands & Results

```text
python -m pytest -q
→ 187 passed, 2 skipped

cd frontend && npm test -- --run
→ 3 files, 7 tests passed

cd frontend && npm run build
→ success
```

## Risks, Deviations, Blockers

- **No blockers.**
- **Deviation:** `POST /candidates/cv/pdf` success/replay responses use `JSONResponse` with sorted JSON keys for byte-identical HTTP replay (OpenAPI still documents `CandidateCreatePdfIngressResponse`). Tracked as **`TD-API-015 + Idempotency HTTP response canonicalization vs OpenAPI (POST /candidates/cv/pdf)`** — deferred to API hardening (R-015).
- **Residual:** Orphan candidates after failed create+upload mid-write remain until R-013 dedup/governance. Legacy snapshot JSON keys stripped on SQLite read (R-011.2 compat) — not idempotency-related.

## Debt Handling

- **TD-SKILLS-001 + CV ingestion evolution (MVP cv_submitted)** — **partial close:** real PDF create+upload path is primary recruiter ingress for new candidates.
- **TD-PERSISTENCE-009 + Single active scoring_context store** — **partial close:** context ingress → refresh → ready → scoring consumption visible in UI; still single active store.
- **TD-API-011 + HTTP ingress idempotency and replay-safe retries** — **partial close:** implemented for `POST /candidates/cv/pdf` only; other ingress deferred.
- **TD-API-012 + API boundary coupling to bootstrap helpers** — **partial close:** create+upload reuses use-case ingress; no second business semantics layer.

## Suggested Next Round

- **Routing:** `advance-major` → **R-013** (dedup merge policy + orphan candidate governance per roadmap).
- Optional hardening: extend idempotency pattern to other ingress endpoints in a dedicated API round.
