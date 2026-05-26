# FEEDBACK (Round R-004.1)

## Execution Status

- status: done
- blocker: none

## Plan Step Mapping

- Step 1: done - Hardened `scoring_context.ready` so refresh now requires successful deterministic L2/L3 label materialization, not just object presence. Added persisted `derived_l2_criteria` / `derived_l3_criteria` on `ScoringContext`.
- Step 2: done - Preserved `409 + scoring_context_not_ready` for `cv_submitted` and added stricter readiness tests covering contexts that remain `collecting` because derivation inputs are insufficient.
- Step 3: done - Removed internal workflow events from the public `/events` allowlist. Public recruiter ingress is now bounded to `cv_submitted` plus governance events and `candidate_rejected`.
- Step 4: done - Made deep-scoring ingress fail closed the same way as light scoring: `deep_scoring_completed` now requires an active ready `scoring_context` and always carries the validated context into the payload when accepted.
- Step 5: done - Removed the deprecated combined parse+score compatibility path (`skills/llm/cv_llm_parse_and_score.py`), deleted its dedicated test, removed stub-provider fallback logic for it, and removed the inspection alias that treated it as canonical.
- Step 6: done - Updated `docs/architecture/tech_debt.md` to reflect the now-tight public ingress, reaffirm the single-active-context limitation, and explicitly keep fake/deferred deep cognition open.
- Step 7: verified - Major/minor naming practice and mandatory full-file `tech_debt.md` planning sweep were already present in `AGENTS.md` at execution start as part of the approved planning artifacts; no additional Builder-side doc mutation was required.
- Step 8: done - Kept documentation semantics aligned with `R004` as the parent major capability round and `R004.1` as a corrective minor hardening round; no new capability scope was added.

## Full File Change List

- M `docs/architecture/tech_debt.md` - Updated debt entries for public CV ingress posture and fake deep scoring maturity.
- M `integrations/api/schemas_http.py` - Tightened public `/events` description and exposed derived scoring-context criteria in the response model.
- M `modules/recruitment/policies.py` - Removed internal workflow events from the public ingress allowlist.
- M `modules/recruitment/scoring_context_service.py` - Added stricter readiness validation, deterministic criteria materialization, and removed weak fallback label generation.
- M `modules/recruitment/use_cases.py` - Enforced symmetric ready-context gating for light/deep scoring and provisioned a deterministic ready context for internal demo execution.
- M `runtime/inspection/decision_evidence.py` - Removed legacy combined-skill inspection handling.
- M `schemas/state_schema.py` - Added persisted `derived_l2_criteria` / `derived_l3_criteria` to `ScoringContext`.
- D `skills/llm/cv_llm_parse_and_score.py` - Deleted deprecated combined parse+score compatibility skill.
- M `skills/llm/llm_provider.py` - Removed legacy combined-output stub fallback; stub now supports only the canonical parse-profile or layered-score shapes.
- M `tests/api/test_candidate_actions.py` - Switched helper setup away from public internal events and aligned candidate-action tests with ready-context semantics.
- M `tests/api/test_candidate_list.py` - Stopped relying on removed public internal ingress events.
- M `tests/api/test_cv_ingest.py` - Added stricter `409` coverage for weak/collecting contexts.
- M `tests/api/test_cv_pdf_ingest.py` - Added stricter `409` coverage for weak/collecting contexts on PDF ingress.
- M `tests/api/test_scoring_context_routes.py` - Added refresh failure coverage for insufficient derivation inputs and asserted materialized derived criteria on ready contexts.
- M `tests/api/test_vertical_slice_api.py` - Moved public ingress tests to canonical `cv_submitted` and added explicit rejection coverage for removed internal events.
- M `tests/modules/test_multi_candidate_registry.py` - Removed dependence on public internal event exposure.
- M `tests/modules/test_scoring_context.py` - Added ready materialization assertions and deep-scoring fail-closed coverage.
- M `tests/persistence/test_sqlite_cv_extensions.py` - Brought SQLite setup into compliance with stricter ready requirements.
- D `tests/skills/test_cv_parse_and_score_skill.py` - Deleted deprecated combined-skill test.
- M `tests/skills/test_llm_provider.py` - Updated stub-provider expectations to the canonical profile-only path.

## Exact Ready Rule Before / After

### Before `R-004.1`

- `refresh_active_scoring_context(...)` treated readiness as:
  1. `organization_context` exists.
  2. `recruiter_actor_context` exists.
  3. `job_context` exists and has `title` plus at least one bounded role signal.
- `derive_l2_labels(...)` and `derive_l3_labels(...)` had generic fallback labels, so a context could become `ready` even if the recruiter/organization signals needed for real L2/L3 derivation were effectively missing.
- `ready` did not persist proof that deterministic criteria derivation had already succeeded.

### After `R-004.1`

`scoring_context.status` becomes `ready` only when all of the following are true during explicit refresh:

1. `organization_context.company_name` is non-empty.
2. `organization_context.environment_signals` is non-empty.
3. `organization_context.preference_signals` is non-empty.
4. `recruiter_actor_context.actor_id` is non-empty.
5. `recruiter_actor_context` has at least one of:
   - `preference_signals`
   - `avoid_signals`
6. `job_context.title` is non-empty.
7. `job_context` has at least one bounded role signal from:
   - `hard_requirements`
   - `preferred_requirements`
   - `success_signals`
   - `responsibilities`
8. Deterministic derivation succeeds and yields non-empty outputs for both:
   - `derived_l2_criteria`
   - `derived_l3_criteria`

Additional semantics:

- `derived_l2_criteria` and `derived_l3_criteria` are now persisted on `ScoringContext`.
- Failed refresh clears derived criteria and leaves the context non-ready (`collecting`).
- Mutating a previously-ready context still marks it `stale` immediately; ingress remains blocked until a later refresh succeeds again.
- Fallback generic derivation labels were removed, so `ready` can no longer be satisfied by placeholder criteria.

## Exact `409` Not-Ready Coverage Added / Updated

- `tests/api/test_cv_ingest.py`
  - retained baseline `cv_submitted` -> `409 + scoring_context_not_ready` coverage with no context at all
  - added coverage for a context that has all three objects but still remains `collecting` because organization/recruiter derivation inputs are too weak
- `tests/api/test_cv_pdf_ingest.py`
  - retained baseline PDF CV -> `409 + scoring_context_not_ready` coverage with no context
  - added the same weak-derivation / still-collecting coverage for PDF ingress
- `tests/api/test_scoring_context_routes.py`
  - added explicit `POST /scoring-context/refresh` failure coverage (`422 + invalid_scoring_context`) when derivation prerequisites are insufficient
- `tests/modules/test_scoring_context.py`
  - added module-level assertions that failed refresh leaves `derived_l2_criteria` / `derived_l3_criteria` empty and the context non-ready

## Exact Public Ingress Event Types Removed / Retained

### Removed from public `/events`

- `cv_uploaded`
- `cv_parsed`
- `hard_filter_passed`
- `light_scoring_completed`
- `questionnaire_sent`
- `questionnaire_completed`
- `deep_scoring_completed`

### Retained on public `/events`

- `cv_submitted`
  - canonical recruiter-facing CV ingress
- governance event types from `GOVERNANCE_EVENT_TYPES`
  - recruiter/operator governance actions remain valid public write operations
- `candidate_rejected`
  - preserved because it is not part of the internal workflow-event loophole targeted by this round

### Internal paths preserved

- `publish_recruitment_event(...)` still supports internal workflow events for harness/runtime progression.
- `run_primary_demo_sequence(...)` now ensures a deterministic ready demo `scoring_context` before internal demo progression, so demo coverage still works without re-opening the public ingress loophole.

## Exact Deep-Scoring Gating Before / After

### Before `R-004.1`

- `cv_submitted` required a ready active `scoring_context`.
- `deep_scoring_completed` did **not** require one.
- If an active ready context existed, it was injected opportunistically.
- If no valid context existed, deep scoring could still be published, which left deep context-version semantics dependent on implicit fallback / missing-context behavior.

### After `R-004.1`

- `publish_ingress_event(...)` now calls `_require_ready_scoring_context(...)` for both:
  - `cv_submitted`
  - `deep_scoring_completed`
- Both event types now fail closed with `ScoringContextNotReadyError` when the active context is missing, `collecting`, or `stale`.
- When accepted, both event types receive the validated serialized `scoring_context` in the merged payload.
- Demo/internal sequence compatibility is preserved by provisioning a deterministic ready context before demo progression, rather than by keeping deep scoring permissive.

## Exact Deleted Legacy Compatibility Paths

- Deleted file: `skills/llm/cv_llm_parse_and_score.py`
- Deleted test: `tests/skills/test_cv_parse_and_score_skill.py`
- Removed stub-provider fallback logic in `skills/llm/llm_provider.py` that generated the old combined `profile + criteria + explanation` shape as the default compatibility path
- Removed inspection special-casing in `runtime/inspection/decision_evidence.py` that still treated `recruitment.vertical_slice.cv_parse_and_score` as a live canonical scoring skill

## Technical Debt Review / Updates

Full-file `docs/architecture/tech_debt.md` review was already completed in planning (`Last full registry sweep: 2026-05-26`). Builder executed only the debt actions frozen into `PLAN.md`.

Reviewed / updated items:

- `TD-PERSISTENCE-009` - reaffirmed OPEN
  - single active `scoring_context` store remains the explicit known limitation
  - no requisition-scoped or multi-context runtime expansion was introduced in this round
- `TD-CONTRACTS-010` - updated and remains OPEN
  - clarified that deep scoring is still intentionally deterministic/fake
  - clarified that it now fails closed on ready-context availability
- `TD-SKILLS-001` - updated and remains OPEN
  - public recruiter ingress is now explicitly tightened to `cv_submitted`
  - internal-only harness/runtime workflow events remain acceptable non-public mechanics
  - deprecated combined parse+score compatibility path is now removed

No new debt items were replanned or added outside the Architect-approved `PLAN.md` scope.

## Process / Governance Docs

- `AGENTS.md` already contained the approved governance updates at execution start:
  - major vs minor round naming convention
  - mandatory full-file `docs/architecture/tech_debt.md` review step during planning
  - debt-ID based planning discipline
- Builder verified those rules remained consistent with `PLAN.md`.
- No additional Builder-side edit to `AGENTS.md` was required in order to satisfy the approved process scope.

## Tests and Validation

- command: `python -m pytest tests/modules/test_scoring_context.py tests/api/test_scoring_context_routes.py tests/api/test_cv_ingest.py tests/api/test_cv_pdf_ingest.py tests/api/test_vertical_slice_api.py tests/api/test_candidate_list.py tests/modules/test_multi_candidate_registry.py tests/skills/test_llm_provider.py`
  - result: pass
  - notes: `51 passed, 1 skipped`
- command: `python -m pytest tests/api/test_candidate_actions.py tests/persistence/test_sqlite_cv_extensions.py -q`
  - result: pass
  - notes: `7 passed`
- command: `python -m pytest -q`
  - result: pass
  - notes: `164 passed, 2 skipped, 11 warnings`
- command: `ReadLints` on changed files
  - result: pass
  - notes: no linter errors found

## Deviations, Risks, and Follow-Up

- Deviation from `PLAN.md`:
  - none in scope or architecture posture
- Explicit confirmations:
  - debt handling remained Architect-planned and PM-approved; Builder did not perform execution-time debt replanning
  - no new capability scope was introduced beyond `R-004`
- Remaining open risks:
  - single active `scoring_context` remains a global runtime singleton
  - deep scoring remains deterministic/fake rather than real bounded cognition
  - `candidate_rejected` remains publicly writable and was intentionally left outside this round's internal-workflow-event removal list
  - provider/runtime scoring failures still collapse to coarse `scoring_failed` behavior

