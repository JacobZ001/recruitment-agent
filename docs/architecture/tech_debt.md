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

## Contract Evolution

### Typed payload contracts (events + skill IO)
- **Status**: OPEN
- **Introduced in**: 2026-05-08
- **Last reviewed**: 2026-05-08
- **Current decision**: Keep `payload: Dict[str, Any]` in event payloads and skill IO envelopes for v1.
- **Rationale**: Allows rapid iteration while vocabulary stabilizes and avoids premature coupling between the orchestrator, skills, and schema packages. Typed payloads are valuable, but they are expensive to maintain if domain concepts are still shifting.
- **Future impact**: Weak payload typing reduces compile-time safety, increases contract drift risk, and makes replay/debugging dependent on implicit payload conventions.
- **Priority**: High
- **Recommended future direction**: Introduce typed payload models progressively:
  - Start with per-event payload schemas (e.g., discriminated unions keyed by `EventType`) and enforce via schema validation/harness.
  - For skills, consider generic typed envelopes (e.g., `SkillInput[T]`, `SkillOutput[T]`) for high-value, stable payload shapes.
  - Require versioned contracts + harness coverage for all typed payload migrations.

### Interface and schema versioning strategy
- **Status**: OPEN
- **Introduced in**: 2026-05-08
- **Last reviewed**: 2026-05-08
- **Current decision**: Use lightweight, explicit version fields (e.g., `schema_version` / `interface_version`) with conservative backward compatibility, and avoid building heavy version negotiation infrastructure in v1.
- **Rationale**: Deterministic-first orchestration depends on stable contracts for replay and audit. However, early-stage product learning requires iteration speed; a minimal versioning approach keeps contracts explicit while avoiding premature framework complexity.
- **Future impact**: Without a clear compatibility governance policy:
  - Replay consistency can break when historical events/interfaces are interpreted under newer code paths.
  - Event/schema evolution may introduce silent contract drift across producers/consumers.
  - Orchestrator upgrades become risky (mixed-version skills/events, unclear migration boundaries).
  - Deprecations may be ad-hoc, reducing auditability and long-term interpretation stability.
- **Priority**: High
- **Recommended future direction**: Define a production-grade compatibility governance policy (still lightweight in mechanics):
  - **Backward compatibility guarantees**: Document what is guaranteed across patch/minor/major version changes (e.g., additive fields only in minor; breaking changes require major).
  - **Replay interpretation stability**: Establish rules for how historical events are interpreted (e.g., “interpret using schema version at emission time” + explicit upcasters in deterministic code when needed).
  - **Orchestrator upgrade safety**: Require compatibility tests/harness coverage before upgrading orchestrator/skill versions; document expected mixed-version behavior.
  - **Deprecation policy**: Define deprecation windows and required migration artifacts (mapping docs, upcasters/adapters, and audit notes).
  - **Migration + version negotiation expectations**: Prefer explicit version pinning per contract boundary (event schema, state schema, skill interface) and deterministic adapters over implicit negotiation.

### Potential migration from `Dict[str, Any]` to stricter structures (`extensions` governance)
- **Status**: OPEN
- **Introduced in**: 2026-05-08
- **Last reviewed**: 2026-05-08
- **Current decision**: Use explicit `extensions: Dict[str, Any]` as the forward-compatible escape hatch.
- **Rationale**: Prevents silent schema drift while still allowing controlled extension during early evolution.
- **Future impact**: Overuse can recreate an untyped “blob” domain and erode verifiability.
- **Priority**: High
- **Recommended future direction**: Establish rules: `extensions` only for staged fields; graduate to typed fields with a version bump + harness coverage.

### Timezone-aware datetime handling
- **Status**: OPEN
- **Introduced in**: 2026-05-08
- **Last reviewed**: 2026-05-08
- **Current decision**: Some schemas still use naive UTC timestamp defaults for v1.
- **Rationale**: Simple, consistent early implementation; avoids TZ conversion bugs before requirements are clear.
- **Future impact**: Ambiguity when integrating external systems; harder compliance/time-based reporting and cross-system correlation.
- **Priority**: High
- **Recommended future direction**: Use timezone-aware UTC (`datetime.now(timezone.utc)`) and validate/serialize consistently across services.

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

## Execution Architecture

### Future orchestration replay tooling
- **Status**: OPEN
- **Introduced in**: 2026-05-08
- **Last reviewed**: 2026-05-08
- **Current decision**: Store immutable events and correlation/causation ids; do not build replay tooling yet.
- **Rationale**: Tooling is expensive; first stabilize contracts and deterministic state transitions.
- **Future impact**: Harder debugging/timeline reconstruction at scale without replay automation.
- **Priority**: High
- **Recommended future direction**: Build a “replay runner” that rehydrates `OrchestrationState` from an event stream with strict validation and deterministic logs.

### Shared execution metadata structures
- **Status**: OPEN
- **Introduced in**: 2026-05-08
- **Last reviewed**: 2026-05-08
- **Current decision**: Keep execution metadata (trace/request/correlation/causation ids, actor ids, event/execution ids, tags) defined per interface/schema layer, with explicit fields and `extensions` as the escape hatch.
- **Rationale**: Execution metadata needs differ across events, skills, and state transitions. Early consolidation risks hidden coupling and accidental “global context” creep.
- **Future impact**: Observability and audit trails may become inconsistent across events vs. skill runs (different naming, missing links), reducing replayability and root-cause analysis quality.
- **Priority**: High
- **Recommended future direction**: Introduce a shared “execution identifiers” contract (trace/request/correlation/causation/event/execution ids + actor) that can be embedded by composition in events, skill results, and transition records—without adding orchestration logic. Validate link completeness via the harness.

### Future shared timing/audit abstractions
- **Status**: OPEN
- **Introduced in**: 2026-05-08
- **Last reviewed**: 2026-05-08
- **Current decision**: Timing and audit fields are currently modeled independently per contract (events, state, skills) with only minimal alignment.
- **Rationale**: The project is still discovering which timing/audit fields are truly universal (e.g., started_at/ended_at vs. recorded_at vs. updated_at).
- **Future impact**: Harder to correlate timelines across layers (event timestamps vs. skill execution timing vs. state updates), increasing debugging and compliance effort.
- **Priority**: Medium
- **Recommended future direction**: Define shared `ExecutionTiming` / `ExecutionAudit` building blocks once the minimum required set is proven across at least two subsystems; preserve deterministic-first principles by keeping all audit/timing as *recorded facts* rather than auto-mutating behavior.

### Future shared failure taxonomy consolidation
- **Status**: OPEN
- **Introduced in**: 2026-05-08
- **Last reviewed**: 2026-05-08
- **Current decision**: Maintain localized failure enums/taxonomies (events vs. messaging vs. skill execution) to avoid prematurely locking in semantics.
- **Rationale**: Failures have different remediation paths depending on layer (validation vs. dependency vs. timeout vs. policy), and the system does not yet have stable operational playbooks.
- **Future impact**: Inconsistent failure categorization complicates alerting, SLO reporting, and deterministic replay (different “retryable” or “transient” meanings).
- **Priority**: High
- **Recommended future direction**: Consolidate to a single failure taxonomy with clear layer-agnostic definitions (category/code/message/details_ref + retryability as a signal only). Enforce mapping rules in deterministic code (not prompts) and validate via the harness.

### Potential async skill execution migration
- **Status**: OPEN
- **Introduced in**: 2026-05-08
- **Last reviewed**: 2026-05-08
- **Current decision**: Keep skill execution synchronous at the contract level (bounded call returning a result), and represent longer workflows via event-driven orchestration rather than async skill interfaces.
- **Rationale**: Deterministic orchestration + replayability is easier when skills are bounded and results are recorded as immutable facts; async interfaces can hide partial state and complicate auditability.
- **Future impact**: Some skills may naturally be long-running (external parsing, integrations, human-in-the-loop). Without an async pathway, the orchestrator may need wrapper patterns that encode progress as events.
- **Priority**: Medium
- **Recommended future direction**: If needed, migrate via an *execution envelope* pattern: synchronous “start” skill emits an execution id + references; progress/completion is represented as events/results with the same contract invariants. Avoid embedding routing/retry/state transitions into the skill interface.

### Shared confidence abstraction consolidation
- **Status**: OPEN
- **Introduced in**: 2026-05-08
- **Last reviewed**: 2026-05-08
- **Current decision**: Keep confidence concepts local to each contract layer (e.g., candidate confidence vs. skill execution confidence) until the semantics stabilize.
- **Rationale**: Confidence is overloaded early (model confidence vs. data completeness vs. human certainty). Premature consolidation risks forcing a misleading “one-size-fits-all” meaning.
- **Future impact**: Fragmentation across schemas/interfaces makes aggregation, calibration, and governance reporting harder (different fields, ranges, and rationale representations).
- **Priority**: Medium
- **Recommended future direction**: Define a shared confidence contract (score/level/rationale_ref + extensions) once at least 2–3 stable confidence use-cases converge; migrate via backward-compatible adapters and harness checks.

### Evidence reference standardization (domain + execution)
- **Status**: OPEN
- **Introduced in**: 2026-05-08
- **Last reviewed**: 2026-05-08
- **Current decision**: Allow evidence references to remain heterogeneous while storage/provenance decisions evolve (e.g., `List[str]` in domain records; structured evidence objects in some execution contracts).
- **Rationale**: The system needs evidence *referencing* immediately for auditability and explainability, but the evidence lifecycle (storage, hashing, provenance, access control) is not yet standardized. Keeping the shape flexible avoids premature coupling to a global storage model.
- **Future impact**: Divergent evidence shapes across layers can produce brittle tooling (replay viewers, explainability UIs, audits), inconsistent provenance tracking, and ad-hoc normalization logic.
- **Priority**: High
- **Recommended future direction**: Establish a single evidence reference contract usable across schemas and execution results (kind/ref/hash/created_at/provenance/extensions) and migrate gradually:
  - Permit dual representations during transition (strings + structured).
  - Centralize deterministic normalization/mapping rules in the deterministic layer (not prompts).
  - Validate via harness to prevent silent drift.

## Domain Vocabulary

### Shared domain vocabulary package (enums + stable string vocab)
- **Status**: OPEN
- **Introduced in**: 2026-05-08
- **Last reviewed**: 2026-05-08
- **Current decision**: Enums exist per schema module without a shared vocabulary package; some fields intentionally remain free-form `str` to avoid premature enum fragmentation.
- **Rationale**: Vocabulary evolves with product learning. Centralizing too early creates churn and accidental coupling across schemas.
- **Future impact**: Divergence risk increases (similar concepts named differently across schemas), and integrations may depend on inconsistent strings.
- **Priority**: Medium
- **Recommended future direction**: Establish a `schemas/domain/` vocabulary package that includes stable enums, string vocab registries, and backward-compatible aliases. Promote entries only when they are proven stable and covered by harness validation.

## Operational Governance

### Shared abstraction over-centralization risk
- **Status**: OPEN
- **Introduced in**: 2026-05-08
- **Last reviewed**: 2026-05-08
- **Current decision**: Prefer bounded duplication over premature “shared everything” abstractions. Shared packages must be earned by repeated, stable usage.
- **Rationale**: Over-centralized schema/contract packages create tight coupling, slow iteration, and make local changes harder to validate. The deterministic-first philosophy benefits from explicit, local contracts with clear validation and audit trails.
- **Future impact**: Premature consolidation can cause:
  - Cascading breaking changes across unrelated subsystems.
  - “Global context” creep where contracts become implicit rather than verifiable.
  - Reduced replayability/auditability due to hidden cross-module dependencies.
- **Priority**: High
- **Recommended future direction**: Adopt a consolidation gate:
  - Require 2–3 independent call sites with stable semantics + harness coverage before extracting a shared abstraction.
  - Prefer composition (small shared “building blocks”) over inheritance-heavy global base classes.
  - Keep shared modules thin, versioned, and backward compatible; explicitly document invariants and migration paths.

### Automatic `updated_at` handling via service/orchestrator layer
- **Status**: OPEN
- **Introduced in**: 2026-05-08
- **Last reviewed**: 2026-05-08
- **Current decision**: Schemas default timestamps but do not auto-mutate; services must set `updated_at`.
- **Rationale**: Preserves deterministic behavior and avoids hidden side effects in schema constructors.
- **Future impact**: Inconsistent updates if services forget; audit trails become less reliable.
- **Priority**: High
- **Recommended future direction**: Enforce timestamp updates in a single service-layer write path (repository pattern / unit-of-work) with tests and audit logging.

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

### Future event sourcing optimization
- **Status**: OPEN
- **Introduced in**: 2026-05-08
- **Last reviewed**: 2026-05-08
- **Current decision**: Model event schema for auditability, not throughput.
- **Rationale**: Early-stage correctness > storage/compute optimization.
- **Future impact**: Potentially higher storage costs and slower queries as volume grows.
- **Priority**: Medium
- **Recommended future direction**: Partition/cluster events by `candidate_id`/`correlation_id`, add indexing strategy, and evaluate append-only storage patterns.

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
