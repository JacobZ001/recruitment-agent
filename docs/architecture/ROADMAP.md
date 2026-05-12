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
- **Phase transition**: the **control plane / reference runtime** (orchestrator, transition engine, planner, in-memory bus and store, fake deterministic skills, replay-aware execution semantics) **substantially exists**; a **thin HTTP ingress** (`integrations/api/`) makes the slice **externally exercisable** for validation and debugging. Active work has shifted from **standing up foundational runtime plumbing** to **governed operator workflows, audit-oriented interactions, and deeper proving** (harnesses, governance loops, structured inspection evolution).
- **Execution focus**: close gaps with **end-to-end workflow proving**, deterministic orchestration validation, and **cognition replacement** behind existing contracts—without LLM-driven routing or speculative cross-cutting abstractions by default.
- **Deferred intentionally**: durable persistence, production broker/event store, full replay-from-store runners, deep observability, and multi-tenant hardening remain **scheduled and debt-tracked**—they deepen **runtime evolution** after **replayable workflow confidence** and **human-governed operations** are demonstrated on the slice, not the reverse.
- **Operations-centric posture**: maturity is measured by **governed workflows** (audit, replay signals, operator hooks, external exercise of orchestration) more than by counting backend components.

## Current Architectural State

The **control plane exists** as a synchronous in-process stack with stable orchestration boundaries (planner policy vs. orchestrator execution vs. engine validation vs. skill contracts). **Primary risk is workflow proof and operator confidence**: correct handoffs across events, state, skills, and emissions; **replayable harness behavior**; **inspection/timeline visibility**; **human-in-the-loop governance** (overrides, review, audit); then **controlled cognition** and durable storage under the same gates—not “more infrastructure first.”

## Current Repository Structure

High-level topology (architecture-oriented):

- **`schemas/`**: canonical contracts (state, event, candidate). Schemas are validation-first and remain stable.
- **`interfaces/`**: execution boundaries between subsystems (typed IO contracts; no business logic).
- **`state_machine/`**: deterministic states, transitions, and validation rules.
- **`runtime/`**: reference in-memory implementations of bus and state-store contracts for vertical-slice runs, local tests, and demos (not production persistence); includes **`bootstrap_vertical_slice.py`**, the first synchronous integration entrypoint wiring planner + orchestrator + transition engine + fake skills + bus + store.
- **`skills/`**: bounded execution units
  - **`skills/deterministic/`**: pure programmatic logic (no LLM calls)
  - **`skills/llm/`**: cognition layer (understanding/extraction/generation)
  - **`skills/hybrid/`**: LLM signal extraction + deterministic policy gates
- **`orchestrator/`**: coordinates deterministic workflow by consuming events and producing validated transitions.
- **`integrations/`**: external channel adapters (ingress/egress) that emit/consume events through interfaces; **`integrations/api/`** holds the **reference** sync-first FastAPI boundary for the vertical slice (demonstration and tests—not a production platform claim).
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
- **Fake deterministic vertical-slice skills**: CV upload (`fake_cv_uploaded_skill.py`), hard filter (`fake_hard_filter_skill.py`), light scoring (`fake_light_scoring_skill.py`), deep scoring (`fake_deep_scoring_skill.py`)—plus minimal **stub** skills where the planner still expects a registration (`candidate_created`, `cv_parsed`, `questionnaire_stage`), validating control-plane wiring and contracts without production cognition.
- **Runnable integration bootstrap** (`runtime/bootstrap_vertical_slice.py`): deterministic scripted ingress through default pipeline phases to `deep_scored`, with emission fan-out via an emission collector (state commit ordering vs. nested publish).
- **Python dependency pin** (`requirements.txt`): Pydantic for canonical schemas/interfaces.
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

The **control plane and reference runtime substantially exist** (orchestrator, transition engine, planner, in-memory event bus and state store, fake deterministic skills for intake/filter/light/deep scoring, replay-aware execution semantics). **Orchestration semantics remain deterministic and replay-tested** (replay harnesses + negative-path coverage); **manual integration proof** remains via `runtime/bootstrap_vertical_slice.py` (ingress sequence through `deep_scored` with derived `questionnaire_requested` emission). The runtime is **externally exercisable** through a **thin, validated HTTP boundary** (`integrations/api/`)—sync-first, schema-validated ingress; **no** production deployment claims. **Inspection/timeline** (`runtime/inspection/` and `GET /timeline/{candidate_id}`) gives **operator- and debugging-oriented visibility** (read-only; bounded completeness when history is not fully recorded). **Primary gap vs “proven”** shifts toward **human / operator governance loops** (override, review, audit-oriented interactions), **richer ingress semantics** (identity scope, idempotency—debt-tracked), and **structured inspection/timeline models**—not additional foundational control-plane plumbing by default.

**Sequencing (operations-first)**: **prove** in tests (**in progress**: pytest replay + API harnesses) → **thin ingress** (**delivered**: FastAPI reference; optional CLI/extension later) → **human governance & replay confidence** on the slice → **controlled LLM** experiments behind skill interfaces (may start **before** durable persistence) → **deterministic policy depth** → **persistence & durable runtime** when warranted → **debt-tracked** hardening. **Authoritative ordered list:** **Upcoming (prioritized)** under Immediate Next Steps.

**Clarifications**

- **Governance and determinism** unchanged: programs validate and route; LLMs stay behind typed interfaces; humans retain override authority.
- **Cognition**: fake skills remain the default regression path; **bounded LLM experiments** are allowed once harness + boundaries exist—not blocked on production databases.
- **Persistence**: reference runtime may stay in-memory for some time; **durable storage is not a prerequisite** for thin API or controlled cognition; it arrives when audit/replay **requires** surviving process restarts.
- **Infrastructure hardening** (brokers, deep observability, outbox) remains **debt-tracked** and **bounded**; it augments **replayable operations**, not a checklist of components.

#### First runnable recruiter workflow (acceptance criteria)

Bounded criteria for **Phase 3 proving work**; they **limit scope** while keeping **deterministic-first** behavior.

**Progress note (engineering)**: the **control-plane loop** is **wiring-complete** for the reference fake path (including light + deep scoring fakes). **Phase 3** now emphasizes **governed operator workflows**, **audit-visible overrides**, **richer ingress and inspection contracts** (without diluting deterministic-first semantics), and **expanded replay/governance coverage** where not yet demonstrated (e.g. human override exercised end-to-end, persistence-backed timelines when required).

- A **recruiter can submit or upload a CV** for a candidate (single intake path is enough).
- **Candidate aggregate / state** is created and updated only through **validated schemas** (no ad-hoc blobs as the source of truth).
- **State transitions** are **deterministic** and pass the **transition validation engine** (illegal moves are rejected with explainable outcomes).
- **Skills run only through** the canonical **skill interfaces** (bounded inputs/outputs; no inline LLM orchestration in control flow).
- **Hard filter** and **scoring** (light or deep per slice scope) **both execute** on the path; outcomes are recorded, not silently dropped.
- **Candidate ordering / ranking** in the slice is **explainable** (evidence references and/or structured rationale refs—not opaque scores only).
- A **human override path** exists (approve/reject/override or equivalent) and is **logged** on the timeline.
- The **event and state timeline** for a candidate in the slice is **reconstructable** from persisted facts (ids, correlation/causation where applicable) for audit and debugging—without requiring full production replay tooling.

### Recently delivered (reference slice)

- **Replay harnesses** (`tests/replay/`): automated structural replay for the vertical slice; **negative-path** validation (transition rejection, missing skill registration, `hard_filter_failed` closure, bus handler-exception isolation).
- **`runtime/recording_event_bus.py`**: canonical **`RecordingInMemoryEventBus`** for recorded publish envelopes (tests + API wiring); single implementation—no duplicate bus semantics.
- **`fake_light_scoring_skill`** / **`fake_deep_scoring_skill`**: deterministic scoring stand-ins behind canonical skill contracts, aligned with planner/registry semantics.
- **`runtime/bootstrap_vertical_slice.py`**: synchronous integration entrypoint (transition engine + default registry + planner + orchestrator + fake skills + in-memory bus/state store); demonstrates full pipeline progression to **`deep_scored`** with questionnaire emission handling.
- **`runtime/inspection/`**: human-readable **workflow timeline** formatting from orchestration artifacts (runs, decisions, transitions, skills, emissions, failures)—inspect-only; **`vertical_slice_timeline_text`** and HTTP **`GET /timeline/{candidate_id}`** for developer, operator, and debugging visibility (bounded when full envelope history is unavailable).
- **`integrations/api/`** — thin **FastAPI** boundary and **externally callable** reference workflow runtime (single-process in-memory vertical slice; **not** a production platform): **`GET /health`**, **`POST /events`**, **`GET /state/{candidate_id}`**, **`GET /timeline/{candidate_id}`**; validates ingress, builds `EventEnvelope` via existing bootstrap factory, publishes to the bus—**no** workflow policy in route handlers, **no** direct state mutation, **no** auth/DB.
- **`requirements.txt`**: Pydantic for schemas/interfaces; FastAPI + httpx for the reference API tests.

## Immediate Next Steps

Ordered **upcoming engineering priorities** for **Phase 3** (deterministic-first; realistic sequencing; debt-tracked where noted):

### Upcoming (prioritized)

1. **Human / operator governance loops on the slice**: end-to-end **`human_override`** (and related hooks) with **audit-visible** transitions and timelines; recruiter/operator **actions** as first-class, deterministic events—before persistence depth unless audit demands it.
2. **Richer ingress semantics**: extend the reference **`integrations/api/`** boundary (optional **CLI**, idempotency/dedupe policy, multi-aggregate/candidate scope—**debt-tracked**) without turning ingress into workflow policy; sync-first remains the default posture.
3. **Structured inspection / timeline models**: evolve from deterministic plain-text timelines toward **typed, shareable projections** (text/JSON/UI renderers) while keeping inspection **read-only** and **non-authoritative**.
4. **Replay-validation expansion**: deepen bus + transition engine + orchestrator replay **signals** and harness edge cases (no claim of full historical replay products yet).
5. **Controlled cognition experiments**: first **`skills/llm/`** or hybrid skills (extraction, summarization, structured signals) behind canonical contracts; deterministic policy and orchestration unchanged; **may precede** durable persistence.
6. **Real deterministic recruiter policies**: policy-backed gates, typed vocabularies, versioned rule packs (see tech debt on vocabulary / scoring governance).
7. **Persistence abstraction & durable evolution**: repository/event-store shapes and a first **durable** or file-backed implementation **when operators or replay requirements demand it**—immutable-event discipline preserved.
8. **Richer operator surfaces**: recruiter/admin UI or tooling on top of the API boundary—when workflow and governance paths are stable enough to merit UX investment.
9. **Production infrastructure hardening**: durable bus patterns, telemetry, outbox/idempotent consumers, multi-tenant operational maturity—**debt-tracked**, following **replayable workflow confidence** (not parallel “component accumulation”).

Cross-cutting reminders (unchanged philosophy):

- **Boundary validation**: enforce schema + transition validation at orchestration boundaries; treat failures as structured, auditable outcomes.
- **Human-in-the-loop hooks**: keep override / approval / calibration entry points first-class in contracts and events, even before rich UX.
- **Defer by default**: additional cross-cutting architecture (new global abstractions, wide refactors) only when **Phase 3 proving work** **requires** it or ADR/tech-debt explicitly schedules it.

## Planned Future Phases

Phases below are **outcome-oriented** (workflow confidence, governance, cognition, durable evolution, operations maturity). **Infrastructure appears as an enabler**, not as the definition of progress. **Deterministic-first governance, replay/audit priority, and debt-tracked hardening** stay explicit.

**Emphasis going forward**: later phases center on **operational governance maturity**, **durable runtime evolution**, **controlled cognition integration**, and **multi-aggregate orchestration**—not on “adding APIs” for their own sake. The reference HTTP ingress is a **bounded, demonstration-grade** external exercise surface; further milestones should deepen **governed behavior and auditability**, not checklist API counts.

### Phase 4 — Replayable workflow confidence (maturation)

- **Intent**: raise confidence that **the same inputs yield the same governed outcomes**—harness culture, integration tests, and operational clarity around orchestration runs—not “shipping more components.”
- Broaden **automated** checks across planner → engine → orchestrator → skills → emissions; tighten **replay signal** coverage as debt items demand.
- Treat orchestration as the **governed execution core** of an **AI operations platform** (bounded runs, explicit decisions), not merely a library.

### Phase 5 — Human governance operations

- **Intent**: mature **operator loops**: override, approval, calibration, and audit narratives anchored on **immutable events** and transition records.
- First-class **human actions** on timelines; governance UX may be thin (API + logs) before polished UI.
- **Replay/audit** remain primary—operators must answer **what happened** and **why** without inferring from opaque scores.

### Phase 6 — Controlled cognition integration

- **Intent**: replace or augment fakes with **real cognition** strictly behind **`skills/llm/`** and **hybrid** gates—signals in, deterministic policy out; **no LLM orchestration**.
- Structured extraction, summarization, questionnaire artifacts, explainability references; vocabulary may graduate via tech-debt governance.

### Phase 7 — Deterministic policy & ranking depth

- **Intent**: deepen **deterministic** recruiter/org policy (hard filters, dedupe, ranking primitives, policy packs) with harness coverage—still **programs control**.

### Phase 8 — Recruiter memory & calibration

- Preference artifacts, feedback loops, calibration capture (human adjustments + evidence refs)—**governed learning**, not autonomous optimization.

### Phase 9 — Durable runtime evolution (events, state, replay products)

- **Intent**: **persisted facts** that support **replayable workflow confidence** across restarts and integrations—not “database for its own sake.”
- Append-only event orientation, durable projections as needed, correlation/causation across channels; **full replay-from-store runners** and timeline products evolve here while staying **debt-tracked** where scope explodes.

### Phase 10 — Replay & investigation tooling (operator-facing)

- Move from **signal-only replay** toward **operator workflows**: “why did this candidate land here?”—deterministic reconstruction from stored envelopes + state, aligned with ADR immutability.

### Phase 11 — Observability & architecture governance cadence

- Telemetry and SLO-friendly signals around transitions, throughput, failures, overrides—plus periodic **ADR/debt** review so the platform **evolves under governance**, not ad-hoc growth.

### Phase 12 — Operational maturity & scale

- **Multi-tenant**, operational playbooks, consistency patterns (e.g. outbox, idempotent consumers) where **proven need**—still **bounded** and debt-aligned; **not** a claim of full production readiness by phase label alone.

### Phase 13 — Talent pool & long-horizon matching

- Long-term retention, segmenting, future role matching—**explainable** matching from validated signals and evidence references.

## Long-Term System Vision

- A **governed AI operations** posture: deterministic control over workflow evolution, with cognition as a **bounded, auditable** subsystem—not uncontrolled autonomy.
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

