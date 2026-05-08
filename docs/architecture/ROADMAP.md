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

### Phase 2 — Interface Layer (ACTIVE)

Goal: define stable interfaces between the deterministic orchestrator/state machine, integrations, storage, skills, and UI—without embedding business logic into prompts or schema constructors.

## Immediate Next Steps

- **Interface contracts**: define stable IO contracts for:
  - event ingestion/recording
  - state transition requests + validation outcomes
  - artifact storage references (CVs, transcripts, messages)
  - skill execution inputs/outputs (deterministic + LLM)
- **Repository boundaries**: formalize module boundaries for control-plane vs cognition-plane.
- **Validation harness hooks**: ensure schema validation and transition validation are mandatory at boundaries.

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

