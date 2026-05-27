# FEEDBACK (Round R-007)

## Execution Status

- status: done
- blocker: none

## Plan Step Mapping

- Step 1: done - Scaffolded `frontend/` with Vite + React 18 + TypeScript + Tailwind CSS v4, React Router, TanStack Query, Vitest/RTL, ESLint, and `@/` path alias.
- Step 2: done - Implemented typed API client and DTOs aligned with `integrations/api/schemas_http.py` for list, detail, and recruiter action POST.
- Step 3: done - Built list route with stage/status client filters, `LIST_DISPLAY_LIMIT = 50` cap, score type display, and navigation to detail.
- Step 4: done - Built detail route with profile snippet, scores (overall + criteria), read-only scoring_context summary, and API-driven grouped recruiter actions.
- Step 5: done - Built action modal with required `reason`, optional `VITE_DEFAULT_ACTOR_ID`, mutation + cache invalidation, and stable 422 error codes in UI.
- Step 6: done - Mounted `frontend/dist` at `/app` with SPA `html=True`, optional CORS via `VERTICAL_SLICE_CORS_ORIGINS`, and `/` → `/app/` redirect when dist exists.
- Step 7: done - Configured Vite dev proxy for `/candidates`, `/candidate`, `/demo`, `/health`, and related API paths.
- Step 8: done - Added Vitest coverage for `actionsByGroup` and `extractApiError`; full backend pytest remains green.
- Step 9: done - Added `frontend/README.md` and this report including **Manual smoke test** steps.

## Full File Change List

- A `frontend/` (entire recruiter SPA tree: package config, Vite/Tailwind/TS, `src/` pages, API client, helpers, tests)
- A `frontend/README.md` - install, dev, build, proxy, env vars, smoke paths
- M `integrations/api/app.py` - SPA static mount at `/app`, optional CORS, root redirect when `frontend/dist` exists
- A `tests/api/test_recruiter_spa_mount.py` - SPA mount + `/demo` regression when dist present/absent
- M `docs/architecture/tech_debt.md` - registry sweep date; partial triage notes for `TD-API-005`, `TD-API-007`, `TD-PERSISTENCE-008`

## Recruiter SPA Surfaces Delivered

### List (`GET /candidates`)

- Table columns: rank, candidate id (link), stage, status kind, overall score (value + `light`/`deep` type badge), available action count
- Client filters: pipeline stage, status kind (`active` / `inactive` / `hired`)
- Display cap: `LIST_DISPLAY_LIMIT = 50` after filtering (no API contract change)

### Detail (`GET /candidate/{candidate_id}`)

- Pipeline summary (stage, status, evaluation summary text)
- Profile snippet when present on API payload
- Scores: overall + criteria rows; one-line deep-over-light precedence copy (does not recompute server precedence)
- Scoring context read-only: `context_version`, `status`, organization, job title, recruiter actor id
- Recruiter actions grouped by API `group`, sorted by (`order`, `label`, `event_type`); button labels use API `label` only

### Actions (`POST /candidates/{candidate_id}/action`)

- Modal collects required `reason` and `actor_id` (default from `VITE_DEFAULT_ACTOR_ID` or `recruiter-spa`)
- Payload: `{ actor_id, actor_type: "recruiter", reason, evidence_refs: [] }`
- On success: invalidates candidate + list queries so stage/status refresh
- On 422: surfaces `invalid_candidate_action` / `invalid_candidate_action_payload` codes when present in FastAPI `detail`

## Backend Integration

- When `frontend/dist/index.html` exists:
  - `GET /` → `307` redirect to `/app/`
  - `GET /app/` and client routes served via `StaticFiles(..., html=True)`
- When dist absent: API behavior unchanged; `/demo`, `/docs`, `/health` unaffected
- Optional `VERTICAL_SLICE_CORS_ORIGINS` (comma-separated) enables CORSMiddleware for Vite dev origin

## Test Commands and Results

- `cd frontend && npm test` → **4 passed**
- `cd frontend && npm run build` → **success** (`frontend/dist/` produced)
- `python -m pytest -q` → **173 passed, 2 skipped, 13 warnings** (existing Pydantic `utcnow` deprecation warnings)

## Technical Debt Touched

| Debt ID + title | Round handling |
|---|---|
| `TD-API-005` - Candidate list has no pagination or filtering | **Partial** — client-side filters + cap only; API unchanged; `Last reviewed` updated |
| `TD-API-007` - Recruiter action label ownership | **Partial** — SPA renders API `label` only; no frontend label map; `Last reviewed` updated |
| `TD-PERSISTENCE-008` - Evaluation precedence semantics | **Partial** — UI shows `overall_score` + `type` with precedence copy; no client-side score recomputation; `Last reviewed` updated |
| `TD-ORCHESTRATOR-011`, `TD-API-011`, `TD-API-012`, `TD-INSPECTION-002`, `TD-INSPECTION-003` | **Deferred** per plan |

- File-level **Last full registry sweep**: updated to **2026-05-27**

## Risks and Deviations

- No deviations from `PLAN.md` scope.
- `frontend/dist` is build output; production smoke requires `npm run build` before serving `/app/`.
- Client-side list cap does not close `TD-API-005`; server still returns full candidate list.

## Scope Confirmation

- No scoring-context authoring routes in SPA
- No CV PDF, timeline productization, or `/demo/run` product path
- No server-side pagination, auth, multi-tenant, or Playwright E2E
- No schema / state-machine / transition contract changes

## Suggested Next-Round Focus

- Deterministic hard-filter restoration (`TD-ORCHESTRATOR-011`) or API hardening (`TD-API-011` / `TD-API-012`) per roadmap priority
- Server-side list pagination/filters when candidate volume exceeds client-cap usefulness

## Manual smoke test

**Prerequisites:** Node.js 20+, Python deps installed, API can bind port 8000.

### Path A — production bundle via FastAPI (`/app/`)

1. `cd frontend && npm install && npm run build`
2. From repo root: `python -m uvicorn integrations.api.app:app --host 127.0.0.1 --port 8000`
3. Open `http://127.0.0.1:8000/app/` — expect recruiter list UI (not 404).
4. Optional: `http://127.0.0.1:8000/` should redirect to `/app/`.
5. Click a candidate row → detail shows scores, scoring context block, grouped action buttons (labels from API).
6. Optional seed: `curl -X POST http://127.0.0.1:8000/demo/run` then refresh list/detail.
7. Run one recruiter action (e.g. Schedule Interview) with a non-empty reason → stage/status updates after confirm.
8. Confirm `http://127.0.0.1:8000/demo` still returns HTML demo page.

**White-screen hint:** DevTools → Network: `/app/` must return HTML; JS/CSS under `/app/assets/` must be 200. Missing `npm run build` or wrong `base` in Vite config are the usual causes.

### Path B — Vite dev server (proxy to API)

1. Terminal 1 (repo root): `python -m uvicorn integrations.api.app:app --reload --host 127.0.0.1 --port 8000`
2. Terminal 2: `cd frontend && npm install && npm run dev`
3. Open the URL Vite prints (typically `http://127.0.0.1:5173/app/`).
4. Repeat list → detail → action steps from Path A steps 5–7.
5. If browser blocks cross-origin calls from a non-proxied origin, set `VERTICAL_SLICE_CORS_ORIGINS=http://127.0.0.1:5173` and restart API.

**White-screen hint:** Check Vite terminal for compile errors; confirm proxy targets port 8000 and API `/health` returns 200.
