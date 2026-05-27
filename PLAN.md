# PLAN (Round R-006)

## Round Type

- Type: **Major round** (new capability round)
- Naming practice (governance rule):
  - **Major rounds** (`R003`, `R004`, `R005`, `R006`, ...) add scope/capabilities.
  - **Minor rounds** (`R005.1`, `R005.2`, ...) refine/fix within an existing major round without adding new capability scope.

## Routing Context

- Proposed routing outcome from prior closeout: `advance-major`
- PM confirmed routing: `advance-major`
- Major-round snapshot needed: `yes`
- Routing rationale: `R-005` closed as a completed major round after the prose-first `scoring_context` cutover and its major-round snapshot. `R-006` opens a new major capability round focused on recruiter-facing surface hardening, with PM explicitly prioritizing recruiter operator surfaces over a strict top-to-bottom pass through the remaining roadmap queue.

## Planning-Phase Roadmap Alignment (Architect-Owned)

- `docs/architecture/ROADMAP.md` review is completed in planning.
- Selected `Upcoming (Action Queue)` item for this round:
  - **Recruiter surface hardening** (`TD-API-008`, `TD-API-009`, `TD-API-010`, `TD-API-013`)
- Capability areas advanced by this round:
  - `Recruiter Workflow Operation`
  - `Human Governance`
- Alignment rationale:
  - this round hardens recruiter-facing list/detail/action surfaces after `R-005` improved internal `scoring_context` discipline,
  - unifies recruiter action semantics across the public API surface,
  - and makes recruiter-visible workflow affordances reflect deterministic policy truth rather than static hints or loosely typed action posts.
- Queue note:
  - `ROADMAP.md` item 2 (`Deterministic hard-filter restoration`) remains valid, but PM explicitly selected recruiter-surface hardening as the next major round.

## Planning-Phase Debt Triage (Architect-Owned)

- `docs/architecture/tech_debt.md` review is completed by Architect during planning (before Builder execution starts).
- PM-approved debt handling for this round is frozen into this `PLAN.md`; Builder executes only those approved debt actions.
- Debt IDs selected for this round:
  - `TD-API-008` - make recruiter action availability capable of reflecting transition-guard truth rather than only phase-level registry matching
  - `TD-API-009` - add deterministic per-action payload validation at the recruiter action boundary
  - `TD-API-010` - add deterministic action ordering/grouping metadata without introducing a duplicate phase-action map
  - `TD-API-013` - remove static `next_actions` drift from candidate detail surfaces
- Debt IDs explicitly deferred this round:
  - `TD-ORCHESTRATOR-011` - deterministic hard-filter restoration remains a separate roadmap round
  - `TD-API-011`, `TD-API-012` - broad API hardening remains a separate round
  - `TD-INSPECTION-002`, `TD-INSPECTION-003` - candidate-scoped timeline/history work remains a separate round
  - `TD-API-007` - recruiter action label ownership / copy strategy remains deferred unless minimally needed for parity in this bounded slice
- Debt status corrections made during sweep:
  - none planned in advance; update only if implementation reality explicitly resolves or supersedes an entry touched by this round

## Goal

Introduce a bounded recruiter-surface hardening vertical slice: `GET /candidates`, `GET /candidate/{candidate_id}`, and `POST /candidates/{candidate_id}/action` should all consume the same deterministic recruiter-action semantics, candidate detail should stop relying on static action hints as its authoritative source, and recruiter action payloads should validate through programmatic per-event rules before publish.

## Scope In

- Unify recruiter-facing action derivation for:
  - `GET /candidates`
  - `GET /candidate/{candidate_id}`
  - `POST /candidates/{candidate_id}/action`
- Introduce a canonical deterministic recruiter-action descriptor/projection layer driven from transition-registry truth rather than a second phase-to-action table.
- Replace static detail-view `next_actions` drift with data derived from the same canonical action source used by recruiter list/detail/action flows.
- Add deterministic recruiter action metadata needed for ordering/grouping in recruiter-facing API surfaces.
- Add deterministic per-action payload validation keyed by recruiter `event_type`, while preserving thin HTTP routes.
- Add focused tests proving recruiter list/detail/action parity, stable validation behavior, and preserved transition outcomes for the current action set.
- Keep the demo/recruiter presentation aligned if a recruiter-facing surface would otherwise drift from the hardened API semantics.

## Scope Out

- No new recruiter actions, pipeline phases, transition rules, or orchestration-state redesign.
- No broad API hardening (`TD-API-011`, `TD-API-012`).
- No timeline/history hardening (`TD-INSPECTION-002`, `TD-INSPECTION-003`).
- No auth/RBAC, multi-tenant, or runtime-isolation work.
- No deterministic hard-filter restoration (`TD-ORCHESTRATOR-011`).
- No deep-scoring / questionnaire continuity redesign.

## Constraints

- Deterministic ownership remains in program logic:
  - recruiter action availability, validation, and ordering must remain programmatic,
  - prompts / LLMs must **not** own recruiter action semantics, routing, or guard evaluation.
- Transition-registry truth remains canonical for recruiter action availability; do **not** introduce a second authoritative phase→action mapping table.
- Keep API routes thin:
  - recruiter-action derivation and payload validation belong in deterministic recruitment modules,
  - not inside FastAPI route handlers.
- Preserve compatibility where reasonable:
  - prefer deriving the existing `next_actions: List[str]` detail surface from canonical recruiter-action data before widening public response shape.
- Guard-aware hardening should be real, but bounded:
  - if the default recruiter-facing rules remain unguarded in this round, prove guard-aware behavior with targeted registry/fixture tests rather than by forcing new business policy into the default registry.
- Existing valid shortlist / interview / offer / reject / reconsider flows must preserve current deterministic transition behavior.

## Execution Steps

1. **Introduce a canonical recruiter-action projection layer**
   - Create one deterministic recruiter-action source that derives actions from transition-registry truth.
   - Ensure it can carry recruiter-safe metadata such as:
     - `label`
     - optional grouping/category metadata
     - optional deterministic sort/order metadata
   - Keep registry truth canonical; do **not** reintroduce a duplicate phase-action map.

2. **Align recruiter list and detail surfaces to the same source**
   - Make `GET /candidates` and `GET /candidate/{candidate_id}` consume the same underlying recruiter-action semantics.
   - Remove the authoritative role of static `_next_actions_for_phase(...)`-style detail hints.
   - Keep detail-view compatibility as much as possible by deriving current `next_actions` strings from canonical action items unless a response-shape widening is clearly justified.

3. **Add deterministic recruiter action payload validation**
   - Introduce a deterministic action-payload schema / validator registry keyed by recruiter `event_type`.
   - Validate recruiter action payloads at the API/use-case boundary before publish.
   - Keep unstructured payloads only for actions that truly remain payload-light in this bounded slice.

4. **Make recruiter action POST consume the same canonical action semantics**
   - Keep `POST /candidates/{candidate_id}/action` aligned with the same canonical recruiter-action source used by list/detail surfaces.
   - Ensure advertised availability and POST-time validation stay consistent.
   - Add guard-aware plumbing so recruiter surfaces can stay truthful when guarded rules exist.

5. **Preserve recruiter-surface truth across nearby surfaces**
   - Align any recruiter-facing demo/API surface that would otherwise drift from the canonical recruiter-action source after this round.
   - Keep this bounded to recruiter-surface truthfulness, not broader demo/runtime redesign.

6. **Test the bounded recruiter surface hardening slice**
   - Add/adjust tests for:
     - recruiter list/detail/action parity,
     - deterministic action ordering/grouping metadata,
     - per-action payload validation and stable error behavior,
     - guard-aware availability behavior (including fixture/registry-based coverage if default rules stay unguarded),
     - preserved valid shortlist/interview/offer/reject/reconsider flows.

## Acceptance Criteria

- [ ] `GET /candidates` and `GET /candidate/{candidate_id}` are driven by the same deterministic recruiter-action source.
- [ ] Candidate detail no longer relies on static phase-based `next_actions` hints as the authoritative action surface.
- [ ] `POST /candidates/{candidate_id}/action` validates payload shape per recruiter `event_type` through deterministic program logic and returns stable validation errors for bad payloads.
- [ ] Recruiter action ordering is deterministic and policy-shaped rather than raw alphabetical `event_type` sorting.
- [ ] If a guarded recruiter action rule exists, recruiter surfaces and action POST behavior remain consistent with the same rule outcome.
- [ ] Existing valid shortlist / interview / offer / reject / reconsider flows preserve their current deterministic transition behavior.
- [ ] No unrelated roadmap items are pulled into `R-006` scope:
  - no hard-filter restoration,
  - no broad API hardening,
  - no timeline/history hardening,
  - no auth/multi-tenant/runtime-isolation redesign.

## Required Builder Feedback

Builder Agent must overwrite `FEEDBACK.md` and include:

- round status (`done` / `partial` / `blocked`) and blockers
- step-by-step mapping against the 6 execution steps above
- full file change list (`A` / `M` / `D`)
- exact recruiter-action source-of-truth behavior before/after for:
  - `GET /candidates`
  - `GET /candidate/{candidate_id}`
  - `POST /candidates/{candidate_id}/action`
- exact action metadata added/changed for recruiter surfaces (labels, grouping, ordering, compatibility notes)
- exact payload validation behavior added/changed per recruiter `event_type`
- exact detail-view `next_actions` semantics before/after
- exact guard-aware behavior added, including whether the default registry remained unguarded and how guarded semantics were tested
- exact tests added/updated for recruiter list/detail/action parity and stable validation behavior
- technical debt updates made (items reviewed, changed, deferred, or resolved)
- confirmation that no new workflow states/phases or unrelated ingress/runtime hardening work were added to `R-006`
