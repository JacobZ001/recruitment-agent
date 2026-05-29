# BlueOcean Recruitment Agent — Development Roadmap

Purpose: preserve long-term development continuity, keep future AI agents and human developers aligned on what the system can do today, and track both capability progress and near-term action priorities without duplicating `PLAN.md` or `tech_debt.md`.

## Project Vision Layer

Build a deterministic, AI-native human evaluation infrastructure for recruitment workflows:

- Programs control workflow through explicit schemas, validated transitions, and deterministic orchestration.
- LLMs provide bounded cognition for understanding, extraction, and generation behind strict interfaces; they do not own routing, ranking, retries, or state mutation.
- Humans govern outcomes through explicit override, approval, calibration, and audit surfaces.

## Current Operating Posture

The current repo is a deterministic, single-process proving runtime with SQLite-backed state, multi-candidate routing, a recruiter SPA on hardened list/detail/action APIs, and narrow LLM cognition at ingress. R-011 linkage cleanup baseline is complete; the near-term delivery focus is **R-011.1** (corrective minor): write/sync consolidation plus full-repo architectural tail cleanup, DB visibility reset/reseed verification, and demo-era fixture removal. It is not yet a multi-tenant product runtime, a durable event product, or a production-grade infrastructure topology.

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
- Deep scoring maturity and questionnaire continuity - `Gap`
- Deterministic provider failure taxonomy - `Gap`

### 5. Operational Readiness
Stage status: `Partial`

- Restart-safe local SQLite runtime - `Partial`
- API ingress hardening (idempotency, provenance, runtime-grade envelope construction) - `Gap`
- Runtime scope / isolation hygiene - `Gap`
- Single-tenant reset, validation, and deployment playbook - `Gap`

### 6. Platform Expansion
Stage status: `Vision`

- Multi-tenant isolation and production infrastructure - `Vision`
- Durable event/read products and operator-grade history surfaces - `Vision`
- Cross-requisition talent intelligence and long-lived talent pool capabilities - `Vision`

## Upcoming (Action Queue)

This is the near-term action queue derived from capability gaps plus debt priorities; it is not a second roadmap: each action should advance one or more capability areas, and may reference debt IDs when debt-driven but does not require a debt entry for every item. Round-scoped actions and general capability actions are maintained in this same list (no separate subsection). Only not-yet-completed actions belong here; completed rounds/actions must be removed during planning reconciliation.

1. **R-011.1 — Candidate write/sync consolidation and transitional module closure (current corrective minor under R-011)**
   - Advances: `Deterministic Foundation`
   - Goal: consolidate surviving logic from `candidate_writes` / `candidate_sync` into stable ownership modules and close transitional module sprawl (no behavior change).
   - Entry condition: `R-011` baseline accepted (already met); this round is the mandatory stabilization/closure follow-up.
   - Hard acceptance gates for this minor:
     - full-repo architectural tail cleanup for read/write model alignment (not only mainline flow).
     - stop API -> delete `data/app.db` -> rerun seed -> restart API; verify no legacy `links-only` visibility gap remains.
     - remove demo-era fixture profile (`DEMO_CANDIDATE_DISPLAY`) and related stale demo-first dependency paths.
   - `candidate_sync.py` exit criteria (all required before deletion/absorption):
     - snapshot write path no longer has non-recoverable dual-write partial-success window.
     - read path no longer needs `converge_snapshot_for_read` best-effort reconcile.
     - fail-fast outage behavior and error taxonomy remain preserved in stable owners (`bootstrap` / `use_cases` / `runtime`).
     - regression tests for partial failure + convergence remain green after module closure.
     - no reintroduction of legacy snapshot profile/evaluation fallback semantics.

2. **R-012 — Deterministic hard-filter restoration** (`TD-ORCHESTRATOR-011`)
   - Advances: `Recruiter Workflow Operation`
   - Goal: restore canonical low-cost deterministic hard-filter stage before light scoring.

3. **R-013 — Candidate deduplication and merge policy** (`TD-PERSISTENCE-012`)
   - Advances: `Recruiter Workflow Operation`, `Operational Readiness`
   - Goal: deterministic duplicate detection using `dedup_signals` (normalized email/phone, CV fingerprint) with operator-facing merge/link policy (no silent auto-merge).

4. **R-014 — Candidate-scoped timeline safety** (`TD-INSPECTION-002`, `TD-INSPECTION-003`)
   - Advances: `Recruiter Workflow Operation`, `Operational Readiness`
   - Goal: replace process-global timeline behavior with candidate-aware history, or explicitly narrow timeline product scope.

5. **R-015 — API hardening** (`TD-API-011`, `TD-API-012`)
   - Advances: `Operational Readiness`
   - Goal: add replay-safe ingress semantics and replace bootstrap-shaped envelope construction with a runtime-grade boundary.

6. **R-016 — Single-tenant operational playbook** (`TD-PERSISTENCE-001`, `TD-API-001`)
   - Advances: `Operational Readiness`
   - Goal: document reset, validation, and local deployment expectations for current SQLite runtime posture.

7. **R-017 — Provider-hardening for bounded cognition** (`TD-API-006`)
    - Advances: `Controlled Cognition`, `Operational Readiness`
    - Goal: move from coarse cognition failure surfaces toward deterministic retryability and clearer provider/runtime semantics.

8. **R-018 — Questionnaire/deep-evaluation continuity** (`TD-CONTRACTS-010`, `TD-ORCHESTRATOR-004`)
    - Advances: `Controlled Cognition`, `Human Governance`
    - Goal: carry typed layered evaluation semantics more clearly through post-light-scoring stages.

9. **R-019 — Full demo phase-out** (`TD-DX-002`, `TD-API-012`, `TD-INSPECTION-003`)
    - Advances: `Recruiter Workflow Operation`, `Operational Readiness`
    - Goal: remove `/demo*` routes and compatibility shims; keep product-path recruiter/API surfaces only.

10. **R-020 — Contract and timestamp hardening** (`TD-CONTRACTS-005`, `TD-CONTRACTS-011`, `TD-CONTRACTS-012`)
    - Advances: `Deterministic Foundation`, `Operational Readiness`
    - Goal: remove naive UTC defaults and tighten shared execution metadata/timing semantics before broader contract hardening.

11. **R-021 — Contract hardening wave** (`TD-CONTRACTS-001`, `TD-CONTRACTS-004`)
    - Advances: `Deterministic Foundation`, `Operational Readiness`
    - Goal: push typed payload contracts beyond recruiter read models and tighten `extensions` governance.

12. **R-022 — Governance domain storage evaluation (planning spike)** (`TD-ORCHESTRATOR-012`)
    - Advances: `Human Governance`, `Deterministic Foundation`
    - Goal: decide whether `DecisionState` / `CommunicationState` remain on `OrchestrationState` or split storage without cross-store coupling in orchestrator hot path.
