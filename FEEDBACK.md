# FEEDBACK (Round R-002)

## Execution Status

- status: done
- blocker: none

## Plan Step Mapping

- Step 1: done - Removed legacy score/filter compatibility reads from planner, projection, and inspection paths so typed snapshot fields are the only supported evaluation path.
- Step 2: done - Validated the local SQLite cutover stance by documenting reset expectations and verifying clean boot after deleting `data/app.db`.
- Step 3: done - Added explicit `.env` loading at the FastAPI startup boundary and created `.env.example` for local provider/runtime setup.
- Step 4: done - Added mocked provider-path tests for configuration/network/http/invalid-response behavior and an opt-in live smoke test entry point while keeping deterministic `stub` as the default test path.
- Step 5: done - Registered architecture debt for the coarse `scoring_failed` taxonomy and aligned debt notes with the typed evaluation cutover.
- Step 6: done - Synchronized `ROADMAP.md`, `design_doc.md`, `ADR.md`, and `AGENTS.md` to current system reality and cutover guardrails.

## File Changes (Full List)

- A `.env.example` - Added local environment template for provider selection, API keys, model choice, DB path, and optional live smoke flag.
- A `tests/api/test_app_boot.py` - Added a clean-boot regression test that verifies the default local SQLite path is recreated after reset.
- A `tests/skills/test_llm_provider.py` - Added mocked provider/configuration tests covering not-configured, missing-key, network, HTTP, invalid-response, success, and env-loading behavior.
- A `tests/skills/test_llm_provider_live_smoke.py` - Added an opt-in live smoke test guarded by `RUN_LLM_PROVIDER_LIVE_SMOKE=1`.
- M `AGENTS.md` - Added cutover guardrails so approved removals do not regress into compatibility-shim creep.
- M `docs/architecture/ADR.md` - Added ADR-009 (bounded LLM cognition at CV ingress) and ADR-010 (typed evaluation cutover over legacy `decision.*` compatibility).
- M `docs/architecture/ROADMAP.md` - Updated current capability posture, Stage B/Stage D status, repository topology, and immediate next capabilities to match the SQLite-backed typed-evaluation system.
- M `docs/architecture/design_doc.md` - Updated the “reference implementation today” section and workflow narrative to reflect bounded CV cognition, typed `evaluation`, and local SQLite reset expectations.
- M `docs/architecture/tech_debt.md` - Reframed extension/evaluation debt after cutover, updated candidate-view and CV-ingress notes, and added the `scoring_failed` taxonomy debt entry.
- M `integrations/api/app.py` - Added explicit local `.env` loading at startup without overriding pre-existing process environment.
- M `modules/recruitment/projection.py` - Removed legacy `extensions["decision.*"]` fallback reads so recruiter projections depend only on typed snapshot evaluation.
- M `orchestrator/vertical_slice_planner.py` - Removed legacy extension-to-evaluation reconstruction during skill-state updates.
- M `runtime/inspection/decision_explainer.py` - Removed legacy score/filter extension fallback logic so inspection reads typed evaluation only.
- M `tests/conftest.py` - Kept deterministic `stub` defaults while allowing explicit external provider overrides for opt-in smoke validation.
- M `tests/inspection/test_decision_evidence_navigation.py` - Removed legacy fallback assertions and kept typed-evaluation inspection coverage.
- M `tests/modules/test_list_candidates.py` - Removed legacy-extension-only scoring coverage so list projection tests assert the canonical typed path only.

## Tests and Validation

- command: `python -m pytest tests/modules/test_list_candidates.py tests/inspection/test_decision_evidence_navigation.py tests/skills/test_llm_provider.py tests/skills/test_llm_provider_live_smoke.py tests/api/test_app_boot.py tests/api/test_vertical_slice_api.py tests/api/test_cv_ingest.py -q`
  - result: pass
  - notes: 34 passed, 1 skipped (`RUN_LLM_PROVIDER_LIVE_SMOKE` not enabled), 11 warnings

- command: `python -m pytest -q`
  - result: pass
  - notes: 144 passed, 1 skipped, 11 warnings

- command: `ReadLints` on changed files
  - result: pass
  - notes: no linter errors found

- command: local clean-boot validation using default app startup + `/admin/reset`, then delete `data/app.db`, then repeat
  - result: pass
  - notes: verified `data/app.db` is recreated after deletion; removed the validation DB file afterward to avoid leaving local state behind

## Legacy Compatibility Confirmation

- Confirmed removed: no production/read path now depends on `extensions["decision.*"]` for current score/filter semantics.
- Removed from runtime code: `modules/recruitment/projection.py`, `runtime/inspection/decision_explainer.py`, `orchestrator/vertical_slice_planner.py`.
- Removed from tests: legacy-only fallback assertions in `tests/modules/test_list_candidates.py` and `tests/inspection/test_decision_evidence_navigation.py`.
- Intentionally retained exceptions: none for current score/filter semantics.

## Documentation Delta Summary

- `docs/architecture/ROADMAP.md`: updated the current system posture to durable SQLite + multi-candidate + bounded CV cognition; kept “Immediate next capabilities” at capability level rather than refactor detail.
- `docs/architecture/design_doc.md`: aligned the “reference implementation today” and CV/scoring workflow sections with typed evaluation semantics and the current provider-backed ingress path.
- `docs/architecture/ADR.md`: recorded the first bounded cognition pilot and the approved typed-evaluation cutover/reset stance as explicit ADRs.
- `docs/architecture/tech_debt.md`: updated debt entries from legacy `decision.*` persistence to typed evaluation reality and added the coarse `scoring_failed` taxonomy debt.
- `AGENTS.md`: added process rules that approved cutovers should remove obsolete compatibility paths instead of preserving silent dual semantics.

## Risks, Deviations, and Follow-Up

- Deviations from `PLAN.md`: none.
- Risks / unresolved items:
  - Optional live smoke coverage exists but was not run in this round; default validation remains deterministic by design.
  - `scoring_failed` is still a coarse fail-closed surface until application errors are split into deterministic subcodes.
  - Historical local SQLite rows from before the typed-evaluation cutover are intentionally unsupported without reset; this is documented rather than hidden.
- Suggested next focus:
  - Split `scoring_failed` into deterministic subcodes with retryability semantics.
  - Decide when to expand bounded cognition beyond CV ingress without blurring orchestration ownership.
