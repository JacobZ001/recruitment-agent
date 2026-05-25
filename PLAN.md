# PLAN (Round R-004)

## Goal

Ship a backend-first **job-aware three-layer scoring MVP**: add typed `job_context` awareness, separate recruiter/company context from score output, and evolve `evaluation.light` into a canonical three-layer scoring structure with deterministic aggregation.

## Scope In

- Introduce a bounded typed context model for:
  - `job_context` (role / requirements / success signals)
  - `recruiter_actor_context` (the operating context of the specific recruiter / hiring operator)
  - `organization_context` (company / team / environment context needed for evaluation)
- Introduce top-level `scoring_context` as the canonical evaluation context object built from those inputs.
- Allow `organization_context` to influence both role interpretation and preference derivation; do **not** introduce `recruiter_preference` as a separate canonical context/domain object.
- Upgrade the light-scoring contract from a flat universal-criteria payload to a **three-layer** structure with explicit layer field names:
  - `l1_universal`
  - `l2_role_specific`
  - `l3_recruiter_preference`
- Keep scoring in the existing workflow stage slot (`evaluation.light`) while changing its internal schema to support layered evaluation.
- Add bounded job-context ingestion paths so cognition can score against role context:
  - direct text input
  - bounded PDF input
  - bounded recruiter-answer normalization path for requirement extraction
- Extend the cognition layer so scoring uses `cv + scoring_context`.
- Keep read models / APIs able to expose layer breakdowns and deterministic overall score.
- Update architecture docs so `ROADMAP.md` reflects that job-aware three-layer scoring is now an immediate capability priority.

## Scope Out

- No broad recruiter console/frontend build in this round.
- No full requisition management product or multi-requisition orchestration.
- No free-form autonomous conversational recruiter interview loop; keep any requirement elicitation path bounded and contract-driven.
- No production auth/permissions, tenant isolation, or distributed infra changes.
- No hidden compatibility layer for the old flat `evaluation.light.criteria` shape unless explicitly required by this plan.

## Constraints

- Preserve DDD-lite + single-tenant modular monolith boundaries.
- Keep deterministic ownership of transitions, routing, ranking, and final aggregation in program logic.
- LLM handles semantic understanding/extraction only; it must not directly control workflow state or final orchestration decisions.
- Distinguish clearly between:
  - **workflow stage** (`hard_filter`, `light`, `deep`)
  - **score layers inside one stage** (`l1_universal`, `l2_role_specific`, `l3_recruiter_preference`)
- Do **not** hard-code the current PA role into logic, prompts, schemas, or API contracts.
- Favor minimal typed contracts that can later grow into a requisition-level domain without forcing a rewrite now.
- Because this round changes canonical scoring/state shape, local SQLite reset / cutover is acceptable; do not preserve legacy compatibility readers/writers unless absolutely required and explicitly documented.
- PDF/text ingress for job context should reuse existing bounded ingestion patterns where possible; do not balloon this round into a full document platform.

## Architect Decisions Agreed

- **Single source of truth remains snapshot-driven and DB-centered**:
  - the persisted orchestration snapshot remains the canonical runtime truth for candidate workflow state
  - in-memory objects are runtime materializations/caches only, not a second source of truth
- Introduce a top-level typed **`scoring_context`** concept for evaluation readiness and provenance.
- `scoring_context` must contain distinct typed sub-objects:
  - `organization_context`
  - `recruiter_actor_context`
  - `job_context`
- `scoring_context` is the canonical evaluation context name for this project; do **not** use vague parallel names such as `resolved_scoring_context`.
- `scoring_context` should expose explicit lifecycle/provenance fields, at minimum:
  - `context_version`
  - `status`
  - any additional timestamps / refs needed for traceability
- Use an explicit `scoring_context.status` enum:
  - `collecting`
  - `ready`
  - `stale`
- Prefer this explicit status model over boolean-only flags such as `isReady` / `isUpdated`.
- `job_context` is the primary **L2 role-specific criteria source**.
- `organization_context` may shape role interpretation and therefore influence **L2 role-specific criteria derivation** alongside `job_context`.
- `organization_context` + `recruiter_actor_context` jointly map to **L3 recruiter-preference criteria source**.
- `l3_recruiter_preference` remains a scoring-layer name only; organization-level and recruiter-level preference signals are derived into L3 criteria rather than stored as a separate canonical context object.
- The scoring system still has exactly **three scoring layers**:
  - `l1_universal`
  - `l2_role_specific`
  - `l3_recruiter_preference`
- Context authoring/configuration does **not** go through the candidate event bus; candidate workflow still effectively begins at `cv_submitted`.
- Candidate CV ingress is forbidden until `scoring_context.status == ready`.
- If any context input changes, the system must create/update `scoring_context.context_version` and require explicit re-scoring.
- Parsing and scoring are separate responsibilities:
  - parse candidate profile/evidence first
  - persist parsed candidate profile
  - score afterwards using `scoring_context`
- Use the existing candidate pipeline vocabulary where possible:
  - `cv_received`
  - `cv_parsed`
  - `light_scored`
  instead of inventing redundant new phases unless truly necessary.
- `evaluation.light` and `evaluation.deep` must share the same high-level layered evaluation schema; deep scoring is richer evidence, not a different scoring architecture.

## Execution Steps

1. **Define canonical context domain contracts**
   - Add explicit typed schema classes for `organization_context`, `recruiter_actor_context`, `job_context`, and top-level `scoring_context`.
   - Ensure role-specific criteria are derived from `job_context`, with `organization_context` allowed to shape role interpretation where relevant.
   - Ensure recruiter-preference criteria are derived from `organization_context` + `recruiter_actor_context` and represented as typed scoring output, not as a separate canonical context object and not buried inside free-form extensions.
   - Keep the current single-tenant slice simple: if a separate persistent requisition aggregate is too large for R004, persist canonical `scoring_context` data in a way that is requisition-ready later.
   - Document canonical ownership clearly:
     - DB-backed canonical context data
     - candidate snapshot as workflow truth for candidate state/evaluation
     - no dual SSOT between memory and DB
  - Define `scoring_context.status` and `context_version` semantics explicitly, including:
    - `collecting`: context inputs are incomplete; candidate CV ingress is not allowed
    - `ready`: context is valid for scoring
    - `stale`: the context or score provenance is outdated and explicit re-scoring is required
   - Define the `ready` rule explicitly: `scoring_context.status` may be set to `ready` only when all of the following are true:
     - `organization_context` is present, passes bounded validation, and provides the organization-level signals required for the current L2/L3 derivations
     - `recruiter_actor_context` is present, passes bounded validation, and provides the recruiter-level signals required for the current L3 derivation
     - `job_context` is present and passes bounded validation
     - required normalization/derivation steps for the current scoring contract succeed
   - If any required context component is missing or normalization/derivation fails, `scoring_context.status` must remain `collecting`.

2. **Redesign shared evaluation schema for light + deep**
   - Replace the current flat score contract with a typed three-layer structure reusable by both `evaluation.light` and `evaluation.deep`.
   - Keep a deterministic overall aggregate score and confidence derived from the three layers.
   - Preserve explainability:
     - per-layer criteria
     - per-criterion score/confidence/reason
     - layer-level explanation or summary where helpful
   - Ensure the schema cleanly distinguishes:
     - context sources (`organization_context`, `recruiter_actor_context`, `job_context`)
     - derived layer outputs (`l2_role_specific`, `l3_recruiter_preference`)
   - Be explicit in docs/contracts that:
     - `organization_context` may influence both `l2_role_specific` and `l3_recruiter_preference`
     - `recruiter_actor_context` influences `l3_recruiter_preference`
     - `job_context` is the primary source for `l2_role_specific`
   - Use explicit layer field names in the canonical evaluation schema:
     - `l1_universal`
     - `l2_role_specific`
     - `l3_recruiter_preference`

3. **Add job-context ingestion and normalization paths**
   - Add bounded context-authoring use cases outside the candidate event bus for:
     - `organization_context`
     - `recruiter_actor_context`
     - `job_context`
   - Introduce bounded application/API ingress for direct `job_context` submission as text.
   - Add bounded PDF ingestion for job-context documents using the same style of guardrails as CV PDF ingestion.
   - Add one bounded fixed-question requirement-extraction/normalization path for recruiter-provided answers so the system can derive structured `job_context` without requiring raw JD text only.
   - Apply the same normalization pattern to `recruiter_actor_context` authoring when needed so recruiter preference signals remain part of recruiter context rather than a separate object.
   - Normalize `organization_context` with the same discipline so org-level signals can be used consistently in both L2 and L3 derivation.
   - Keep normalization deterministic at the orchestration boundary even if cognition is used internally for parsing/normalization.
  - After the required context inputs exist, create/update `scoring_context`; only `ready` context may unlock candidate CV ingress.
  - If `cv_submitted` is attempted while `scoring_context.status != ready`, return HTTP `409 Conflict` with a structured error code `scoring_context_not_ready`.

4. **Split CV parsing from scoring and extend cognition for job-aware scoring**
   - Separate CV parsing/persistence from light scoring logic; do not keep the old combined parse-and-score behavior as the long-term canonical design.
   - Prefer reusing the existing pipeline phases `cv_received` and `cv_parsed` before `light_scored`.
   - Split responsibilities cleanly:
     - one bounded cognition path may normalize/extract typed context
     - one bounded cognition path parses candidate CV/profile/evidence
     - one bounded cognition or hybrid path scores the candidate against `scoring_context`
   - The scoring skill must no longer assume only universal competencies.
   - The scoring skill output must map cleanly into the typed three-layer contract and be validated before persistence.
   - Program logic, not the LLM, computes final weighted aggregates and any canonical combined score fields.

5. **Wire persistence, projections, and API/read models**
   - Persist canonical context data and `scoring_context` with explicit version/status semantics.
   - Persist layered evaluation on the canonical candidate snapshot with the `context_version` used to compute it.
   - Update recruiter-facing projections / read APIs so a candidate view can expose:
     - the active `scoring_context` summary
     - layered score breakdown
     - deterministic overall score
     - score/context version linkage when useful for inspection
   - Keep `GET /candidates` lightweight; it only needs the aggregate score and any minimal layer metadata if useful.
   - Avoid broad UI work in this round; only do the minimum read-model/API work needed to validate the backend contract.

6. **Tests and fail-closed behavior**
   - Add/update focused tests for:
     - `cv_submitted` rejected when `scoring_context.status != ready`
     - HTTP contract for that rejection is `409 Conflict` with structured error code `scoring_context_not_ready`
     - scoring-context status/version transitions
     - job-context text ingestion success
     - job-context PDF ingestion success/failure
     - recruiter-answer normalization success/failure
     - recruiter/organization context authoring success/failure
     - CV parse success independent of scoring
     - CV scoring success with three-layer output
     - deep scoring success with the same layered schema
     - explicit re-score required after context change
     - schema validation failures for malformed layer payloads
     - provider/config failure semantics remain explicit and fail-closed
   - Keep deterministic default tests using `stub`; live provider smoke remains optional and clearly separated.

7. **Docs and roadmap synchronization**
   - Update `docs/architecture/ROADMAP.md` to make **job-aware three-layer scoring** an immediate next capability, ahead of recruiter-console work.
   - Update `docs/architecture/design_doc.md` so the designed three-layer model now clearly distinguishes:
     - current implemented MVP target in R004
     - later richer recruiter-console / requisition workflows
   - Update `docs/architecture/ADR.md` if a durable architectural decision is made about:
     - layered scoring shape
     - context-domain modeling
     - job-context ingestion boundary
   - Add `tech_debt.md` follow-up items only for consciously deferred pieces, not for scope that should actually be in R004.

## `ROADMAP.md` Update Guidance

Builder should reflect the following priority adjustment while syncing docs:

1. Move **job-aware three-layer evaluation** into `Immediate next capabilities (engineering)` as the top capability item.
2. Place **operator-grade recruiter surface / recruiter console** after the three-layer backend, because operator UX should present the correct score model rather than a temporary universal-only model.
3. Update the Stage 4 / Stage 6 wording so the honest snapshot no longer implies cognition is only “CV ingress parsing”; it should now describe the target as **bounded job-aware evaluation cognition**.
4. Keep multi-requisition platform work, production infra, and full policy-pack governance out of the immediate list unless directly needed for the R004 slice.

Suggested `Immediate next capabilities` ordering after this round:

1. **Job-aware three-layer evaluation**
2. **Operator-grade recruiter surface**
3. **Provider-hardening for bounded cognition**
4. **Questionnaire / deeper-evaluation continuity**
5. **Single-tenant operational playbook**

## Acceptance Criteria

- [ ] The codebase has explicit typed contracts for `organization_context`, `recruiter_actor_context`, `job_context`, and top-level `scoring_context`.
- [ ] `scoring_context` has explicit `status` and `context_version` semantics.
- [ ] `scoring_context.status` uses the explicit enum `collecting | ready | stale`.
- [ ] `l3_recruiter_preference` is not implemented as a separate canonical context object; L3 preference signals derive from `organization_context` + `recruiter_actor_context`.
- [ ] `evaluation.light` and `evaluation.deep` both use the same canonical three-layer scoring structure.
- [ ] `organization_context` is able to influence both L2 role-specific derivation and L3 recruiter-preference derivation where relevant.
- [ ] The backend can ingest job context through at least one direct text path and one bounded PDF path.
- [ ] The backend can normalize recruiter-supplied requirement inputs into typed job context without hard-coding the current PA role.
- [ ] Candidate CV ingress is blocked until `scoring_context.status == ready`.
- [ ] `cv_submitted` while context is not ready returns HTTP `409 Conflict` with structured error code `scoring_context_not_ready`.
- [ ] Candidate profile parsing is persisted before light scoring, with parse and score treated as separate responsibilities.
- [ ] CV scoring consumes `cv + scoring_context` and persists a valid three-layer result on the typed snapshot.
- [ ] Persisted evaluations record the `context_version` used for scoring.
- [ ] Context change requires explicit re-scoring semantics; stale score behavior is not left implicit.
- [ ] The implementation contains an explicit deterministic rule for when `scoring_context.status` may transition to `ready`.
- [ ] Deterministic program logic computes and persists the aggregate score/confidence fields; the LLM does not own final control semantics.
- [ ] Recruiter-facing read models can show a layer breakdown and overall score for at least the detailed candidate view.
- [ ] Default automated tests remain deterministic and pass without real provider keys.
- [ ] `ROADMAP.md` is updated to reflect the new priority order and capability posture.

## Required Builder Feedback

Builder Agent must overwrite `FEEDBACK.md` and include:

- execution status and blockers
- mapping against each execution step above
- full file change list (`A` / `M` / `D`)
- exact schema shape chosen for:
  - `scoring_context`
  - `context_version` / `status`
  - `job_context`
  - recruiter / organization context
  - shared layered schema for `evaluation.light` and `evaluation.deep`, including explicit fields:
    - `l1_universal`
    - `l2_role_specific`
    - `l3_recruiter_preference`
- exact derivation rules for:
  - L2 from `job_context` (+ `organization_context` where relevant)
  - L3 from `organization_context` + `recruiter_actor_context`
- exact implemented rule for when `scoring_context.status` becomes `ready`
- exact API/use-case contracts chosen for:
  - organization context authoring
  - recruiter actor context authoring
  - job-context text input
  - job-context PDF input
  - recruiter-answer normalization
- exact HTTP error contract for `scoring_context_not_ready`
- whether context authoring remained outside the candidate event bus
- whether local SQLite reset / schema cutover was required
- test commands/results (deterministic suite + optional live smoke if run)
- manual verification notes showing one end-to-end path:
  - establish `scoring_context` to `ready`
  - submit CV
  - inspect parsed profile persistence
  - inspect persisted layered light/deep score / recruiter view
- doc updates performed (`ROADMAP.md`, `design_doc.md`, `ADR.md`, `tech_debt.md`) and any remaining R005 risks
