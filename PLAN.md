# PLAN (Round R-004.1)

## Round Type

- Type: **Small round** (stabilization within parent capability round)
- Parent capability round: `R-004`
- Naming practice (new governance rule):
  - **Major rounds** (`R003`, `R004`, ...) add scope/capabilities.
  - **Minor rounds** (`R004.1`, `R004.2`, ...) refine/fix within an existing major round without adding new capabilities.

## Routing Context

- Proposed routing outcome from prior closeout: `corrective-minor`
- PM confirmed routing: `corrective-minor`
- Major-round snapshot needed: `no`
- Routing rationale: this round exists to harden and correct the still-open `R-004` major-round objective before any `advance-major` decision.

## Planning-Phase Debt Triage (Architect-Owned)

- `docs/architecture/tech_debt.md` review is completed by Architect during planning (before Builder execution starts).
- PM-approved debt handling for this round is frozen into this `PLAN.md`; Builder executes only those approved debt actions.
- Debt handling decisions for `R-004.1`:
  - tighten `scoring_context.ready` gating semantics where R-004 implementation remained weaker than planned;
  - remove public API exposure of internal workflow events that bypass the canonical `cv_submitted` ingress path;
  - make deep-scoring context gating symmetric with light-scoring gating;
  - remove deprecated compatibility code/tests for the legacy combined `cv_parse_and_score` path;
  - verify and keep explicit debt tracking for single active `scoring_context` and deep-scoring cognition maturity.

## Goal

Harden R-004 implementation quality without expanding capabilities: tighten deterministic `scoring_context.ready` gating, formalize round naming practice, and institutionalize a per-round `tech_debt.md` review step.

## Scope In

- Strengthen `scoring_context.status == ready` rule to match the stricter R-004 planning intent.
- Require `ready` to mean deterministic L2/L3 criteria derivation has already succeeded, not just that source objects/signals are present.
- Tighten public API ingress so internal workflow events cannot be posted through the same public surface as canonical recruiter ingress.
- Make deep-scoring context gating symmetric with light-scoring context gating.
- Remove the deprecated combined `cv_parse_and_score` compatibility path instead of preserving it for test convenience.
- Keep single active `scoring_context` behavior unchanged (single-tenant/single-requisition), but ensure debt entry remains explicit and current.
- Confirm deep scoring cognition remains intentionally fake/stub for now; ensure this is clearly tracked in technical debt as an open follow-up.
- Add round naming practice (`major` vs `minor`) into collaboration/process docs.
- Add a mandatory whole-file `docs/architecture/tech_debt.md` review + debt paydown opportunities step to round planning workflow.

## Scope Out

- No new scoring layers, no new scoring capabilities.
- No requisition-scoped/multi-context runtime changes.
- No production-grade provider go-live validation requirement in this round.
- No deep-scoring real cognition implementation.

## Constraints

- Preserve current R-004 architecture boundaries and contracts.
- No capability expansion: this round is correction/hardening only.
- Deterministic ownership remains in program logic (no prompt-owned workflow/control decisions).
- Keep API fail-closed semantics for scoring ingress.

## Execution Steps

1. **Harden ready-rule semantics (deterministic)**
   - Update scoring-context readiness checks to require not only component presence but also bounded minimum signal sufficiency aligned with R-004 intent.
   - `ready` must mean that deterministic layer-criteria derivation has already succeeded for the active `scoring_context`.
   - Explicitly validate:
     - `organization_context` has required signals for intended L2/L3 derivations.
     - `recruiter_actor_context` has required signals for L3 derivation.
     - `job_context` remains required with bounded role signals.
     - deterministic derivation of `l2_role_specific` and `l3_recruiter_preference` criteria succeeds and yields bounded non-empty outputs required by the current contract.
   - Keep refresh as the explicit transition action to `ready`.
   - For `R-004.1`, focus on enforcing the stricter ready gate and explicit successful criteria derivation/materialization semantics, without expanding this round into richer cognition-driven criteria-generation policy design.

2. **Lock API contract for not-ready ingress**
   - Preserve and verify: `cv_submitted` with non-ready context returns HTTP `409` with code `scoring_context_not_ready`.
   - Add/adjust tests for stricter ready-rule failures that should remain `collecting` (or `stale`) and therefore reject CV ingress.

3. **Close public-ingress compatibility loopholes**
   - Remove internal workflow events from the public HTTP ingress allowlist when they are no longer canonical recruiter/operator entry points.
   - At minimum, reassess public exposure of:
     - `cv_uploaded`
     - `cv_parsed`
     - `hard_filter_passed`
     - `light_scoring_completed`
     - `questionnaire_sent`
     - `questionnaire_completed`
     - `deep_scoring_completed`
   - Preserve harness/demo/internal execution paths as needed without keeping those event types publicly writable by default.

4. **Make deep-scoring context gating symmetric**
   - Ensure post-questionnaire deep scoring does not silently proceed with missing/non-ready scoring context while light scoring is gated.
   - Preserve deterministic `context_version` semantics for `evaluation.deep`; do not allow implicit fallback to an arbitrary default version when active context is not valid for scoring.

5. **Remove deprecated combined parse+score compatibility path**
   - Delete deprecated compatibility code/tests for the old combined `cv_parse_and_score` runtime path unless a current round requirement explicitly justifies keeping a shim.
   - Clean up related inspection/test/provider helper references so the canonical runtime path is unambiguous.

6. **Technical debt synchronization (mandatory in this round)**
   - Apply only Architect-planned and PM-approved debt actions frozen in this `PLAN.md` (no execution-time debt replanning).
   - Review the full `docs/architecture/tech_debt.md`, not only entries touched by R-004 implementation files.
   - Ensure these are explicitly present and up to date:
     - single active `scoring_context` (not requisition-scoped yet) remains OPEN.
     - deep scoring cognition maturity / fake deep behavior remains OPEN and explicit.
     - any newly confirmed R-004 compatibility loopholes that are not fixed in this round are added or updated explicitly.
   - If any debt item was resolved in code this round, mark it resolved or update status/review date.

7. **Institutionalize planning/process improvements**
   - Add round naming practice guidance (major vs minor rounds) into process/governance docs.
   - Add a required planning checklist step: each round must review `tech_debt.md` and identify:
     - debt items to close this round (if in-scope),
     - debt items to re-affirm as deferred (with reason).

8. **Documentation consistency pass**
   - Ensure `PLAN.md`/process docs and any touched architecture docs use the same naming and semantics:
     - `R004` as major capability round,
     - `R004.1` as minor hardening round,
     - no implied capability expansion.

## Acceptance Criteria

- [ ] `scoring_context.ready` transition enforces stricter deterministic signal-sufficiency checks (not just object presence).
- [ ] `scoring_context.ready` means deterministic L2/L3 criteria derivation has already succeeded for the active context.
- [ ] `cv_submitted` not-ready contract remains `409 + scoring_context_not_ready` and is covered by tests under stricter ready-rule scenarios.
- [ ] Public HTTP ingress no longer exposes obsolete/internal workflow events that bypass the canonical `cv_submitted` path.
- [ ] Deep-scoring context gating is symmetric with light-scoring gating, and `evaluation.deep.context_version` no longer relies on implicit fallback behavior when active context is invalid.
- [ ] Deprecated combined `cv_parse_and_score` compatibility code/tests are removed unless explicitly justified in Builder feedback.
- [ ] `tech_debt.md` explicitly and correctly tracks:
  - single active scoring-context scope limitation,
  - deep scoring cognition maturity gap (fake/deferred real skill).
- [ ] Full-file `docs/architecture/tech_debt.md` review was performed in planning and reflected in round debt handling decisions.
- [ ] Process docs include major/minor round naming practice.
- [ ] Process docs include mandatory per-round `tech_debt.md` review step.
- [ ] No new capabilities were introduced beyond R-004.

## Required Builder Feedback

Builder Agent must overwrite `FEEDBACK.md` and include:

- round status (`done` / `partial` / `blocked`) and blockers
- step-by-step mapping against the 8 execution steps above
- full file change list (`A` / `M` / `D`)
- exact ready-rule before/after behavior (including signal sufficiency gates and deterministic L2/L3 criteria derivation requirements)
- exact tests added/updated for `409 + scoring_context_not_ready` under stricter readiness checks
- exact public ingress event types removed/retained and why
- exact deep-scoring gating behavior before/after
- exact deleted compatibility paths for legacy combined parse+score flow
- technical debt updates made (items reviewed, changed, deferred, or resolved)
- process/governance docs updated for naming practice and mandatory debt review step
- confirmation that debt handling remained Architect-planned and PM-approved (no Builder execution-time debt replanning)
- confirmation that no new capability scope was added in `R-004.1`
