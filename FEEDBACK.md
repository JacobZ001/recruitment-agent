# FEEDBACK — R-013

## Round ID + Status

- **Round:** R-013 (major)
- **Status:** `done`

## Step Completion Mapping

| PLAN step | Status | Notes |
|-----------|--------|-------|
| 1. Dedup inputs + normalization | done | `modules/recruitment/dedup.py` — email/phone/fingerprint + CV text extraction |
| 2. Dedup evaluation model | done | `DedupOutcome`, `DedupMatch`, `DedupEvaluation` |
| 3. `POST /candidates/cv/pdf` dedup分流 | done | High-confidence block before allocate; suspected flag after success |
| 4. Link / keep-separate API + audit | done | `POST .../dedup/link`, `POST .../dedup/keep-separate` on `candidate.extensions.dedup` |
| 5. Frontend duplicate + governance UI | done | Create flow shows block matches; list/detail governance panel |
| 6. Orphan detection | done | `idempotency_store.list_in_progress()` → `governance_flags.orphan_ingress` on list/detail |
| 7. Tests | done | `test_dedup.py`, `test_candidate_dedup_r013.py`; full suite green |
| 8. FEEDBACK | done | This file |

## File Change Summary

| Path | Change |
|------|--------|
| `modules/recruitment/dedup.py` | A |
| `modules/recruitment/exceptions.py` | M |
| `modules/recruitment/use_cases.py` | M |
| `modules/recruitment/projection.py` | M |
| `modules/recruitment/idempotency_store.py` | M |
| `modules/recruitment/__init__.py` | M |
| `integrations/api/app.py` | M |
| `integrations/api/errors.py` | M |
| `integrations/api/schemas_http.py` | M |
| `tests/modules/test_dedup.py` | A |
| `tests/api/test_candidate_dedup_r013.py` | A |
| `frontend/src/api/client.ts` | M |
| `frontend/src/api/types.ts` | M |
| `frontend/src/pages/CandidateListPage.tsx` | M |
| `frontend/src/pages/CandidateDetailPage.tsx` | M |
| `frontend/src/components/recruiter/CandidateGovernancePanel.tsx` | A |
| `frontend/src/components/recruiter/CreateCandidatePdfUpload.tsx` | M |
| `FEEDBACK.md` | M |

## Test Commands & Results

```text
python -m pytest -q
→ 192 passed, 2 skipped

cd frontend && npm test -- --run
→ 7 passed

cd frontend && npm run build
→ success
```

## Risks, Deviations, Blockers

- **No blockers.**
- **Deviation:** Dedup signals for create+upload are extracted from CV text pre-create (regex), not post-parse skill output; aligns with “block before write” and may miss email only present after LLM parse (conservative for high-confidence block).
- **Deviation:** `TD-API-016` registry entry not added in this Builder pass (Architect/PM may add in roadmap/debt sync).
- **Residual:** Link governance records audit on source candidate only; no cross-candidate data merge (by design).

## Debt Handling

- **TD-API-016 + Candidate deduplication, merge/link, and orphan governance** — **partial close:** deterministic dedup matrix, create+upload分流, link/keep-separate with audit, orphan visibility.
- **TD-API-004 + Candidate list is store-driven** — **partial close:** `governance_flags` on list/detail rows.
- **TD-API-011 + HTTP ingress idempotency** — **partial close:** dedup runs after idempotency replay path, before new allocation; replay unchanged.

## Suggested Next Round

- **Routing:** `advance-major` → **R-014** (timeline / inspection productization per roadmap) or PM-selected API hardening (**R-015**).
- Architect: register **TD-API-016** in `tech_debt.md` if not already present; reconcile `ROADMAP.md`.
