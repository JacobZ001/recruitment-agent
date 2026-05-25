# FEEDBACK (Round R-003)

## Execution Status

- status: done
- blocker: none

## Plan Step Mapping

- Step 1: done - Added a bounded dedicated API ingress route for PDF CV submission and kept route handlers thin by delegating to a new application use case.
- Step 2: done - Added deterministic PDF base64 decode + PDF text extraction helpers with byte/page/text guards, then routed extracted text into existing `submit_cv(..., cv_text=...)`.
- Step 3: partial/done-for-current-env - Verified startup `.env` loading still works end-to-end for the new PDF path via env-file-driven stub configuration; real-provider manual validation could not be executed because no provider credentials were present in the local environment.
- Step 4: done - Verified post-ingress snapshot and recruiter read surfaces (`GET /state/{candidate_id}`, `GET /candidate/{candidate_id}`, `GET /candidates`) reflect typed `profile`, `evaluation.light`, and derived overall score after PDF ingestion.
- Step 5: done - Added deterministic tests for PDF success, empty/invalid extraction failure, provider-not-configured fail-closed behavior, env-file startup wiring, and an opt-in live provider smoke test for the new route.
- Step 6: done - Added the required Local SQLite schema/cutover migration strategy debt entry and updated `ROADMAP.md` at capability level because the slice now supports real PDF CV ingress.

## File Changes (Full List)

- A `modules/recruitment/pdf_ingest.py` - Added deterministic PDF CV decode/extraction helpers with byte/page/text guards and typed extracted-text handoff.
- A `tests/api/test_cv_pdf_ingest.py` - Added API coverage for PDF success, empty-text failure, provider-not-configured fail-closed behavior, env-file startup wiring, and optional live smoke.
- A `tests/modules/test_cv_pdf_ingestion.py` - Added application-layer tests for `submit_cv_pdf` and empty-extraction rejection.
- M `docs/architecture/ROADMAP.md` - Updated capability posture to acknowledge bounded PDF CV ingress in the current recruiter-operable slice.
- M `docs/architecture/tech_debt.md` - Added Local SQLite schema/cutover migration strategy debt entry and updated CV ingress evolution notes for PDF upload reality.
- M `integrations/api/app.py` - Added `POST /candidates/{candidate_id}/cv/pdf` route that delegates to the application layer and reuses `EventIngressResponse`.
- M `integrations/api/errors.py` - Mapped PDF validation/extraction failures to HTTP `422` with a stable `invalid_pdf_cv` code.
- M `integrations/api/schemas_http.py` - Added the bounded request model for PDF ingress (`pdf_base64`, `file_name`, optional `correlation_id`).
- M `modules/recruitment/__init__.py` - Exported the new PDF ingress use case and error type.
- M `modules/recruitment/exceptions.py` - Added `InvalidCvPdfError` for explicit PDF validation/extraction failures.
- M `modules/recruitment/use_cases.py` - Added `submit_cv_pdf(...)`, which converts PDF payloads to text and routes into the existing `cv_submitted` path.
- M `requirements.txt` - Added `pypdf` for deterministic PDF text extraction.

## PDF API Contract Chosen

- Route: `POST /candidates/{candidate_id}/cv/pdf`
- Request content type: `application/json`
- Request body shape:
  - `file_name: str` - must end with `.pdf`
  - `pdf_base64: str` - raw base64-encoded PDF bytes, no data-URL prefix
  - `correlation_id?: UUID`
- Response shape: existing `EventIngressResponse` contract, because the application still publishes a normal `cv_submitted` event after extraction.

### Request Example

```json
{
  "file_name": "candidate_cv.pdf",
  "pdf_base64": "JVBERi0xLjQKJcTl8uXrp...",
  "correlation_id": "7f4de2a0-c704-4ca4-bcf3-2890603a4b9b"
}
```

### Success Response Example

```json
{
  "ingress_accepted": true,
  "publish_status": "accepted",
  "event_id": "0d3527e9-4ffc-4fc6-92f8-d8561de375ca",
  "event_type": "cv_submitted",
  "publish_result": {
    "...": "existing EventIngressResponse payload"
  },
  "state_summary": {
    "pipeline_phase": "light_scored",
    "transitions_count": 1,
    "state_id": "...",
    "store_revision": 2
  }
}
```

### Failure Response Example

```json
{
  "detail": {
    "code": "invalid_pdf_cv",
    "message": "blank_cv.pdf: PDF text extraction produced empty text"
  }
}
```

## Tests and Validation

- command: `python -m pytest tests/modules/test_cv_pdf_ingestion.py tests/api/test_cv_pdf_ingest.py tests/api/test_cv_ingest.py tests/modules/test_cv_ingestion.py tests/skills/test_llm_provider.py -q`
  - result: pass
  - notes: 18 passed, 1 skipped

- command: `python -m pytest tests/api/test_cv_pdf_ingest.py tests/modules/test_cv_pdf_ingestion.py -q`
  - result: pass
  - notes: 6 passed, 1 skipped

- command: `python -m pytest -q`
  - result: pass
  - notes: 150 passed, 2 skipped, 11 warnings

- command: `ReadLints` on changed files
  - result: pass
  - notes: no linter errors found

## Manual Verification Notes

- End-to-end PDF flow manually verified with `LLM_PROVIDER=stub` using the new route:
  - `POST /candidates/{candidate_id}/cv/pdf` returned `publish_status=accepted`
  - `GET /state/{candidate_id}` returned `pipeline_phase=light_scored`
  - `GET /candidate/{candidate_id}` showed non-empty `profile.summary`, populated `evaluation.light.source=system_llm`, and a non-null `scores.overall_score`
  - `GET /candidates` showed the same candidate row with matching `overall_score`, `rank`, and `total_candidates`
- Startup env-loading path also verified end-to-end for PDF ingress via test-created `.env` file (`LLM_PROVIDER=stub`, `LLM_MODEL=stub-cv`) with no explicit process env override.
- Real-provider manual validation:
  - not run in this environment
  - local env inspection found no `LLM_PROVIDER` and no `OPENAI_API_KEY` / `OPENROUTER_API_KEY` / `LLM_API_KEY`
  - optional live smoke test remains available and skipped by default

## Debt / Docs Updates

- `docs/architecture/tech_debt.md`:
  - added **Local SQLite schema/cutover migration strategy (OPEN)**
  - updated the `cv_submitted` ingress debt entry to reflect bounded PDF upload -> deterministic text extraction -> existing typed snapshot path
- `docs/architecture/ROADMAP.md`:
  - updated only at capability-posture level to mention bounded PDF CV upload in the current recruiter-operable slice
  - kept Immediate Next Capabilities wording capability-level; no refactor-detail drift introduced

## Risks, Deviations, and Follow-Up

- Deviations from `PLAN.md`:
  - No scope deviation in code shape; the only unmet ideal was real-provider manual execution because credentials were unavailable locally.
- Remaining MVP go-live risks:
  - Real provider behavior on full recruiter PDFs is still unverified in this environment; only deterministic/stub and mocked paths were exercised here.
  - PDF extraction currently assumes text-based PDFs; OCR/scanned-image CVs remain outside this round’s contract and will fail closed.
  - `scoring_failed` remains coarse for provider/config/runtime failures after extraction succeeds.
- Suggested next focus:
  - Run the optional live smoke on the new PDF route in a credentialed local environment and capture provider-specific failure notes.
  - Decide whether scanned/OCR PDFs belong in MVP scope or should remain explicitly unsupported.
