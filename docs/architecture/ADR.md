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

