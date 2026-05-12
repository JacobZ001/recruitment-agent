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

### Event envelope payload governance
- **Status**: OPEN
- **Introduced in**: 2026-05-09
- **Last reviewed**: 2026-05-09
- **Current decision**: Keep event envelopes and payloads generic (`Dict[str, Any]`) for v1, but treat payload shape stability and hygiene as an explicit governance concern.
- **Rationale**: Deterministic replay/auditability requires that historical events remain interpretable over time. Even before typed payload schemas exist, we need explicit norms to prevent silent drift and accidental coupling to producer-specific quirks.
- **Future impact**: Without payload governance:
  - Historical event interpretation can break (replay consistency risk).
  - Producers/consumers may diverge on implicit payload contracts.
  - Debugging/audits degrade due to inconsistent evidence references or missing context.
- **Priority**: High
- **Recommended future direction**: Establish a payload governance checklist (lightweight, no overengineering):
  - Prefer **references** (artifact/evidence refs) over raw blobs.
  - Document required/optional keys per event type in a versioned contract note (even before full typing).
  - Add harness validation for payload invariants (presence, allowed types, key stability).
  - Introduce typed payload schemas progressively once shapes stabilize (per “Typed payload contracts”).

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

### Canonical workflow decision and rejection vocabulary governance
- **Status**: OPEN
- **Introduced in**: 2026-05-12
- **Last reviewed**: 2026-05-12
- **Current decision**: Fake deterministic vertical-slice skills (e.g. ``skills/deterministic/fake_hard_filter_skill.py``, ``skills/deterministic/fake_cv_uploaded_skill.py``) emit **local, machine-oriented reason codes** and **planner-aligned decision semantics** inside skill ``payload`` / ``extensions`` without a shared, versioned workflow ontology. The first vertical slice **intentionally** allows these **bounded local vocabularies** so runtime wiring, harness tests, and explainable pass/fail paths can iterate quickly before cognition layers land.
- **Rationale**: Preserves **deterministic-first** orchestration and **bounded** skill execution: programs still own transitions and routing; skills remain explainable via structured strings without prematurely freezing a global enum set while domain language is still moving.
- **Future impact**:
  - **Semantic drift across skills**: each fake (then real) skill may invent overlapping but non-equivalent codes for similar situations, complicating cross-pipeline reasoning.
  - **Inconsistent rejection terminology**: operators, audit UIs, and integrations may show divergent labels for the same underlying gate unless mappings are maintained by hand.
  - **Replay/audit ambiguity**: historical runs may be harder to interpret uniformly if reason codes lack stable cross-version definitions or canonical parents.
  - **Orchestration interpretation inconsistencies**: subscribers that branch on skill output strings may disagree with planner/event semantics unless contracts are centralized.
  - **Analytics fragmentation**: dashboards and warehouse models cannot rely on a single dimension for “why rejected” without ad-hoc normalization tables.
- **Priority**: Medium
- **Recommended future direction** (preserve deterministic-first posture, explainable workflow semantics, and bounded orchestration—**no** autonomous routing in vocabularies):
  - **Centralized canonical decision vocabularies**: small shared modules/schemas for pass/fail/no-op categories and workflow stage decisions, composed into skill outputs rather than ad-hoc literals.
  - **Stable rejection reason registries**: versioned registries (code → definition, severity, retryability *signal*, optional human-facing copy) with harness checks for unknown codes.
  - **Shared orchestration semantic contracts**: document how planner triggers, event types, and skill decision fields relate (e.g. explicit mapping tables, not implicit string equality in scattered handlers).
  - **Cross-skill vocabulary governance**: lint or CI rules for allowed prefixes/namespaces; deprecation windows when codes merge or split.
  - **Machine-readable workflow ontology/versioning**: optional ontology or graph metadata (versioned) for “allowed transitions × decision artifacts,” consumed by replay/reporting tools—not for LLM control.

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

### Shared delivery semantics taxonomy (event bus + handlers)
- **Status**: OPEN
- **Introduced in**: 2026-05-09
- **Last reviewed**: 2026-05-09
- **Current decision**: Keep delivery/ack semantics minimal and interface-scoped in v1 (e.g., `accepted/failed/rejected/skipped` + `ack/nack/drop`) without implementing broker-specific behavior.
- **Rationale**: The system needs consistent semantics for determinism, observability, and replay across subsystems, but the operational model (in-memory vs DB-backed vs broker-backed) is still evolving.
- **Future impact**: Without a shared, documented delivery taxonomy:
  - Components may interpret `skipped`, `rejected`, or `nack` differently (semantic drift).
  - Replay tooling and audit reports may misclassify failures vs intentional no-ops.
  - Orchestrator upgrade safety decreases due to inconsistent handling expectations.
- **Priority**: Medium
- **Recommended future direction**: Publish a small shared taxonomy (doc/module) defining:
  - Delivery statuses and invariants (e.g., `skipped` is non-error; forbids failure details).
  - Ack decisions as **signals** only (policy owned by deterministic orchestration).
  - Minimum required audit/tracing fields for publish vs handle operations.
  - Harness tests that enforce consistent interpretation across implementations.

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

### Deterministic runtime clock governance (fake skills + slice execution)
- **Status**: OPEN
- **Introduced in**: 2026-05-12
- **Last reviewed**: 2026-05-12
- **Current decision**: Vertical-slice **fake** deterministic skills (e.g. ``skills/deterministic/fake_cv_uploaded_skill.py``) use **module-local deterministic reference clocks** for fields such as skill ``ExecutionTiming`` / ``ExecutionAudit.recorded_at`` and related evidence timestamps, instead of wall-clock or orchestrator-supplied logical time.
- **Rationale**: Intentional **bounded simplification** for the first runnable slice: bit-stable skill outputs and harness comparisons without coupling tests to real time, while keeping orchestration **deterministic-first** and **replay-safe** at the payload/provenance level (correlation via event and execution ids). Skills remain **synchronous and bounded**; clocks are not used for routing or scoring.
- **Future impact**:
  - **Cross-skill temporal inconsistency**: different fake (or mixed real/fake) skills may stamp results with unrelated reference epochs, weakening “what happened before what?” reasoning within a single orchestration run when only skill audit fields are consulted.
  - **Replay timeline coordination**: replay runners that merge event ``occurred_at`` with skill timing fields may see artificial inversions or flat segments unless they explicitly prioritize envelope/state timelines over skill-local clocks.
  - **Distributed execution timestamp alignment**: if workers later stamp skill results independently without a shared logical clock contract, cross-node ordering and audit exports become harder to normalize.
  - **Audit sequencing ambiguity**: operators or tools that sort strictly by skill ``recorded_at`` / ``started_at`` may mis-order steps relative to immutable events unless governance docs and UIs anchor on event ids and orchestration decision records.
- **Priority**: Low
- **Recommended future direction** (preserve deterministic-first, replay-safe, bounded execution):
  - **Centralized deterministic runtime clock providers**: inject a single logical clock interface into skill execution (tests freeze it; production supplies UTC or logical ticks) without moving routing/retry policy into skills.
  - **Replay-aware logical clocks**: tie skill audit timestamps to replay context (e.g. envelope logical time, monotonic tick per run) so reconstructed timelines align with stored facts.
  - **Orchestration-level timing coordination**: optionally have the orchestrator pass an explicit “execution instant” or tick in ``ExecutionContext.extensions`` for all skills in one dispatch, keeping policy in the orchestrator and skills as pure functions of context + input.
  - **Monotonic execution timeline governance**: document and enforce ordering rules for persisted artifacts (events primary, skill results secondary) and add harness checks that forbid ambiguous orderings where it matters for compliance or debugging.

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

### Orchestration side-effect consistency after publish failure
- **Status**: OPEN
- **Introduced in**: 2026-05-11
- **Last reviewed**: 2026-05-11
- **Current decision**: The synchronous orchestrator applies validated state transitions and runs skills **before** it attempts to publish derived events; publish outcomes are checked only after those steps. On publish failure, the returned `OrchestrationExecutionResult` does not commit a new `OrchestrationState`, but **skills may already have executed** and any external side effects from skills are outside the orchestrator's rollback scope.
- **Rationale**: This ordering is an intentional, bounded tradeoff for the first **single-process vertical-slice** runtime: it prioritizes a runnable `event → validate → skills → state → emit` path without introducing transactional persistence, outbox writers, or distributed consistency machinery in the control plane yet.
- **Future impact**: Operators and replay tooling may observe **partial effects** (e.g., skill side effects or prior successful publishes in a multi-emission batch) when emission fails mid-flight, complicating audit narratives and recovery unless callers compensate explicitly.
- **Priority**: Medium
- **Recommended future direction**: Harden cross-layer consistency as the stack gains persistence:
  - **Transactional outbox**: record intended emissions atomically with state commits; publish from the outbox with idempotent consumers.
  - **Durable event store**: append-only log as the source of truth for “what was emitted,” aligned with correlation/causation ids.
  - **Exactly-once / eventual consistency strategies**: idempotent event handlers, dedupe keys, and documented dual-write semantics where full ACID across bus + DB is unavailable.
  - **Replay-safe recovery semantics**: deterministic reconciliation jobs and harness-defined rules for “continue from last acknowledged emission” vs. full segment replay.

### Planner determinism verification harness
- **Status**: OPEN
- **Introduced in**: 2026-05-11
- **Last reviewed**: 2026-05-11
- **Current decision**: `OrchestrationStepPlanner` implementations are **expected** to be deterministic, pure policy code (no LLM routing, no autonomous workflow control). The orchestrator **does not verify** that property; it consumes the plan by contract only.
- **Rationale**: Centralizing planner analysis in the orchestrator would blur the boundary between execution and policy, and meaningful checks (entropy, IO, clocks) require dedicated harness infrastructure not justified until planner modules multiply and stabilize.
- **Future impact**: A nondeterministic or environment-coupled planner undermines replay guarantees, audit explainability, and test stability without failing fast at the boundary.
- **Priority**: Low
- **Recommended future direction**: Add engineering guardrails as planners grow:
  - **Deterministic replay harnesses**: fixed seeds, frozen clocks, recorded envelopes → expect bit-for-bit stable plans or stable normalized plan hashes where appropriate.
  - **Nondeterminism detection**: optional static/dynamic checks for banned APIs (random, wall-clock reads outside injected time, hidden global mutable state).
  - **Planner invariant testing**: property tests over state/event pairs for monotonicity, allowed triggers, and schema-safe payloads.
  - **Forbidden entropy source checks**: CI lint or runtime probes for `random`, uncontrolled `datetime.now`, environment reads, and network calls inside planner modules.

### Conditional questionnaire workflow branching (vertical slice planner)
- **Status**: OPEN
- **Introduced in**: 2026-05-11
- **Last reviewed**: 2026-05-11
- **Current decision**: The first vertical-slice planner (``orchestrator/vertical_slice_planner.py``) wires a **fixed** questionnaire leg after light scoring: deterministic transitions and emissions always advance along ``light_scored`` → ``questionnaire_pending`` → ``questionnaire_sent`` → ``questionnaire_completed`` before deep scoring. There is **no** conditional bypass, alternate questionnaire template routing, or role-specific graph selection in v1.
- **Rationale**: Intentional **bounded simplification** so deterministic runtime validation, harness tests, and demos stay small: one explainable path beats premature branching before recruiter configuration and intake semantics stabilize.
- **Future impact**: Real pipelines will need **policy branching** that the current slice does not model:
  - Some candidates may **bypass** questionnaire collection (e.g. sufficient structured profile, executive fast-path, internal referral rules).
  - **Questionnaire routing** should become explicit **deterministic policy branching** (still not LLM routing): which template, which channels, which gates.
  - Branch decisions may depend on **profile completeness**, **recruiter/org configuration**, or **role requirements**—all inputs that must flow through typed, testable planner policy, not ad-hoc conditionals scattered across integrations.
- **Priority**: Low
- **Recommended future direction** (preserve deterministic-first posture; planner remains **policy**, orchestrator **execution**):
  - **Deterministic branch policies** inside planner implementations (pure functions, stable branch ids, audit-friendly reasons).
  - **Configurable workflow policies** (versioned policy packs loaded at wiring time; no runtime “magic” config reads without injection for tests).
  - **Role-specific recruiter pipelines** (explicit graph variants or composed registries with deterministic merge rules—see transition-registry debt for merge semantics).
  - **Optional questionnaire stages** (skip edges with explicit triggers and harness coverage; never silent skips).
  - **Workflow graph branching semantics** (documented fork/join, lineage ids, replay alignment with ``rule_set_id`` / branch metadata).

### Recursive publish / re-entrancy governance (in-memory event bus)
- **Status**: OPEN
- **Introduced in**: 2026-05-11
- **Last reviewed**: 2026-05-11
- **Current decision**: The synchronous in-memory bus does not detect or forbid nested ``publish()`` calls from within subscriber handlers; ordering and partial dispatch traces depend on call patterns at runtime.
- **Rationale**: Vertical-slice wiring prioritizes a minimal runtime; formal re-entrancy policies (depth limits, deadlock detection, flattening rules) add measurable complexity before multi-subscriber demos stabilize.
- **Future impact**: Handlers that synchronously publish can produce nested traces, overlapping ``PublishAudit`` ids, and subtle audit ordering unless callers discipline themselves—especially dangerous when combined with orchestrator-driven emissions.
- **Priority**: Medium
- **Recommended future direction**: Define explicit policies and harness coverage:
  - Optional **re-entrancy depth cap** or “no nested publish” mode for tests.
  - Documented **dispatch freeze** rules during handler execution vs. deferred publish queues (still synchronous; not a broker queue—could be a simple collect-then-flush list owned by the caller).
  - Audit correlation fields linking nested ``publish_id`` / ``delivery_id`` chains.

### Dispatch backpressure handling (event bus runtime)
- **Status**: OPEN
- **Introduced in**: 2026-05-11
- **Last reviewed**: 2026-05-11
- **Current decision**: In-memory dispatch applies only fixed numeric caps (subscriptions registered, max handler dispatches per publish); there is no cooperative **slow consumer** or load-shedding signal beyond bounded counts.
- **Rationale**: Backpressure bridges runtime policy and operational capacity; the first slice targets deterministic correctness on a single thread with explicit limits, not fair scheduling across subscribers.
- **Future impact**: Pathological handlers can still tie up the publisher thread for long CPU-bound stretches; observability may show latency without a structured “apply pressure” channel.
- **Priority**: Medium
- **Recommended future direction**: When persistence or multi-tenant handlers arrive, introduce deterministic **backpressure signals** (skip with audit reason, structured ``HandleResult``, or caller-owned admission control) without introducing async brokers—keep semantics documented in the shared delivery taxonomy.

### Publish aggregate status precedence governance (event bus)
- **Status**: OPEN
- **Introduced in**: 2026-05-11
- **Last reviewed**: 2026-05-11
- **Current decision**: The in-memory bus aggregates subscriber ``HandleResult.status`` values into a single ``PublishResult.status`` using an implementation-defined precedence (currently: any ``failed`` wins, else any ``rejected``, else all ``skipped`` → ``skipped``, else ``accepted``).
- **Rationale**: A vertical slice needs a predictable rule set quickly; global precedence semantics were deferred until multiple bus implementations and orchestrator coupling patterns exist.
- **Future impact**: Different runtimes could aggregate differently unless documented, harming cross-environment audits and replay comparisons (“publish succeeded” vs. “one subscriber failed”).
- **Priority**: Medium
- **Recommended future direction**: Publish a **canonical precedence table** + ack implications in architecture docs; add harness tests across reference implementations; consider explicit ``PublishResult.extensions`` fields for per-status counts instead of inferring from traces alone.

### Candidate multi-state index governance (in-memory state store)
- **Status**: OPEN
- **Introduced in**: 2026-05-11
- **Last reviewed**: 2026-05-11
- **Current decision**: The in-memory state store builds a ``candidate_id → orchestration_state_id`` index from ``StateLink`` entries whose ``kind`` matches ``candidate`` (case-insensitive). When multiple links or successive writes touch the same candidate id, the index is **last-write-wins** within the store’s deterministic replace path. The **vertical-slice assumption** is **one primary orchestration state per candidate** for the runnable recruiter path.
- **Rationale**: A single-map index keeps the first runtime small, deterministic, and easy to wire for demos/tests without introducing multi-tenant workflow keys or temporal scoping in v1.
- **Future impact**: As the product grows, last-write-wins becomes unsafe or ambiguous when:
  - **Multiple active workflows per candidate** (parallel roles, pipelines, or re-applications) need distinct state identities.
  - **Talent pool / history semantics** require retaining prior orchestration snapshots as first-class facts rather than silent overwrite.
  - **Workflow branching** (e.g. alternate paths, experiments) needs stable correlation without collapsing to one live row per candidate.
  - **Historical orchestration lookup** becomes unclear (“which state id is canonical for this candidate at time T?”) without temporal or lineage metadata.
- **Priority**: Medium
- **Recommended future direction**:
  - **Candidate → multiple state mappings**: explicit composite keys (candidate + job + workflow_version + branch id) or a structured registry table in persistence—not a flat singleton map.
  - **Temporal indexing**: valid-from/valid-to or as-of queries for snapshots; align with event timelines and replay runners.
  - **Workflow lineage tracking**: parent/child state ids, fork metadata, and explicit “superseded_by” links for audit trails.
  - **Projection / read-model separation**: keep write-side ``OrchestrationState`` canonical while materializing query-friendly views (active-by-candidate, history-by-candidate) without overloading the in-memory index contract.

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

### Event naming convention governance
- **Status**: OPEN
- **Introduced in**: 2026-05-09
- **Last reviewed**: 2026-05-09
- **Current decision**: Avoid prematurely enum’ing all event types, but require deterministic, reviewable naming conventions for event identifiers.
- **Rationale**: Event types are control-plane vocabulary. Even as strings, they must remain stable for replay, routing determinism, and long-term interpretation.
- **Future impact**: Without naming governance:
  - Similar events may proliferate under different names (drift).
  - Consumers may hardcode inconsistent strings, increasing breaking-change risk.
  - Audit/replay tooling becomes brittle and harder to reason about.
- **Priority**: Medium
- **Recommended future direction**: Define and enforce conventions:
  - Naming pattern (e.g., `noun_verb` or `domain.action`, stable casing).
  - Rules for new event introduction (ADR/registry update, payload notes, backward compatibility expectations).
  - Deprecation rules for renamed/superseded events (emit new event types; avoid mutation; provide mapping docs).

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

### Extraction of default transition registries from the engine module
- **Status**: OPEN
- **Introduced in**: 2026-05-11
- **Last reviewed**: 2026-05-11
- **Current decision**: Keep `default_pipeline_registry()` (and similar defaults) co-located with `transition_engine.py` for early discoverability.
- **Rationale**: A single module reduces indirection while the rule set is small and there is only one consumer; moving too early splits governance from implementation without clear benefit.
- **Future impact**: As domains and rule variants grow, default registries in the engine file increase noise and make versioned rule packs harder to swap in tests and production.
- **Priority**: Low
- **Recommended future direction**: Move default registries to `state_machine/registries/` (or `state_machine/rules/`) as explicit versioned modules (e.g. `pipeline_v1.py`) loaded by wiring code; keep `TransitionEngine` free of product-specific graphs.

### Transition registry modularization (multi-domain rule packs)
- **Status**: OPEN
- **Introduced in**: 2026-05-11
- **Last reviewed**: 2026-05-11
- **Current decision**: Use one immutable `TransitionRegistry` type with a flat sorted rule tuple; compose multiple domains in a single registry instance when needed.
- **Rationale**: Keeps the validation engine simple and deterministic; premature package fragmentation can obscure global invariants (e.g. terminal sets, trigger naming).
- **Future impact**: Large monolithic registries become harder to review, diff, and assign ownership; cross-pack conflicts (duplicate `rule_id`, overlapping edges) need explicit policy.
- **Priority**: Medium
- **Recommended future direction**: Introduce composable registry builders (merge with deterministic conflict rules), namespace `rule_id` prefixes per pack, and harness tests for merge semantics and replay alignment with `rule_set_id`.
