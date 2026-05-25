# FEEDBACK (Round R-004)

## Execution Status

- status: done
- blocker: none

## Plan Step Mapping

- Step 1: done - Added explicit typed contracts for `organization_context`, `recruiter_actor_context`, `job_context`, and top-level `scoring_context`, plus a separate canonical scoring-context store wired into the runtime.
- Step 2: done - Replaced flat light/deep scoring semantics with a canonical three-layer schema (`l1_universal`, `l2_role_specific`, `l3_recruiter_preference`) and deterministic aggregate score/confidence computation.
- Step 3: done - Added bounded scoring-context authoring outside the candidate event bus for organization/recruiter context plus job-context ingestion via direct text, PDF, and recruiter-answer normalization. Added explicit `refresh` to move context from `collecting` / `stale` to `ready`.
- Step 4: done - Split CV parsing from scoring: `cv_submitted` now persists `cv_received` with parsed profile first, emits `cv_parsed`, then emits `light_scoring_completed` for job-aware layered scoring against `cv + scoring_context`.
- Step 5: done - Persisted `context_version` on light/deep evaluations, marked existing candidate evaluations stale when scoring context changes, and exposed scoring-context summary + layered score breakdown in recruiter-facing projections.
- Step 6: done - Added focused deterministic tests for readiness gating, status/version transitions, text/PDF/recruiter-answer normalization, parse-before-score sequencing, stale re-score semantics, and updated existing API/module tests to the new contracts.
- Step 7: done - Updated `ROADMAP.md`, `design_doc.md`, `ADR.md`, and `tech_debt.md` to reflect job-aware three-layer scoring as the immediate backend priority and documented the separate scoring-context model.

## File Changes (Full List)

- A `modules/recruitment/scoring_context_service.py` - Deterministic normalization, status/version lifecycle, L2/L3 derivation rules, aggregate score computation, and stale-marking helpers.
- A `modules/recruitment/scoring_context_store.py` - Canonical active scoring-context persistence (in-memory + SQLite-backed).
- A `skills/llm/cv_llm_parse_profile.py` - New profile-only bounded LLM skill for `cv_submitted`.
- A `skills/llm/cv_llm_score_candidate.py` - New bounded LLM skill for layered light scoring against `cv + scoring_context`.
- A `tests/api/test_scoring_context_routes.py` - API coverage for organization/recruiter/job authoring, job PDF ingestion, recruiter-answer normalization, and refresh-to-ready lifecycle.
- A `tests/modules/test_scoring_context.py` - Module-level coverage for scoring-context transitions, parse-before-score sequencing, and stale re-score semantics.
- M `docs/architecture/ADR.md` - Added ADR-011 for canonical `scoring_context` + layered job-aware scoring.
- M `docs/architecture/ROADMAP.md` - Promoted job-aware three-layer evaluation to the top immediate capability and updated Stage 4 / Stage 6 wording.
- M `docs/architecture/design_doc.md` - Updated implementation-reality sections for scoring-context gating, split parse/score, and layered evaluation.
- M `docs/architecture/tech_debt.md` - Updated `cv_submitted` evolution notes and added single-active-scoring-context debt entry.
- M `integrations/api/app.py` - Added scoring-context authoring/read/refresh routes and wired new use cases.
- M `integrations/api/errors.py` - Added `invalid_scoring_context` (422) and `scoring_context_not_ready` (409) mappings.
- M `integrations/api/schemas_http.py` - Added request/response models for scoring-context APIs and candidate-view scoring-context summary.
- M `modules/recruitment/__init__.py` - Exported new scoring-context use cases and errors.
- M `modules/recruitment/bootstrap.py` - Wired new parse and score LLM skills into the runtime.
- M `modules/recruitment/exceptions.py` - Added `InvalidScoringContextError` and `ScoringContextNotReadyError`.
- M `modules/recruitment/projection.py` - Added recruiter-facing scoring-context summary and layered score flattening for detailed candidate views.
- M `modules/recruitment/runtime.py` - Wired the canonical scoring-context store into the API runtime and reset flow.
- M `modules/recruitment/use_cases.py` - Added scoring-context authoring/refresh/get use cases, readiness gating, stale propagation, and context injection for `cv_submitted` / deep scoring ingress.
- M `orchestrator/vertical_slice_planner.py` - Split parse vs score orchestration, added `cv_submitted -> cv_received -> cv_parsed -> light_scoring_completed`, and mapped layered evaluations into typed snapshot writes.
- M `runtime/inspection/decision_evidence.py` - Recognized the new scoring skill for inspection summaries.
- M `schemas/state_schema.py` - Added scoring-context schemas and upgraded `ScoreEvaluation` to layered + versioned structure.
- M `skills/deterministic/fake_deep_scoring_skill.py` - Propagated context version through deterministic deep scoring when active scoring context is present.
- M `skills/llm/cv_llm_parse_and_score.py` - Kept deprecated compatibility test path aligned with the new layered `ScoreEvaluation` schema.
- M `skills/llm/llm_provider.py` - Extended stub-provider behavior to support profile-only parse, layered scoring, and legacy combined test coverage.
- M `state_machine/transition_engine.py` - Updated transition registry for `cv_submitted -> cv_received` and `cv_parsed -> light_scored`.
- M `tests/api/test_cv_ingest.py` - Added scoring-context readiness setup and explicit 409 contract coverage.
- M `tests/api/test_cv_pdf_ingest.py` - Added readiness setup plus 409 coverage for PDF CV ingress without ready context.
- M `tests/api/test_demo_recruiter_surface.py` - Updated candidate-view expectations for layered scores.
- M `tests/conftest.py` - Added shared helper fixture to establish ready scoring context for CV-ingress tests.
- M `tests/inspection/test_decision_evidence_navigation.py` - Updated snapshot evaluation fixtures to the layered/versioned schema.
- M `tests/modules/test_cv_ingestion.py` - Updated expectations for gated split-flow CV ingestion and layered evaluation writes.
- M `tests/modules/test_cv_pdf_ingestion.py` - Updated PDF ingestion expectations for the split-flow path.
- M `tests/modules/test_list_candidates.py` - Updated overall-score fixtures to use layered evaluation builders.
- M `tests/modules/test_recruitment_boundary.py` - Updated boundary test to establish ready scoring context before `cv_submitted`.
- M `tests/persistence/test_sqlite_cv_extensions.py` - Added scoring-context setup to SQLite persistence coverage.

## Exact Schema Shapes Chosen

### `scoring_context`

```json
{
  "context_version": 3,
  "status": "ready",
  "organization_context": {
    "company_name": "BlueOcean",
    "industry": "recruitment",
    "team_name": "Talent Ops",
    "environment_signals": ["fast-moving recruiter workflow"],
    "preference_signals": ["clear communication", "structured follow-through"],
    "summary": "...",
    "source_refs": ["test://organization"]
  },
  "recruiter_actor_context": {
    "actor_id": "test-recruiter",
    "actor_role": "lead_recruiter",
    "hiring_focus": ["operator-ready execution"],
    "preference_signals": ["stakeholder communication", "ownership"],
    "avoid_signals": ["unclear communication"],
    "summary": "...",
    "source_refs": ["test://recruiter"]
  },
  "job_context": {
    "title": "Recruiting Operations Specialist",
    "summary": "...",
    "responsibilities": ["coordinate interviews", "surface blockers early"],
    "hard_requirements": ["stakeholder communication", "process ownership"],
    "preferred_requirements": ["ATS familiarity"],
    "success_signals": ["keep candidate flow organized"],
    "source_refs": ["normalized://recruiter_answers/job_context"]
  },
  "created_at": "...",
  "updated_at": "...",
  "ready_at": "...",
  "stale_at": null,
  "source_refs": ["..."]
}
```

### `context_version` / `status`

- `context_version`: monotonic integer, incremented on every organization/recruiter/job context mutation.
- `status`: explicit enum `collecting | ready | stale`.
- `collecting`: required components are missing or refresh has not yet validated the full context.
- `ready`: set only by explicit `refresh_active_scoring_context(...)` / `POST /scoring-context/refresh` when all required components are present and bounded validation succeeds.
- `stale`: produced when a previously `ready` scoring context is changed; existing candidate evaluations are marked stale until explicit refresh establishes a new ready version.

### `job_context`

- Canonical fields: `title`, `summary`, `responsibilities[]`, `hard_requirements[]`, `preferred_requirements[]`, `success_signals[]`, `source_refs[]`.
- Text/PDF normalization produces the same typed `job_context`.
- Recruiter-answer normalization also produces the same typed `job_context`; no parallel raw-answer aggregate was introduced.

### Recruiter / Organization Context

- `organization_context`: `company_name`, `industry`, `team_name`, `environment_signals[]`, `preference_signals[]`, `summary`, `source_refs[]`.
- `recruiter_actor_context`: `actor_id`, `actor_role`, `hiring_focus[]`, `preference_signals[]`, `avoid_signals[]`, `summary`, `source_refs[]`.

### Shared Layered Schema for `evaluation.light` and `evaluation.deep`

```json
{
  "normalized_score": 0.54339,
  "confidence": 0.63,
  "explanation": "...",
  "source": "system_llm",
  "context_version": 3,
  "stale": false,
  "l1_universal": {
    "summary": "...",
    "criteria": {
      "communication": { "score": 0.73, "confidence": 0.78, "reason": "..." }
    }
  },
  "l2_role_specific": {
    "summary": "...",
    "criteria": {
      "stakeholder communication": { "score": 0.62, "confidence": 0.73, "reason": "..." }
    }
  },
  "l3_recruiter_preference": {
    "summary": "...",
    "criteria": {
      "ownership": { "score": 0.58, "confidence": 0.71, "reason": "..." }
    }
  },
  "evidence_refs": ["..."]
}
```

## Exact Derivation Rules

### L2 from `job_context` (+ `organization_context` where relevant)

- Primary source: `job_context.hard_requirements[:2]`.
- Then: `job_context.preferred_requirements[:1]`.
- Then, if present: one organization-shaped criterion `Operate effectively in {environment_signal}` from `organization_context.environment_signals[:1]`.
- Then: `job_context.success_signals[:1]`.
- Result is bounded to at most 3 L2 criteria.

### L3 from `organization_context` + `recruiter_actor_context`

- Primary source: `recruiter_actor_context.preference_signals[:2]`.
- Then: `organization_context.preference_signals[:1]`.
- Then, if present: one inverted preference criterion `Avoid: {avoid_signal}` from `recruiter_actor_context.avoid_signals[:1]`.
- Result is bounded to at most 3 L3 criteria.

## Exact Implemented Ready Rule

`scoring_context.status` becomes `ready` only when all of the following are true:

1. `organization_context` exists and passes typed validation.
2. `recruiter_actor_context` exists and passes typed validation.
3. `job_context` exists and has a non-empty `title` plus at least one bounded role signal from `hard_requirements`, `preferred_requirements`, `success_signals`, or `responsibilities`.
4. The explicit refresh step (`refresh_active_scoring_context(...)` / `POST /scoring-context/refresh`) succeeds.

If any required component is missing, status remains `collecting`.
If a previously-ready context is mutated, status becomes `stale` until explicit refresh succeeds again.

## Exact API / Use-Case Contracts Chosen

### Organization Context Authoring

- Route: `POST /scoring-context/organization`
- Body: `OrganizationContextBody`
- Use case: `author_organization_context(runtime, OrganizationContext(...))`

### Recruiter Actor Context Authoring

- Route: `POST /scoring-context/recruiter-actor`
- Body: `RecruiterActorContextBody`
- Use case: `author_recruiter_actor_context(runtime, RecruiterActorContext(...))`

### Job-Context Text Input

- Route: `POST /scoring-context/job/text`
- Body:

```json
{
  "raw_text": "Role: ...\nMust: ...\nPreferred: ...\nSuccess: ...",
  "source_ref": "optional://source"
}
```

- Use case: `author_job_context_from_text(runtime, raw_text, source_ref=...)`

### Job-Context PDF Input

- Route: `POST /scoring-context/job/pdf`
- Body:

```json
{
  "file_name": "job_context.pdf",
  "pdf_base64": "JVBERi0xLjQK..."
}
```

- Use case: `author_job_context_from_pdf(runtime, pdf_base64, file_name=...)`

### Recruiter-Answer Normalization

- Route: `POST /scoring-context/job/recruiter-answers`
- Body:

```json
{
  "role_title": "Recruiting Operations Specialist",
  "must_haves_answer": "stakeholder communication\nprocess ownership",
  "preferred_answer": "ATS familiarity",
  "success_answer": "keep candidate flow organized",
  "responsibilities_answer": "coordinate interviews\nsurface blockers early"
}
```

- Use case: `author_job_context_from_recruiter_answers(...)`

### Refresh to `ready`

- Route: `POST /scoring-context/refresh`
- Use case: `refresh_active_scoring_context(runtime)`

### Read Active Scoring Context

- Route: `GET /scoring-context`
- Returns the canonical active `ScoringContextResponse`.

## Exact HTTP Error Contract for `scoring_context_not_ready`

```json
{
  "detail": {
    "code": "scoring_context_not_ready",
    "message": "scoring_context_not_ready: active scoring_context status is collecting"
  }
}
```

- Status code: `409 Conflict`

## Context Authoring Boundary

- Context authoring remained outside the candidate event bus: **yes**
- Candidate workflow still begins at `cv_submitted`: **yes**

## Local SQLite Reset / Schema Cutover

- Existing local SQLite rows should be treated as disposable for this round.
- R-004 changed canonical snapshot evaluation shape and added a separate persisted scoring-context store, so local reset / recreation is the expected cutover workflow for old developer DBs.

## Tests and Validation

- command: `python -m pytest tests/skills/test_llm_provider.py -q`
  - result: pass
  - notes: 9 passed
- command: `python -m pytest tests/api/test_demo_recruiter_surface.py -q`
  - result: pass
  - notes: 10 passed
- command: `python -m pytest tests/modules/test_cv_ingestion.py tests/modules/test_cv_pdf_ingestion.py tests/api/test_cv_ingest.py tests/api/test_cv_pdf_ingest.py tests/persistence/test_sqlite_cv_extensions.py -q`
  - result: pass
  - notes: 13 passed, 1 skipped
- command: `python -m pytest tests/skills/test_cv_parse_and_score_skill.py tests/inspection/test_decision_evidence_navigation.py tests/modules/test_list_candidates.py tests/replay/test_vertical_slice_replay.py -q`
  - result: pass
  - notes: 15 passed
- command: `python -m pytest tests/modules/test_scoring_context.py tests/api/test_scoring_context_routes.py -q`
  - result: pass
  - notes: 5 passed
- command: `python -m pytest -q`
  - result: pass
  - notes: 157 passed, 2 skipped, 11 warnings
- command: `ReadLints` on changed files
  - result: pass
  - notes: no linter errors found

## Manual Verification Notes

- Manual stub-provider path executed end-to-end through API:
  1. `POST /scoring-context/organization`
  2. `POST /scoring-context/recruiter-actor`
  3. `POST /scoring-context/job/recruiter-answers`
  4. `POST /scoring-context/refresh` -> `status=ready`, `context_version=3`
  5. `POST /events` with `event_type=cv_submitted`
  6. `GET /candidate/{id}` confirmed:
    - non-empty parsed `profile.summary`
    - layered `evaluation.light`
    - `scores.overall_score = {"value": 0.54339, "type": "light"}`
    - `scores.context_version = 3`
  7. `POST /events` with `questionnaire_sent`, `questionnaire_completed`, `deep_scoring_completed`
  8. Final checks:
    - `GET /candidate/{id}` -> `stage=shortlisted`
    - `evaluation.deep.context_version = 3`
    - `GET /state/{id}` -> `pipeline_phase=shortlisted`
    - `GET /candidates` row reflected matching overall score/type and recruiter actions

## Docs / Debt Updates

- `docs/architecture/ROADMAP.md`
  - promoted **Job-aware three-layer evaluation** to the top immediate capability
  - moved recruiter-surface work after the backend score-model slice
  - updated Stage 4 / Stage 6 posture to describe bounded job-aware evaluation cognition instead of CV-ingress parsing only
- `docs/architecture/design_doc.md`
  - updated engineering-reality sections for canonical `scoring_context`, parse-before-score sequencing, and layered evaluation semantics
- `docs/architecture/ADR.md`
  - added **ADR-011 — Job-aware layered scoring uses a separate canonical `scoring_context`**
- `docs/architecture/tech_debt.md`
  - updated the `cv_submitted` evolution entry to the split parse/score path
  - added **Single active `scoring_context` store (not requisition-scoped yet)**

## Risks, Deviations, and Remaining R005 Focus

- Deviations from `PLAN.md`:
  - none in architecture scope; context authoring stayed outside the candidate event bus and the canonical scoring path is now typed + layered.
- Remaining R005 risks:
  - The runtime still supports only one active scoring context, not requisition-scoped parallel contexts.
  - Deep scoring now uses the same layered schema and version linkage, but the deep skill itself remains deterministic/fake rather than job-aware cognition.
  - `scoring_failed` remains coarse for provider/config/runtime failures.
  - Deprecated compatibility code/tests for the old combined `cv_parse_and_score` skill still exist for harness stability, even though the canonical runtime path is now split parse + score.
- Suggested next focus:
  - Bind candidates to requisition-scoped scoring contexts instead of one global active context.
  - Upgrade deep scoring from deterministic placeholder behavior to context-aware bounded cognition on the same layered contract.
  - Refine `scoring_failed` into deterministic subcodes and explicit retryability semantics.

