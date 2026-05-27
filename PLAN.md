# PLAN (Round R-007)

## Round Type

- **Round ID:** R-007
- **Type:** `major` (parent major round: R-007)
- **One-sentence goal:** Ship a product-grade recruiter SPA on hardened R-006 APIs (list, detail, grouped actions, scoring_context read-only summary) with FastAPI-mounted production build and Vite dev proxy.

## Routing Context

- **Proposed routing outcome** (prior closeout): `advance-major`
- **PM confirmed routing:** `advance-major`
- **Major-round snapshot needed:** `no` (this round opens R-007; snapshot applies when closing a major round on advance)

## Planning-Phase Roadmap Alignment

- Source: [`docs/architecture/ROADMAP.md`](docs/architecture/ROADMAP.md)
- **Upcoming item selected:** #2 **Recruiter frontend MVP** — tied to `TD-API-005` (Candidate list has no pagination or filtering), `TD-API-007` (Recruiter action label ownership), `TD-PERSISTENCE-008` (Evaluation precedence semantics)
- **Capability areas advanced:** `Recruiter Workflow Operation` (Product-grade recruiter frontend: Gap → Partial), `Human Governance` (operator surfaces)

## Planning-Phase Debt Triage

| Debt (ID + title) | This round |
|---|---|
| `TD-API-005` (Candidate list has no pagination or filtering) | **Partial** — client-side cap + stage/status filters; **no** API contract change (no limit/offset on `GET /candidates`) |
| `TD-API-007` (Recruiter action label ownership) | **Partial** — UI renders `available_actions[].label` only; no parallel label map in frontend |
| `TD-PERSISTENCE-008` (Evaluation precedence semantics) | **Partial** — show `overall_score` + `type` (light/deep) with one-line precedence copy aligned to API |
| `TD-ORCHESTRATOR-011` (Canonical hard-filter stage is not restored on recruiter ingress path) | **Defer** |
| `TD-API-011` (HTTP ingress idempotency and replay-safe retries); `TD-API-012` (API boundary coupling to bootstrap helpers) | **Defer** |
| `TD-INSPECTION-002` (Timeline rendering format); `TD-INSPECTION-003` (Timeline is global, not candidate-scoped) | **Defer** |
| `TD-API-008` (Action availability ignores transition guards); `TD-API-009` (Untyped recruiter action payloads); `TD-API-010` (Recruiter action list ordering and grouping); `TD-API-013` (Candidate view ``next_actions`` static) | **RESOLVED** in R-006 — consume only |

**Registry sweep:** Builder updates [`docs/architecture/tech_debt.md`](docs/architecture/tech_debt.md) file-level **Last full registry sweep** date and **Last reviewed** on the three touched OPEN items above to reflect this triage (no status flip to RESOLVED unless implementation fully closes the debt).

## Scope In

- New [`frontend/`](frontend/) app: **Vite + React 18 + TypeScript + Tailwind CSS + TanStack Query + React Router**
- **Pages**
  - **List:** `GET /candidates` — table: rank, stage, status, `overall_score` (value + type), action count; client filters (stage, status kind); display cap default **50** (named constant)
  - **Detail:** `GET /candidate/{candidate_id}` — summary, profile snippet, `scores` (overall + criteria if present), **scoring_context** read-only block (`context_version`, `status`, org/recruiter/job summary fields returned by API), `available_actions` grouped by `group` and sorted by (`order`, `label`, `event_type`)
  - **Actions:** modal collects `reason` (required, min length 1); optional `actor_id` via `VITE_DEFAULT_ACTOR_ID` env; POST `POST /candidates/{candidate_id}/action` with `{ event_type, payload }`; surface `422` codes `invalid_candidate_action` / `invalid_candidate_action_payload`
- **Backend (minimal, no schema/state-machine contract changes)**
  - [`integrations/api/app.py`](integrations/api/app.py): mount `frontend/dist` at **`/app`** with SPA `html=True` when `frontend/dist` exists; optional **CORS** when `VERTICAL_SLICE_CORS_ORIGINS` is set (comma-separated origins)
  - Optional `GET /` → redirect to `/app/` when dist exists (does not remove `/docs`, `/health`, `/demo`)
- **Docs:** [`frontend/README.md`](frontend/README.md) — install, dev, build, proxy, env vars, smoke paths
- **Tests:** Vitest + RTL for helpers (action sort/group, error parse); **`python -m pytest -q`** unchanged green; **`/demo`** regression preserved

### Visual Standards (MVP)

- Layout: `min-h-screen`, content `max-w-6xl` mx-auto, `px-4` `py-6`; clear separation list vs detail
- Typography: one `h1` per route; section `h2`; muted helper text for secondary info
- Spacing: `gap-2`–`gap-4` in control groups; `space-y-6` between sections
- Table: distinct header row; optional row hover; sticky header optional
- Buttons: one primary solid style; secondary outline/ghost; destructive (reject) distinct (e.g. red); disabled clearly non-interactive
- States: loading indicator on list/detail; API errors show message + `code` when present; empty list message
- Forms: action modal shows validation for `reason`; labeled `actor_id` if exposed
- a11y baseline: interactive elements are `button`/`a`; icon-only controls have `aria-label`; avoid low-contrast microcopy

## Scope Out

- Scoring-context authoring POST routes
- CV PDF, timeline productization, `/demo/run` as product path
- Server-side pagination/cursor (full close of `TD-API-005` deferred)
- Auth, multi-tenant, i18n, full design system, Playwright E2E

## Architecture Boundaries

- UI must **not** re-implement transition rules; `available_actions` from API is authoritative
- Do **not** duplicate `ACTION_DESCRIPTORS` / label tables in frontend
- Score display follows API `scores.overall_score` (deep-over-light precedence already applied server-side in projection); UI may add a one-line explanation only

## Ordered Execution Steps

1. Scaffold `frontend/` (Vite `react-ts`), add Tailwind, ESLint, `@/` alias, dependencies: `react-router-dom`, `@tanstack/react-query`, dev test stack
2. Implement API client + typed DTOs aligned with [`integrations/api/schemas_http.py`](integrations/api/schemas_http.py) list/detail/action
3. List route + filters + cap + navigation to detail
4. Detail route + scores + scoring_context summary + grouped actions
5. Action modal + mutation + cache invalidation + error handling
6. FastAPI static mount + optional CORS + optional `/` → `/app/`
7. Vite proxy for `/candidates`, `/candidate`, `/candidates`, `/demo`, `/health` (and other same-origin API paths used by dev)
8. Vitest tests + full pytest
9. Overwrite [`FEEDBACK.md`](FEEDBACK.md) with round report including **§ Manual smoke test** (numbered steps: Node prereq, path A production `/app`, path B Vite dev, minimal click path, one-line white-screen hint)

## Acceptance Criteria

- [ ] Visual standards visibly met (spot-check: layout, button hierarchy, loading/error)
- [ ] `npm run build` produces `frontend/dist`; with API running, browser **`http://127.0.0.1:<PORT>/app/`** serves SPA (not 404)
- [ ] List: multiple candidates, filters + cap work; `overall_score.type` shown when present
- [ ] Detail: scores + scoring_context summary + grouped actions; post-action UI refresh reflects new stage/status
- [ ] Invalid action/payload shows stable error **code** in UI
- [ ] Action labels from API `label` only
- [ ] `python -m pytest -q` all pass; `npm test` in `frontend/` passes
- [ ] `/demo` HTML demo still works
- [ ] `FEEDBACK.md` contains **`## Manual smoke test`** (or equivalent heading) with copy-paste steps for paths A and B

## Required Builder Feedback Format Reminder

Per [`AGENTS.md`](AGENTS.md): round ID, status, step mapping, file list `A`/`M`/`D`, test commands + results, risks, debt **ID + title** touched, roadmap updates if any, suggested next focus; **plus** the Manual smoke test section mandated above.
