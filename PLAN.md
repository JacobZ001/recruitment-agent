# PLAN (Round R-008)

## Round Type

- **Round ID:** R-008
- **Type:** `major`
- **One-sentence goal:** Harden recruiter API semantics and contracts (`CandidateListItem` / `CandidateViewResponse`) while enforcing projection as the only recruiter read-model assembly boundary.

## Planning-Phase Roadmap Alignment

- Source: [`docs/architecture/ROADMAP.md`](docs/architecture/ROADMAP.md)
- This round advances:
  - `Recruiter Workflow Operation`
  - `Human Governance`
- R-008 focus is contract/core architecture stabilization before deeper canonical write-path migration.

## Planning-Phase Debt Triage

| Debt (ID + title) | This round handling |
|---|---|
| `TD-API-014` (Candidate view explanation vs snapshot boundary) | **Primary** — remove demo-shaped narrative assumptions and stabilize candidate-view semantics |
| `TD-PERSISTENCE-008` (Evaluation precedence semantics) | **Primary** — keep precedence explicit and aligned across projection/API/UI |
| `TD-API-005` (Candidate list has no pagination or filtering) | **Partial** — improve list readability fields only; no pagination contract this round |
| `TD-API-007` (Recruiter action label ownership) | **Partial** — preserve API label authority; no frontend local label map |
| `TD-CONTRACTS-001` (Typed payload contracts (events + skill IO)) | **Deferred to later major** |
| `TD-CONTRACTS-004` (Potential migration from `Dict[str, Any]` to stricter structures (`extensions` governance)) | **Deferred to later major** |
| `TD-PERSISTENCE-009` (Single active `scoring_context` store (not requisition-scoped yet)) | **Deferred to later major** |
| `TD-API-012` (API boundary coupling to bootstrap helpers (`_envelope`, fixed clock)), `TD-INSPECTION-003` (Timeline is global, not candidate-scoped (multi-candidate safety)) | **Deferred** with full demo phase-out queue |

## Scope In

1. **Recruiter API contract hardening**
   - Update only:
     - `CandidateListItem` in `integrations/api/schemas_http.py`
     - `CandidateViewResponse` in `integrations/api/schemas_http.py`
   - `CandidateViewResponse.profile` must no longer be loose `Dict[str, Any]`; use typed contract.
   - Improve list readability fields only (no pagination contract).
2. **Projection boundary enforcement**
   - Keep `modules/recruitment/projection.py` as the sole read-model assembly layer for recruiter API output.
   - Do not bypass projection in route handlers.
3. **Frontend minimal sync**
   - Update only API types and list/detail field consumption needed for the hardened contracts.

## Scope Out

- `/demo*` route removal (`/demo`, `/demo/candidate`, `/demo/run`) this round
- Full Candidate canonical write-path cutover (dual write, migration, consistency strategy)
- scoring_context/CV ingress quality redesign
- Global `Dict[str, Any]` elimination across event/skill/persistence contracts

## Ordered Execution Steps (Builder)

1. Apply architecture baseline constraints in code paths touching recruiter API read models (projection-only assembly; no route-layer composition).
2. Harden `CandidateListItem` / `CandidateViewResponse` contracts (typed profile, no demo-field assumptions).
3. Update projection assembly to satisfy new contracts while preserving deterministic behavior.
4. Sync frontend types/pages to the hardened API contracts.
5. Update tests impacted by contract changes and projection semantics.
6. Run verification:
   - `cd frontend && npm test`
   - `cd frontend && npm run build`
   - `python -m pytest -q`
7. Overwrite `FEEDBACK.md` with round report and explicit “deferred-to-roadmap” section.

## Acceptance Criteria

- [ ] `CandidateListItem` and `CandidateViewResponse` no longer rely on demo-shaped fields.
- [ ] `CandidateViewResponse.profile` is typed (not `Dict[str, Any]`).
- [ ] Projection remains the only recruiter read-model assembly boundary.
- [ ] Frontend list/detail renders against typed contract without field guessing.
- [ ] Tests pass (`npm test`, `npm run build`, `pytest -q`).
- [ ] `FEEDBACK.md` explicitly records deferred items queued to roadmap.

## Required Builder Feedback Format Reminder

Per `AGENTS.md`: round status, step mapping, file summary, tests, risks/deviations, debt updates (ID + title), roadmap update notes, and suggested next-round focus.
