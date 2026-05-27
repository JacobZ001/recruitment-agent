# FEEDBACK (Round R-006)

## Execution Status

- status: done
- blocker: none

## Plan Step Mapping

- Step 1: done - Hardened `modules/recruitment/policies.py` into the canonical recruiter-action projection layer. Recruiter actions are still derived from transition-registry truth, but now carry deterministic `group` and `order` metadata and can evaluate guards through `TransitionEngine`.
- Step 2: done - Aligned `GET /candidates` and `GET /candidate/{candidate_id}` to the same recruiter-action source. Candidate detail now exposes structured `available_actions`, and compatibility `next_actions` is derived from those canonical actions instead of a static phase-hint map.
- Step 3: done - Added deterministic recruiter action payload validation keyed by recruiter `event_type` before publish. The current bounded action set validates through a per-event registry and returns stable `invalid_candidate_action_payload` errors for malformed payloads.
- Step 4: done - Updated `perform_candidate_action(...)` / `POST /candidates/{candidate_id}/action` to use the same canonical recruiter-action semantics as list/detail, including guard-aware availability and pre-publish payload validation.
- Step 5: done - Kept the recruiter-facing demo surface aligned with hardened API semantics by rendering canonical `available_actions` and letting `next_actions` reflect the same source.
- Step 6: done - Added focused regression coverage for recruiter list/detail/action parity, deterministic action metadata ordering/grouping, stable bad-payload failures, and guard-aware availability consistency.

## Full File Change List

- M `docs/architecture/tech_debt.md` - Resolved `TD-API-008`, `TD-API-009`, `TD-API-010`, and `TD-API-013` to reflect the completed recruiter-surface hardening slice.
- M `integrations/api/demo_page.py` - Rendered canonical recruiter `available_actions` metadata in the demo recruiter surface.
- M `integrations/api/errors.py` - Added stable HTTP mapping for `invalid_candidate_action_payload`.
- M `integrations/api/schemas_http.py` - Added `group` / `order` to `RecruiterActionItem` and added `available_actions` to candidate detail responses.
- M `modules/recruitment/__init__.py` - Exported the new recruiter action payload validation exception.
- M `modules/recruitment/exceptions.py` - Added `InvalidRecruiterActionPayloadError`.
- M `modules/recruitment/policies.py` - Centralized recruiter-action derivation, metadata ordering/grouping, guard-aware validation, and per-event payload validator registry.
- M `modules/recruitment/projection.py` - Made list/detail recruiter surfaces consume the same canonical action source and removed static `next_actions` authority.
- M `modules/recruitment/use_cases.py` - Made recruiter action POST use canonical action validation plus deterministic payload validation before publish.
- M `tests/api/test_candidate_actions.py` - Added recruiter list/detail parity and stable bad-payload coverage.
- M `tests/api/test_demo_recruiter_surface.py` - Updated recruiter detail expectations for canonical `available_actions` / derived `next_actions`.
- M `tests/modules/test_recruiter_actions_from_registry.py` - Added ordering/grouping assertions and guard-aware recruiter action coverage.

## Exact Recruiter-Action Source Of Truth Before / After

### `GET /candidates`

- before:
  - `available_actions` came from `get_available_actions_for_phase(phase)`
  - availability was registry-derived, but sorted alphabetically by `event_type`
  - no `group` / `order` metadata
  - no guard-aware filtering
- after:
  - `available_actions` still come from transition-registry truth only
  - action projection now validates each candidate action path through `TransitionEngine`
  - response items include:
    - `key`
    - `label`
    - `event_type`
    - `group`
    - `order`
  - ordering is deterministic and policy-shaped, not raw alphabetical sorting
  - guarded actions disappear when the same canonical validation path rejects them

### `GET /candidate/{candidate_id}`

- before:
  - detail view had no structured recruiter action list
  - `next_actions` came from a static `_next_actions_for_phase(...)` hint table
  - detail action hints could drift from candidate list action availability
- after:
  - detail view now includes canonical `available_actions` using the same projection path as `GET /candidates`
  - compatibility `next_actions: List[str]` is derived from the canonical action list (`label` only), not from a separate static phase map
  - detail and list now expose the same recruiter-action truth for the same candidate phase/snapshot context

### `POST /candidates/{candidate_id}/action`

- before:
  - validated recruiter action availability by phase only
  - payload remained effectively untyped at the recruiter action boundary
  - malformed payloads were deferred into downstream planning/parsing behavior
- after:
  - validates the requested recruiter action through the same canonical action source used by list/detail
  - uses snapshot extensions when evaluating guarded action availability
  - validates the merged governance payload via a deterministic per-event payload validator registry before publish
  - returns stable `422` with `detail.code = "invalid_candidate_action_payload"` when the recruiter payload shape is invalid

## Exact Action Metadata Added / Changed

Canonical recruiter action metadata now includes:

- `label` - recruiter-facing label, still descriptor-backed with fallback to `label_from_event_type(...)`
- `group` - deterministic category used for recruiter presentation:
  - `decision`
  - `interview`
  - `offer`
  - `recovery`
- `order` - deterministic sort order used before label / event-type tie-breakers

Current bounded recruiter action ordering behavior:

- `recruiter_reconsider_candidate` -> `order=10`, `group="recovery"`
- shortlist / approve style actions -> `order=20`, `group="decision"`
- `recruiter_schedule_interview` -> `order=30`, `group="interview"`
- `recruiter_complete_interview` -> `order=40`, `group="interview"`
- `recruiter_send_offer` -> `order=50`, `group="offer"`
- `recruiter_mark_hired` -> `order=60`, `group="offer"`
- `recruiter_reject_candidate` -> `order=90`, `group="decision"`
- uncatalogued recruiter actions still fall back deterministically for label/group/order without becoming a second availability map

Compatibility note:

- `next_actions` remains present on candidate detail, but it is now only a compatibility projection derived from canonical `available_actions`.

## Exact Payload Validation Behavior Added / Changed Per Recruiter `event_type`

Current recruiter action payload validator registry covers:

- `recruiter_shortlist_candidate`
- `recruiter_reject_candidate`
- `recruiter_schedule_interview`
- `recruiter_complete_interview`
- `recruiter_send_offer`
- `recruiter_reconsider_candidate`
- `recruiter_approve_candidate`
- `recruiter_mark_hired`

For the current bounded recruiter action set:

- all listed recruiter actions validate against the shared bounded governance payload contract before publish
- API defaults are still merged first (`actor_id`, `actor_type`, `reason`, `evidence_refs`)
- extra/unknown payload fields now fail fast at the recruiter action boundary
- malformed payloads now produce stable `422` responses instead of relying on planner-time parse fallout

What did *not* change in this round:

- no new recruiter action business fields were introduced
- no new recruiter actions were added
- no new workflow states/phases or transition rules were added

## Exact Detail-View `next_actions` Semantics Before / After

- before:
  - `next_actions` was a static phase→string-hint table in `modules/recruitment/projection.py`
  - `new` phase returned `[]` even though recruiter rejection was already a valid registry-derived action on the list surface
  - detail semantics were explicitly non-authoritative and could drift from actual action availability
- after:
  - `next_actions` is derived directly from canonical `available_actions`
  - `new` phase now truthfully reflects the currently available recruiter action labels
  - detail keeps backward-compatible string output while structured recruiter clients can use `available_actions`

## Exact Guard-Aware Behavior Added

- default reference registry behavior:
  - remains effectively unguarded for the current default recruiter-facing rules
  - no new business policy or new guards were forced into the default registry just to satisfy this round
- added infrastructure behavior:
  - recruiter action projection can now evaluate `guard_ids` through `TransitionEngine`
  - recruiter list/detail exposure and recruiter action POST validation use the same guard-aware path
  - snapshot extensions are passed into action validation so guarded rules can inspect deterministic context
- test proof added:
  - custom registry fixture adds a guard to `pipeline.shortlisted_to_interview_pending`
  - projected availability hides `recruiter_schedule_interview` when the guard rejects
  - `validate_recruiter_event_for_phase(...)` rejects the same action with a `currently unavailable` error under the same guard outcome

## Exact Tests Added / Updated

- `tests/modules/test_recruiter_actions_from_registry.py`
  - asserts action metadata now includes deterministic `group` / `order`
  - proves guarded availability projection and POST-time validation stay aligned
- `tests/api/test_candidate_actions.py`
  - proves candidate list and detail use the same canonical recruiter-action semantics
  - proves invalid recruiter payloads return stable `invalid_candidate_action_payload`
- `tests/api/test_demo_recruiter_surface.py`
  - updates candidate detail expectations for canonical `available_actions`
  - proves `next_actions` is derived from canonical action labels instead of a static hint table

Validation run:

- `python -m pytest tests/modules/test_recruiter_actions_from_registry.py tests/api/test_candidate_actions.py tests/api/test_candidate_list.py tests/api/test_demo_recruiter_surface.py -q`
  - result: `35 passed`
- `python -m pytest -q`
  - result: `171 passed, 2 skipped, 13 warnings`
  - warnings remain the existing Pydantic `datetime.utcnow()` deprecation warnings

## Technical Debt Updates Made

- reviewed and updated:
  - `TD-API-008` -> resolved by canonical guard-aware recruiter action projection
  - `TD-API-009` -> resolved by deterministic recruiter action payload validator registry
  - `TD-API-010` -> resolved by canonical `group` / `order` recruiter action metadata
  - `TD-API-013` -> resolved by deriving detail `next_actions` from canonical recruiter action items
- deferred unchanged:
  - `TD-ORCHESTRATOR-011`
  - `TD-API-011`
  - `TD-API-012`
  - `TD-INSPECTION-002`
  - `TD-INSPECTION-003`
  - `TD-API-007`

## Scope Confirmation

- no new workflow states/phases were added
- no new recruiter actions were added
- no transition registry redesign was introduced
- no broad API hardening work (`TD-API-011`, `TD-API-012`) was pulled into this round
- no timeline/history hardening work (`TD-INSPECTION-002`, `TD-INSPECTION-003`) was pulled into this round
- no hard-filter restoration work (`TD-ORCHESTRATOR-011`) was pulled into this round
- no auth, multi-tenant, or runtime-isolation redesign was added to `R-006`

## Suggested Next-Round Focus

- Open **R-007** as the next major round on **Recruiter frontend MVP** (Upcoming queue item 2): candidate list, detail, and recruiter actions wired to hardened APIs; defer timeline/idempotency/hard-filter scope unless PM reprioritizes.

## Roadmap Updates Made (Architect Reconciliation)

- `Current Operating Posture`: notes canonical recruiter API hardening and frontend MVP as near-term focus.
- `Human Governance`: guard-aware recruiter action availability and typed recruiter action payloads moved from `Gap` to `Partial`.
- `Upcoming`: removed completed **Recruiter surface hardening** item; renumbered remaining queue.
