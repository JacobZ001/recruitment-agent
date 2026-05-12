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
- **Foundation for v1**: schemas, interfaces, state-machine validation contracts, and the **reference runtime stack** (in-memory bus + state store + orchestrator + vertical-slice planner) are treated as **stable enough to build on**; schedule pressure is on **proving** end-to-end recruiter workflows, not inventing new control-plane shape.
- **Phase transition**: the **control plane / reference runtime** (orchestrator, transition engine, planner, in-memory bus and store, fake deterministic skills, replay-aware execution semantics) **substantially exists**; active work has shifted from **standing up runtime infrastructure** to **proving runnable deterministic workflow execution** (harnesses, integration correctness, replay validation).
- **Execution focus**: close gaps with **end-to-end workflow proving**, deterministic orchestration validation, and **cognition replacement** behind existing contracts—without LLM-driven routing or speculative cross-cutting abstractions by default.
- **Deferred intentionally**: durable persistence, production broker/event store, full replay-from-store runners, deep observability, external integrations, production LLM wiring, and recruiter-facing UI remain **scheduled and debt-tracked**; they follow workflow proof, not the other way around.

## Current Architectural State

The **control plane exists** as a synchronous in-process stack with stable orchestration boundaries (planner policy vs. orchestrator execution vs. engine validation vs. skill contracts). **Primary engineering risk is now integration and proof**: wiring correctness across events, state, skills, and emissions; replay/harness confidence; then replacing fake cognition with real skills under the same gates.

## Current Repository Structure

High-level topology (architecture-oriented):

- **`schemas/`**: canonical contracts (state, event, candidate). Schemas are validation-first and remain stable.
- **`interfaces/`**: execution boundaries between subsystems (typed IO contracts; no business logic).
- **`state_machine/`**: deterministic states, transitions, and validation rules.
- **`runtime/`**: reference in-memory implementations of bus and state-store contracts for vertical-slice runs, local tests, and demos (not production persistence).
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
- **Interface layer** (`interfaces/`) defining execution boundaries: event bus contracts (publish, delivery, structured handle/publish results) and skill execution contracts (typed envelopes, execution context, bounded results)—no embedded business logic in interfaces.
- **Deterministic transition engine** (`state_machine/`) with registry-backed validation, structured transition records, and replay-validation modes for deterministic structural checks.
- **In-memory event bus** (`runtime/in_memory_event_bus.py`) implementing the canonical bus interface: deterministic subscriber ordering, selector fan-out, structured failure isolation per handler, and replay **signals** on `DeliveryContext` (not a persisted event store).
- **In-memory state store** (`runtime/in_memory_state_store.py`) for orchestration state snapshots and candidate linkage in vertical-slice runs (explicitly not durable multi-tenant storage).
- **Orchestrator runtime** (`orchestrator/orchestrator.py`): synchronous control-plane loop (ingest → plan invariants → validate transition → run skills → commit new state → publish derived events), with replay flags forwarded into transition validation.
- **Vertical slice planner** (`orchestrator/vertical_slice_planner.py`): pure deterministic policy mapping envelopes + state snapshots to plans aligned with the default pipeline registry (no LLM routing, no autonomous workflow control).
- **Fake deterministic skills** (e.g. `skills/deterministic/fake_cv_uploaded_skill.py`, `skills/deterministic/fake_hard_filter_skill.py`) validating end-to-end control-plane wiring, skill IO boundaries, and explainable pass/fail paths without production cognition.
- **Replay-safe execution semantics** (orchestrator + transition engine + bus): replay treated as explicit, signal-driven context—same envelope, delivery replay context, and state snapshot yield the same deterministic plan/validation outcomes; full historical replay runners and durable logs remain future work (see tech debt).
- **Deterministic orchestration governance**: ADRs, tech-debt registry, and code-level boundaries preserving “programs control; LLMs understand” through reference runtime delivery.
- **State machine foundation** (deterministic transitions as an architectural requirement)—now exercised by the orchestrator and planner, not only specified.
- **Event-driven architecture foundation** (immutable events, correlation/causation support in contracts)—now exercised through the bus and orchestrator publish path.
- **Architecture governance system** (documented principles and boundaries).
- **ADR registry** (`docs/architecture/ADR.md`).
- **Technical debt registry** (`docs/architecture/tech_debt.md`).

## Current Development Phase

### Phase 3 — Deterministic Workflow Execution (ACTIVE)

**Milestone**: **Proven** end-to-end deterministic recruiter workflows—runnable paths, harness-backed assertions, replay-validation confidence, and integration correctness—while cognition and product surfaces remain mostly fake or absent.

The **control plane and reference runtime now substantially exist** (orchestrator, transition engine, planner, in-memory event bus and state store, fake deterministic skills, replay-aware execution semantics). **Primary engineering risk and priority** have shifted from **building runtime infrastructure** to **proving runnable deterministic workflow execution**: end-to-end recruiter scenarios, **integration correctness** across handoffs, **replay validation**, **harness execution**, and **deterministic orchestration validation**. **Major remaining work** is **workflow validation** plus **cognition replacement** (real skills and policies behind the same interfaces), not greenfield orchestration.

**Current priority**: ship missing path coverage (e.g. light/deep scoring fakes), **E2E runnable harnesses**, expanded replay-validation tests, and persistence/API boundaries only as needed for proof—**integration complexity** is the main schedule driver; avoid speculative new subsystems.

**Clarifications**

- **Governance and determinism** unchanged: programs validate and route; LLMs stay behind typed interfaces; humans retain override authority.
- **Cognition**: still **fake / simulated** on the proven path; **no production LLM** yet; real cognition is a **replacement** step after workflow proof.
- **Persistence / UI / integrations**: reference path remains **in-memory**, **no recruiter UI**, **no external integrations**; see Planned Future Phases and tech debt.
- **Infrastructure hardening** follows **proof** (durable bus/store, stream replay products, telemetry)—still debt-tracked, not the current bottleneck.

#### First runnable recruiter workflow (acceptance criteria)

Bounded criteria for **Phase 3 proving work**; they **limit scope** while keeping **deterministic-first** behavior.

**Progress note (engineering)**: the **control-plane loop** is **wiring-complete** for fake skills; **Phase 3** closes the gap on **full-path execution proof**, replay/harness confidence, and remaining slice criteria (scoring on path, explainability, persistence-backed timelines where required).

- A **recruiter can submit or upload a CV** for a candidate (single intake path is enough).
- **Candidate aggregate / state** is created and updated only through **validated schemas** (no ad-hoc blobs as the source of truth).
- **State transitions** are **deterministic** and pass the **transition validation engine** (illegal moves are rejected with explainable outcomes).
- **Skills run only through** the canonical **skill interfaces** (bounded inputs/outputs; no inline LLM orchestration in control flow).
- **Hard filter** and **scoring** (light or deep per slice scope) **both execute** on the path; outcomes are recorded, not silently dropped.
- **Candidate ordering / ranking** in the slice is **explainable** (evidence references and/or structured rationale refs—not opaque scores only).
- A **human override path** exists (approve/reject/override or equivalent) and is **logged** on the timeline.
- The **event and state timeline** for a candidate in the slice is **reconstructable** from persisted facts (ids, correlation/causation where applicable) for audit and debugging—without requiring full production replay tooling.

## Immediate Next Steps

Ordered **upcoming engineering priorities** for **Phase 3** (deterministic-first; realistic sequencing; debt-tracked where noted):

1. **`fake_light_scoring_skill`**: deterministic light-scoring stand-in wired through the same skill contracts as production-scoring predecessors.
2. **`fake_deep_scoring_skill`**: deterministic deep-scoring stand-in post-questionnaire, aligned with registry edges and planner semantics.
3. **End-to-end runnable workflow harness**: scripted or test-harness-driven runs that exercise the full orchestrator loop (ingress events through derived emissions) with fixed inputs and stable assertions.
4. **Replay validation tests**: expand coverage for replay signal paths (bus + transition engine + orchestrator), including edge cases called out in `docs/architecture/tech_debt.md` (without claiming full stream replay yet).
5. **Persistence abstraction**: introduce repository/store interfaces and a first durable or file-backed implementation when the harness requires it—preserving immutable-event discipline.
6. **Real deterministic recruiter policies**: replace or narrow fake skill behavior with policy-backed gates, typed reason vocabularies, and versioned rule packs as domain language stabilizes (see tech debt on vocabulary governance).
7. **LLM cognition layer integration**: wire real LLM skills **only** behind `skills/llm/` and hybrid gates—signals in, deterministic policy out; no LLM orchestration.
8. **API / service boundary layer**: expose the orchestration runtime through a stable service API (sync first), keeping schemas and validation at the edge.
9. **Recruiter dashboard / UI**: human-in-the-loop operations (review, override, calibration, evidence navigation) on top of the service boundary.
10. **Production infrastructure hardening**: durable bus, telemetry, consistency patterns (outbox, idempotent consumers), and operational playbooks—after **Phase 3** harness and workflow proof.

Cross-cutting reminders (unchanged philosophy):

- **Boundary validation**: enforce schema + transition validation at orchestration boundaries; treat failures as structured, auditable outcomes.
- **Human-in-the-loop hooks**: keep override / approval / calibration entry points first-class in contracts and events, even before rich UX.
- **Defer by default**: additional cross-cutting architecture (new global abstractions, wide refactors) only when **Phase 3 proving work** **requires** it or ADR/tech-debt explicitly schedules it.

## Planned Future Phases

### Phase 4 — Orchestrator Core (maturation)

- **Progress**: reference synchronous orchestrator and deterministic planner exist; remaining work matures orchestration as a **core** subsystem (broader contexts, operational concerns), not greenfield creation from zero.
- Deterministic orchestration engine that consumes events and produces validated state transition requests.
- Human override workflows as first-class, logged actions.

### Phase 5 — Event Bus + Persistence

- **Progress**: canonical bus interfaces and a synchronous **in-memory** bus runtime exist; Phase 5 adds **durable** append-only recording, external bus implementations, and persistence depth beyond process memory.
- Event recording layer (append-only) and event bus abstraction.
- Correlation/causation tracing across integrations and internal subsystems.

### Phase 6 — Deterministic Skills Layer

- **Progress**: fake deterministic skills (including hard filter and intake) validate contracts and wiring; Phase 6 expands **real** deterministic policy coverage, deduplication, ranking primitives, and gates.
- Hard filters, deduplication, deterministic ranking primitives, policy gates.
- Test coverage for all critical deterministic behaviors.

### Phase 7 — LLM Cognition Layer

- Structured extraction, summarization, questionnaire generation, and explainability artifacts.
- Strict IO contracts; LLM outputs treated as signals, not control.

### Phase 8 — Recruiter Memory System

- Preference alignment artifacts and feedback loops.
- Calibration data capture (human adjustments + evidence references).

### Phase 9 — Replay / Debugging Tooling

- **Progress**: replay is **signal-driven** in the reference runtime (consistent `DeliveryContext` / transition replay context); Phase 9 adds **automated replay from stored streams**, timeline reconstruction products, and operator-facing investigation workflows.
- Deterministic replay runner and timeline reconstruction tooling.
- Investigation workflows: “why did this candidate end up here?”

### Phase 10 — Telemetry + Architecture Review Tooling

- Observability around transitions, event throughput, failure modes, and human overrides.
- Periodic architecture review checks against ADRs and debt registry.

### Phase 11 — Admin / Recruiter UI

- Human-in-the-loop operations: candidate review, override, calibration, and evidence navigation.

### Phase 12 — Talent Pool System

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

