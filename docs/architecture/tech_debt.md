# BlueOcean Recruitment Agent — Architecture Debt Registry

Purpose: track deferred architecture improvements, scaling risks, and engineering rationale so we don’t lose critical future considerations. This project prioritizes **deterministic orchestration** and **verifiable behavior** over “smart prompts”.

## Debt lifecycle

- **OPEN**: identified, not started
- **IN_PROGRESS**: actively being addressed
- **RESOLVED**: implemented and verified
- **SUPERSEDED**: replaced by a different approach/decision

## Registry entry format

- **Status**: OPEN | IN_PROGRESS | RESOLVED | SUPERSEDED
- **Introduced in**: date or milestone (e.g. 2026-05-08 / v0.1)
- **Last reviewed**: date
- **Owner** (optional): team/person
- **Current decision**
- **Rationale**
- **Future impact**
- **Priority**: High | Medium | Low
- **Recommended future direction**

## Future Enhancements

### Typed payload schemas for events
- **Status**: OPEN
- **Introduced in**: 2026-05-08
- **Last reviewed**: 2026-05-08
- **Current decision**: Keep `payload: Dict[str, Any]` in `OrchestrationEvent` for v1.
- **Rationale**: Allows rapid iteration while the event vocabulary stabilizes; avoids premature coupling to evolving structures.
- **Future impact**: Weak payload typing reduces compile-time safety and can hide contract drift.
- **Priority**: High
- **Recommended future direction**: Introduce typed payload models per `EventType` (e.g., discriminated unions) and enforce via schema validation/harness.

### Future orchestration replay tooling
- **Status**: OPEN
- **Introduced in**: 2026-05-08
- **Last reviewed**: 2026-05-08
- **Current decision**: Store immutable events and correlation/causation ids; do not build replay tooling yet.
- **Rationale**: Tooling is expensive; first stabilize contracts and deterministic state transitions.
- **Future impact**: Harder debugging/timeline reconstruction at scale without replay automation.
- **Priority**: High
- **Recommended future direction**: Build a “replay runner” that rehydrates `OrchestrationState` from an event stream with strict validation and deterministic logs.

### Future event sourcing optimization
- **Status**: OPEN
- **Introduced in**: 2026-05-08
- **Last reviewed**: 2026-05-08
- **Current decision**: Model event schema for auditability, not throughput.
- **Rationale**: Early-stage correctness > storage/compute optimization.
- **Future impact**: Potentially higher storage costs and slower queries as volume grows.
- **Priority**: Medium
- **Recommended future direction**: Partition/cluster events by `candidate_id`/`correlation_id`, add indexing strategy, and evaluate append-only storage patterns.

## Scaling Risks

### Future read-model separation
- **Status**: OPEN
- **Introduced in**: 2026-05-08
- **Last reviewed**: 2026-05-08
- **Current decision**: Candidate aggregate may contain optional snapshots/refs; no dedicated read models yet.
- **Rationale**: Keep architecture simple until real query patterns and UI needs emerge.
- **Future impact**: Mixed read/write concerns can slow product iteration and complicate performance tuning.
- **Priority**: High
- **Recommended future direction**: Separate write-side contracts (events/state) from read-side projections (query-optimized materializations).

### Potential migration from `Dict[str, Any]` to stricter structures
- **Status**: OPEN
- **Introduced in**: 2026-05-08
- **Last reviewed**: 2026-05-08
- **Current decision**: Use explicit `extensions: Dict[str, Any]` as the forward-compatible escape hatch.
- **Rationale**: Prevents silent schema drift while still allowing controlled extension.
- **Future impact**: Overuse can recreate an untyped “blob” domain and erode verifiability.
- **Priority**: High
- **Recommended future direction**: Establish rules: `extensions` only for staged fields; graduate to typed fields with a version bump + harness coverage.

## Schema Improvements

### Timezone-aware datetime handling
- **Status**: OPEN
- **Introduced in**: 2026-05-08
- **Last reviewed**: 2026-05-08
- **Current decision**: Use naive UTC `datetime.utcnow()` defaults for v1 schema timestamps.
- **Rationale**: Simple, consistent in early implementation; avoids TZ conversion bugs before requirements are clear.
- **Future impact**: Ambiguity when integrating external systems; more difficult compliance/time-based reporting.
- **Priority**: High
- **Recommended future direction**: Use timezone-aware UTC (`datetime.now(timezone.utc)`) and validate/serialize consistently across services.

### Shared domain vocabulary enums across schemas
- **Status**: OPEN
- **Introduced in**: 2026-05-08
- **Last reviewed**: 2026-05-08
- **Current decision**: Enums exist per schema module (state/event/candidate) without a shared domain package. Some fields intentionally remain `str` (e.g., `HumanDecision.decision_type`) to avoid premature enum fragmentation.
- **Rationale**: Faster iteration while vocabulary stabilizes.
- **Future impact**: Divergence risk (e.g., similar concepts named differently across schemas).
- **Priority**: Medium
- **Recommended future direction**: Create a shared `schemas/domain_enums.py` (or equivalent) and consolidate stable vocabularies with backward-compatible aliases.

### Typed profile links instead of `List[str]`
- **Status**: OPEN
- **Introduced in**: 2026-05-08
- **Last reviewed**: 2026-05-08
- **Current decision**: Keep `external_profile_urls: List[str]` in `Identity`.
- **Rationale**: Low friction intake; link diversity is high early.
- **Future impact**: Harder validation/dedup and limited explainability (no typed semantics).
- **Priority**: Medium
- **Recommended future direction**: Replace with typed link objects (kind/provider/url, normalized handle, evidence refs).

### Typed recruiter feedback adjustments
- **Status**: OPEN
- **Introduced in**: 2026-05-08
- **Last reviewed**: 2026-05-08
- **Current decision**: Keep `RecruiterFeedback.adjustments: Dict[str, Any]`.
- **Rationale**: Recruiter calibration structures are still evolving.
- **Future impact**: Inconsistent adjustment semantics complicate calibration, analysis, and governance.
- **Priority**: High
- **Recommended future direction**: Define a small set of typed adjustment operations (e.g., `ScoreAdjustment`, `LabelOverride`, `RuleException`) and validate with a harness.

### Typed event payload structures
- **Status**: OPEN
- **Introduced in**: 2026-05-08
- **Last reviewed**: 2026-05-08
- **Current decision**: Same as “Typed payload schemas for events” (payload remains untyped for v1).
- **Rationale**: Avoid premature modeling.
- **Future impact**: Replay/debug depends on payload shape stability; untyped payload increases drift risk.
- **Priority**: High
- **Recommended future direction**: Add per-event payload schemas + strict validation; treat payload as a first-class contract.

## Architecture Refactors

### Potential future state transition typing improvements
- **Status**: OPEN
- **Introduced in**: 2026-05-08
- **Last reviewed**: 2026-05-08
- **Current decision**: `StateTransitionRecord` supports multiple domains using `state_domain` + validated `from_state`/`to_state` strings.
- **Rationale**: Avoids over-coupling while enabling cross-domain timeline reconstruction.
- **Future impact**: Less static type safety; domain expansion increases validator complexity.
- **Priority**: Medium
- **Recommended future direction**: Consider discriminated union transition records per domain (pipeline/decision/communication) with typed enums per record.

## Deferred Strict Typing

### Evidence references standardization
- **Status**: OPEN
- **Introduced in**: 2026-05-08
- **Last reviewed**: 2026-05-08
- **Current decision**: Use `List[str]` evidence references across records (scores/decisions/feedback/risk).
- **Rationale**: Keeps storage/indexing choices open while ensuring references are explicit.
- **Future impact**: Without a unified evidence reference schema, downstream tooling may fragment.
- **Priority**: Medium
- **Recommended future direction**: Introduce a typed `EvidenceRef` object (kind, ref, hash, provenance) and migrate gradually.

## Operational Concerns

### Automatic `updated_at` handling via service/orchestrator layer
- **Status**: OPEN
- **Introduced in**: 2026-05-08
- **Last reviewed**: 2026-05-08
- **Current decision**: Schemas default timestamps but do not auto-mutate; services must set `updated_at`.
- **Rationale**: Preserves deterministic behavior and avoids hidden side effects in schema constructors.
- **Future impact**: Inconsistent updates if services forget; audit trails become less reliable.
- **Priority**: High
- **Recommended future direction**: Enforce timestamp updates in a single service-layer write path (repository pattern / unit-of-work) with tests and audit logging.

