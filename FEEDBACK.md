# FEEDBACK — R-009.1 (Corrective Minor)

## Round

- **Round ID:** R-009.1
- **Status:** `done`

## PLAN step mapping

| Step | Status | Notes |
|------|--------|-------|
| 1. Reconciliation helper(s) | done | `modules/recruitment/candidate_sync.py` |
| 2. Subscriber integration | done | `bootstrap._OrchestrationSubscriber.handle` uses `persist_candidate_and_snapshot_with_reconcile` |
| 3. Read-time convergence (list/detail) | done | `load_candidate_and_snapshot_for_read` + `converge_snapshot_for_read` |
| 4. Fail-fast 503 | done | `CandidateStoreUnavailableError` / `CandidateCanonicalMissingError` → `integrations/api/errors.py` |
| 5. Pydantic v2 (touched files) | done | `projection._model_dump_json` uses `model_dump` only; `requirements.txt` already pins `pydantic>=2` |
| 6. HTTP schema doc fix | done | `CandidateListItem.headline` description |
| 7. Regression tests | done | `tests/modules/test_candidate_snapshot_sync.py`; `test_list_candidates.py` updated |
| 8. DB reset + seed | done | No prior `data/app.db`; ran `scripts/seed_testing_candidate_from_pdf.py` → `21024f7f-e639-580f-aae6-d4d2776f910e` |
| 9. Verification | done | see below |
| 10. FEEDBACK | done | this file |

## File changes

| Path | Change |
|------|--------|
| `modules/recruitment/candidate_sync.py` | A |
| `modules/recruitment/exceptions.py` | M |
| `modules/recruitment/bootstrap.py` | M |
| `modules/recruitment/projection.py` | M |
| `modules/recruitment/use_cases.py` | M |
| `integrations/api/errors.py` | M |
| `integrations/api/schemas_http.py` | M |
| `integrations/api/demo_page.py` | M |
| `tests/modules/test_candidate_snapshot_sync.py` | A |
| `tests/modules/test_list_candidates.py` | M |
| `FEEDBACK.md` | M |

## Tests

```text
python -m pytest -q
→ 179 passed, 2 skipped

cd frontend && npm test
→ 4 passed

cd frontend && npm run build
→ OK
```

## Acceptance criteria

- [x] Partial dual-write: bounded snapshot retries in `persist_candidate_and_snapshot_with_reconcile`; failure codes + pending marker on candidate extensions when exhausted.
- [x] List/detail converge stale `evaluation_status_ref` when `evaluation_revision` is newer.
- [x] Candidate store outage on recruiter read → HTTP 503 with `candidate_store_unavailable` / `fail_fast_no_legacy_snapshot_fallback` (no legacy ingress profile/evaluation fallback on list/detail).
- [x] Recruiter list/detail/action flows: full suite green.
- [x] `CandidateListItem.headline` doc reflects canonical Candidate source.
- [x] Pydantic v2 pinned; v1 fallback removed in touched `projection.py`.
- [x] DB seed documented and executed.

## Debt

- **TD-PERSISTENCE-008** (Evaluation precedence semantics): partial hardening via convergence; full precedence policy still open.
- **TD-ORCHESTRATOR-012**, **TD-PERSISTENCE-012**: deferred per PLAN.
- **TD-DX-003** (repo-wide Pydantic v1 fallback cleanup): suggest register/open — only touched-file cleanup done this round (`projection`, not `candidate_writes`).

## Risks / deviations

- None blocking. Demo HTML page loads candidate from store before `build_candidate_view` (not a recruiter API surface).

## Suggested next-round focus

- R-010 or next major: remove legacy snapshot `ingress_profile` / `evaluation` fields after migration window; continue TD-PERSISTENCE-008 precedence semantics.
