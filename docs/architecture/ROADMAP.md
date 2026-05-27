# BlueOcean Recruitment Agent — Development Roadmap

Purpose: preserve long-term development continuity, keep future AI agents and human developers aligned on what the system can do today, and track both capability progress and near-term action priorities without duplicating `PLAN.md` or `tech_debt.md`.

## Project Vision Layer

Build a deterministic, AI-native human evaluation infrastructure for recruitment workflows:

- Programs control workflow through explicit schemas, validated transitions, and deterministic orchestration.
- LLMs provide bounded cognition for understanding, extraction, and generation behind strict interfaces; they do not own routing, ranking, retries, or state mutation.
- Humans govern outcomes through explicit override, approval, calibration, and audit surfaces.

## Current Operating Posture

The current repo is a deterministic, single-process proving runtime with SQLite-backed state, multi-candidate routing, bounded recruiter-facing APIs, and narrow LLM cognition at ingress. Recruiter list/detail/action surfaces now share canonical guard-aware action semantics and typed payload validation; the near-term delivery focus is a recruiter frontend MVP on those APIs. It is not yet a multi-tenant product runtime, a durable event product, or a production-grade infrastructure topology.

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
- Product-grade recruiter frontend / workflow workspace - `Gap`
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

This is the near-term action queue derived from capability gaps plus debt priorities; it is not a second roadmap: each action should advance one or more capability areas, and may reference debt IDs when debt-driven but does not require a debt entry for every item.

1. **Deterministic hard-filter restoration** (`TD-ORCHESTRATOR-011`)
   - Advances: `Recruiter Workflow Operation`
   - Goal: restore a canonical low-cost deterministic hard-filter stage before light scoring.

2. **Recruiter frontend MVP** (`TD-API-005`, `TD-API-007`, `TD-PERSISTENCE-008`)
   - Advances: `Recruiter Workflow Operation`, `Human Governance`
   - Goal: ship a real recruiter-facing frontend on top of the hardened candidate list/detail/action APIs, with bounded list ergonomics, frontend-safe action copy semantics, and clear score/action presentation for end-to-end product validation.

3. **Candidate-scoped timeline safety** (`TD-INSPECTION-002`, `TD-INSPECTION-003`)
   - Advances: `Recruiter Workflow Operation`, `Operational Readiness`
   - Goal: replace process-global timeline behavior with candidate-aware history, or explicitly narrow timeline product scope.

4. **API hardening** (`TD-API-011`, `TD-API-012`)
   - Advances: `Operational Readiness`
   - Goal: add replay-safe ingress semantics and replace bootstrap-shaped envelope construction with a runtime-grade boundary.

5. **Contract and timestamp hardening** (`TD-CONTRACTS-005`, `TD-CONTRACTS-011`, `TD-CONTRACTS-012`)
   - Advances: `Deterministic Foundation`, `Operational Readiness`
   - Goal: remove naive UTC contract defaults, tighten shared execution metadata/timing semantics, and reduce schema-level warning debt before broader integration-facing hardening.

6. **Provider-hardening for bounded cognition** (`TD-API-006`)
   - Advances: `Controlled Cognition`, `Operational Readiness`
   - Goal: move from coarse cognition failure surfaces toward deterministic retryability and clearer provider/runtime semantics.

7. **Questionnaire/deep-evaluation continuity** (`TD-CONTRACTS-010`, `TD-ORCHESTRATOR-004`)
   - Advances: `Controlled Cognition`, `Human Governance`
   - Goal: carry typed layered evaluation semantics more clearly through post-light-scoring stages.

8. **Single-tenant operational playbook** (`TD-PERSISTENCE-001`, `TD-API-001`)
   - Advances: `Operational Readiness`
   - Goal: document reset, validation, and local deployment expectations for the current SQLite-backed runtime posture.
