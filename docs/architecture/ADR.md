# BlueOcean Recruitment Agent — Architecture Decision Records (ADR)

Purpose: preserve long-term architectural reasoning, prevent drift, and provide durable engineering memory for future AI agents and human developers. This project optimizes for **deterministic orchestration**, **verifiable behavior**, **auditability**, and **human governance**, using LLMs strictly as a cognition layer (under program control).

---

## ADR-001 — Deterministic orchestration over autonomous agent control

- **ADR ID**: ADR-001
- **Title**: Deterministic orchestration over autonomous agent control
- **Status**: Accepted
- **Decision date**: 2026-05-08
- **Context**: Autonomous agents can produce non-deterministic workflow behavior, hidden state changes, and unpredictable failure modes. Recruitment evaluation requires traceability, repeatability, and the ability to validate critical actions.
- **Decision**: Workflow routing, state transitions, retries, and ranking are controlled by deterministic program logic. LLMs are limited to semantic understanding/extraction/generation and may produce signals but do not directly control orchestration.
- **Consequences**: Predictable system behavior; higher upfront engineering discipline; clearer boundaries between control-plane and cognition.
- **Tradeoffs**: Less “agent autonomy” and slower iteration on fully-agentic behavior; additional interface/schema work to integrate LLM outputs safely.
- **Future Considerations**: Expand agent capabilities only through verifiable interfaces (typed I/O, validation harness, deterministic policy gates, audit logs).

---

## ADR-002 — Event-driven architecture for orchestration and auditability

- **ADR ID**: ADR-002
- **Title**: Event-driven architecture for orchestration and auditability
- **Status**: Accepted
- **Decision date**: 2026-05-08
- **Context**: Recruitment pipelines must support timeline reconstruction, debugging, and controlled replay across multiple integrations and human interventions.
- **Decision**: The system is event-driven. Events represent immutable facts (“things that happened”) and serve as the primary audit and debugging substrate.
- **Consequences**: Strong observability and replay potential; easier integration with external systems; enables deterministic state reconstruction when paired with validation.
- **Tradeoffs**: Additional complexity in modeling event types/payloads and projections; requires discipline around event contracts and idempotency.
- **Future Considerations**: Add typed payload schemas, replay tooling, and read-model projections as usage patterns stabilize.

---

## ADR-003 — Schema-first engineering approach

- **ADR ID**: ADR-003
- **Title**: Schema-first engineering approach
- **Status**: Accepted
- **Decision date**: 2026-05-08
- **Context**: Without stable contracts, systems drift, integrations break silently, and LLM-driven features become fragile and untestable.
- **Decision**: Canonical schemas define the contracts for state, events, and aggregates. Validation is explicit; schema evolution is deliberate and backward-compatible where possible.
- **Consequences**: Higher reliability, easier testing/harness validation, and clearer system boundaries. Facilitates multi-team and multi-agent development.
- **Tradeoffs**: More up-front design; schema changes require more intentional coordination.
- **Future Considerations**: Version schemas, add compatibility checks, and expand the harness to validate deterministic invariants and schema drift.

---

## ADR-004 — Human-in-the-loop mandatory governance

- **ADR ID**: ADR-004
- **Title**: Human-in-the-loop mandatory governance
- **Status**: Accepted
- **Decision date**: 2026-05-08
- **Context**: Hiring decisions have high consequence and require accountability, bias controls, and operator authority.
- **Decision**: Human operators retain authority to approve/reject/override outcomes, adjust scores, and override states. Overrides are logged as auditable records/events.
- **Consequences**: Strong governance and accountability; supports calibration and preference alignment; safer deployment in real hiring contexts.
- **Tradeoffs**: Requires operator UX and operational processes; reduces full automation.
- **Future Considerations**: Add calibration workflows, permissioning, and structured feedback artifacts to improve repeatability and learning.

---

## ADR-005 — Immutable event records

- **ADR ID**: ADR-005
- **Title**: Immutable event records
- **Status**: Accepted
- **Decision date**: 2026-05-08
- **Context**: Debugging and replay depend on trusting the event timeline. Mutability introduces ambiguity (“what actually happened?”).
- **Decision**: Events are immutable once recorded. Corrections are represented as new events (e.g., compensating events) rather than in-place mutation.
- **Consequences**: Clear audit trail; deterministic replay; improved compliance posture.
- **Tradeoffs**: Requires careful modeling of correction flows; can increase event volume.
- **Future Considerations**: Define standard correction/compensation patterns and add tooling for timeline inspection and replay.

---

## ADR-006 — Reference-based artifact architecture instead of embedding raw content

- **ADR ID**: ADR-006
- **Title**: Reference-based artifact architecture instead of embedding raw content
- **Status**: Accepted
- **Decision date**: 2026-05-08
- **Context**: CVs, transcripts, messages, and evidence can be large, sensitive, and multi-source. Embedding them directly in primary records increases coupling, storage cost, and risk.
- **Decision**: Primary schemas store references (keys/URIs/hashes) to artifacts rather than embedding raw blobs. Evidence and explanations are linked via references for explainability.
- **Consequences**: Smaller and safer core records; easier deduplication and integrity checks; supports privacy and storage policies while retaining explainability.
- **Tradeoffs**: Requires reliable artifact storage and reference resolution; debugging sometimes requires joining across stores.
- **Future Considerations**: Standardize evidence reference schemas, retention policies, and access controls; add artifact integrity verification.

---

## ADR-007 — Deferred shared domain vocabulary consolidation

- **ADR ID**: ADR-007
- **Title**: Deferred shared domain vocabulary consolidation
- **Status**: Accepted
- **Decision date**: 2026-05-08
- **Context**: Early-stage domain vocabulary evolves rapidly. Premature consolidation into shared enums risks frequent churn and breaking changes across schemas.
- **Decision**: Some vocabularies may temporarily remain as validated strings in specific schemas to avoid fragmentation. Consolidation into shared, reusable domain enums is deferred until vocabulary stabilizes.
- **Consequences**: Faster iteration now; reduced risk of enum drift becoming breaking churn. Requires explicit documentation to avoid silent divergence.
- **Tradeoffs**: Less static type safety in the short term; potential inconsistency across modules if not tracked.
- **Future Considerations**: Create a shared domain vocabulary module once stable, introduce backward-compatible aliases, and migrate string fields to shared enums with harness validation.

---

## ADR-008 — Modular monolith application boundary (`modules/recruitment`)

- **ADR ID**: ADR-008
- **Title**: Single-tenant modular monolith with a recruitment application module
- **Status**: Accepted
- **Decision date**: 2026-05-12
- **Context**: Incremental capabilities were spreading across `integrations/api`, `runtime`, and inspection helpers, requiring coordinated edits across many files for small features. Dependency direction was unclear (HTTP vs domain vs orchestration).
- **Decision**: Introduce `modules/recruitment` as the **application/domain boundary** for recruitment business actions (policies, use cases, read projections). Dependency flow is **`integrations/api` → `modules/recruitment` → `runtime` / orchestrator / store**. The API layer owns HTTP models, FastAPI wiring, runtime lifecycle, and mapping application exceptions to status codes. `modules/recruitment` does not import `integrations.api`, does not construct runtimes, and does not raise `HTTPException`. Transition legality and workflow routing remain in `state_machine` and `orchestrator` respectively.
- **Consequences**: New recruiter-facing features have a clear home (`use_cases.py`, `policies.py`, `projection.py`); API routes stay thin; orchestration and schemas stay unchanged in Step 1.
- **Tradeoffs**: Some duplication of runtime typing via Protocols until a shared ports module exists; projections may still read bootstrap/inspection helpers directly.
- **Future Considerations**: Move additional runtime wiring behind explicit ports; grow modules only when a second bounded context appears (avoid premature microservices).

---

## ADR-009 — Bounded LLM cognition at CV ingress

- **ADR ID**: ADR-009
- **Title**: First controlled cognition pilot at CV ingress
- **Status**: Accepted
- **Decision date**: 2026-05-25
- **Context**: The single-tenant recruiter slice now has durable state, multi-candidate routing, and typed recruiter projections. The next capability step is bounded semantic understanding of CV text without allowing model output to own workflow control.
- **Decision**: Introduce a single `skills/llm/` CV parse-and-score skill at `cv_submitted` ingress. The skill may extract typed profile data and light-evaluation signals, but deterministic program logic retains ownership of transitions, routing, ranking, retries, and fail-closed behavior. Provider selection is explicit through local environment configuration; automated tests keep deterministic `stub` mode as the default.
- **Consequences**: The repo now exercises a real cognition boundary while preserving architecture rules. Teams can validate provider wiring and structured output contracts without turning prompts into workflow logic.
- **Tradeoffs**: Introduces external dependency failure modes, provider configuration overhead, and a temporary coarse error surface (`scoring_failed`) until taxonomy hardening catches up.
- **Future Considerations**: Expand cognition only through explicit contracts, deterministic provider-failure mapping, and harness coverage; do not let additional LLM skills backslide into orchestration control.

---

## ADR-010 — Typed evaluation cutover over legacy `decision.*` compatibility

- **ADR ID**: ADR-010
- **Title**: Typed evaluation is the sole canonical score/filter path
- **Status**: Accepted
- **Decision date**: 2026-05-25
- **Context**: Earlier migration work temporarily kept compatibility readers for score/filter data stored in `extensions["decision.*"]`. That dual path blurred governance `decision` vs evaluation semantics and extended the burden of old local SQLite rows.
- **Decision**: Use typed snapshot fields (`ingress_profile`, `evaluation`, `ingress_flags`) as the only supported read/write path for current recruiter semantics. Remove runtime compatibility readers that reinterpret `extensions["decision.*"]` as evaluation. When this cutover breaks old local SQLite state, local `data/app.db` reset is the accepted developer workflow for this round.
- **Consequences**: Snapshot and API semantics are clearer, projections are simpler, and future development no longer needs to preserve dual evaluation meanings. Old local rows that depended on compatibility readers are intentionally outside the supported path after this cutover.
- **Tradeoffs**: Developers must reset local SQLite state after the cutover if they were carrying pre-cutover rows. There is no general migration framework for historical local snapshots in this round.
- **Future Considerations**: If retained historical data becomes a product requirement, solve it with an explicit migration/upcaster strategy rather than reviving ad-hoc compatibility readers in runtime code.

---

## ADR-011 — Job-aware layered scoring uses a separate canonical `scoring_context`

- **ADR ID**: ADR-011
- **Title**: Job-aware three-layer evaluation with canonical scoring-context storage
- **Status**: Accepted
- **Decision date**: 2026-05-25
- **Context**: The repo had a typed candidate snapshot and a first bounded cognition pilot, but light scoring still assumed universal-only criteria and CV parse/score were coupled in one ingress step. The next MVP capability required recruiter/job awareness without turning prompts into workflow logic or duplicating context onto every candidate snapshot.
- **Decision**:
  - Introduce a separate canonical `scoring_context` object with typed `organization_context`, `recruiter_actor_context`, and `job_context` components.
  - Persist that context outside candidate workflow snapshots and gate `cv_submitted` until `scoring_context.status == ready`.
  - Split candidate CV parsing from scoring: persist `ingress_profile` first, then score against `cv + scoring_context`.
  - Use the same layered schema for `evaluation.light` and `evaluation.deep`: `l1_universal`, `l2_role_specific`, `l3_recruiter_preference`, plus deterministic aggregate score/confidence and `context_version`.
  - Keep programs responsible for aggregate scoring, version/stale semantics, transitions, and ranking; LLM output remains bounded to typed extraction/scoring signals only.
- **Consequences**: Recruiter/job-aware scoring is now explicit, versioned, and inspectable. Candidate views can expose layer breakdowns and score provenance. Context changes can mark existing evaluations stale without mutating workflow routing semantics.
- **Tradeoffs**: The current implementation keeps a single active scoring context for the whole reference runtime, not a full requisition aggregate. Context authoring and candidate workflow are clearer, but richer requisition management remains deferred.
- **Future Considerations**: Grow the single active scoring-context store into requisition-scoped context aggregates only through explicit contracts and migration plans; do not collapse back to snapshot-local context blobs or prompt-owned scoring semantics.

