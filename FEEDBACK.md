# FEEDBACK (Round R-008)

## Execution Status

- status: done
- blocker: none

## Plan Step Mapping

- Step 1: done - Enforced projection-only recruiter read-model assembly and removed demo-shaped assumptions from recruiter read contracts.
- Step 2: done - Hardened `CandidateListItem` / `CandidateViewResponse` contracts in `integrations/api/schemas_http.py` (typed `profile`; list readability fields).
- Step 3: done - Updated `modules/recruitment/projection.py` to satisfy new contracts deterministically from `snapshot.ingress_profile`.
- Step 4: done - Synced frontend API types and list/detail field consumption to the hardened contracts.
- Step 5: done - Updated tests impacted by list contract changes.
- Step 6: done - Ran verification (`npm test`, `npm run build`, `pytest -q`).
- Step 7: done - Overwrote this `FEEDBACK.md` including a deferred-to-roadmap section.

## Full File Change List

- M `integrations/api/schemas_http.py`
- M `modules/recruitment/projection.py`
- M `frontend/src/api/types.ts`
- M `frontend/src/pages/CandidateListPage.tsx`
- M `frontend/src/pages/CandidateDetailPage.tsx`
- M `tests/api/test_candidate_list.py`
- D `FEEDBACK.md` (R-007)
- A `FEEDBACK.md` (R-008)

## Recruiter API Contract Hardening

### `CandidateViewResponse.profile` is typed

- `CandidateViewResponse.profile` moved from `Dict[str, Any]` → `CandidateProfile`.
- `CandidateProfile` is the typed projection of `schemas.state_schema.IngressProfile` plus `extensions: {}`:
  - `years_experience`, `seniority`, `roles`, `skills`, `industries`, `summary`, `extensions`.

### `CandidateListItem` readability fields (no demo fields)

- Added: `headline`, `summary`, `top_skills` (all derived from `snapshot.ingress_profile`; empty when absent).

## Verification

- `cd frontend && npm test` → pass (4/4)
- `cd frontend && npm run build` → success
- `python -m pytest -q` → **173 passed, 2 skipped**

## Risks / Deviations

- No scope deviations from `PLAN.md`.
- `headline` is best-effort and may be empty if roles/seniority/years are missing.

## Debt Handling (per `PLAN.md`)

- **Primary**
  - `TD-API-014` (Candidate view explanation vs snapshot boundary): reduced demo-shaped assumptions and typed the profile boundary.
  - `TD-PERSISTENCE-008` (Evaluation precedence semantics): projection still deep-over-light; UI continues to render score type without recomputing precedence.
- **Partial**
  - `TD-API-005` (Candidate list has no pagination or filtering): readability fields only; no pagination contract.
  - `TD-API-007` (Recruiter action label ownership): frontend continues to use API `label` only.

## Deferred-to-Roadmap (explicit)

- `TD-API-005` (Candidate list has no pagination or filtering): server-side pagination/filters still needed.
- `TD-CONTRACTS-001` (Typed payload contracts (events + skill IO))
- `TD-CONTRACTS-004` (Potential migration from `Dict[str, Any]` to stricter structures (`extensions` governance))
- `TD-PERSISTENCE-009` (Single active `scoring_context` store (not requisition-scoped yet))
- Demo phase-out / timeline isolation queue (e.g. `TD-API-012`, `TD-INSPECTION-003`) remains deferred.

## Suggested Next-Round Focus

- Address server-side pagination/filtering for `TD-API-005` or continue stabilizing candidate-view semantics around `TD-API-014`.

