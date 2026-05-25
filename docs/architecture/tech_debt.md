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

### Local SQLite schema/cutover migration strategy
- **Status**: OPEN
- **Scope**: Persistence+DX
- **Revisit when**: Before the next breaking local schema/cutover round or before any expectation of preserving developer SQLite rows across upgrades
- **Introduced in**: 2026-05-25
- **Last reviewed**: 2026-05-25
- **Current decision**: The single-tenant reference runtime treats local SQLite as a disposable developer store. When schema or cutover changes invalidate old local rows, the supported workflow is to reset/delete `data/app.db` and let the app recreate it on boot/reset.
- **Rationale**: This keeps approved cutovers small and honest while the MVP surface is still evolving quickly. It avoids smuggling migration complexity into runtime read/write paths before a durable migration contract exists.
- **Future impact**: Repeated local resets are acceptable for MVP development, but they do not scale into a stable operator/developer upgrade story once data longevity matters or schema changes become frequent.
- **Priority**: Medium
- **Recommended future direction**: Define an explicit local migration stance: either (a) codified disposable-dev SQLite with automated reset tooling, or (b) a lightweight deterministic migration/upcaster path with version checks and failure guidance. Do not revive runtime compatibility shims as a substitute for a real migration strategy.

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

## Evaluation and extension persistence

### Extensions namespace structure after evaluation cutover
- **Status**: OPEN
- **Scope**: Persistence+Contracts
- **Revisit when**: When extension keys multiply or a second producer starts writing the same diagnostic/governance prefixes
- **Introduced in**: 2026-05-25
- **Last reviewed**: 2026-05-25
- **Current decision**: Current score/filter semantics no longer live in ``extensions``. Typed snapshot fields (``ingress_profile``, ``evaluation``, ``ingress_flags``) are canonical. ``extensions`` remains a flat escape hatch for diagnostic or governance-adjacent facts such as ``inactive.*`` and ``governance.*``.
- **Rationale**: The approved decision/evaluation cutover removed dual semantics and made typed snapshot fields the only supported read/write path for evaluation.
- **Future impact**: Remaining flat extension keys can still grow without collision policy, especially as more diagnostic and operator-facing metadata accumulates.
- **Priority**: Medium
- **Recommended future direction**: Define typed logical namespaces or a versioned schema contract for extension keys (prefix rules, allowlists, or nested typed sub-documents).

### Evaluation evidence lineage
- **Status**: OPEN
- **Scope**: Persistence
- **Revisit when**: When operator UI needs per-skill evidence attribution
- **Introduced in**: 2026-05-12
- **Last reviewed**: 2026-05-25
- **Current decision**: Evidence references now live on typed evaluation surfaces (``evaluation.hard_filter.evidence_refs``, ``evaluation.light.evidence_refs``, ``evaluation.deep.evidence_refs``), but there is still no first-class linkage to the exact skill execution id or transition that produced each ref.
- **Rationale**: The typed evaluation cutover preserves per-surface evidence without introducing a second lineage model in the same round.
- **Future impact**: Operators and audits can distinguish surface-level evidence, but cannot yet pinpoint the precise producing execution without correlating run history manually.
- **Priority**: Medium
- **Recommended future direction**: Add per-step or per-skill attribution (e.g. structured entries with producer, execution id, and transition/event lineage) while keeping typed evaluation as the canonical read model.

### Evaluation-to-transition linkage
- **Status**: OPEN
- **Scope**: Persistence+Orchestrator
- **Revisit when**: When audit tooling needs transition-scoped decision facts
- **Introduced in**: 2026-05-12
- **Last reviewed**: 2026-05-25
- **Current decision**: Evaluation state lives on the aggregate snapshot and is read directly from typed fields. There is still no explicit lineage id tying a given evaluation surface update to a specific transition or skill execution beyond temporal ordering and run history.
- **Rationale**: Keeps the cutover simple and avoids introducing a second persistence contract during the same round.
- **Future impact**: Targeted audit/debug remains harder than necessary when asking “which transition or execution wrote this evaluation surface?”.
- **Priority**: Low
- **Recommended future direction**: Introduce explicit lineage (transition id, ingested ``event_id``, execution id, or step index) for evaluation updates and align operator read models to that provenance.

### Evaluation precedence semantics
- **Status**: OPEN
- **Scope**: Persistence
- **Revisit when**: When UI/API must show single authoritative score
- **Introduced in**: 2026-05-12
- **Last reviewed**: 2026-05-25
- **Current decision**: ``evaluation.light`` and ``evaluation.deep`` coexist. Current recruiter-facing read models use a simple deep-over-light precedence for overall score display, while still exposing both surfaces separately.
- **Rationale**: Light and deep remain different evaluation stages, but the typed cutover makes their separation explicit instead of hiding it in flat keys.
- **Future impact**: UI or policy may still disagree on “the” candidate score unless precedence stays documented and versioned.
- **Priority**: Low
- **Recommended future direction**: Keep precedence explicit for display/ranking, or evolve toward versioned stage records if product semantics need stronger audit guarantees.

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
- **Status**: SUPERSEDED
- **Scope**: API+Persistence
- **Revisit when**: N/A (see successor entries below)
- **Introduced in**: 2026-05-12
- **Last reviewed**: 2026-05-22
- **Current decision**: **Superseded** by Stage B multi-candidate wiring: ``POST /events`` and read APIs accept arbitrary ``candidate_id`` values; orchestration snapshots are created on **ingress (write path)** and resolved via the store’s ``get_for_candidate`` index. The bootstrap **default demo candidate** remains the wired reference subject for ``/demo/*`` and timeline (see **Timeline is global, not candidate-scoped**).
- **Rationale**: Original entry tracked pre–Stage B single-aggregate HTTP rejection; behavior has moved forward without closing all related debt (mapping duplication, global timeline).
- **Future impact**: None as a standalone gate; follow **Candidate → state_id mapping (single source of truth)** and timeline entries instead.
- **Priority**: Low
- **Recommended future direction**: Treat this registry row as historical; do not re-open unless aggregate lifecycle requirements regress.

### Candidate → state_id mapping (single source of truth)
- **Status**: OPEN
- **Scope**: API+DX
- **Revisit when**: Before changing namespace, mapping format, or orchestration id versioning (including replay fixture regeneration)
- **Introduced in**: 2026-05-22
- **Last reviewed**: 2026-05-22
- **Current decision**: Deterministic ``candidate_id → orchestration state id`` uses the same formula in **two places** today:
  - **Application layer (canonical for writes)**: ``modules/recruitment/registry.py`` — ``get_state_id(candidate_id)`` → ``uuid5(BOOT_NS, f"candidate:{candidate_id}")``; consumed by ``modules/recruitment/use_cases.py`` (``_ensure_candidate_state`` before ingress publish).
  - **Bootstrap wiring (duplicated)**: ``modules/recruitment/bootstrap.py`` — private ``_state_id_for_candidate(candidate_id)`` with the **same** ``uuid5(_BOOT_NS, f"candidate:{candidate_id}")`` expression for ``VERTICAL_SLICE_DEFAULT_STATE_ID``, ``_state_id()``, and initial slice wiring.
  The subscriber resolves live state via ``store.get_for_candidate(envelope.subject_id)`` and does **not** import the registry (intentional boundary). **No refactor is scheduled in the current milestone**—behavior and tests remain as-is.
- **Rationale**: **Acceptable short-term**: bootstrap needed stable default ids before ``registry.py`` existed; duplicating a one-line deterministic formula avoided bootstrap → application import cycles during the modular monolith migration. The formula is trivial and currently identical in both sites.
- **Future impact** (if left unresolved when mapping evolves):
  - **Inconsistent mapping** if one site changes namespace, string format, or versioning and the other does not.
  - **Replay / harness mismatch** when bootstrap-created snapshots use a different ``state_id`` than ingress-created rows for the same ``candidate_id``.
  - **Bootstrap encodes domain identity** despite being a wiring layer—future contributors may “fix” mapping in the wrong file.
- **Priority**: Medium
- **Recommended future direction** (do **not** implement until explicitly scheduled):
  - **Centralize** mapping in one application module—e.g. extend ``modules/recruitment/registry.py`` or introduce ``modules/recruitment/identity.py`` with a single exported function (same semantics, documented contract).
  - **Bootstrap imports** that function for ``VERTICAL_SLICE_DEFAULT_STATE_ID`` / ``_state_id()`` instead of redefining ``_state_id_for_candidate``.
  - Add a **harness or unit test** that asserts bootstrap default ids equal ``get_state_id(VERTICAL_SLICE_DEFAULT_CANDIDATE_ID)`` so drift is caught in CI.
  - Coordinate with **Candidate multi-state index governance** if composite keys (job, workflow version) replace the flat ``candidate:{id}`` string.

### Candidate list is store-driven (not domain-driven)
- **Status**: OPEN
- **Scope**: API
- **Revisit when**: When multi-application-per-candidate or candidate lifecycle outside pipeline is required
- **Introduced in**: 2026-05-22
- **Last reviewed**: 2026-05-22
- **Current decision**: ``GET /candidates`` is implemented by ``list_candidates`` in ``modules/recruitment/use_cases.py``, which calls ``store.list_all_state_ids()``, loads each snapshot, and projects via ``build_candidate_list_item``. There is **no** explicit candidate aggregate, application entity, or domain registry—only orchestration snapshots indexed by ``StateLink`` (candidate kind).
- **Rationale**: Stage B MVP needs a recruiter-facing list **without** new persistence models or snapshot schema changes; store enumeration reuses existing SQLite/in-memory stores and keeps the read path simple.
- **Future impact** / **risks**—cannot support without redesign:
  - **Multiple applications per candidate** (same person, different reqs / pipelines).
  - **Candidate lifecycle** independent of orchestration pipeline phase (archived, dormant, deleted).
  - **Deletion / archiving** semantics (list always reflects “whatever states exist in the store”).
- **Priority**: Medium
- **Recommended future direction**: Introduce a **candidate / application** domain model (or explicit registry table) as the list source of truth; treat orchestration state as a child resource; keep projections read-only over snapshots.

### Candidate list has no pagination or filtering
- **Status**: OPEN
- **Scope**: API
- **Revisit when**: Before recruiter UI lists more than a small bounded set of candidates per tenant
- **Introduced in**: 2026-05-22
- **Last reviewed**: 2026-05-22
- **Current decision**: ``list_candidates`` loads **all** snapshots into memory, builds the full list, and returns it with **no** ``limit``/``offset``, cursor, or filters (stage, status, search). Sort is **deterministic** by ``candidate_id`` string only—not recruiter-facing recency or score order (see TODO in ``use_cases.list_candidates``).
- **Rationale**: Acceptable for single-tenant Stage B demos and integration tests; defers query design until domain list semantics exist.
- **Future impact** / **risks**:
  - **Performance degradation** as distinct orchestration states grow (full scan + N snapshot loads per request).
  - **API unsuitable for real UI** at scale without pagination and basic filters.
- **Priority**: Medium
- **Recommended future direction**: Add **limit/offset** or **cursor** pagination on the list use case; support basic filters (``stage``, ``status.kind``, optional search); drive queries from domain/registry or indexed read models—not unbounded ``list_all_state_ids`` in hot paths.

### CV ingestion evolution (MVP ``cv_submitted``)
- **Status**: OPEN
- **Scope**: Skills+API
- **Revisit when**: When LLM parsing or multi-stage CV enrichment is required
- **Introduced in**: 2026-05-22
- **Last reviewed**: 2026-05-25
- **Current decision**: Real CV ingress now supports bounded PDF upload payloads at the API boundary, which are deterministically converted into plain ``cv_text`` and then published as the existing ``cv_submitted`` event. The bounded LLM skill still emits typed ``ingress_profile`` plus ``evaluation.light``; deterministic stages own hard filtering, deep scoring, ranking, and routing. Demo flows may still use ``cv_uploaded`` in scripted sequences, but current recruiter semantics come from the typed snapshot path.
- **Rationale**: One business action per event preserves usable ingress while allowing bounded cognition where it matters: semantic extraction from real recruiter-provided CV artifacts.
- **Future impact**: Later stages can add richer artifact references, multi-stage enrichment, or separate parse/score edges without leaking workflow control into prompts or reviving flat score keys.
- **Priority**: Medium
- **Recommended future direction**: Split or wrap ``cv_parse_and_score`` only when bounded artifact storage, payload contracts, and provider operations need it; keep orchestration contracts stable and deterministic.

### Coarse `scoring_failed` failure taxonomy
- **Status**: OPEN
- **Scope**: API+Skills
- **Revisit when**: When retry policy, operator messaging, or provider observability needs differ by failure class
- **Introduced in**: 2026-05-25
- **Last reviewed**: 2026-05-25
- **Current decision**: `cv_submitted` fail-closed behavior currently collapses provider/config/validation failures into a single application/API surface: `scoring_failed`.
- **Rationale**: Keeps the cutover stable and predictable while the first bounded provider path is being hardened; avoids accidental workflow continuation on partial cognition failures.
- **Future impact**: Retries, alerting, operator guidance, and API ergonomics cannot distinguish authorization vs network vs invalid-response vs not-configured failures.
- **Priority**: High
- **Recommended future direction**: Preserve fail-closed behavior, but split `scoring_failed` into deterministic subcodes with explicit retryability and provider-category mapping at the application boundary.

### Recruiter action label ownership
- **Status**: OPEN
- **Scope**: API
- **Revisit when**: When recruiter UI needs copy changes, i18n, or role-specific phrasing without touching governance vocabulary
- **Introduced in**: 2026-05-22
- **Last reviewed**: 2026-05-22
- **Current decision**: ``available_actions[].label`` is resolved via ``ACTION_DESCRIPTORS`` in ``modules/recruitment/policies.py`` (keyed by ``event_type``) with **fallback** to ``label_from_event_type`` (string transform) when no descriptor exists. Availability remains **registry-only**; descriptors are UI metadata, not a second action map.
- **Rationale**: Decouples display copy from domain ``event_type`` names for catalogued actions while keeping a deterministic fallback for registry-only events (e.g. ``recruiter_shortlist_candidate``) before descriptors are added.
- **Future impact** / **risks**:
  - **Copy changes** for uncatalogued events still require accepting transform output or adding a descriptor entry.
  - **No multi-language or role-specific phrasing** in the API layer today.
  - **Drift** if frontend and ``ACTION_DESCRIPTORS`` diverge when clients render their own labels.
- **Priority**: Low
- **Recommended future direction**: Expand ``ACTION_DESCRIPTORS`` (or a dedicated labels module) for all recruiter ``event_type`` values exposed by the registry; alternatively move label responsibility entirely to the **frontend** and return ``event_type`` only from the API.

### Action availability ignores transition guards
- **Status**: OPEN
- **Scope**: API+TransitionEngine
- **Revisit when**: When guard-conditioned edges must hide actions until prerequisites are met
- **Introduced in**: 2026-05-22
- **Last reviewed**: 2026-05-22
- **Current decision**: ``get_available_actions_for_phase`` exposes an action if a registry rule applies (``from_state`` is the current phase or ``*``) and carries a resolvable ``manual_recruiter_*`` trigger. It does **not** evaluate **guard conditions** on those rules or snapshot context.
- **Rationale**: Keeps list derivation read-only and cheap; guards may be stubs or context-dependent in the reference slice.
- **Future impact** / **risks**:
  - **UI may show actions** that orchestration would reject when guards fail.
  - Operators may attempt actions that appear available but produce no plan or a validation failure downstream.
- **Priority**: Medium
- **Recommended future direction**: Evaluate guards (or call :class:`~state_machine.transition_engine.TransitionEngine` validation with current snapshot) before exposing an action; or return a **conditionally available** flag when guards are not satisfied.

### Untyped recruiter action payloads
- **Status**: OPEN
- **Scope**: API+Contracts
- **Revisit when**: When recruiter actions require structured fields (interview slot, offer terms, audit templates)
- **Introduced in**: 2026-05-22
- **Last reviewed**: 2026-05-22
- **Current decision**: ``perform_candidate_action`` and ``POST /candidates/{candidate_id}/action`` accept an optional ``payload`` as ``Dict[str, Any]``, merged over fixed API governance defaults. There is **no** per-``event_type`` payload schema or validation before publish.
- **Rationale**: Stage B wires existing governance events through one action API before investing in action-specific forms.
- **Future impact** / **risks**:
  - **No validation per action** — missing or inconsistent fields across clients.
  - **Fragile integration** when new registry triggers add actions with implicit payload expectations.
  - **Audit ambiguity** when downstream systems expect structured evidence per action type.
- **Priority**: Medium
- **Recommended future direction**: Define **per-``event_type`` payload schemas** (Pydantic models) and validate in ``perform_candidate_action`` before publish; keep optional ``payload`` for backward compatibility until clients migrate.

### Recruiter action list ordering and grouping (UI)
- **Status**: OPEN
- **Scope**: API
- **Revisit when**: When recruiter list UI needs sections (lifecycle, risk, priority)
- **Introduced in**: 2026-05-22
- **Last reviewed**: 2026-05-22
- **Current decision**: ``available_actions`` is a **flat list** sorted by ``event_type`` string only—no grouping, priority, or role-based ordering.
- **Rationale**: Stage B MVP exposes registry truth without product semantics.
- **Future impact**: Recruiter clients must invent their own ordering; inconsistent UX across surfaces.
- **Priority**: Low
- **Recommended future direction**: Add optional **group** / **sort_order** metadata derived from registry ``rule_id`` or product policy—without reintroducing duplicate action-key tables.

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
- **Last reviewed**: 2026-05-22
- **Current decision**: Inspection (`runtime/inspection/`) and **`GET /timeline/{candidate_id}`** expose **deterministic plain text** timelines only. There is **no** canonical structured timeline schema (JSON rows, typed segments) or alternate renderers (UI components, export formats) in the reference runtime. **Scope caveat**: timeline content is **not** candidate-scoped today—see **Timeline is global, not candidate-scoped (multi-candidate safety)**.
- **Rationale**: Human-readable text is the smallest **read-only** projection for early operator visibility on the reference slice; structured timelines add schema churn before operator and integration contracts stabilize.
- **Future impact**: Downstream tools cannot consume **machine-stable** timeline entries without parsing text; multiple surfaces may diverge if each invents its own JSON.
- **Priority**: Medium
- **Recommended future direction**: Introduce an intermediate **structured timeline model** (immutable facts → entries) shared by **text / JSON / UI** renderers; keep rendering **non-authoritative** and **deterministic**; align with **Inspection event-history provenance and catalog governance** and **Timeline is global, not candidate-scoped**.

### Timeline is global, not candidate-scoped (multi-candidate safety)
- **Status**: OPEN
- **Scope**: Inspection+API
- **Revisit when**: When exposing timeline for non-default candidates or shipping recruiter-facing audit/history UX
- **Introduced in**: 2026-05-22
- **Last reviewed**: 2026-05-22
- **Current decision**: Timeline rendering is **system-level**, not per-candidate:
  - **Data sources**: global ``bundle.subscriber.run_history`` (all orchestration runs handled by the wired subscriber) plus a **merged envelope catalog** (primary scripted ingress + ``RecordingInMemoryEventBus.recorded_envelopes`` when present)—see ``modules/recruitment/projection.get_timeline`` and ``runtime/inspection``.
  - **Important**: This is **not** a candidate audit trail. It reflects **process-wide execution artifacts** for the single wired bus/subscriber, not an isolated history keyed by ``candidate_id``.
  - **Multi-candidate workaround (explicit, no filtering yet)**: ``GET /timeline/{candidate_id}`` via ``get_timeline_for_candidate`` allows timeline **only** when ``candidate_id`` equals the bootstrap **default demo candidate** (``VERTICAL_SLICE_DEFAULT_CANDIDATE_ID``). Any other candidate id returns **404** (`CandidateNotFoundError`: ``timeline not supported for multi-candidate yet``), **even if** that candidate has orchestration state from ``POST /events``. **No candidate filtering is implemented** in this milestone—behavior is intentionally unchanged.
- **Rationale**: **Acceptable short-term** after Stage B multi-candidate ingress: exposing the global timeline for arbitrary ids would **leak cross-candidate runs** (misleading or unsafe). A 404 gate is safer than implying per-candidate history. Filtering and catalog scoping are deferred to avoid false “audit trail” semantics before contracts exist.
- **Future impact** / **risks**:
  - **Misleading interpretation**: developers or recruiters may treat ``GET /timeline/{id}`` as **that candidate’s workflow history**—it is not, unless/until candidate-scoped filtering exists.
  - **Future bugs**: re-enabling timeline for all candidates **without** filtering would mix ``run_history`` and bus tapes across candidates—**cross-candidate contamination** in one text blob.
  - **Product gap**: non-demo candidates have state/summary/candidate view but **no** timeline surface until scoping is designed.
- **Priority**: High (safety + clarity for multi-candidate Stage B)
- **Recommended future direction** (do **not** implement until explicitly scheduled):
  - **Option A (preferred)**: Make timeline **candidate-aware**—filter ``run_history`` and catalog envelopes by ``envelope.subject_id == candidate_id`` (and/or correlation policy); render only matching orchestration runs; add harness tests for two-candidate isolation on timeline text.
  - **Option B**: **Deprecate** timeline as a recruiter-facing product feature—keep plain-text rendering as **debug/harness-only** (CLI, internal tools), not ``GET /timeline`` on the public API.
  - In either case, document in API/operator docs that timeline is **not** canonical audit (transition records + persisted snapshot remain source of truth until a durable event read model exists—see **Inspection event-history provenance and catalog governance**).

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

## Post-Workflow-Alignment Stabilization

### Placeholder ranking policy
- **Status**: OPEN
- **Scope**: Skills+Orchestrator
- **Revisit when**: When multi-candidate ranking is needed for production shortlisting or automated scoring
- **Introduced in**: 2026-05-14
- **Last reviewed**: 2026-05-14
- **Current decision**: The reference vertical slice uses a placeholder policy (`runtime/vertical_slice_ranking.py`): single-candidate, deterministic branch resolution (`ranking.branch` override + fixed defaults).
- **Rationale**: Enables initial orchestration and replay while deferring the design and testing of multi-candidate/collection-aware ranking.
- **Future impact**: Not scalable to pools or real automation; integration of TOP_K/collection-based policy will require additional state and contract changes.
- **Priority**: Medium
- **Recommended future direction**: Replace with collection-aware ranking policy and deterministic contract for shortlisting; validate with harness and promote typed ranking envelopes once in scope.

### `ranking_completed` event (deprecated)

Summary (v2 cleanup):

- **Deprecated**: was used as an intermediate orchestration event on the bus.
- **Replaced by**: direct planner decision (same ingest) for clarity and determinism.
- **Removal**: enum / timeline skip logic to be fully removed in v2 once replay fixtures allow.

- **Status**: SUPERSEDED (envelope type retained for schema/replay of old recordings only)
- **Scope**: Orchestrator+Planner+Bus
- **Revisit when**: v2 removal of `EventType.RANKING_COMPLETED` and scrub of historical tapes
- **Introduced in**: 2026-05-14
- **Last reviewed**: 2026-05-14
- **Current decision**: Ranking is a **direct planner decision** chained in the same ingest as ``light_scoring_completed`` / ``deep_scoring_completed`` via ``OrchestrationPlan.secondary_proposed_transition`` (validated and committed immediately after the primary transition). The orchestrator **does not** publish ``ranking_completed``. API ingress allowlists no longer include it; inspection timelines **skip** runs whose sole ingest was ``ranking_completed`` so primary lines read ``light_scoring_completed`` → ``questionnaire_pending`` (etc.) without an intermediate envelope row.
- **Rationale**: ``ranking_completed`` was an intermediate orchestration event; in-process chaining reduces bus noise and keeps replay deterministic with fewer subscriber runs for the same pipeline outcome.
- **Future impact**: Old event catalogs or tests that published ``ranking_completed`` explicitly must migrate; enum value remains until v2.
- **Priority**: Low
- **Recommended future direction**: Remove ``ranking_completed`` from ``EventType`` and delete timeline skip logic once no replay fixtures depend on it.

**Ranking decision visibility**

- ``ranking_completed`` was removed for clarity (no duplicate ingest for the same planner outcome).
- Ranking decisions are **implicit** in the planner (chained secondary transition on the same envelope as ``light_scoring_completed`` / ``deep_scoring_completed``).
- For explainability, **persist and surface** ``ranking.branch`` and ``ranking.stage`` on transition records and snapshot ``OrchestrationState.extensions`` (same merge pattern as ``inactive.*``); timelines and inspection read these keys only.

### Candidate view ``next_actions`` (static)
- **Status**: OPEN
- **Scope**: API read model (`integrations/api/candidate_view.py`)
- **Revisit when**: Transition engine exposes a stable, machine-readable list of allowed ingresses or next valid triggers per phase
- **Introduced in**: 2026-05-12
- **Last reviewed**: 2026-05-12
- **Current decision**: ``build_candidate_view`` uses a **static** phase→hint string list for recruiter UX in the vertical-slice demo only (marked with an in-code TODO).
- **Rationale**: Avoid encoding transition policy twice next to the engine; product-facing hints stay explicitly non-authoritative until derived from the engine.
- **Future impact**: ``next_actions`` may drift from actual allowed transitions if the graph changes without updating the static map.
- **Priority**: Low
- **Recommended future direction**: Derive next actions from the transition engine (or a single published capability artifact) and regression-test against the graph.

### Candidate view explanation vs snapshot boundary
- **Status**: OPEN
- **Scope**: API read model (`integrations/api/candidate_view.py`) + inspection explainer
- **Revisit when**: Audit/replay requirements demand bit-stable human copy on old snapshots
- **Introduced in**: 2026-05-12
- **Last reviewed**: 2026-05-25
- **Current decision**: ``GET /candidate`` ``summary`` now prefers typed ``ingress_profile.summary`` and otherwise falls back to a placeholder. ``scores`` and ``evaluation`` are read from typed snapshot fields, while ``ranking`` remains a single-candidate stub and human-readable explanation text is still derived at read time.
- **Rationale**: The typed evaluation cutover makes score/filter semantics explicit on the snapshot, but product-facing narrative remains intentionally lightweight.
- **Future impact**: Ranking visibility is still thin, and explainer-derived text can drift from historical operator expectations unless versioned or persisted.
- **Priority**: Low
- **Recommended future direction**: Persist or version human-facing explanation strings when audit-stable copy becomes necessary, and replace the ranking stub once multi-candidate read models mature.

### Legacy governance event types
- **Status**: OPEN
- **Scope**: Governance+TransitionEngine
- **Revisit when**: v2 breaking-change window, or when all pipelines and events migrate to new ingress types
- **Introduced in**: 2026-05-14
- **Last reviewed**: 2026-05-14
- **Current decision**: `recruiter_approve_candidate` and `recruiter_mark_hired` remain in allowlists and the transition registry for replay compatibility.
- **Rationale**: Ensures legacy events are replayable during migration and audit.
- **Future impact**: Causes migration/maintenance burden as new events (`recruiter_shortlist_candidate`, `candidate_accept_offer`, `event:offer_accepted`) become canonical.
- **Priority**: Low
- **Recommended future direction**: Remove legacy event types in a v2 breaking-change window; enforce new ingress and update transition registry accordingly.

### `inactive` phase recoverability and audit
- **Status**: OPEN
- **Scope**: TransitionEngine+Governance
- **Revisit when**: When terminal state handling changes, or audit semantics are expanded
- **Introduced in**: 2026-05-14
- **Last reviewed**: 2026-05-14
- **Current decision**: `inactive` is not a strict terminal phase; transition graph and planner allow `manual_recruiter_reconsider` back to `shortlisted`.
- **Rationale**: Supports recoverability while maintaining a verifiable audit trail.
- **Future impact**: Snapshot `extensions` keys such as `inactive.reason` are diagnostic; audit/source-of-truth is transition record history (`StateTransitionRecord` + governance extensions). Diagnostic keys may be cleared on recovery by policy.
- **Priority**: Medium
- **Recommended future direction**: Continue to rely on explicit transition/audit history for canonical reasons; consider stricter conventions for extension clearing and messaging when leaving `inactive`.
