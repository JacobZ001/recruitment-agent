# R-014.2 (Minor) — Org Materialization Format Guidance (Checklist)

**PM Approved:** pending

**Parent major round:** R-014

## Round Goal

When stub org **materialization** still blocks `ready`, show **actionable format guidance** on checklist **item 1 (Organization)** — bullets + collapsible copy-paste example — so PM/recruiters can reach `ready` without guessing prose shape.

## Round Type

- `minor` (corrective under R-014; follows completed R-014.1)

---

## PM Decisions (frozen)

### 1. Trigger — when to show format help

Show org format guidance on checklist **item 1** when **either**:

- `materialization_blockers` contains  
  `organization_context must include non-empty company_name plus bounded environment_signals and preference_signals before ready`, **or**
- Item 1 is ✓ (prose confirmed) **and** item 4 is ⚠ with an **organization-targeted** materialized blocker (same string above).

Do **not** show the full example when org prose is simply missing (item 1 ○) — existing friendly copy on item 4 / mapping suffices.

### 2. Placement & content (PM AskQuestion 2026-05-30)

**On checklist item 1 only** (not item 4 long paste):

1. **Three bullets** (plain language):
   - **Company name** — e.g. start with `Company: …`
   - **Team environment** — how your team works (pace, workflow)
   - **What you value** — traits you look for in candidates

2. **Collapsible «Copy example»** (`<details>` or equivalent) containing **stub-proven** prose (deterministic constant, shared with tests):

```text
Company: BlueOcean Recruitment
Our team works in a fast-paced recruiter workflow environment.
We value clear communication and structured follow-through.
```

Alternative single-paragraph stub-proven text (from `tests/conftest.py` `establish_ready_scoring_context`) may be documented in FEEDBACK but **display constant** must be the three-line block above unless PM re-approves.

3. Example block must be **selectable/copy-friendly** (monospace or pre-wrap); no LLM generation.

### 3. Interaction

- Existing behavior unchanged: click item 1 → open drawer + scroll to Organization.
- Format guidance is **visible on the checklist card** under item 1 label when triggered; does not duplicate in drawer (scope out drawer paste).

### 4. Scope boundaries

- **In:** FE checklist + shared constant(s) + vitest for trigger + example constant stability.
- **Out:** Backend / stub `normalize_organization_context_from_text` rule changes; recruiter-answers UI (**R-024**); golden prose pytest fixtures (still queued post-**R-020**).

---

## Scope In

1. `frontend/src/lib/scoringContextBlockers.ts` (or adjacent util) — export org materialization blocker detector + **`ORG_STUB_AUTHORING_EXAMPLE`** constant + bullet labels (deterministic).
2. `frontend/src/components/recruiter/ScoringReadinessChecklist.tsx` — conditional item-1 detail: bullets + `<details>Copy example</details>`.
3. Unit tests: show/hide trigger for known blocker string; example constant non-empty / matches expected lines.
4. `npm test` / `npm run build`; `FEEDBACK.md`; stub manual UAT.

## Scope Out

- Changes to `compute_scoring_context_materialization_blockers` or materialize validation.
- Item 4 replacing org-specific guidance (item 4 keeps current mapped sentence; may add one line «See format under Organization above» only if needed for clarity — **optional**, Builder discretion if item 1 already visible).

## Constraints

- Product path `/app/` List; **`LLM_PROVIDER=stub`**.
- Example text is **fixed** in repo (not user-editable, not LLM).

## Acceptance Criteria

- With org materialization blocker active, checklist item 1 shows **3 bullets + Copy example** fold; without blocker, **no** example block.
- PM can paste example into Organization → Confirm → (with prefs/job already confirmed) refresh → **`ready`** → Create PDF enabled (stub).
- Click item 1 still opens drawer + scroll to Organization.
- `npm test -- --run` + `npm run build` pass; blocker util tests extended.
- R-014.1 behaviors unchanged (drawer, PDF direct upload, Cancel, inline status, etc.).

## Debt Triage

- **Partial (this round):** org prose authoring UX — format example only; stub parse strictness remains until a future cognition/authoring round.
- **Deferred:** **R-015** queue unchanged; advance after R-014.2 UAT.

## Builder Feedback Reminder

`FEEDBACK.md` must include PM manual step: reproduce org blocker → see example on item 1 → copy → Confirm → ready.
