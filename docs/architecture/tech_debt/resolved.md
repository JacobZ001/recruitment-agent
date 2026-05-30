# BlueOcean Recruitment Agent — Resolved/Superseded Debt Archive

Purpose: keep historical debt decisions that are no longer active (`RESOLVED` / `SUPERSEDED`) while reducing active planning sweep context.

- **Archive created**: 2026-05-30
- **Source split from**: `docs/architecture/tech_debt.md`

## Archive rules

- `Debt ID` is immutable and never reused.
- Entries are moved here by preserving original `### TD-...` heading and body.
- Re-open work by creating a new active debt entry (or explicitly moving an entry back with PM-approved rationale).

---

## Orchestrator

### TD-ORCHESTRATOR-006 `ranking_completed` event (deprecated)

Summary (v2 cleanup):

- **Deprecated**: was used as an intermediate orchestration event on the bus.
- **Replaced by**: direct planner decision (same ingest) for clarity and determinism.
- **Removal**: enum / timeline skip logic to be fully removed in v2 once replay fixtures allow.

- **Status**: SUPERSEDED (envelope type retained for schema/replay of old recordings only)
- **Revisit when**: v2 removal of `EventType.RANKING_COMPLETED` and scrub of historical tapes
- **Introduced in**: 2026-05-14
- **Last reviewed**: 2026-05-26
- **Current decision**: Ranking is a **direct planner decision** chained in the same ingest as ``light_scoring_completed`` / ``deep_scoring_completed`` via ``OrchestrationPlan.secondary_proposed_transition`` (validated and committed immediately after the primary transition). The orchestrator **does not** publish ``ranking_completed``. API ingress allowlists no longer include it; inspection timelines **skip** runs whose sole ingest was ``ranking_completed`` so primary lines read ``light_scoring_completed`` → ``questionnaire_pending`` (etc.) without an intermediate envelope row.
- **Rationale**: ``ranking_completed`` was an intermediate orchestration event; in-process chaining reduces bus noise and keeps replay deterministic with fewer subscriber runs for the same pipeline outcome.
- **Future impact**: Old event catalogs or tests that published ``ranking_completed`` explicitly must migrate; enum value remains until v2.
- **Priority**: Low
- **Recommended future direction**: Remove ``ranking_completed`` from ``EventType`` and delete timeline skip logic once no replay fixtures depend on it.

**Ranking decision visibility**

- ``ranking_completed`` was removed for clarity (no duplicate ingest for the same planner outcome).
- Ranking decisions are **implicit** in the planner (chained secondary transition on the same envelope as ``light_scoring_completed`` / ``deep_scoring_completed``).
- For explainability, **persist and surface** ``ranking.branch`` and ``ranking.stage`` on transition records and snapshot ``OrchestrationState.extensions`` (same merge pattern as ``inactive.*``); timelines and inspection read these keys only.

---

## Persistence

### TD-PERSISTENCE-002 SQLite replace uses DELETE + INSERT instead of UPSERT
- **Status**: RESOLVED
- **Revisit when**: N/A (re-open only if a narrower child-table write-path debt is carved out later)
- **Introduced in**: 2026-05-12
- **Last reviewed**: 2026-05-26
- **Current decision**: The central `orchestration_state` write path in `runtime/persistence/sqlite_state_store.py` now uses `INSERT ... ON CONFLICT(state_id) DO UPDATE` for snapshot replacement. The original debt row described a full delete-and-reinsert strategy for the primary state row, which is no longer accurate.
- **Rationale**: The old debt was specific to the primary SQLite replace path. That implementation detail has now been corrected without reopening broader persistence architecture questions.
- **Future impact**: None for the original claim. If later optimization work is needed for child tables or audit/index write churn, record that as a narrower new debt instead of keeping this resolved row open.
- **Priority**: Low
- **Recommended future direction**: Keep this row as historical closure. Do not re-open unless a new, more precise SQLite write-path debt is identified.

---

## API

### TD-API-002 Fixed aggregate identity (single candidate-scoped orchestration instance)
- **Status**: SUPERSEDED
- **Revisit when**: N/A (see successor entries below)
- **Introduced in**: 2026-05-12
- **Last reviewed**: 2026-05-26
- **Current decision**: **Superseded** by Stage B multi-candidate wiring: ``POST /events`` and read APIs accept arbitrary ``candidate_id`` values; orchestration snapshots are created on **ingress (write path)** and resolved via the store’s ``get_for_candidate`` index. The bootstrap **default demo candidate** remains the wired reference subject for ``/demo/*`` and timeline (see **Timeline is global, not candidate-scoped**).
- **Rationale**: Original entry tracked pre–Stage B single-aggregate HTTP rejection; behavior has moved forward without closing all related debt (mapping duplication, global timeline).
- **Future impact**: None as a standalone gate; follow **Candidate → state_id mapping (single source of truth)** and timeline entries instead.
- **Priority**: Low
- **Recommended future direction**: Treat this registry row as historical; do not re-open unless aggregate lifecycle requirements regress.

### TD-API-008 Action availability ignores transition guards
- **Status**: RESOLVED
- **Revisit when**: Re-open only if recruiter surfaces need to expose richer guard diagnostics than the current available/unavailable contract
- **Introduced in**: 2026-05-22
- **Last reviewed**: 2026-05-26
- **Current decision**: Recruiter action availability now evaluates the canonical transition registry plus optional guard conditions through ``TransitionEngine`` validation. ``GET /candidates``, ``GET /candidate/{candidate_id}``, and ``POST /candidates/{candidate_id}/action`` all use the same action projection path and the same snapshot-derived extensions when checking availability.
- **Rationale**: `R-006` made recruiter action availability authoritative enough for recruiter-facing surfaces without introducing a duplicate phase→action policy table.
- **Future impact** / **risks**:
  - The default registry in the reference slice still has no production guard catalog; guard-aware behavior is now supported and regression-tested, but richer runtime guard coverage remains a separate policy concern.
- **Priority**: High
- **Recommended future direction**: Keep action projection routed through transition-engine validation. If product surfaces need to explain *why* an action is blocked, add structured guard-diagnostic metadata without relaxing the single source of truth.

### TD-API-009 Untyped recruiter action payloads
- **Status**: RESOLVED
- **Revisit when**: Re-open only when a recruiter action needs richer typed fields beyond the current governance payload contract
- **Introduced in**: 2026-05-22
- **Last reviewed**: 2026-05-26
- **Current decision**: ``POST /candidates/{candidate_id}/action`` now validates payloads through a deterministic recruiter-action payload registry keyed by recruiter ``event_type`` before publish. The current action set still shares the bounded governance payload contract, but unknown or malformed fields now fail fast with a stable ``invalid_candidate_action_payload`` error.
- **Rationale**: `R-006` hardened the recruiter action boundary without widening scope into new action-specific business fields.
- **Future impact** / **risks**:
  - The registry currently maps the bounded recruiter action set to the shared governance payload model; future richer actions should add narrower typed models rather than bypass the registry.
- **Priority**: Medium
- **Recommended future direction**: Extend the existing registry one action at a time when interview scheduling, offer authoring, or audit templates require additional typed fields.

### TD-API-010 Recruiter action list ordering and grouping (UI)
- **Status**: RESOLVED
- **Revisit when**: Re-open only if recruiter product surfaces need more presentation metadata than group/order
- **Introduced in**: 2026-05-22
- **Last reviewed**: 2026-05-26
- **Current decision**: Recruiter action projections now include deterministic ``group`` and ``order`` metadata and are sorted by policy-shaped order rather than raw alphabetical ``event_type``. The metadata is carried on recruiter-facing API surfaces without introducing a second authoritative phase-action map.
- **Rationale**: `R-006` needed stable ordering/grouping for recruiter clients while preserving transition-registry truth as the availability source.
- **Future impact**: Minimal for the original debt. If future UI needs richer sections, icons, or role-aware copy, add them as metadata on the same action catalog rather than rebuilding availability logic elsewhere.
- **Priority**: Low
- **Recommended future direction**: Keep catalog metadata bounded to presentation concerns and continue deriving actual availability from registry validation.

### TD-API-013 Candidate view ``next_actions`` (static)
- **Status**: RESOLVED
- **Revisit when**: Re-open only if the public candidate detail surface later removes ``next_actions`` entirely in favor of richer action objects
- **Introduced in**: 2026-05-12
- **Last reviewed**: 2026-05-26
- **Current decision**: ``build_candidate_view`` now derives both ``available_actions`` and compatibility ``next_actions`` from the same canonical recruiter action projection used by the candidate list and recruiter action POST boundary. ``next_actions`` remains a string list for compatibility, but it is no longer a static phase-hint map.
- **Rationale**: `R-006` removed the last recruiter-detail action drift without forcing an immediate breaking response-shape cutover.
- **Future impact**: The original static-drift risk is removed. Remaining product decisions are about how long to keep the compatibility string list alongside structured action items.
- **Priority**: Low
- **Recommended future direction**: Keep ``next_actions`` as a compatibility projection only; prefer structured ``available_actions`` for any new recruiter client behavior.

### TD-API-016 Candidate deduplication, merge/link, and orphan governance
- **Status**: RESOLVED
- **Revisit when**: Before expanding dedup policy beyond balanced/hybrid matrix, cross-candidate **data** merge, or typed ``extensions.dedup`` contracts
- **Introduced in**: 2026-05-30 (R-013)
- **Last reviewed**: 2026-05-30 (closed R-013.2)
- **Current decision**: Delivered deterministic duplicate governance for the recruiter create+upload path across **R-013**, **R-013.1**, and **R-013.2**:
  - **R-013**: balanced/hybrid matrix (email/phone high-confidence block; fingerprint-only suspected); ``POST /candidates/cv/pdf`` routing; recruiter ``link`` / ``keep-separate`` with extension audit; orphan visibility from idempotency ``IN_PROGRESS``.
  - **R-013.1**: real UTC dedup audit timestamps; ``ingress_in_progress`` vs stale ``orphan_ingress`` (``ORPHAN_INGRESS_STALE_SECONDS``); indexed email/phone/fingerprint lookups with email/phone pre-check before allocation.
  - **R-013.2**: removed runtime SQLite ``ALTER``/backfill for dedup columns (local cutover = delete ``data/app.db`` per ``frontend/README.md``); post-parse high-confidence evaluation after cv_parse persistence → ``post_ingress_duplicate`` flag with matches merge when pre-create suspected also fired; in-flight retry post-parse idempotency; HTTP/idempotency ``dedup`` body aligned with store.
- **Rationale**: Non-silent, operator-controlled duplicate handling without auto-merge or background delete; deterministic policy in program logic; preserves R-012 idempotency semantics.
- **Future impact**: None for the original MVP governance slice. Follow-on work is intentionally separate (see non-goals).
- **Priority**: High (at introduction; closed at baseline)
- **Recommended future direction**: If policy expands beyond balanced/hybrid or cross-candidate merge is required, open a **new** debt entry rather than re-opening this ID.

**Intentional non-goals (not unresolved debt):**

- No cross-candidate **data** merge (link metadata only).
- ``extensions.dedup`` remains app-owned dict (typed contract → ``TD-CONTRACTS-004`` or successor).
- Other ingress paths may still use ``FIXED_CLOCK`` (``TD-API-012`` / R-019).
- Candidate list source-of-truth remains store-driven (``TD-API-004``).

