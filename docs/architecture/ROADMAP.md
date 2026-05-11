# BlueOcean Recruitment Agent — Development Roadmap

Purpose: preserve long-term development continuity, keep future AI agents and human developers aligned on the current project stage, and serve as the canonical high-level roadmap.

## Project Vision

Build a deterministic, AI-native **human evaluation infrastructure** for recruitment workflows:

- **Programs control workflow** (deterministic orchestration, verifiable transitions).
- **LLMs provide cognition** (semantic understanding, extraction, generation) under strict interfaces.
- **Humans govern outcomes** (override, approval, calibration) with audit logs.

## Current Architecture Status

- **Architecture posture**: deterministic-first control plane + constrained LLM cognition layer.
- **Primary contracts**: schema-first (state/event/candidate), explicit typing, validation-ready structure.
- **Workflow model**: event-driven, with auditability and replay as first-class goals.
- **Governance**: ADR registry and tech-debt registry to prevent drift.
- **Foundation for v1**: schemas, interfaces, and state-machine validation contracts are treated as **stable enough to build on**; further broad architecture expansion is intentionally secondary to runnable delivery.
- **Execution focus**: integrate the **event → state → skill → decision** loop end-to-end so recruiter workflows can run deterministically with governance hooks, not add new cross-cutting abstractions by default.
- **Deferred intentionally**: infrastructure hardening (bus implementations, persistence depth, replay tooling, telemetry) stays on the roadmap and tech-debt registry but is **not** the primary schedule driver until the first vertical slice is demonstrably running.

## Current Repository Structure

High-level topology (architecture-oriented):

- **`schemas/`**: canonical contracts (state, event, candidate). Schemas are validation-first and remain stable.
- **`interfaces/`**: execution boundaries between subsystems (typed IO contracts; no business logic).
- **`state_machine/`**: deterministic states, transitions, and validation rules.
- **`skills/`**: bounded execution units
  - **`skills/deterministic/`**: pure programmatic logic (no LLM calls)
  - **`skills/llm/`**: cognition layer (understanding/extraction/generation)
  - **`skills/hybrid/`**: LLM signal extraction + deterministic policy gates
- **`orchestrator/`**: coordinates deterministic workflow by consuming events and producing validated transitions.
- **`integrations/`**: external channel adapters (ingress/egress) that emit/consume events through interfaces.
- **`tests/`**: harness and correctness tests for deterministic behavior and contract validation.
- **`docs/architecture/`**: ADRs, tech debt registry, design docs, and roadmap (architecture memory).
- **`configs/`**: environment and system configuration (non-code runtime settings).

## Completed Foundations

- **Canonical schemas** (state, event, candidate) with extensibility and strict validation.
- **State machine foundation** (deterministic transitions as an architectural requirement).
- **Event-driven architecture foundation** (immutable events, correlation/causation support).
- **Architecture governance system** (documented principles and boundaries).
- **ADR registry** (`docs/architecture/ADR.md`).
- **Technical debt registry** (`docs/architecture/tech_debt.md`).

## Current Development Phase

### Phase 2 — Vertical Slice Runtime Delivery (ACTIVE)

**Milestone**: First End-to-End Recruiter Workflow.

The project remains **governance-first** and **deterministic-first**: programs validate and route; LLMs stay behind typed interfaces; humans retain override authority. Within that posture, the **active execution strategy** is a **bounded vertical slice**: ship a minimal runnable path before scaling architecture surface area.

**Current priority**: prioritize **runnable orchestration and recruiter workflow execution** over additional architecture expansion. Interface and transition contracts established in Phase 2 are the substrate; the emphasis is now **runtime wiring**—ingesting events, applying validated state transitions, invoking bounded skills, and recording decision signals—so operators can exercise a real workflow loop.

**Clarifications**

- The **architecture foundation** (schemas, interfaces, transition validation, governance docs) is considered **stable for v1** in the sense of “sufficient to integrate,” not “frozen forever.” Targeted fixes and contract tightening continue at boundaries as the slice exposes gaps.
- **Current focus** is **runtime integration** of the **event → state → skill → decision** loop with explicit validation at each handoff, not new speculative subsystems.
- **Infrastructure hardening** (durable bus, storage, replay runners, deep observability) remains **deferred intentionally** until the first slice proves the control plane and recruiter path; scaling stays **iterative** and debt-tracked rather than front-loaded.

#### Vertical Slice Success Criteria

Bounded acceptance criteria for the **first runnable recruiter workflow**. These define “done” for Phase 2’s vertical slice and **limit scope** during runtime iteration while keeping **deterministic-first** behavior.

- A **recruiter can submit or upload a CV** for a candidate (single intake path is enough).
- **Candidate aggregate / state** is created and updated only through **validated schemas** (no ad-hoc blobs as the source of truth).
- **State transitions** are **deterministic** and pass the **transition validation engine** (illegal moves are rejected with explainable outcomes).
- **Skills run only through** the canonical **skill interfaces** (bounded inputs/outputs; no inline LLM orchestration in control flow).
- **Hard filter** and **scoring** (light or deep per slice scope) **both execute** on the path; outcomes are recorded, not silently dropped.
- **Candidate ordering / ranking** in the slice is **explainable** (evidence references and/or structured rationale refs—not opaque scores only).
- A **human override path** exists (approve/reject/override or equivalent) and is **logged** on the timeline.
- The **event and state timeline** for a candidate in the slice is **reconstructable** from persisted facts (ids, correlation/causation where applicable) for audit and debugging—without requiring full production replay tooling.

## Immediate Next Steps

- **Vertical slice**: implement the minimal **event → state → skill → decision** path needed for one recruiter-visible workflow (deterministic orchestration, no autonomous routing in LLMs).
- **Boundary validation**: enforce schema + transition validation at orchestration boundaries; treat failures as structured, auditable outcomes.
- **Human-in-the-loop hooks**: ensure override / approval / calibration entry points exist in the slice, even if UX is minimal.
- **Defer by default**: additional cross-cutting architecture (new global abstractions, wide refactors) only when the slice **requires** it or ADR/tech-debt explicitly schedules it.

## Planned Future Phases

### Phase 3 — Orchestrator Core

- Deterministic orchestration engine that consumes events and produces validated state transition requests.
- Human override workflows as first-class, logged actions.

### Phase 4 — Event Bus + Persistence

- Event recording layer (append-only) and event bus abstraction.
- Correlation/causation tracing across integrations and internal subsystems.

### Phase 5 — Deterministic Skills Layer

- Hard filters, deduplication, deterministic ranking primitives, policy gates.
- Test coverage for all critical deterministic behaviors.

### Phase 6 — LLM Cognition Layer

- Structured extraction, summarization, questionnaire generation, and explainability artifacts.
- Strict IO contracts; LLM outputs treated as signals, not control.

### Phase 7 — Recruiter Memory System

- Preference alignment artifacts and feedback loops.
- Calibration data capture (human adjustments + evidence references).

### Phase 8 — Replay / Debugging Tooling

- Deterministic replay runner and timeline reconstruction tooling.
- Investigation workflows: “why did this candidate end up here?”

### Phase 9 — Telemetry + Architecture Review Tooling

- Observability around transitions, event throughput, failure modes, and human overrides.
- Periodic architecture review checks against ADRs and debt registry.

### Phase 10 — Admin / Recruiter UI

- Human-in-the-loop operations: candidate review, override, calibration, and evidence navigation.

### Phase 11 — Talent Pool System

- Long-term retention, segmenting, and future role matching.
- Explainable candidate-to-role matching driven by validated signals and evidence references.

## Long-Term System Vision

- A reusable evaluation infrastructure beyond recruitment (executive hiring, partner assessment, staffing).
- Strong auditability and explainability across all recommendations and decisions.
- Deterministic, replayable workflows that remain stable as LLM capabilities evolve.

## Engineering Constraints

- **Deterministic-first architecture** for all control and routing decisions.
- **Avoid autonomous uncontrolled agents** for orchestration and ranking.
- **Schema validation required** at all boundaries (event/state/skill IO).
- **Event immutability** (corrections via new events, not mutation).
- **Explainability required** for scoring and decisions (evidence references over free text).
- **Human override always available** and always logged.

## AI-Native Development Principles

- **Stable architecture > smart prompts**.
- **Programs control; LLMs understand**.
- **Critical behaviors must be verifiable** (tests + harness).
- **Prefer explicit typing and contracts**; use extensibility fields intentionally, then graduate to typed fields.

