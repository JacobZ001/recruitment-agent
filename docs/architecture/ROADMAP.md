# BlueOcean Recruitment Agent — Development Roadmap

Purpose: preserve long-term development continuity, keep future AI agents and human developers aligned on what the system can do today, and track both capability progress and near-term action priorities without duplicating `PLAN.md` or `tech_debt.md`.

## Project Vision Layer

Build a deterministic, AI-native human evaluation infrastructure for recruitment workflows:

- Programs control workflow through explicit schemas, validated transitions, and deterministic orchestration.
- LLMs provide bounded cognition for understanding, extraction, and generation behind strict interfaces; they do not own routing, ranking, retries, or state mutation.
- Humans govern outcomes through explicit override, approval, calibration, and audit surfaces.

## Current Operating Posture

The current repo is a deterministic, single-process proving runtime with SQLite-backed state, multi-candidate routing, a recruiter SPA on hardened list/detail/action APIs, and narrow LLM cognition at ingress. R-009/R-009.1 completed Candidate aggregate canonical cutover plus consistency hardening; the near-term delivery focus is **R-010**: Candidate Detail UI field curation and recruiter-facing readability hardening before deeper storage/linkage cleanup. It is not yet a multi-tenant product runtime, a durable event product, or a production-grade infrastructure topology.

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

This is the near-term action queue derived from capability gaps plus debt priorities; it is not a second roadmap: each action should advance one or more capability areas, and may reference debt IDs when debt-driven but does not require a debt entry for every item.

1. **Deterministic hard-filter restoration** (`TD-ORCHESTRATOR-011`)
   - Advances: `Recruiter Workflow Operation`
   - Goal: restore a canonical low-cost deterministic hard-filter stage before light scoring.

2. ~~**Recruiter frontend MVP**~~ — **Delivered (R-007 / R-008)**; residual list pagination remains under `TD-API-005` in later queue items.

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

### Round-scoped queue (post R-008)

9. **R-009 — Candidate aggregate canonical cutover (completed major baseline)**
   - Advances: `Recruiter Workflow Operation`, `Deterministic Foundation`
   - Goal: persist canonical `Candidate` (identity, profile, `evaluation_status`); CV parse fills `full_name` / `headline`; planner writes Candidate + snapshot `evaluation_status_ref` only; projection/API read from Candidate; `schema_version` bump + DB reset/seed; YAGNI field prune on `candidate_schema`.
   - Debt: `TD-PERSISTENCE-001` (Local SQLite schema/cutover migration strategy), `TD-PERSISTENCE-008` (Evaluation precedence semantics) — partial close; introduces `TD-PERSISTENCE-012` (dedup keys only).

10. **R-010 — Candidate Detail UI field curation fix (major)**
    - Advances: `Recruiter Workflow Operation`
    - Goal: refine `CandidateDetail` recruiter UX by curating field exposure, reducing noisy blocks, and stabilizing display hierarchy (identity/stage/status/profile/scores/actions) without changing state-machine behavior.
    - Goal (same round): keep API contract changes minimal and display-oriented only; if a projection/DTO tweak is needed, scope it to recruiter read-model clarity and keep backward-safe for current frontend surfaces.
    - Debt: capability-first UI round; persistence and linkage debts are explicitly deferred to next major.

11. **R-011 — OrchestrationState linkage cleanup + compatibility branch removal (major)**
    - Advances: `Deterministic Foundation`, `Recruiter Workflow Operation`
    - Goal: remove loose `links` binding and legacy snapshot fields (`ingress_profile`, full `evaluation`); rely on explicit `OrchestrationState.candidate_id` + Candidate store for all candidate-owned data; align SQLite persistence index with explicit `candidate_id` only.
    - Goal (same round): remove migration-only logic inside `modules/recruitment/candidate_writes.py` (legacy fallback/read-compat branches) so it holds only canonical write helpers.
    - `candidate_sync.py` exit criteria (must all pass before deleting/absorbing module):
      - snapshot write path no longer performs dual-write with partial-success window, or dual-write is made atomically recoverable without dedicated sync helper.
      - read path no longer needs `converge_snapshot_for_read` best-effort reconcile to serve canonical fields.
      - fail-fast outage behavior and error taxonomy are preserved in stable owning modules (`bootstrap`/`use_cases`/`runtime`).
      - dedicated regression tests for partial failure + convergence continue to pass after module removal.
      - no reintroduction of legacy snapshot profile/evaluation fallback semantics.
    - Debt: follow-on from R-009 cutover; reduces dual-source drift risk.

12. **Candidate write/sync consolidation (post R-011)**
    - Advances: `Deterministic Foundation`
    - Goal: avoid module sprawl by moving surviving canonical helpers from `modules/recruitment/candidate_writes.py` and `modules/recruitment/candidate_sync.py` into stable ownership modules (`bootstrap` / `use_cases` or a single canonical service), then delete transitional helper modules.
    - Constraint: no behavior change; pure ownership/consolidation refactor with replay/test parity.

13. **Candidate deduplication and merge policy**
    - Advances: `Recruiter Workflow Operation`, `Operational Readiness`
    - Goal: deterministic duplicate detection using R-009 `dedup_signals` (normalized email/phone, CV fingerprint); operator-facing merge/link policy (no silent auto-merge).
    - Debt: `TD-PERSISTENCE-012` (Candidate deduplication and merge policy).

14. **Full demo phase-out**
    - Advances: `Recruiter Workflow Operation`, `Operational Readiness`
    - Goal: remove `/demo*` routes and compatibility shims; product-path-only recruiter/API surfaces.
    - Debt: `TD-DX-002` (Compatibility shim sprawl and demo-first residue), `TD-API-012` (API boundary coupling to bootstrap helpers (`_envelope`, fixed clock)), `TD-INSPECTION-003` (Timeline is global, not candidate-scoped (multi-candidate safety)).

15. **Contract hardening wave**
    - Advances: `Deterministic Foundation`, `Operational Readiness`
    - Goal: typed payload contracts beyond recruiter read models; tighten `extensions` governance.
    - Debt: `TD-CONTRACTS-001` (Typed payload contracts (events + skill IO)), `TD-CONTRACTS-004` (Potential migration from `Dict[str, Any]` to stricter structures (`extensions` governance)).

16. **Governance domain storage evaluation (planning spike)**
    - Advances: `Human Governance`, `Deterministic Foundation`
    - Goal: decide whether `DecisionState` / `CommunicationState` remain on `OrchestrationState` or split storage without cross-store coupling in the orchestrator hot path.
    - Debt: `TD-ORCHESTRATOR-012` (Decision/communication domains on OrchestrationState — to be registered at R-009 closeout).
