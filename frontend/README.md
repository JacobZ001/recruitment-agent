# Recruiter SPA (R-007)

Product-grade recruiter frontend for the hardened R-006 API surfaces.

## Prerequisites

- Node.js 20+ and npm
- Python API running on `http://127.0.0.1:8000` (see repo root)

## Install

```bash
cd frontend
npm install
```

## Environment

Optional Vite env (create `frontend/.env.local` if needed):

```env
VITE_DEFAULT_ACTOR_ID=recruiter-spa
```

Backend optional CORS (comma-separated origins):

```env
VERTICAL_SLICE_CORS_ORIGINS=http://127.0.0.1:5173,http://localhost:5173
```

## Development (path B)

Terminal 1 — API:

```bash
python -m uvicorn integrations.api.app:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2 — Vite dev server (proxies API paths):

```bash
cd frontend
npm run dev
```

Open `http://127.0.0.1:5173/app/` (Vite `base` is `/app/`).

## Production build (path A)

```bash
cd frontend
npm run build
```

With `frontend/dist` present, FastAPI serves the SPA at `/app/` and redirects `/` → `/app/`.

```bash
python -m uvicorn integrations.api.app:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/app/`.

## Tests

```bash
cd frontend
npm test
npm run build
```

Backend regression (from repo root):

```bash
python -m pytest -q
```

## Richer local test data (PDF candidate)

The default fixture candidate (Alex Morgan) is display-only and sparse. To seed a **real parsed CV** into `data/app.db`:

```bash
# From repo root; uses fixtures/candidate_cv.pdf (copied from Desktop) or --pdf
python scripts/seed_testing_candidate_from_pdf.py
```

Stable id: `21024f7f-e639-580f-aae6-d4d2776f910e` (`TESTING_DESKTOP_CANDIDATE_ID` in `modules/recruitment/fixtures.py`). Requires `LLM_PROVIDER=stub` (set by the script). Restart uvicorn if it was already running so list/detail pick up the DB.

## Smoke paths

1. List page loads candidates from `GET /candidates`.
2. Click a candidate → detail shows scores, scoring context summary, grouped actions.
3. Run a recruiter action → modal requires reason; UI refreshes stage/status after success.
4. Invalid payload surfaces API error `code` in the modal.

If the page is blank, open browser devtools → Network: confirm `/app/` returns HTML and JS assets load (wrong `base` or missing `npm run build` are the usual causes).
