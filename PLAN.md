# R-015 (Major) — Candidate-Scoped Timeline Safety

**PM Approved:** pending

## Round Goal

Replace process-global timeline behavior with candidate-aware history (or explicitly narrow timeline product scope), plus bounded **`TD-CONTRACTS-015`** slice: thread recruiter-authored `source_ref` through scoring-context materialize into typed `source_refs`.

## Round Type

- `major`

## Scope In (draft — Architect to expand after PM routing confirmation)

1. Timeline: candidate-scoped inspection/history read path (`TD-INSPECTION-002`, `TD-INSPECTION-003`).
2. Scoring context: authoring `source_ref` → materialized typed `source_refs` lineage (partial `TD-CONTRACTS-015`; not full evidence contract redesign).
3. Tests + FEEDBACK; product-path verification on Detail (not `/demo/*`).

## Scope Out (draft)

- Full demo phase-out (**R-020**).
- API ingress hardening wave (**R-016**).
- Golden prose pytest fixtures (queue after R-020; round unassigned).

## Roadmap Alignment

- **R-015** from `docs/architecture/ROADMAP.md` Upcoming (top queue after R-014 closeout).

## Debt Triage (draft)

- **Partial:** `TD-CONTRACTS-015`, `TD-INSPECTION-002`, `TD-INSPECTION-003`
- **Deferred:** full evidence reference standardization beyond scoring-context lineage slice

## Architect Closeout Note (R-014)

- **Execution:** `FEEDBACK.md` status `done`; 208 pytest passed; Builder scope complete.
- **Routing recommendation to PM:** **`advance-major`** → open **R-015** (timeline + source_ref slice) unless PM manual UAT finds blocking ingress gaps → then **`corrective-minor` R-014.1**.
- **Residual risks:** real-LLM materialize fingerprint drift (accepted); delete `data/app.db` after schema cutover; demo path still exists until R-020.

## Builder Feedback Reminder

`FEEDBACK.md` must include acceptance traceability per `AGENTS.md` when this round is frozen and approved.
