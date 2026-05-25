# PLAN (Round R-003)

## Goal

Ship a real PDF CV ingress path that runs end-to-end through `cv_submitted -> parsing -> scoring -> typed snapshot -> recruiter UI projection`, with real provider configuration ready for MVP go-live validation.

## Scope In

- Add bounded **PDF CV ingress** path in API/application boundary.
- Extract text from real PDF files and route into existing `submit_cv` flow.
- Keep typed snapshot semantics (`ingress_profile`, `evaluation`, `ingress_flags`) as the only canonical path.
- Validate real provider configuration path (`.env` + API key) in local environment.
- Ensure recruiter-facing read models reflect new snapshot state after PDF ingestion.
- Add/adjust tests for PDF success and failure paths (deterministic + provider-guarded where appropriate).
- Add `tech_debt.md` entry for **Local SQLite schema/cutover migration strategy (OPEN)**.

## Scope Out

- No questionnaire/WhatsApp/external messaging integration in this round.
- No multi-tenant or distributed deployment changes.
- No broad frontend redesign; only ensure existing recruiter surfaces can reflect snapshot updates.
- No production-grade auth/permission model in this round.

## Constraints

- Preserve DDD-lite + single-tenant modular monolith boundaries.
- Keep deterministic ownership of transitions/routing/ranking in program logic.
- LLM remains bounded to semantic extraction/evaluation; no orchestration control.
- Keep fail-closed semantics for ingestion/parsing/scoring failures.
- Do not reintroduce legacy `decision.*` compatibility semantics.

## Execution Steps

1. **PDF ingress contract and route**
   - Add a bounded API ingress path for PDF CV upload (or encoded PDF payload) with explicit validation.
   - Map ingress input to application use case boundary (no business logic in route handlers).

2. **PDF text extraction adapter**
   - Introduce deterministic PDF-to-text extraction in the application layer boundary (or a dedicated deterministic skill/helper).
   - Enforce size/page/text extraction guards; fail with structured error when extraction is empty/invalid.
   - Pass extracted text into existing `submit_cv(..., cv_text=...)`.

3. **Provider-ready end-to-end path**
   - Confirm real provider config path is usable via `.env` + env loading at startup.
   - Verify one real provider flow manually (OpenAI or OpenRouter) and keep deterministic `stub` as default test mode.

4. **Snapshot/UI reflection validation**
   - Verify post-ingress state and projection surfaces:
     - `GET /state/{candidate_id}`
     - `GET /candidate/{candidate_id}`
     - `GET /candidates`
   - Confirm `profile` + `evaluation.light` + `overall_score` are visible and consistent.

5. **Failure semantics and tests**
   - Add tests for:
     - valid PDF ingest success path
     - invalid/empty PDF failure path
     - provider-not-configured / provider-failure behavior remains fail-closed
   - Keep live provider smoke optional and non-default.

6. **Debt and docs sync for MVP posture**
   - Add `tech_debt.md` entry: **Local SQLite schema/cutover migration strategy (OPEN)**.
   - Update `ROADMAP.md` only if capability posture changed after PDF ingress completion.
   - Keep Immediate-next wording capability-level (no refactor-detail drift).

## Acceptance Criteria

- [ ] A real PDF CV can be ingested and converted to text through the new ingress path.
- [ ] End-to-end flow works: `pdf ingress -> cv_submitted -> parsing -> scoring -> typed snapshot`.
- [ ] Recruiter read surfaces reflect updated snapshot fields (`profile`, `evaluation`, derived scores).
- [ ] Failure paths are explicit and fail-closed (no silent success, no partial state corruption).
- [ ] Default automated tests remain deterministic and pass without real provider keys.
- [ ] Optional live provider validation is documented and runnable when keys are present.
- [ ] `tech_debt.md` contains the new Local SQLite cutover migration strategy entry.

## Required Builder Feedback

Builder Agent must overwrite `FEEDBACK.md` and include:

- execution status and blockers
- mapping against each execution step above
- full file change list (`A` / `M` / `D`)
- exact API contract chosen for PDF ingress (request/response examples)
- test commands/results (deterministic suite + optional live smoke if run)
- manual verification notes for end-to-end PDF flow and UI reflection
- debt/doc updates performed and any remaining risks for MVP go-live
