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
- **Phase transition**: the **control plane / reference runtime** (orchestrator, transition engine, planner, in-memory bus and store, fake deterministic skills, replay-aware execution semantics) **substantially exists**; a **thin HTTP ingress** (`integrations/api/`) makes the slice **externally exercisable** for validation and debugging. **Bounded governance ingress**, **read-only inspection** (timelines, operator navigation, decision/evidence summaries), and **replay/governance tests** are in place. Active work shifts from **internal runtime expansion** toward a **recruiter-visible demo** that **consumes** the existing API and projections—still **deterministic-first**, **not** a production product milestone.
- **Execution focus**: ship a **recruiter-visible demo** on top of the existing API and inspection projections; continue **end-to-end workflow proving** and deterministic validation; **cognition replacement** behind existing contracts when ready—**without** LLM-driven routing or speculative cross-cutting abstractions by default.
- **Deferred intentionally**: durable persistence, production broker/event store, full replay-from-store runners, deep observability, and multi-tenant hardening remain **scheduled and debt-tracked**—they deepen **runtime evolution** after **replayable workflow confidence** and **human-governed operations** are demonstrated on the slice, not the reverse.
- **Operations-centric posture**: maturity is measured by **governed workflows** (audit, replay signals, operator hooks, external exercise of orchestration) more than by counting backend components.

## Current Architectural State

The **control plane exists** as a synchronous in-process stack with stable orchestration boundaries (planner policy vs. orchestrator execution vs. engine validation vs. skill contracts). **Architecturally** the slice is strong (replay, API, governance, inspection). **Practically**, the next bottleneck is **recruiter-facing demo value**: thin candidate/CV artifacts and minimal presentation surface. Priority: **demo that exercises the runtime** (submit/simulate profile → progression → visible state, scores, filter reasoning, evidence refs, governance, timeline)—**without** implying production frontend or persistence.

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
- **Reference HTTP ingress** (`integrations/api/`): sync-first FastAPI boundary for the vertical slice (health, events, state, timeline)—demonstration and harnesses, not a shipped product surface.
- **Replay and governance harnesses** (`tests/replay/`, `tests/governance/`): structural replay, negative paths, bounded `recruiter_*` governance events with deterministic transition validation.
- **Inspection and operator navigation** (`runtime/inspection/`): deterministic timelines, governance and transition audit lines, **decision/evidence summaries** and **navigation projections** (read-only; no orchestration policy in renderers).

## Current Development Phase

### Phase 3 — Deterministic Workflow Execution (ACTIVE)

**Milestone**: **Proven** end-to-end deterministic recruiter workflows—runnable paths, harness-backed assertions, replay-validation confidence, and integration correctness—while cognition and product surfaces remain mostly fake or absent.

The **control plane and reference runtime substantially exist** (orchestrator, transition engine, planner, in-memory event bus and state store, fake deterministic skills for intake/filter/light/deep scoring, replay-aware execution semantics). **Orchestration semantics remain deterministic and replay-tested** (replay harnesses + negative-path coverage); **manual integration proof** remains via `runtime/bootstrap_vertical_slice.py` (ingress sequence through `deep_scored` with derived `questionnaire_requested` emission). The runtime is **externally exercisable** through a **thin, validated HTTP boundary** (`integrations/api/`)—sync-first, schema-validated ingress; **no** production deployment claims. **Inspection** (`runtime/inspection/`, `GET /timeline/{candidate_id}`) includes timelines plus **decision/evidence summaries and operator navigation** (read-only; bounded when envelope history is incomplete). **Primary near-term gap** is a **recruiter-visible demo surface** and **richer demo artifacts** so the same runtime reads as a credible walkthrough—not more control-plane invention by default. Deeper items (**structured inspection/timeline models** as first-class typed products, richer ingress idempotency, persistence) follow the demo unless a demo milestone explicitly requires them sooner.

**Sequencing (operations-first)**: **prove** in tests (**delivered** baseline: pytest replay + API + governance harnesses) → **thin ingress** (**delivered**: FastAPI reference) → **recruiter-visible demo** (thin presentation + richer demo artifacts; **not** production SPA) → **extend governance / ingress** as demos expose gaps → **structured inspection models** when demo or integrations require typed projections → **controlled LLM** experiments behind skill interfaces → **deterministic policy depth** → **persistence** when warranted → **debt-tracked** hardening. **Authoritative ordered list:** **Upcoming (prioritized)** under Immediate Next Steps.

**Clarifications**

- **Governance and determinism** unchanged: programs validate and route; LLMs stay behind typed interfaces; humans retain override authority.
- **Cognition**: fake skills remain the default regression path; **bounded LLM experiments** are allowed once harness + boundaries exist—not blocked on production databases.
- **Persistence**: reference runtime may stay in-memory for some time; **durable storage is not a prerequisite** for thin API or controlled cognition; it arrives when audit/replay **requires** surviving process restarts.
- **Infrastructure hardening** (brokers, deep observability, outbox) remains **debt-tracked** and **bounded**; it augments **replayable operations**, not a checklist of components.

#### First runnable recruiter workflow (acceptance criteria)

Bounded criteria for **Phase 3 proving work**; they **limit scope** while keeping **deterministic-first** behavior.

**Progress note (engineering)**: the **control-plane loop** is **wiring-complete** for the reference fake path (including light + deep scoring fakes). **Bounded governance** (`recruiter_*` events) and **decision/evidence navigation** projections are delivered. **Phase 3** now prioritizes a **thin recruiter demo** (consume `POST /events` / `GET /state` / `GET /timeline`) and **richer candidate/CV demo payloads** so hard-filter reasoning, score summaries, evidence refs, and governance actions read clearly in timeline/navigation output—**without** LLM routing, **without** durable persistence or auth as prerequisites, and **without** committing to a production UI framework.

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
- **`runtime/inspection/`** — read-only **workflow timeline** (`render_vertical_slice_timeline_text`, `vertical_slice_timeline_text`), **operator navigation** and **decision/evidence summaries** (`decision_evidence.py`: filter/scoring/governance lines, transition trail helpers); HTTP **`GET /timeline/{candidate_id}`**; bounded catalog completeness when history is incomplete.
- **`integrations/api/`** — thin **FastAPI** boundary (**externally callable** reference runtime; single-process in-memory; **not** production): **`GET /health`**, **`POST /events`**, **`GET /state/{candidate_id}`**, **`GET /timeline/{candidate_id}`**; validates ingress; **no** workflow policy in routes, **no** direct state mutation, **no** auth/DB.
- **Bounded governance slice**: deterministic `recruiter_*` ingress, transition-engine–validated overrides, governance fields on transition records and timelines (`tests/governance/`).
- **`requirements.txt`**: Pydantic for schemas/interfaces; FastAPI + httpx for the reference API tests.

## Immediate Next Steps

Ordered **upcoming engineering priorities** for **Phase 3** (deterministic-first; realistic sequencing; debt-tracked where noted):

### Upcoming (prioritized)

1. **Thin Recruiter Demo Surface**: a **demo-grade** way for a recruiter to drive the slice end-to-end—e.g. minimal HTML/CLI/scripted walkthrough or tiny static page that calls the **existing** `integrations/api/` endpoints—so **pipeline phase**, **score summaries**, **hard-filter reasoning**, **evidence refs**, **governance actions**, and **timeline/navigation text** are visible in one sitting. **Not** production frontend work; **not** a broad SPA/React commitment; **no** auth required for the first demo; **no** LLM routing.
2. **Rich Candidate Artifact Demo**: thicken **deterministic** demo inputs (fixtures, declared CV-like fields, structured payloads through `POST /events`) so fake filter/scoring skills emit **meaningful** summaries in timelines—still bounded, replay-stable, schema-validated; **no** real persistence required yet.
3. **Human / operator governance (extend)**: deepen recruiter/operator paths and audit narratives on top of the bounded `recruiter_*` slice where demos expose gaps—still event-driven, transition-validated, replay-tested.
4. **Richer ingress semantics**: optional **CLI**, idempotency/dedupe, multi-aggregate scope (**debt-tracked**); ingress remains a thin adapter—**no** workflow policy at the HTTP edge.
5. **Structured inspection / timeline models**: typed JSON (or similar) **shareable projections** when the demo or integrations need them—**intentionally after** the thin demo surface unless a demo milestone requires machine-stable timeline rows first; inspection stays read-only and non-authoritative.
6. **Replay-validation expansion**: deepen replay **signals** and harness edge cases (no full historical replay product claim).
7. **Controlled cognition experiments**: first **`skills/llm/`** or hybrid skills behind canonical contracts; deterministic orchestration unchanged; **may precede** durable persistence.
8. **Real deterministic recruiter policies**: policy-backed gates, typed vocabularies, versioned rule packs (see tech debt).
9. **Persistence abstraction & durable evolution**: when operators or replay **require** surviving restarts—immutable-event discipline preserved.
10. **Richer operator surfaces**: polished recruiter/admin UI—**after** demo and governance paths stabilize; still **not** implied production readiness.
11. **Production infrastructure hardening**: brokers, telemetry, outbox, multi-tenant maturity—**debt-tracked**; not parallel component accumulation.

Cross-cutting reminders (unchanged philosophy):

- **Demo constraints**: recruiter-visible surfaces consume the **existing** API and inspection projections; **no** LLM-driven routing; **no** production readiness claim; persistence and auth remain optional until demos or audit demand them.
- **Boundary validation**: enforce schema + transition validation at orchestration boundaries; treat failures as structured, auditable outcomes.
- **Human-in-the-loop hooks**: keep override / approval / calibration entry points first-class in contracts and events, even before rich UX.
- **Defer by default**: additional cross-cutting architecture (new global abstractions, wide refactors) only when **Phase 3 proving work** **requires** it or ADR/tech-debt explicitly schedules it.

## Planned Future Phases

Phases below are **outcome-oriented** (workflow confidence, governance, cognition, durable evolution, operations maturity). **Infrastructure appears as an enabler**, not as the definition of progress. **Deterministic-first governance, replay/audit priority, and debt-tracked hardening** stay explicit.

**Emphasis going forward**: the next **practical** milestone is **recruiter-visible demonstration** of the existing deterministic stack (API + state + timeline + governance + evidence summaries)—not additional internal runtime surface for its own sake. Later phases still center on **operational governance maturity**, **durable runtime evolution**, **controlled cognition**, and **multi-aggregate orchestration**; the reference HTTP ingress remains **demonstration-grade** until product and persistence requirements harden.

### Phase 4 — Replayable workflow confidence (maturation)

- **Intent**: raise confidence that **the same inputs yield the same governed outcomes**—harness culture, integration tests, and operational clarity around orchestration runs—not “shipping more components.”
- **Current note**: vertical slice already has **structural replay**, **negative-path** tests, and **timeline/navigation** projections; Phase 4 broadens coverage and moves toward **semantic/assertion profiles** where strict JSON equality is insufficient (see tech debt)—without requiring a production replay product.
- Broaden **automated** checks across planner → engine → orchestrator → skills → emissions; tighten **replay signal** coverage as debt items demand.
- Treat orchestration as the **governed execution core** of an **AI operations platform** (bounded runs, explicit decisions), not merely a library.

### Phase 5 — Human governance operations

- **Intent**: mature **operator loops**: override, approval, calibration, and audit narratives anchored on **immutable events** and transition records.
- **Current note**: **bounded** governance ingress and audit-visible transitions on the slice are **in place**; Phase 5 deepens **operator workflows** and vocabulary—not replacing deterministic validation.
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
- **Current note**: plain-text timelines plus **decision/evidence summaries** and **navigation helpers** already support **manual** investigation on the reference runtime; Phase 10 adds **durable** stores and productized tooling when persistence lands—not a blocker for the thin demo milestone.

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

