# BlueOcean Recruitment Agent — Development Roadmap

Purpose: preserve long-term development continuity, keep future AI agents and human developers aligned on what the system can do today, and track both capability progress and near-term action priorities without duplicating `PLAN.md` or `tech_debt.md`.

## Project Vision Layer

Build a deterministic, AI-native human evaluation infrastructure for recruitment workflows:

- Programs control workflow through explicit schemas, validated transitions, and deterministic orchestration.
- LLMs provide bounded cognition for understanding, extraction, and generation behind strict interfaces; they do not own routing, ranking, retries, or state mutation.
- Humans govern outcomes through explicit override, approval, calibration, and audit surfaces.

## Current Operating Posture

The current repo operates as a deterministic, single-process SQLite runtime with multi-candidate routing and a recruiter SPA over list/detail/action APIs, including full dedup governance (pre-create block, suspected fingerprint, post-parse `post_ingress_duplicate`, link/keep-separate, orphan/in-progress flags, indexed lookups).
As of **R-014** closeout, List scoring-context ingress runs on the product path with fingerprint-gated `context_version` and materialization blockers; PM confirmed **`corrective-minor`** → **R-014.1** for stub UAT UI logic gaps (ready gate, dimension state machine, messages, Job PDF).

## Capability Roadmap Layer

Status vocabulary used below: `Acquired`, `Partial`, `Gap`, `Vision`.

### 1. Deterministic Foundation
Stage status: `Acquired`

- Canonical contracts - `Acquired`
- Deterministic runtime orchestration - `Acquired`
- Replayable orchestration and replay tooling - `Partial`

### 2. Recruiter Workflow Operation
Stage status: `Partial`

- Multi-candidate persistent recruiter workflow - `Partial`
- Recruiter-facing state and candidate views - `Partial`
- Product-grade recruiter frontend / workflow workspace - `Partial`
- Real PDF + scoring-context ingress on List (recruiter-operable baseline) - `Partial` (R-014: ready gating, ingress state machine, version/fingerprint; requisition scope still deferred)
- Candidate-scoped workflow timeline/history - `Gap`
- Deterministic hard-filtered canonical ingress path - `Gap`

### 3. Human Governance
Stage status: `Partial`

- Typed recruiter lifecycle ingress - `Partial`
- Audit-visible governance lines and bounded override semantics - `Partial`
- Guard-aware recruiter action availability - `Partial`
- Typed recruiter action payloads - `Partial`

### 4. Controlled Cognition
Stage status: `Partial`

- CV profile parsing - `Partial`
- Job-aware layered light scoring - `Partial`
- Ready-state criteria generation governance - `Partial` (R-014: `collecting`|`ready`, fingerprint idempotency, candidate evaluation stale)
- Real-input cognition quality evaluation (non-fixture ingress path) - `Partial`
- Deep scoring maturity and questionnaire continuity - `Gap`
- Deterministic provider failure taxonomy - `Gap`

### 5. Operational Readiness
Stage status: `Partial`

- Restart-safe local SQLite runtime - `Partial`
- Bounded HTTP ingress idempotency (`POST /candidates/cv/pdf`) - `Partial`
- API ingress hardening (global idempotency, provenance, runtime-grade envelope construction) - `Gap`
- Runtime scope / isolation hygiene - `Gap`
- Single-tenant reset, validation, and deployment playbook - `Gap`

### 6. Platform Expansion
Stage status: `Vision`

- Multi-tenant isolation and production infrastructure - `Vision`
- Durable event/read products and operator-grade history surfaces - `Vision`
- Cross-requisition talent intelligence and long-lived talent pool capabilities - `Vision`

## Upcoming (Action Queue)

This is the near-term action queue derived from capability gaps plus debt priorities; it is not a second roadmap: each action should advance one or more capability areas, and debt-driven actions must reference debt entries using `Debt ID + title` (matching `tech_debt.md`). Round-scoped actions and general capability actions are maintained in this same list (no separate subsection). Only not-yet-completed actions belong here; completed rounds/actions must be removed during planning reconciliation.

**List format:** entries are **not** numbered. The **round ID** (e.g. `R-014`) is the sole stable identifier; add/remove/reorder rows without renumbering. Priority is top-to-bottom in this file until PM reprioritizes.

- **R-015 — Candidate-scoped timeline safety** (`TD-INSPECTION-002 + Timeline rendering format (plain text vs structured projections)`, `TD-INSPECTION-003 + Timeline is global, not candidate-scoped (multi-candidate safety)`; **`TD-CONTRACTS-015` partial — scoring_context `source_ref` lineage through materialize**)
  - Advances: `Recruiter Workflow Operation`, `Operational Readiness`, `Controlled Cognition` (provenance slice)
  - Goal: replace process-global timeline behavior with candidate-aware history, or explicitly narrow timeline product scope; **also** thread recruiter-authored `source_ref` (prose Confirm / Job PDF) into materialized typed `source_refs` and reduce top-level vs typed provenance drift (bounded slice of evidence-reference debt — not full `TD-CONTRACTS-015` contract redesign).

- **R-016 — API hardening** (`TD-API-011 + HTTP ingress idempotency and replay-safe retries`, `TD-API-012 + API boundary coupling to bootstrap helpers (_envelope, fixed clock)`, `TD-API-015 + Idempotency HTTP response canonicalization vs OpenAPI (POST /candidates/cv/pdf)`)
  - Advances: `Operational Readiness`
  - Goal: extend replay-safe ingress beyond create+upload, replace bootstrap-shaped envelope construction with a runtime-grade boundary, and align canonical JSON encoding with OpenAPI for idempotent routes.

- **R-017 — Single-tenant operational playbook** (`TD-PERSISTENCE-001 + Local SQLite schema/cutover migration strategy`, `TD-API-001 + API runtime singleton (single process, shared runtime)`)
  - Advances: `Operational Readiness`
  - Goal: document reset, validation, and local deployment expectations for current SQLite runtime posture.

- **R-018 — Provider-hardening for bounded cognition** (`TD-API-006 + Coarse scoring_failed failure taxonomy`)
  - Advances: `Controlled Cognition`, `Operational Readiness`
  - Goal: move from coarse cognition failure surfaces toward deterministic retryability and clearer provider/runtime semantics.

- **R-019 — Questionnaire/deep-evaluation continuity** (`TD-CONTRACTS-010 + Workflow-context-aware scoring priors`, `TD-ORCHESTRATOR-004 + Conditional questionnaire workflow branching (vertical slice planner)`)
  - Advances: `Controlled Cognition`, `Human Governance`
  - Goal: carry typed layered evaluation semantics more clearly through post-light-scoring stages.

- **R-020 — Full demo phase-out** (`TD-API-012 + API boundary coupling to bootstrap helpers (_envelope, fixed clock)`, `TD-INSPECTION-003 + Timeline is global, not candidate-scoped (multi-candidate safety)`)
  - Advances: `Recruiter Workflow Operation`, `Operational Readiness`
  - Goal: remove `/demo*` routes and compatibility shims, including default candidate bootstrap path (`VERTICAL_SLICE_DEFAULT_CANDIDATE_ID`); keep product-path recruiter/API surfaces only.
  - **Production runtime clock policy (post-cutover):** product-path ingress, audit, and governance timestamps must use real UTC time (`datetime.now(timezone.utc)` or injected clock provider). `modules/recruitment/ingress.FIXED_CLOCK` and other demo fixed clocks must not be used for production audit/governance write paths after cutover.

- **Scoring context golden prose regression (pytest fixtures; round unassigned)** — **queue after R-020**
  - Advances: `Controlled Cognition`, `Operational Readiness`
  - Goal: add version-controlled org / recruiter / job authoring prose under `tests/fixtures/` (distinct from DB seed script `scripts/seed_testing_candidate_from_pdf.py`); under **`LLM_PROVIDER=stub`**, pytest asserts stable **materialized fingerprint** (and bounded L2/L3) after refresh/materialize so skill or fingerprint-rule changes fail CI intentionally. Does not replace PM List UAT; does not eliminate live-LLM drift (accepted risk unless pinned live CI is later approved). Assign round ID when Architect schedules with PM.

- **R-021 — Contract and timestamp hardening** (`TD-CONTRACTS-005 + Timezone-aware datetime handling`, `TD-CONTRACTS-011 + Shared execution metadata structures`, `TD-CONTRACTS-012 + Future shared timing/audit abstractions`)
  - Advances: `Deterministic Foundation`, `Operational Readiness`
  - Goal: remove naive UTC defaults and tighten shared execution metadata/timing semantics before broader contract hardening.

- **R-022 — Contract hardening wave** (`TD-CONTRACTS-001 + Typed payload contracts (events + skill IO)`, `TD-CONTRACTS-004 + Potential migration from Dict[str, Any] to stricter structures (extensions governance)`)
  - Advances: `Deterministic Foundation`, `Operational Readiness`
  - Goal: push typed payload contracts beyond recruiter read models and tighten `extensions` governance.

- **R-023 — Governance domain storage evaluation (planning spike)**
  - Advances: `Human Governance`, `Deterministic Foundation`
  - Goal: decide whether `DecisionState` / `CommunicationState` remain on `OrchestrationState` or split storage without cross-store coupling in orchestrator hot path.

- **R-024 — Job context recruiter Q&A ingress (recruiter-answers productization)**
  - Advances: `Recruiter Workflow Operation`, `Controlled Cognition`
  - Goal: recruiter-facing guided Q&A (LLM-driven) to build job scoring context, wired to existing or evolved job-context authoring APIs (successor to raw `POST /scoring-context/job/recruiter-answers` + prose/PDF paths on List).

## Deferred Without Round Assignment

- `TD-ORCHESTRATOR-011 + Hard filter still represented as scoring preference`
  - Decision: deferred indefinitely (no round assignment for now).
  - Re-entry trigger: only when PM explicitly reintroduces hard-filter as active scope.
