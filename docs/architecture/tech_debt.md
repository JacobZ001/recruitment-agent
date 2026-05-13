# BlueOcean Recruitment Agent — Architecture Debt Registry

Purpose: track deferred architecture improvements, scaling risks, and engineering rationale so we don’t lose critical future considerations. This project prioritizes **deterministic orchestration** and **verifiable behavior** over “smart prompts”.

## Debt lifecycle

- **OPEN**: identified, not started
- **IN_PROGRESS**: actively being addressed
- **RESOLVED**: implemented and verified
- **SUPERSEDED**: replaced by a different approach/decision

## Registry entry format

- **Status**: OPEN | IN_PROGRESS | RESOLVED | SUPERSEDED
- **Scope**: which subsystem this touches (use one primary label from the legend below; optional `+` for a tight secondary, e.g. `API+Persistence`).
- **Revisit when**: explicit trigger to reopen the work—milestone, dependency, risk symptom, or product stage—not “eventually”.
- **Introduced in**: date or milestone (e.g. 2026-05-08 / v0.1)
- **Last reviewed**: date
- **Owner** (optional): team/person
- **Current decision**
- **Rationale**
- **Future impact**
- **Priority**: High | Medium | Low
- **Recommended future direction**

### Scope legend (pick one primary per entry)

| Scope | Typical paths / concerns |
| ----- | ------------------------- |
| **Contracts** | `schemas/`, payload/versioning, cross-layer identifiers |
| **Orchestrator** | `orchestrator/`, plan/commit/emission ordering, side effects |
| **TransitionEngine** | `state_machine/`, registries, validation rules |
| **Persistence** | `runtime/persistence/`, snapshot/audit durability, SQLite semantics |
| **Bus** | `runtime/in_memory_event_bus.py`, publish/dispatch/handler semantics |
| **Skills** | `skills/`, execution contracts, deterministic fakes |
| **API** | `integrations/api/`, HTTP ingress, process-wide runtime wiring |
| **Inspection** | `runtime/inspection/`, timelines, catalogs, read-only projections |
| **Governance** | `recruiter_*` ingress, human override paths, governance schemas |
| **Replay** | harnesses, replay runners, assertion profiles (may span tests + runtime) |
| **Ops** | concurrency, scaling posture, operational docs—not product workflow |
| **DX** | developer ergonomics, refactors that unblock velocity without changing semantics |

## Contract Evolution

### Typed payload contracts (events + skill IO)
- **Status**: OPEN
- **Scope**: Contracts
- **Revisit when**: When first external integration or typed-payload pilot is scheduled
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
- **Scope**: Contracts
- **Revisit when**: When first external integration or typed-payload pilot is scheduled
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
- **Scope**: Contracts
- **Revisit when**: When first external integration or typed-payload pilot is scheduled
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
- **Scope**: Contracts
- **Revisit when**: When extensions sprawl threatens harness coverage
- **Introduced in**: 2026-05-08
- **Last reviewed**: 2026-05-08
- **Current decision**: Use explicit `extensions: Dict[str, Any]` as the forward-compatible escape hatch.
- **Rationale**: Prevents silent schema drift while still allowing controlled extension during early evolution.
- **Future impact**: Overuse can recreate an untyped “blob” domain and erode verifiability.
- **Priority**: High
- **Recommended future direction**: Establish rules: `extensions` only for staged fields; graduate to typed fields with a version bump + harness coverage.

### Timezone-aware datetime handling
- **Status**: OPEN
- **Scope**: Contracts
- **Revisit when**: Before external system date correlation or compliance reporting
- **Introduced in**: 2026-05-08
- **Last reviewed**: 2026-05-08
- **Current decision**: Some schemas still use naive UTC timestamp defaults for v1.
- **Rationale**: Simple, consistent early implementation; avoids TZ conversion bugs before requirements are clear.
- **Future impact**: Ambiguity when integrating external systems; harder compliance/time-based reporting and cross-system correlation.
- **Priority**: High
- **Recommended future direction**: Use timezone-aware UTC (`datetime.now(timezone.utc)`) and validate/serialize consistently across services.

### Typed profile links instead of `List[str]`
- **Status**: OPEN
- **Scope**: Contracts
- **Revisit when**: When intake requires typed profile URLs
- **Introduced in**: 2026-05-08
- **Last reviewed**: 2026-05-08
- **Current decision**: Keep `external_profile_urls: List[str]` in `Identity`.
- **Rationale**: Low friction intake; link diversity is high early.
- **Future impact**: Harder validation/dedup and limited explainability (no typed semantics).
- **Priority**: Medium
- **Recommended future direction**: Replace with typed link objects (kind/provider/url, normalized handle, evidence refs).

### Typed recruiter feedback adjustments
- **Status**: OPEN
- **Scope**: Contracts
- **Revisit when**: When recruiter calibration product hardens
- **Introduced in**: 2026-05-08
- **Last reviewed**: 2026-05-08
- **Current decision**: Keep `RecruiterFeedback.adjustments: Dict[str, Any]`.
- **Rationale**: Recruiter calibration structures are still evolving.
- **Future impact**: Inconsistent adjustment semantics complicate calibration, analysis, and governance.
- **Priority**: High
- **Recommended future direction**: Define a small set of typed adjustment operations (e.g., `ScoreAdjustment`, `LabelOverride`, `RuleException`) and validate with a harness.

### Canonical workflow decision and rejection vocabulary governance
- **Status**: OPEN
- **Scope**: Contracts
- **Revisit when**: When first external integration or typed-payload pilot is scheduled
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

### Centralized scoring policy governance
- **Status**: OPEN
- **Scope**: Contracts
- **Revisit when**: When first external integration or typed-payload pilot is scheduled
- **Introduced in**: 2026-05-12
- **Last reviewed**: 2026-05-12
- **Current decision**: Fake deterministic scoring (e.g. ``skills/deterministic/fake_light_scoring_skill.py``) applies **local, bounded weighting policies** and **local normalized score semantics** (factor definitions, weight vectors, clamping rules) embedded in each skill module. The vertical slice **intentionally** keeps policy local so orchestration validation, harness tests, and explainable numeric outputs can ship before org-wide calibration and policy infrastructure exist.
- **Rationale**: Maintains **deterministic-first** control (orchestrator/planner still own workflow), **explainable** factorized outputs, and **bounded** execution without prematurely centralizing recruiter policy while product semantics are still moving.
- **Future impact**:
  - **Scoring semantic drift across skills**: light vs deep (and future) scoring modules may interpret “normalized score,” factor names, or weights differently unless aligned by contract.
  - **Inconsistent recruiter weighting policies**: different pipelines or tenants may encode incompatible defaults, complicating comparisons and governance reviews.
  - **Replay inconsistency after policy evolution**: historical ``SkillExecutionResult`` payloads may not carry enough **policy identity/version** to reinterpret scores under the rules that were logically in effect at emission time.
  - **Organization-wide ranking fragmentation**: without shared policy artifacts, cross-role or cross-requisition comparability of scores remains informal and error-prone.
  - **Unclear normalized-score interpretation across workflows**: consumers may treat ``[0, 1]`` as comparable across stages when factors and weights differ, harming audit narratives and analytics.
- **Priority**: Medium
- **Recommended future direction** (preserve deterministic-first, explainable scoring, bounded orchestration—**no** LLM-driven policy mutation):
  - **Centralized scoring policy registries**: canonical factor taxonomies, default weights, and clamp rules as data or typed modules referenced by skills—not ad-hoc literals scattered per skill.
  - **Versioned recruiter scoring policies**: explicit ``policy_id`` / ``policy_version`` (or equivalent) embedded in skill outputs and audit extensions for traceability.
  - **Replay-stable scoring policy capture**: persist or hash the effective policy snapshot used per run so replay and compliance tooling can reproduce numeric results deterministically.
  - **Organization-level scoring governance**: ownership, approval, and publication workflow for policy packs (still deterministic at execution time).
  - **Scoring calibration and distribution semantics**: documented meaning of normalized scores (e.g. per-stage, per-requisition), optional calibration curves as **deterministic** transforms with harness coverage—not autonomous tuning loops in skills.
  - **Deterministic policy rollout/versioning**: staged rollout (pinned defaults, explicit migrations, harness checks) so orchestrator upgrades do not silently change score meaning without a recorded policy bump.

### Workflow-context-aware scoring priors
- **Status**: OPEN
- **Scope**: Contracts
- **Revisit when**: When first external integration or typed-payload pilot is scheduled
- **Introduced in**: 2026-05-12
- **Last reviewed**: 2026-05-12
- **Current decision**: Fake deep scoring (``skills/deterministic/fake_deep_scoring_skill.py``) applies **deterministic workflow-stage priors**—for example, when questionnaire fields are omitted it assumes a **bounded default questionnaire component** and records a **stage prior** signal—so the vertical slice can simulate “richer post-questionnaire cognition” without wiring full questionnaire payloads into every harness case.
- **Rationale**: **Bounded** vertical-slice simulation: keeps execution **deterministic-first**, **explainable** (explicit flags such as ``used_questionnaire_stage_prior`` / signal codes), and **replay-stable** for the same inputs, while deferring centralized contextual policy infrastructure.
- **Future impact**:
  - **Hidden contextual weighting drift**: priors embedded in skills can diverge from real pipeline context as graphs multiply unless policy identity is explicit in outputs.
  - **Inconsistent stage priors across workflows**: different stages or tenants may need incompatible priors; local constants risk forked semantics without registries.
  - **Replay inconsistencies after policy evolution**: historical scores may change meaning if priors change without a captured **prior version** alongside results.
  - **Unclear recruiter interpretation of contextual score boosts**: operators may read a higher score as “better candidate” rather than “stage assumption + sparse inputs” unless UI/docs map priors clearly.
- **Priority**: Medium
- **Recommended future direction** (preserve deterministic-first, explainable scoring, bounded orchestration):
  - **Centralized contextual scoring policy governance**: own stage/default rules in versioned policy packs referenced by skills, not magic numbers scattered per module.
  - **Workflow-aware scoring policy registries**: map ``(workflow_id, pipeline_phase, skill_kind)`` → allowed priors and defaults with harness validation.
  - **Replay-stable prior versioning**: embed ``prior_policy_id`` / ``prior_policy_version`` (or hash) in skill output extensions when any prior applies.
  - **Explainable contextual weighting semantics**: documented formulas and UI-safe labels distinguishing **declared evidence** vs **stage priors** vs **neutral fillers**.
  - **Deterministic workflow-context scoring calibration**: explicit calibration tables (deterministic transforms only) and tests that pin expected scores for canonical fixture payloads.

## Persistence (SQLite)

### SQLite replace uses DELETE + INSERT instead of UPSERT
- **Status**: OPEN
- **Scope**: Persistence
- **Revisit when**: When tuning SQLite write path or adding multi-writer stress tests
- **Introduced in**: 2026-05-12
- **Last reviewed**: 2026-05-12
- **Current decision**: ``runtime/persistence/sqlite_state_store.py`` implements ``replace`` by deleting the ``orchestration_state`` row for ``state_id``, then re-inserting snapshot + indexes + audit in one transaction. Behavior matches optimistic revision semantics and is correct for the single-row model.
- **Rationale**: Straightforward correctness over micro-optimization while the SQLite adapter is new.
- **Future impact**: Extra churn vs a pure ``INSERT ... ON CONFLICT(state_id) DO UPDATE`` path (fewer round-trips, clearer upsert story).
- **Priority**: Low
- **Recommended future direction**: Refactor ``replace`` to rely on **UPSERT-only** updates for ``orchestration_state`` while preserving revision monotonicity and candidate/audit rewrite semantics—still transactional; add harness tests if assertion shapes change.

### Transition audit serialization contract
- **Status**: OPEN
- **Scope**: Persistence
- **Revisit when**: When external tools read audit table without snapshot
- **Introduced in**: 2026-05-12
- **Last reviewed**: 2026-05-12
- **Current decision**: ``state_transition_audit`` rows are derived from ``snapshot.transitions`` with ad-hoc field mapping (``extensions`` as JSON, actor/event columns). The **canonical** source of truth remains ``orchestration_state.snapshot_json``; the audit table is a non-authoritative mirror.
- **Rationale**: Ship bounded operator/debug visibility without freezing a second schema contract on day one.
- **Future impact**: Drift between reloaded ``OrchestrationState`` transition models and stored audit columns if ``StateTransitionRecord`` evolves; external tools reading only audit may misinterpret history.
- **Priority**: Low
- **Recommended future direction**: Define a **stable serialization boundary** (versioned columns or a single JSON blob per row with a ``record_schema_version``) for persisted transition mirrors; keep snapshot JSON authoritative; document read paths.

### Persistence write concurrency model
- **Status**: OPEN
- **Scope**: Persistence+Ops
- **Revisit when**: When API runs multi-threaded or multi-worker against SQLite
- **Introduced in**: 2026-05-12
- **Last reviewed**: 2026-05-12
- **Current decision**: ``SQLiteStateStore`` uses ``check_same_thread=False`` on the connection; **no** internal lock. Callers (e.g. FastAPI) are assumed to **serialize** writes to the store or accept undefined interleaving.
- **Rationale**: Matches the current **single-aggregate** reference API posture; avoids hiding correctness issues behind a store lock before concurrency requirements are explicit.
- **Future impact**: Concurrent ``replace`` / ``create`` on the same DB from multiple threads can race; last-writer-wins or sqlite errors may surface without a clear product contract.
- **Priority**: Medium
- **Recommended future direction**: Document **concurrency guarantees** (per-process, per-aggregate, or “external lock required”); or introduce a small **write lock** / queue abstraction around the store for multi-threaded hosts; consider WAL + timeout policy when load grows.

## Decision persistence

### Decision namespace structure
- **Status**: OPEN
- **Scope**: Persistence+Contracts
- **Revisit when**: When extension keys multiply or second producer writes decision.*
- **Introduced in**: 2026-05-12
- **Last reviewed**: 2026-05-12
- **Current decision**: ``OrchestrationState.extensions`` holds flat keys such as ``decision.*``, ``inactive.*``, and ``governance.*`` without a formal namespace contract or collision policy.
- **Rationale**: Ship persisted evaluation signals quickly on top of the existing extensions escape hatch.
- **Future impact**: Unstructured growth and accidental key collisions across producers (skills, planner, governance).
- **Priority**: Medium
- **Recommended future direction**: Define typed logical namespaces or a versioned schema contract for extension keys (prefix rules, allowlists, or nested typed sub-documents).

### Decision evidence lineage
- **Status**: OPEN
- **Scope**: Persistence
- **Revisit when**: When operator UI needs per-skill evidence attribution
- **Introduced in**: 2026-05-12
- **Last reviewed**: 2026-05-12
- **Current decision**: ``decision.evidence_refs`` merges refs across pipeline steps into one deduped list; source skill/step is not recorded.
- **Rationale**: Keeps snapshot shape small and avoids extra columns while proving end-to-end persistence.
- **Future impact**: Operators and audits cannot tell which skill emitted which ref without correlating run history manually.
- **Priority**: Medium
- **Recommended future direction**: Add per-step or per-skill attribution (e.g. ``decision.evidence_sources`` mapping ref → producer, or structured entries per transition).

### Decision-to-transition linkage
- **Status**: OPEN
- **Scope**: Persistence+Orchestrator
- **Revisit when**: When audit tooling needs transition-scoped decision facts
- **Introduced in**: 2026-05-12
- **Last reviewed**: 2026-05-12
- **Current decision**: Decision fields live on the aggregate snapshot and are copied into ``StateTransitionRecord.extensions`` for the committing transition, but there is no explicit link (e.g. id) tying a given decision key set to a specific transition or event id beyond ordering.
- **Rationale**: Reuse the same flat merge for audit rows and snapshot without a second linkage model.
- **Future impact**: Harder targeted audit/debug (“which transition wrote this score?”) under concurrent or replay tooling.
- **Priority**: Low
- **Recommended future direction**: Introduce explicit lineage (transition id, ingested ``event_id``, or step index) on decision blobs or transition extensions.

### Decision overwrite semantics
- **Status**: OPEN
- **Scope**: Persistence
- **Revisit when**: When UI/API must show single authoritative score
- **Introduced in**: 2026-05-12
- **Last reviewed**: 2026-05-12
- **Current decision**: ``decision.light_score`` / ``decision.deep_score`` (and confidences) coexist; no documented rule for which layer is authoritative for downstream consumers.
- **Rationale**: Light and deep are different stages; both remain visible for inspection.
- **Future impact**: UI or policy may disagree on “the” candidate score without an explicit precedence contract.
- **Priority**: Low
- **Recommended future direction**: Document and enforce precedence (e.g. deep overrides light for display/ranking) or split into versioned stage records instead of a single flat key set.

## Execution Architecture

### Future orchestration replay tooling
- **Status**: IN_PROGRESS
- **Scope**: Replay
- **Revisit when**: When scheduling durable stream replay runner or operator MVP
- **Introduced in**: 2026-05-08
- **Last reviewed**: 2026-05-12
- **Current decision**: Immutable events + correlation/causation ids remain the persistence contract target. **Not resolved**: no durable stream “replay runner” or operator-facing replay products yet. **In progress**: synchronous **structural replay harnesses** under ``tests/replay/`` exercise the vertical slice end-to-end (happy path byte-stable JSON equality; deterministic negative-path cases including transition rejection, missing skill registration, ``hard_filter_failed`` closure, and bus handler-exception isolation). **Additional coverage**: ``tests/persistence/`` exercises SQLite snapshot round-trips (including decision extensions) so replay-relevant state survives process boundaries **without** implying a full append-only event replay product yet. These prove orchestrator + bus + transition-engine wiring **before** storage-backed **event-stream** replay.
- **Rationale**: Tooling is expensive; stabilize contracts and deterministic transitions first. Harness-first replay validates control-plane semantics **without** conflating “harness + snapshot persistence exists” with “durable ingress/event stream is solved.”
- **Future impact**: Until a stream-backed runner exists, cross-process and post-mortem reconstruction still rely on explicit logging discipline; harness coverage does not replace durable timelines.
- **Priority**: High
- **Recommended future direction**: Build a “replay runner” that rehydrates `OrchestrationState` from an **append-only event stream** with strict validation and deterministic logs; extend harness assertions toward **semantic** and **governance** profiles (see “Replay validation evolution”) rather than only full JSON equality.

### Replay validation evolution (structural vs semantic equality)
- **Status**: OPEN
- **Scope**: Replay
- **Revisit when**: When strict JSON replay tests churn on observability metadata
- **Introduced in**: 2026-05-12
- **Last reviewed**: 2026-05-12
- **Current decision**: Vertical-slice harness validation uses **strict structural replay equality** as the default gate: canonical ingress is driven through independently wired runtimes and artifacts are compared via **deterministic, byte-stable JSON serialization** where applicable (`tests/replay/test_vertical_slice_replay.py` happy path; negative-path cases in `tests/replay/test_vertical_slice_negative_paths.py` pin stable failure semantics—transition rejection, missing skill, slice closure on ``hard_filter_failed``, bus synthetic handler failures). This intentionally treats observability-shaped fields as part of the contract **while** harness surface area remains small. **Future**: the same suite must evolve toward **layered** assertions—**structural** (workflow facts), **semantic** (normalized projections / tolerances), **governance/audit** (operator timelines)—so instrumentation can grow without false-positive harness churn (see Future impact below).
- **Rationale**: Early validation should maximize signal per test run and catch unintended drift in control-plane wiring. Structural equality over full serialized artifacts is the simplest contract when instrumentation surface area is small and deterministic-first semantics are the primary product.
- **Future impact**:
  - **Observability / tracing metadata** will evolve on timelines **independent of workflow semantics** (spans, host labels, sampling flags). If replay tests remain strict JSON equality over entire execution results, **benign instrumentation changes will fail tests** unrelated to orchestration correctness.
  - **Strict JSON equality may become too rigid** as runtime diagnostics grow (dispatch traces, publish extensions, subscriber rows). The harness must not force either (a) freezing incidental metadata forever or (b) abandoning replay discipline entirely.
  - Replay validation will likely need **layered equality semantics**, applied deliberately rather than one blanket assertion:
    - **Structural replay equality**: stable state transitions, pipeline phase progression, emitted event types/ids/payloads relevant to workflow facts, skill outcomes material to decisions.
    - **Semantic replay equivalence**: normalize or project artifacts before compare (e.g. strip volatile tracing fields; compare hashed stable subsets; equivalence classes for numeric tolerances where explicitly governed).
    - **Governance / audit replay equality**: prove immutable audit narratives—who/what/when for transitions and overrides—with explicit schemas for operator-facing timelines, possibly distinct from developer-facing debug payloads.
  - **Expansion pressure** (still bounded, deterministic-first): failure-path replay, partial-success (`PARTIAL_SUCCESS`) replay, replay **under schema evolution** (versioned interpretation rules), replay **across policy-version upgrades** (rule set id + compatibility harness), and eventually **distributed/concurrent execution** replay—each introduces dimensions where strict byte equality is either insufficient or the wrong default.
- **Priority**: Medium
- **Recommended future direction** (preserve **deterministic-first** orchestration, **replay/audit** primacy, **bounded** runtime semantics):
  - Define **explicit replay assertion profiles** (e.g. `structural_strict`, `semantic_workflow`, `audit_timeline`) and map harness tests to profiles as the runtime grows.
  - Partition persisted/captured models into **workflow facts** vs **diagnostic overlays**; tests compare facts by default; overlays opt-in or snapshot selectively.
  - Expand **failure** and **partial-success** replay profiles beyond the initial negative-path bundle; keep strict structural harness as the regression anchor until semantic projection helpers land.
  - Coordinate with **schema versioning** and **policy pack versioning** entries: replay fixtures pin `(schema_version, rule_set_id)` and document intentional upgrade breaks vs drift bugs.
  - For future concurrency: specify **ordering contracts** and replay scopes (single aggregate vs multi-tenant isolation)—without implying premature production posture.

### Inspection event-history provenance and catalog governance
- **Status**: OPEN
- **Scope**: Inspection
- **Revisit when**: When defining canonical event-history read model or envelope provenance
- **Introduced in**: 2026-05-12
- **Last reviewed**: 2026-05-12
- **Current decision**: ``runtime/inspection/`` renders **read-only**, deterministic human-readable timelines from supplied artifacts (``OrchestrationExecutionResult`` history + envelope catalogs). **Unified catalog** wiring merges **primary scripted ingress** envelopes with envelopes captured from the full **published stream** when available (e.g. ``tests/replay/recording_bus.RecordingInMemoryEventBus.recorded_envelopes``), so nested orchestration runs triggered by **runtime-emitted** events (e.g. ``questionnaire_requested``) resolve ``event_type`` in inspection output. ``RecordingInMemoryEventBus`` remains **test instrumentation**, not a canonical production event-history store. **Ingress classification** for display uses a **heuristic**: ``ingest.kind=runtime_emission`` when ``EventEnvelope.metadata.causation_id`` is present (orchestrator emissions set causation to the parent ingest); **external** bootstrap ingress uses ``causation_id=None``. The default reference ``InMemoryEventBus`` does **not** retain publish history—callers without a recorded stream may pass an explicit envelope catalog or accept incomplete labeling for emitted-only ingests.
- **Rationale**: Inspection must stay **non-authoritative**: it interprets recorded facts and merges catalogs for developer/operator clarity **without** embedding orchestration policy or mutating runtime state. **Orchestration snapshot** persistence (e.g. SQLite ``snapshot_json``) can exist independently of inspection; a **durable append-only event / ingress stream** and canonical event-history read models remain intentionally deferred. Bounded merge + causation-based labeling ships **reference-slice** operator visibility **before** those event-store contracts exist.
- **Future impact**:
  - **Incomplete catalogs**: plain runtime without recorded envelopes (or without explicit catalog injection) may lack emitted-event envelopes—timeline reconstruction can miss labels even when orchestration runs succeeded.
  - **Heuristic brittleness**: ``causation_id`` may **not** cleanly separate **external integration** ingress from **runtime emission** once external producers also populate causation links—classification could drift without explicit provenance fields.
  - **Semantic drift**: operator-facing timelines may disagree across tools if **event provenance / source** semantics are not standardized alongside envelope contracts.
  - **Product boundaries**: future API/UI surfaces need **stable event-history** (read models or append-only feeds)—test-local recording buses are not sufficient as the system-of-record story evolves.
- **Priority**: Medium
- **Recommended future direction** (preserve **deterministic-first** posture; inspection stays **read-only**; **no** production event store by debt entry alone):
  - Introduce **explicit provenance / source** fields (or versioned metadata extensions) on ``EventEnvelope`` for **external ingress** vs **control-plane emission** vs other categories—rather than relying solely on causation presence.
  - Define **canonical event-history / read-model contracts** when **durable runtime** and persistence work land; align append-only semantics with replay and audit entries—implement storage **there**, not inside the inspection renderer.
  - Keep the inspection layer as **projection-only**: render text / JSON / UI from **recorded facts**; add **structured timeline entries** later as an intermediate representation shared by multiple renderers.
  - Coordinate with **future orchestration replay tooling** and **event envelope payload governance** entries so timelines remain reproducible under schema and policy evolution.

### API runtime singleton (single process, shared runtime)
- **Status**: OPEN
- **Scope**: API
- **Revisit when**: When Stage B requires per-session or multi-tenant runtime isolation
- **Introduced in**: 2026-05-12
- **Last reviewed**: 2026-05-12
- **Current decision**: The reference HTTP ingress (`integrations/api/`) wires **one** `VerticalSliceApiRuntime` per application process (singleton-style lifespan). All requests share the **same** in-memory event bus and **one** orchestration aggregate (deterministic bootstrap ids). The **snapshot store** may be **in-memory** or **SQLite-backed** (e.g. ``VERTICAL_SLICE_DB_PATH`` / default ``data/app.db``); there is **no** per-request or per-tenant runtime isolation in v1.
- **Rationale**: **Deterministic-first**, **bounded** vertical-slice validation: a single shared world maximizes reproducibility for demos and integration tests without introducing session factories, pooling, or multi-tenant routing in the API layer yet.
- **Future impact**: Unsuitable for **multi-candidate** or **multi-session** execution at scale; concurrent clients can interfere with each other’s workflow view; load tests and shared environments need explicit process boundaries or future isolated runtime instances.
- **Priority**: Medium
- **Recommended future direction**: Introduce **explicit runtime scopes** (factory or context-owned `VerticalSliceApiRuntime` instances) only when product requirements demand isolation—preserve deterministic wiring and harness-friendly construction; avoid embedding orchestration policy in the API.

### Fixed aggregate identity (single candidate-scoped orchestration instance)
- **Status**: OPEN
- **Scope**: API+Persistence
- **Revisit when**: When Stage B ships multi-candidate HTTP or aggregate registry
- **Introduced in**: 2026-05-12
- **Last reviewed**: 2026-05-12
- **Current decision**: The reference API assumes the bootstrap **`VERTICAL_SLICE_DEFAULT_CANDIDATE_ID`** (and associated single orchestration aggregate). Requests for other candidate ids are rejected (e.g. 404)—there is **no** runtime-created aggregate identity or multi-aggregate registry at the HTTP edge.
- **Rationale**: Keeps ingress validation and tests **tight** on one explainable path; defers **multi-aggregate lifecycle** (create candidate / bind aggregate / route at HTTP edge) until Stage B wiring exists. **Snapshot persistence for the wired aggregate** (SQLite) is orthogonal: it does not by itself add new candidate identities or a registry at the API boundary.
- **Future impact**: External systems cannot drive **per-candidate** workflows through the API until aggregate creation, routing, and scope rules exist outside the bootstrap script.
- **Priority**: Medium
- **Recommended future direction**: Add **deterministic** aggregate lifecycle operations (create/bind ids, explicit aggregate keys) in **runtime construction** or a thin registry—**not** in route handlers as ad-hoc policy; align with future persistence and audit entries.

### HTTP ingress idempotency and replay-safe retries
- **Status**: OPEN
- **Scope**: API
- **Revisit when**: Before external integrator or Stage B ingress hardening (whichever first)
- **Introduced in**: 2026-05-12
- **Last reviewed**: 2026-05-12
- **Current decision**: **`POST /events`** has **no** idempotency contract: duplicate submits may enqueue **duplicate** envelopes (subject to existing orchestration validation). Clients cannot rely on deduplication, stable publish outcomes under retries, or ingress-level audit of “same logical submission.”
- **Rationale**: Sync-first reference boundary prioritizes validated publish semantics over distributed ingress guarantees; idempotency keys, dedupe stores, and ingress audit trails imply infrastructure and policy choices deferred for the slice.
- **Future impact**: Retries, double-clicks, and proxy duplicates can produce **duplicate workflow signals** or confusing audit narratives unless upstream compensates; compliance-heavy deployments will need **replay-safe** ingress semantics.
- **Priority**: High
- **Recommended future direction**: Define **idempotency keys** (header or body), **dedupe policy** (window, scope, outcome mapping), **replay-safe retry** rules, and **ingress audit** records (who/when/key hash)—implemented in **deterministic** layers adjacent to the bus/persistence, not in LLM or autonomous routing; coordinate with **Orchestration side-effect consistency after publish failure** and shared delivery taxonomy.

### Timeline rendering format (plain text vs structured projections)
- **Status**: OPEN
- **Scope**: Inspection+API
- **Revisit when**: When consumers need machine-stable timeline JSON
- **Introduced in**: 2026-05-12
- **Last reviewed**: 2026-05-12
- **Current decision**: Inspection (`runtime/inspection/`) and **`GET /timeline/{candidate_id}`** expose **deterministic plain text** timelines only. There is **no** canonical structured timeline schema (JSON rows, typed segments) or alternate renderers (UI components, export formats) in the reference runtime.
- **Rationale**: Human-readable text is the smallest **read-only** projection for early operator visibility on the reference slice; structured timelines add schema churn before operator and integration contracts stabilize.
- **Future impact**: Downstream tools cannot consume **machine-stable** timeline entries without parsing text; multiple surfaces may diverge if each invents its own JSON.
- **Priority**: Medium
- **Recommended future direction**: Introduce an intermediate **structured timeline model** (immutable facts → entries) shared by **text / JSON / UI** renderers; keep rendering **non-authoritative** and **deterministic**; align with **Inspection event-history provenance and catalog governance**.

### API boundary coupling to bootstrap helpers (`_envelope`, fixed clock)
- **Status**: OPEN
- **Scope**: API+DX
- **Revisit when**: When extracting stable envelope factory from bootstrap
- **Introduced in**: 2026-05-12
- **Last reviewed**: 2026-05-12
- **Current decision**: The API imports **bootstrap-oriented** helpers (e.g. `_envelope`, `_FIXED_CLOCK`, wiring conveniences from `runtime/bootstrap_vertical_slice.py`) to build `EventEnvelope` instances and keep tests deterministic.
- **Rationale**: **Bounded** vertical slice: fastest path to a validated ingress without duplicating envelope construction; acceptable while bootstrap remains the single reference composition root.
- **Future impact**: Production-shaped ingress may accidentally depend on **demo-only** or **script-oriented** helpers; refactors to bootstrap can ripple into HTTP tests without a clear **runtime construction** API.
- **Priority**: Medium
- **Recommended future direction**: Extract **stable runtime construction** helpers (envelope factory with injected clock/correlation policy, no demo-only defaults) from bootstrap utilities; keep API as a **thin adapter** that calls those helpers—preserve **no workflow policy in routes**.

### Inspection ingress classification: causation_id heuristic vs explicit provenance
- **Status**: OPEN
- **Scope**: Inspection
- **Revisit when**: When external producers set causation_id on ingress
- **Introduced in**: 2026-05-12
- **Last reviewed**: 2026-05-12
- **Current decision**: **`runtime_emission`** vs external ingress labeling in inspection uses a **heuristic**: presence of **`EventEnvelope.metadata.causation_id`** implies runtime-emitted lineage; **`causation_id=None`** implies external/script ingress. This is **not** a guaranteed provenance taxonomy once external producers also set causation metadata.
- **Rationale**: Ships **bounded** reference-slice readability without new envelope fields or migration; aligns with **deterministic-first** inspection as projection-only (see **Inspection event-history provenance and catalog governance**).
- **Future impact**: Misclassification risk when integrations populate causation for legitimate external submits; audit and operator UIs may show incorrect **source** semantics.
- **Priority**: Medium
- **Recommended future direction**: Add **explicit provenance / source metadata** (versioned envelope extensions or first-class fields) for categories such as external ingress, control-plane emission, replay injection—**deterministic** classification in inspection from recorded facts, not inferred solely from causation presence; coordinate with **Shared execution metadata structures**.

### Governance semantic partitioning (shared stream vs read-model clarity)
- **Status**: OPEN
- **Scope**: Governance
- **Revisit when**: When read-models split governance vs operational streams
- **Introduced in**: 2026-05-12
- **Last reviewed**: 2026-05-12
- **Current decision**: First bounded governance ingress (``recruiter_*`` events) rides the **same** append-only publish/handle path as operational ingress and orchestration-derived envelopes. Timelines and replay harnesses treat them as typed ``event_type`` facts without a separate governance channel or persisted partition yet.
- **Rationale**: Keeps the vertical slice **single-bus**, **replay-testable**, and small—no second runtime or premature split of what counts as an immutable fact.
- **Future impact**: As workflows grow, timeline and replay consumers may overload one stream with mixed semantics (operator decisions vs domain progression vs emissions) unless projections can filter or label categories reliably.
- **Priority**: Medium
- **Recommended future direction**: When read-model needs emerge, **distinguish governance decisions from operational signals** in **deterministic projections** (tags, provenance fields, or typed catalog views)—**preserve replay compatibility** on the underlying immutable stream; avoid forking control-plane semantics until harness and audit contracts need it.

### Governance authority semantics (``human_override`` / force paths)
- **Status**: OPEN
- **Scope**: Governance
- **Revisit when**: When expanding human_override edge matrix
- **Introduced in**: 2026-05-12
- **Last reviewed**: 2026-05-12
- **Current decision**: ``recruiter_force_transition`` sets ``ProposedTransition.human_override`` as a **bounded audit signal**; transitions still pass through ``TransitionEngine.validate`` with the same registry rules—**no** open-ended skip-validation path.
- **Rationale**: Deterministic-first posture: operators are visible in history without granting unrestricted graph edits.
- **Future impact**: Product language around emergency override, escalation tiers, and which edges may use ``human_override`` is **not** yet codified—risk of inconsistent operator expectations vs engine behavior as more edges appear.
- **Priority**: Medium
- **Recommended future direction**: Document **allowable override classes** (terminal escape, policy exception, replay-only, etc.) in small ADR or registry metadata; keep **replay and audit logs** the source of truth; **no** autonomous mutation authority outside validated transitions.

### Governance identity lineage (opaque ``actor_id``)
- **Status**: OPEN
- **Scope**: Governance
- **Revisit when**: When delegation / impersonation enters product scope
- **Introduced in**: 2026-05-12
- **Last reviewed**: 2026-05-12
- **Current decision**: Governance payloads use a **minimal** stable ``actor_id`` string plus ``actor_type`` (see ``schemas/governance_schema.py``). No delegation chain, impersonation metadata, or multi-step review graph.
- **Rationale**: Ships accountable human facts on the slice without permission systems or identity products.
- **Future impact**: Delegation, escalation lineage, impersonation controls, calibration attribution, and multi-review provenance cannot be expressed faithfully without richer—but still **deterministic**—metadata.
- **Priority**: Low
- **Recommended future direction**: **Intentionally evolve only when** governance workflows require it: optional structured lineage fields (parent action id, review role, calibration session id) behind versioned payload contracts; keep defaults minimal for harness stability.

### Governance policy modularization (planner-local vs packs)
- **Status**: OPEN
- **Scope**: Governance+Orchestrator
- **Revisit when**: When vertical_slice_planner.py governance section exceeds reviewable size
- **Introduced in**: 2026-05-12
- **Last reviewed**: 2026-05-12
- **Current decision**: Bounded governance transitions and whitelist rules live **inline** in ``orchestrator/vertical_slice_planner.py`` next to the rest of slice policy.
- **Rationale**: Fast iteration, single file to read for vertical-slice behavior; avoids abstract policy frameworks before shapes stabilize.
- **Future impact**: More recruiter/operator paths will **densify** the planner—harder to review, version, and test in isolation without duplication risk.
- **Priority**: Medium
- **Recommended future direction**: Extract **versioned governance policy tables or registries** (pure data + harness) called from the planner—**deterministic planning unchanged**; **no** premature framework; refactor only when file complexity hurts correctness reviews.

### Governance lifecycle policy centralization
- **Status**: OPEN
- **Scope**: Governance+Orchestrator
- **Revisit when**: When recruiter action matrix needs single source of truth
- **Introduced in**: 2026-05-12
- **Last reviewed**: 2026-05-12
- **Current decision**: Recruiter **lifecycle governance** semantics remain **explicitly distributed**: ``orchestrator/vertical_slice_planner.py`` maps ingress ``event_type`` + ``PipelinePhase`` → ``ProposedTransition`` (including wrong-phase / terminal **empty plans** for deterministic NOOPs); ``state_machine/transition_engine.py`` / ``default_pipeline_registry()`` own **edge legality** and **allowed triggers**; ``schemas/governance_schema.py`` constrains **ingress payload shape**; HTTP/adapters must not contaminate those payloads (``extra=forbid``). This is **acceptable** for the current **bounded vertical slice**: each layer stays small, testable, and replay-stable without a second source of truth.
- **Rationale**: A **full policy engine** (generic condition/action interpreter, dynamic rule loading, implicit trigger resolution) would add **entropy** now—harder to prove determinism, easier to hide routing in “data,” and more surfaces for drift between “what operators think happened” and what the engine validated. The slice prioritizes **legible, harness-backed** behavior over premature centralization.
- **Future impact**: As **more recruiter actions**, **deeper lifecycle**, **multiple operator personas**, and **governance product evolution** land, the same facts will be touched in more places—risk of **semantic drift** (e.g. duplicate-action behavior, terminal handling, trigger names) unless coordination discipline improves.
- **Priority**: Low (**not urgent** while the slice stays narrow and planner-owned tables remain reviewable).
- **Recommended future direction** (still **deterministic-first**; **not** an autonomous policy runtime):
  - **Declarative governance transition registry**: single versioned table (event × from-phase × to-phase × trigger × audit template) consumed by the planner **or** generated into planner code—**transition engine remains authoritative** for legality.
  - **Terminal-state semantics table**: explicit matrix for which phases reject / NOOP / require override—shared by planner and docs, validated by harness.
  - **Duplicate-action policy normalization**: one documented rule (e.g. always NOOP vs explicit rejection envelope) applied consistently and asserted in tests.
  - **Shared governance capability metadata**: small schema or doc artifact listing supported actions, allowed phases, and decision codes for operators and integrations—**read-only** projections derive from it where helpful.

### Shared delivery semantics taxonomy (event bus + handlers)
- **Status**: OPEN
- **Scope**: Bus+Contracts
- **Revisit when**: When second bus implementation or broker adapter lands
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
- **Scope**: Contracts
- **Revisit when**: When cross-layer trace linking breaks in production incidents
- **Introduced in**: 2026-05-08
- **Last reviewed**: 2026-05-08
- **Current decision**: Keep execution metadata (trace/request/correlation/causation ids, actor ids, event/execution ids, tags) defined per interface/schema layer, with explicit fields and `extensions` as the escape hatch.
- **Rationale**: Execution metadata needs differ across events, skills, and state transitions. Early consolidation risks hidden coupling and accidental “global context” creep.
- **Future impact**: Observability and audit trails may become inconsistent across events vs. skill runs (different naming, missing links), reducing replayability and root-cause analysis quality.
- **Priority**: High
- **Recommended future direction**: Introduce a shared “execution identifiers” contract (trace/request/correlation/causation/event/execution ids + actor) that can be embedded by composition in events, skill results, and transition records—without adding orchestration logic. Validate link completeness via the harness.

### Future shared timing/audit abstractions
- **Status**: OPEN
- **Scope**: Contracts
- **Revisit when**: When correlating skill timing vs envelope time becomes blocking
- **Introduced in**: 2026-05-08
- **Last reviewed**: 2026-05-08
- **Current decision**: Timing and audit fields are currently modeled independently per contract (events, state, skills) with only minimal alignment.
- **Rationale**: The project is still discovering which timing/audit fields are truly universal (e.g., started_at/ended_at vs. recorded_at vs. updated_at).
- **Future impact**: Harder to correlate timelines across layers (event timestamps vs. skill execution timing vs. state updates), increasing debugging and compliance effort.
- **Priority**: Medium
- **Recommended future direction**: Define shared `ExecutionTiming` / `ExecutionAudit` building blocks once the minimum required set is proven across at least two subsystems; preserve deterministic-first principles by keeping all audit/timing as *recorded facts* rather than auto-mutating behavior.

### Deterministic runtime clock governance (fake skills + slice execution)
- **Status**: OPEN
- **Scope**: Skills
- **Revisit when**: When mixing real and fake skills in one run needs unified logical clock
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
- **Scope**: Contracts+Ops
- **Revisit when**: When SLO/alerting needs unified failure codes
- **Introduced in**: 2026-05-08
- **Last reviewed**: 2026-05-08
- **Current decision**: Maintain localized failure enums/taxonomies (events vs. messaging vs. skill execution) to avoid prematurely locking in semantics.
- **Rationale**: Failures have different remediation paths depending on layer (validation vs. dependency vs. timeout vs. policy), and the system does not yet have stable operational playbooks.
- **Future impact**: Inconsistent failure categorization complicates alerting, SLO reporting, and deterministic replay (different “retryable” or “transient” meanings).
- **Priority**: High
- **Recommended future direction**: Consolidate to a single failure taxonomy with clear layer-agnostic definitions (category/code/message/details_ref + retryability as a signal only). Enforce mapping rules in deterministic code (not prompts) and validate via the harness.

### Potential async skill execution migration
- **Status**: OPEN
- **Scope**: Orchestrator+Skills
- **Revisit when**: When first long-running integration skill is specified
- **Introduced in**: 2026-05-08
- **Last reviewed**: 2026-05-08
- **Current decision**: Keep skill execution synchronous at the contract level (bounded call returning a result), and represent longer workflows via event-driven orchestration rather than async skill interfaces.
- **Rationale**: Deterministic orchestration + replayability is easier when skills are bounded and results are recorded as immutable facts; async interfaces can hide partial state and complicate auditability.
- **Future impact**: Some skills may naturally be long-running (external parsing, integrations, human-in-the-loop). Without an async pathway, the orchestrator may need wrapper patterns that encode progress as events.
- **Priority**: Medium
- **Recommended future direction**: If needed, migrate via an *execution envelope* pattern: synchronous “start” skill emits an execution id + references; progress/completion is represented as events/results with the same contract invariants. Avoid embedding routing/retry/state transitions into the skill interface.

### Orchestration side-effect consistency after publish failure
- **Status**: OPEN
- **Scope**: Orchestrator
- **Revisit when**: When adding outbox or atomic emit+state commit
- **Introduced in**: 2026-05-11
- **Last reviewed**: 2026-05-12
- **Current decision**: The synchronous orchestrator applies validated state transitions and runs skills **before** it attempts to publish derived events; publish outcomes are checked only after those steps. On publish failure, the returned `OrchestrationExecutionResult` does not commit a new `OrchestrationState`, but **skills may already have executed** and any external side effects from skills are outside the orchestrator's rollback scope.
- **Rationale**: This ordering is an intentional, bounded tradeoff for the first **single-process vertical-slice** runtime: it prioritizes a runnable `event → validate → skills → state → emit` path **without** introducing **atomic** coupling between (a) **bus publish outcomes** and (b) **durable snapshot commits**—i.e. no transactional outbox, no single ACID unit across “emit envelope” + “persist derived state,” and no distributed consistency machinery in the control plane yet. SQLite can still transactionally persist **snapshots** in the store layer; the gap is **cross-layer** atomicity with emissions.
- **Future impact**: Operators and replay tooling may observe **partial effects** (e.g., skill side effects or prior successful publishes in a multi-emission batch) when emission fails mid-flight, complicating audit narratives and recovery unless callers compensate explicitly.
- **Priority**: Medium
- **Recommended future direction**: Harden cross-layer consistency as **snapshot persistence** and **ingress volume** grow (SQLite today does not remove publish-vs-store ordering risks):
  - **Transactional outbox**: record intended emissions atomically with state commits; publish from the outbox with idempotent consumers.
  - **Durable event store**: append-only log as the source of truth for “what was emitted,” aligned with correlation/causation ids.
  - **Exactly-once / eventual consistency strategies**: idempotent event handlers, dedupe keys, and documented dual-write semantics where full ACID across bus + DB is unavailable.
  - **Replay-safe recovery semantics**: deterministic reconciliation jobs and harness-defined rules for “continue from last acknowledged emission” vs. full segment replay.

### Planner determinism verification harness
- **Status**: IN_PROGRESS
- **Scope**: Orchestrator+Replay
- **Revisit when**: When second planner module lands or CI adds banned-API lint
- **Introduced in**: 2026-05-11
- **Last reviewed**: 2026-05-12
- **Current decision**: `OrchestrationStepPlanner` implementations are **expected** to be deterministic, pure policy code (no LLM routing, no autonomous workflow control). The orchestrator **does not verify** that property directly. **Partial coverage**: vertical-slice workflow replay (happy + negative paths) plus **SQLite persistence tests** (e.g. ``tests/persistence/test_sqlite_state_store.py``) exercise **VerticalSlicePlanner** outputs **indirectly** via orchestration results, transition outcomes, and reloaded snapshots under fixed envelopes—strong signal for wiring drift, **not** a substitute for planner-isolated property tests or banned-API lint.
- **Rationale**: Centralizing planner analysis in the orchestrator would blur the boundary between execution and policy; dedicated planner harnesses were deferred until planner modules multiply. Replay tests now provide an interim integration guardrail.
- **Future impact**: A nondeterministic or environment-coupled planner still undermines replay guarantees if bugs hide behind coincidentally stable scenarios; dedicated planner tests remain valuable.
- **Priority**: Low
- **Recommended future direction**: Add engineering guardrails as planners grow:
  - **Deterministic replay harnesses**: fixed seeds, frozen clocks, recorded envelopes → expect bit-for-bit stable plans or stable normalized plan hashes where appropriate.
  - **Nondeterminism detection**: optional static/dynamic checks for banned APIs (random, wall-clock reads outside injected time, hidden global mutable state).
  - **Planner invariant testing**: property tests over state/event pairs for monotonicity, allowed triggers, and schema-safe payloads.
  - **Forbidden entropy source checks**: CI lint or runtime probes for `random`, uncontrolled `datetime.now`, environment reads, and network calls inside planner modules.

### Conditional questionnaire workflow branching (vertical slice planner)
- **Status**: OPEN
- **Scope**: Orchestrator
- **Revisit when**: When product requires questionnaire bypass or alternate templates
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
- **Scope**: Bus
- **Revisit when**: When handlers emit nested publishes in production wiring
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
- **Scope**: Bus+Ops
- **Revisit when**: When multi-subscriber latency becomes measured problem
- **Introduced in**: 2026-05-11
- **Last reviewed**: 2026-05-11
- **Current decision**: In-memory dispatch applies only fixed numeric caps (subscriptions registered, max handler dispatches per publish); there is no cooperative **slow consumer** or load-shedding signal beyond bounded counts.
- **Rationale**: Backpressure bridges runtime policy and operational capacity; the first slice targets deterministic correctness on a single thread with explicit limits, not fair scheduling across subscribers.
- **Future impact**: Pathological handlers can still tie up the publisher thread for long CPU-bound stretches; observability may show latency without a structured “apply pressure” channel.
- **Priority**: Medium
- **Recommended future direction**: When persistence or multi-tenant handlers arrive, introduce deterministic **backpressure signals** (skip with audit reason, structured ``HandleResult``, or caller-owned admission control) without introducing async brokers—keep semantics documented in the shared delivery taxonomy.

### Publish aggregate status precedence governance (event bus)
- **Status**: OPEN
- **Scope**: Bus+Contracts
- **Revisit when**: When second bus impl must match publish aggregation semantics
- **Introduced in**: 2026-05-11
- **Last reviewed**: 2026-05-11
- **Current decision**: The in-memory bus aggregates subscriber ``HandleResult.status`` values into a single ``PublishResult.status`` using an implementation-defined precedence (currently: any ``failed`` wins, else any ``rejected``, else all ``skipped`` → ``skipped``, else ``accepted``).
- **Rationale**: A vertical slice needs a predictable rule set quickly; global precedence semantics were deferred until multiple bus implementations and orchestrator coupling patterns exist.
- **Future impact**: Different runtimes could aggregate differently unless documented, harming cross-environment audits and replay comparisons (“publish succeeded” vs. “one subscriber failed”).
- **Priority**: Medium
- **Recommended future direction**: Publish a **canonical precedence table** + ack implications in architecture docs; add harness tests across reference implementations; consider explicit ``PublishResult.extensions`` fields for per-status counts instead of inferring from traces alone.

### Candidate multi-state index governance (in-memory state store)
- **Status**: OPEN
- **Scope**: Persistence
- **Revisit when**: When multiple active orchestrations per candidate are required
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
- **Scope**: Contracts
- **Revisit when**: When 2+ stable confidence semantics converge
- **Introduced in**: 2026-05-08
- **Last reviewed**: 2026-05-08
- **Current decision**: Keep confidence concepts local to each contract layer (e.g., candidate confidence vs. skill execution confidence) until the semantics stabilize.
- **Rationale**: Confidence is overloaded early (model confidence vs. data completeness vs. human certainty). Premature consolidation risks forcing a misleading “one-size-fits-all” meaning.
- **Future impact**: Fragmentation across schemas/interfaces makes aggregation, calibration, and governance reporting harder (different fields, ranges, and rationale representations).
- **Priority**: Medium
- **Recommended future direction**: Define a shared confidence contract (score/level/rationale_ref + extensions) once at least 2–3 stable confidence use-cases converge; migrate via backward-compatible adapters and harness checks.

### Evidence reference standardization (domain + execution)
- **Status**: OPEN
- **Scope**: Contracts+Persistence
- **Revisit when**: When evidence storage / viewer MVP ships
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
- **Scope**: Contracts
- **Revisit when**: When schema drift from string vocab hurts integrations
- **Introduced in**: 2026-05-08
- **Last reviewed**: 2026-05-08
- **Current decision**: Enums exist per schema module without a shared vocabulary package; some fields intentionally remain free-form `str` to avoid premature enum fragmentation.
- **Rationale**: Vocabulary evolves with product learning. Centralizing too early creates churn and accidental coupling across schemas.
- **Future impact**: Divergence risk increases (similar concepts named differently across schemas), and integrations may depend on inconsistent strings.
- **Priority**: Medium
- **Recommended future direction**: Establish a `schemas/domain/` vocabulary package that includes stable enums, string vocab registries, and backward-compatible aliases. Promote entries only when they are proven stable and covered by harness validation.

### Event naming convention governance
- **Status**: OPEN
- **Scope**: Contracts
- **Revisit when**: When event type proliferation complicates replay docs
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
- **Scope**: DX
- **Revisit when**: When planning large cross-package refactors
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
- **Scope**: Orchestrator+DX
- **Revisit when**: When audit reports show stale updated_at in production
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
- **Scope**: Ops
- **Revisit when**: When query load or UI projections justify CQRS split
- **Introduced in**: 2026-05-08
- **Last reviewed**: 2026-05-08
- **Current decision**: Candidate aggregate may contain optional snapshots/refs; no dedicated read models yet.
- **Rationale**: Keep architecture simple until real query patterns and UI needs emerge.
- **Future impact**: Mixed read/write concerns can slow product iteration and complicate performance tuning.
- **Priority**: High
- **Recommended future direction**: Separate write-side contracts (events/state) from read-side projections (query-optimized materializations).

### Future event sourcing optimization
- **Status**: OPEN
- **Scope**: Persistence+Ops
- **Revisit when**: When event volume forces partition/index strategy
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
- **Scope**: TransitionEngine+Contracts
- **Revisit when**: When multi-domain transitions need stricter typing
- **Introduced in**: 2026-05-08
- **Last reviewed**: 2026-05-08
- **Current decision**: `StateTransitionRecord` supports multiple domains using `state_domain` + validated `from_state`/`to_state` strings.
- **Rationale**: Avoids over-coupling while enabling cross-domain timeline reconstruction.
- **Future impact**: Less static type safety; domain expansion increases validator complexity.
- **Priority**: Medium
- **Recommended future direction**: Consider discriminated union transition records per domain (pipeline/decision/communication) with typed enums per record.

### Extraction of default transition registries from the engine module
- **Status**: OPEN
- **Scope**: TransitionEngine+DX
- **Revisit when**: When engine file size blocks rule pack reviews
- **Introduced in**: 2026-05-11
- **Last reviewed**: 2026-05-11
- **Current decision**: Keep `default_pipeline_registry()` (and similar defaults) co-located with `transition_engine.py` for early discoverability.
- **Rationale**: A single module reduces indirection while the rule set is small and there is only one consumer; moving too early splits governance from implementation without clear benefit.
- **Future impact**: As domains and rule variants grow, default registries in the engine file increase noise and make versioned rule packs harder to swap in tests and production.
- **Priority**: Low
- **Recommended future direction**: Move default registries to `state_machine/registries/` (or `state_machine/rules/`) as explicit versioned modules (e.g. `pipeline_v1.py`) loaded by wiring code; keep `TransitionEngine` free of product-specific graphs.

### Transition registry modularization (multi-domain rule packs)
- **Status**: OPEN
- **Scope**: TransitionEngine
- **Revisit when**: When composing multiple rule packs with merge tests
- **Introduced in**: 2026-05-11
- **Last reviewed**: 2026-05-11
- **Current decision**: Use one immutable `TransitionRegistry` type with a flat sorted rule tuple; compose multiple domains in a single registry instance when needed.
- **Rationale**: Keeps the validation engine simple and deterministic; premature package fragmentation can obscure global invariants (e.g. terminal sets, trigger naming).
- **Future impact**: Large monolithic registries become harder to review, diff, and assign ownership; cross-pack conflicts (duplicate `rule_id`, overlapping edges) need explicit policy.
- **Priority**: Medium
- **Recommended future direction**: Introduce composable registry builders (merge with deterministic conflict rules), namespace `rule_id` prefixes per pack, and harness tests for merge semantics and replay alignment with `rule_set_id`.
