# PLAN (Round R-005)

## Round Type

- Type: **Major round** (new capability round)
- Naming practice (governance rule):
  - **Major rounds** (`R003`, `R004`, `R005`, ...) add scope/capabilities.
  - **Minor rounds** (`R004.1`, `R004.2`, ...) refine/fix within an existing major round without adding new capability scope.

## Routing Context

- Proposed routing outcome from prior closeout: `advance-major`
- PM confirmed routing: `advance-major`
- Major-round snapshot needed: `yes`
- Routing rationale: `R-004` closed after `R-004.1` corrective hardening. `R-005` opens a new major capability round for prose-first `scoring_context` authoring while preserving typed canonical context and persisted derived criteria.

## Planning-Phase Roadmap Alignment (Architect-Owned)

- `docs/architecture/ROADMAP.md` review is completed in planning.
- Selected `Upcoming (Action Queue)` item for this round:
  - **Job-aware three-layer evaluation hardening** (`TD-SKILLS-001`, `TD-PERSISTENCE-008`, `TD-PERSISTENCE-009`)
- Capability areas advanced by this round:
  - `Recruiter Workflow Operation`
  - `Controlled Cognition`
- Alignment rationale:
  - this round continues hardening the `scoring_context` lifecycle,
  - shifts user-facing authoring to prose-first input,
  - preserves typed canonical context/signals,
  - and makes persisted derived criteria the canonical downstream scoring input.

## Planning-Phase Debt Triage (Architect-Owned)

- `docs/architecture/tech_debt.md` review is completed by Architect during planning (before Builder execution starts).
- PM-approved debt handling for this round is frozen into this `PLAN.md`; Builder executes only those approved debt actions.
- Debt IDs selected for this round:
  - `TD-SKILLS-001` - extend canonical scorer-facing authoring around `cv + scoring_context` without reopening public ingress loopholes
  - `TD-PERSISTENCE-008` - keep evaluation precedence semantics explicit while criteria generation/consumption becomes more canonical
  - `TD-PERSISTENCE-009` - preserve and explicitly track the single active `scoring_context` store while the authoring shape evolves
- Debt IDs explicitly deferred this round:
  - `TD-ORCHESTRATOR-011` - deterministic hard-filter restoration remains a separate round
  - `TD-API-011`, `TD-API-012` - API hardening remains a separate round
  - `TD-CONTRACTS-009` - broader centralized scoring policy governance remains deferred beyond this bounded slice
  - `TD-CONTRACTS-010`, `TD-ORCHESTRATOR-004` - deep scoring continuity / questionnaire branching remain out of scope beyond compatibility-preserving alignment
- Debt status corrections made during sweep:
  - none planned in advance; update only if implementation reality explicitly resolves or supersedes an entry touched by this round

## Goal

Introduce a bounded prose-first `scoring_context` authoring vertical slice: user input becomes freeform, a bounded LLM skill normalizes that input into internal typed canonical context/signals plus persisted `derived_l2_criteria` / `derived_l3_criteria`, and downstream scoring consumes those persisted criteria rather than silently re-deriving them.

## Scope In

- Add freeform authoring support for `organization_context`, `recruiter_actor_context`, and `job_context`.
- Allow prompts/forms to guide users toward signal-rich prose, but do **not** require explicit signal-form entry as the primary authoring UX.
- Preserve typed canonical persistence in `ScoringContext` rather than collapsing the store to prose-only or criteria-only state.
- Keep signal-like canonical fields as internal normalized semantics, generated from prose by a bounded LLM normalization/derivation skill.
- Persist authored prose/source text alongside normalized typed context where it materially improves auditability and future re-derivation.
- Keep `refresh` as the explicit materialization gate that establishes `ready` and persists canonical `derived_l2_criteria` / `derived_l3_criteria`.
- Make downstream scoring consume persisted derived criteria as the canonical L2/L3 inputs instead of re-deriving labels at score time.
- Add focused tests for prose normalization, refresh/readiness behavior, staleness/version semantics, persistence, and canonical criteria consumption.

## Scope Out

- No `Deterministic hard-filter restoration` work.
- No recruiter-surface UX / action-surface redesign.
- No API idempotency / ingress hardening beyond what the new authoring endpoints minimally require.
- No requisition-scoped or multi-active `scoring_context` redesign.
- No real deep-scoring cognition redesign; keep the current bounded fake/deferred posture.
- No deletion of internal signal fields from canonical schemas in this round.

## Constraints

- Deterministic ownership remains in program logic:
  - LLM may extract/normalize/derive bounded context outputs,
  - but LLM must **not** own `ready/stale` transitions, routing, retries, or orchestration control.
- `ScoringContext` must remain the explicit deterministic contract used for gating, versioning, and persistence.
- `refresh` remains the only action that can materialize canonical derived criteria and move context to `ready`.
- Edits to authored prose or normalized canonical fields must continue to increment `context_version` and make prior evaluations stale under the current model.
- Do not introduce a second competing source of truth for criteria:
  - `refresh` materializes,
  - downstream scoring consumes.
- Preserve public recruiter ingress boundaries established in `R-004.1`.

## Execution Steps

1. **Define the prose-first authoring contract**
   - Introduce bounded freeform authoring inputs for organization, recruiter, and job context.
   - Decide which authored prose is persisted directly in canonical context vs retained through explicit `source_refs` / authored-text fields.
   - Keep user-facing authoring prose-first even when prompts/forms guide the user toward signal-rich content.

2. **Add a bounded LLM normalization / criteria-derivation path**
   - Implement or wire a bounded LLM skill that converts authored prose into:
     - internal typed canonical context/signals
     - candidate `derived_l2_criteria`
     - candidate `derived_l3_criteria`
   - Keep outputs bounded, inspectable, and versionable.
   - Do **not** let this skill mutate workflow state directly.

3. **Preserve typed canonical context/signals as the control-plane contract**
   - Store normalized organization/recruiter/job context in `ScoringContext`.
   - Keep internal signal-like fields available as canonical semantics even though the user is no longer asked to author those fields directly.
   - Do **not** remove internal signal fields in this round.

4. **Keep `refresh` as the explicit materialization gate**
   - `collecting` / `stale` remain editable but non-ingress-ready.
   - `ready` must mean:
     - prose has been normalized into typed canonical context/signals,
     - canonical `derived_l2_criteria` / `derived_l3_criteria` were successfully materialized and persisted,
     - the stored ready-state payload is sufficient for later score-time consumption without hidden re-derivation.

5. **Make downstream scoring consume canonical persisted criteria**
   - Update the scoring path so L2/L3 inputs come from persisted `derived_l2_criteria` / `derived_l3_criteria`.
   - Remove the hidden second source of truth where score-time logic locally re-derives criteria from context.
   - Preserve deterministic gating and context-version semantics already established in `R-004` / `R-004.1`.

6. **Align API responses and persistence**
   - Expose the new authoring/normalized state only enough to keep it inspectable and testable.
   - Persist the new `ScoringContext` shape consistently in both in-memory and SQLite-backed stores.
   - Keep current single-active-context scope explicit and unchanged.

7. **Test the bounded vertical slice**
   - Add/adjust tests for:
     - prose authoring input acceptance,
     - bounded LLM normalization output shape,
     - `refresh` success/failure,
     - `ready` / `collecting` / `stale` semantics,
     - SQLite persistence of new fields,
     - downstream scoring consuming canonical persisted criteria rather than local re-derivation.

## Acceptance Criteria

- [ ] A user can author `organization_context`, `recruiter_actor_context`, and `job_context` through freeform inputs rather than signal-form-first input.
- [ ] Prompts/forms may guide signal-rich prose, but the canonical user-authored surface is prose-first.
- [ ] A bounded LLM skill normalizes prose into internal typed canonical context/signals.
- [ ] Internal signal/context fields remain available as normalized canonical semantics; this round does not delete them.
- [ ] `refresh` remains the only materialization gate for `derived_l2_criteria` / `derived_l3_criteria` and `ready` status.
- [ ] `derived_l2_criteria` / `derived_l3_criteria` are persisted in `ScoringContext` and become the canonical source for downstream scoring.
- [ ] Downstream scoring no longer silently re-derives L2/L3 labels at score time.
- [ ] `ScoringContext` versioning, stale-marking, and ingress gating remain deterministic and explicit.
- [ ] Persistence works in both in-memory and SQLite-backed runtime modes for the updated `ScoringContext` shape.
- [ ] No unrelated roadmap items are pulled into `R-005` scope:
  - no hard-filter restoration,
  - no broad API hardening,
  - no requisition-scoped context redesign,
  - no deep-scoring cognition redesign.

## Required Builder Feedback

Builder Agent must overwrite `FEEDBACK.md` and include:

- round status (`done` / `partial` / `blocked`) and blockers
- step-by-step mapping against the 7 execution steps above
- full file change list (`A` / `M` / `D`)
- exact authoring inputs added/changed for prose-first organization/recruiter/job context
- exact canonical typed fields/signals retained internally and how they are populated from prose
- exact bounded LLM skill inputs/outputs introduced for normalization / criteria derivation
- exact `refresh` semantics before/after for prose normalization, criteria materialization, and `ready` gating
- exact downstream scoring behavior before/after regarding persisted criteria vs local re-derivation
- exact persistence changes made for `ScoringContext` in in-memory and SQLite stores
- exact tests added/updated for normalization, `ready/stale`, persistence, and score consumption behavior
- technical debt updates made (items reviewed, changed, deferred, or resolved)
- confirmation that no hidden second source of truth for criteria remains after the round
- confirmation that no out-of-scope capability work was added to `R-005`
