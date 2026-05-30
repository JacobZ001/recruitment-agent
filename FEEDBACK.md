# FEEDBACK — R-013.2

## Round ID + Status

- **Round:** R-013.2 (minor, parent R-013)
- **Status:** `done`

## Step Completion Mapping

| PLAN step | Status | Notes |
|-----------|--------|-------|
| 1. SQLite cutover (remove ALTER/backfill) + README | done | `_migrate_dedup_columns` / `_backfill_dedup_columns` removed; `frontend/README.md` R-013.2 four-step cutover |
| 2. Post-parse dedup + frozen create order | done | `_mark_candidate_post_ingress_duplicate`, `merge_dedup_matches`, retry idempotency |
| 3. API / projection / frontend | done | `post_ingress_duplicate` in governance panel; `CandidatePdfIngressResult.dedup` + route exposes `dedup` in HTTP body |
| 4. Module + API tests | done | `test_r013_2_post_parse_dedup.py`, `test_candidate_post_parse_dedup_r013_2.py` |
| 5. FEEDBACK | done | This file |

## File Change Summary

| Path | Change |
|------|--------|
| `runtime/persistence/sqlite_candidate_store.py` | M |
| `modules/recruitment/dedup.py` | M |
| `modules/recruitment/use_cases.py` | M |
| `integrations/api/app.py` | M |
| `integrations/api/schemas_http.py` | M |
| `frontend/README.md` | M |
| `frontend/src/components/recruiter/CandidateGovernancePanel.tsx` | M |
| `tests/modules/test_r013_2_post_parse_dedup.py` | A |
| `tests/api/test_candidate_post_parse_dedup_r013_2.py` | A |
| `FEEDBACK.md` | M |

## Test Commands & Results

```text
python -m pytest -q
→ 206 passed, 2 skipped

cd frontend && npm test -- --run
→ 7 passed

cd frontend && npm run build
→ success
```

## Risks, Deviations, Blockers

- **No blockers.**
- **Fix during round:** `POST /candidates/cv/pdf` route rebuilt JSON without `dedup`; added `CandidatePdfIngressResult.dedup` and route passthrough so HTTP + idempotency bodies align with `extensions.dedup`.
- **API test note:** Stub email injection uses `rt.bundle.subscriber.orchestrator._ctx.skills[SKILL_CV_PARSE_PROFILE]._provider` because skill instances bind `provider_factory` at construction time.
- **Ops:** Local DB upgrade remains **delete `data/app.db`** (+ WAL/SHM); no runtime migration.

## Debt Handling

- **TD-API-016 + Candidate deduplication, merge/link, and orphan governance** — **ready for Architect RESOLVED** per PLAN closeout checklist (post-parse + cutover delivered; Architect to move to `tech_debt/resolved.md`).
- **TD-PERSISTENCE-001** — **not modified** (doc-only touch optional for Architect).
- **TD-API-004 / TD-API-011 / TD-API-012 / TD-API-015** — **deferred** per PLAN.

## Suggested Next Round

- **Routing:** `advance-major` → **R-014** (timeline / inspection productization).
- Architect: TD-API-016 `RESOLVED` + major-round snapshot if PM confirms advance.
