# BlueOcean Recruitment Agent — Development Roadmap

Purpose: preserve long-term development continuity, keep future AI agents and human developers aligned on what the system can do today, and track both capability progress and near-term action priorities without duplicating `PLAN.md` or `tech_debt.md`.

## Project Vision Layer

Build a deterministic, AI-native human evaluation infrastructure for recruitment workflows:

- Programs control workflow through explicit schemas, validated transitions, and deterministic orchestration.
- LLMs provide bounded cognition for understanding, extraction, and generation behind strict interfaces; they do not own routing, ranking, retries, or state mutation.
- Humans govern outcomes through explicit override, approval, calibration, and audit surfaces.

## Current Operating Posture

The current repo operates as a deterministic, single-process SQLite runtime with multi-candidate routing and a recruiter SPA over list/detail/action APIs, including dedup governance (high-confidence block / suspected flag), operator `link` / `keep-separate`, and indexed dedup lookups on create+upload.
As of **R-013.1**, dedup audit and suspected `detected_at` use real UTC; list/detail expose `ingress_in_progress` separately from stale `orphan_ingress` (24h threshold); create+upload blocks on email/phone index hits before allocation and uses fingerprint only as a second-stage suspected check.

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
- Real PDF + scoring-context ingress on List (recruiter-operable baseline) - `Partial`
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
- Ready-state criteria generation governance - `Partial`
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

1. **R-014 — Candidate-scoped timeline safety** (`TD-INSPECTION-002 + Timeline rendering format (plain text vs structured projections)`, `TD-INSPECTION-003 + Timeline is global, not candidate-scoped (multi-candidate safety)`)
   - Advances: `Recruiter Workflow Operation`, `Operational Readiness`
   - Goal: replace process-global timeline behavior with candidate-aware history, or explicitly narrow timeline product scope.

2. **R-015 — API hardening** (`TD-API-011 + HTTP ingress idempotency and replay-safe retries`, `TD-API-012 + API boundary coupling to bootstrap helpers (_envelope, fixed clock)`, `TD-API-015 + Idempotency HTTP response canonicalization vs OpenAPI (POST /candidates/cv/pdf)`)
   - Advances: `Operational Readiness`
   - Goal: extend replay-safe ingress beyond create+upload, replace bootstrap-shaped envelope construction with a runtime-grade boundary, and align canonical JSON encoding with OpenAPI for idempotent routes.

3. **R-016 — Single-tenant operational playbook** (`TD-PERSISTENCE-001 + Local SQLite schema/cutover migration strategy`, `TD-API-001 + API runtime singleton (single process, shared runtime)`)
   - Advances: `Operational Readiness`
   - Goal: document reset, validation, and local deployment expectations for current SQLite runtime posture.

4. **R-017 — Provider-hardening for bounded cognition** (`TD-API-006 + Coarse scoring_failed failure taxonomy`)
    - Advances: `Controlled Cognition`, `Operational Readiness`
    - Goal: move from coarse cognition failure surfaces toward deterministic retryability and clearer provider/runtime semantics.

5. **R-018 — Questionnaire/deep-evaluation continuity** (`TD-CONTRACTS-010 + Workflow-context-aware scoring priors`, `TD-ORCHESTRATOR-004 + Conditional questionnaire workflow branching (vertical slice planner)`)
    - Advances: `Controlled Cognition`, `Human Governance`
    - Goal: carry typed layered evaluation semantics more clearly through post-light-scoring stages.

6. **R-019 — Full demo phase-out** (`TD-API-012 + API boundary coupling to bootstrap helpers (_envelope, fixed clock)`, `TD-INSPECTION-003 + Timeline is global, not candidate-scoped (multi-candidate safety)`)
   - Advances: `Recruiter Workflow Operation`, `Operational Readiness`
   - Goal: remove `/demo*` routes and compatibility shims, including default candidate bootstrap path (`VERTICAL_SLICE_DEFAULT_CANDIDATE_ID`); keep product-path recruiter/API surfaces only.
   - **Production runtime clock policy (post-cutover):** product-path ingress, audit, and governance timestamps must use real UTC time (`datetime.now(timezone.utc)` or injected clock provider). `modules/recruitment/ingress.FIXED_CLOCK` and other demo fixed clocks must not be used for production audit/governance write paths after cutover.

7. **R-020 — Contract and timestamp hardening** (`TD-CONTRACTS-005 + Timezone-aware datetime handling`, `TD-CONTRACTS-011 + Shared execution metadata structures`, `TD-CONTRACTS-012 + Future shared timing/audit abstractions`)
    - Advances: `Deterministic Foundation`, `Operational Readiness`
    - Goal: remove naive UTC defaults and tighten shared execution metadata/timing semantics before broader contract hardening.

8. **R-021 — Contract hardening wave** (`TD-CONTRACTS-001 + Typed payload contracts (events + skill IO)`, `TD-CONTRACTS-004 + Potential migration from Dict[str, Any] to stricter structures (extensions governance)`)
    - Advances: `Deterministic Foundation`, `Operational Readiness`
    - Goal: push typed payload contracts beyond recruiter read models and tighten `extensions` governance.

9. **R-022 — Governance domain storage evaluation (planning spike)**
    - Advances: `Human Governance`, `Deterministic Foundation`
    - Goal: decide whether `DecisionState` / `CommunicationState` remain on `OrchestrationState` or split storage without cross-store coupling in orchestrator hot path.

## Deferred Without Round Assignment

- `TD-ORCHESTRATOR-011 + Hard filter still represented as scoring preference`
  - Decision: deferred indefinitely (no round assignment for now).
  - Re-entry trigger: only when PM explicitly reintroduces hard-filter as active scope.
