# FEEDBACK — R-014.2

## Round ID + Status

- **Round:** R-014.2 (minor, parent R-014)
- **Status:** `done`

## Step Completion Mapping

| PLAN step | Status | Notes |
|-----------|--------|-------|
| Backend: structured org/recruiter routes + job structured route + tests | done | `POST /scoring-context/*/structured`; **PM mid-round add:** job moved to `/scoring-context/job/structured` + appends `form://job` |
| Frontend: drawer panels (no inline textarea) + Prose/Q&A modals + tag validation | done | Emerald saved panels + ✓; Describe/Edit vs Fill/Edit The Form; tag limits enforced |
| Frontend: Job form uses recruiter-answers; Job PDF block retained | done | Job Q&A → `postJobContextRecruiterAnswers` + `source_ref=form://job`; PDF direct upload unchanged |
| Tests + build + FEEDBACK | done | pytest + vitest + build all green |

## Acceptance Criteria Traceability

| PLAN acceptance criterion | Verification |
|---------------------------|--------------|
| Three panels have no inline textarea; `saved_locked` is emerald + ✓ | `frontend/src/components/recruiter/ScoringContextIngress.tsx` panel layout |
| Empty: Describe + Fill The Form; Saved: Edit + Edit The Form; divider `Or` | `ScoringContextIngress.tsx` |
| Form-only (stub): org + preferences + job via forms → refresh → `ready` | PM manual steps below; API structured route tests |
| `Edit The Form` enabled only if typed context parseable; else disabled + hint | `parse*Context` + hint copy; manual |
| Form→Prose overwrite shows confirmation modal copy | `ConfirmReplaceFormModal.tsx` |
| Tag limits enforced: ≤8, each ≤120; block add + red error | `TagInput.tsx` + `scoringContextFormSchemas.test.ts` |
| Job uses `/scoring-context/job/structured` and appends `form://job` | `frontend/src/api/client.ts`; `tests/api/test_scoring_context_routes.py` |
| R-014.1 regressions remain working (drawer close, checklist scroll, create PDF gate, PDF direct upload) | PM manual smoke; existing checklist/drawer components unchanged |
| Tests & build pass | Commands below |

## File Change Summary

| Path | Change |
|------|--------|
| `integrations/api/schemas_http.py` | M |
| `integrations/api/app.py` | M |
| `modules/recruitment/use_cases.py` | M |
| `modules/recruitment/__init__.py` | M |
| `tests/api/test_scoring_context_routes.py` | M |
| `frontend/src/api/client.ts` | M |
| `frontend/src/lib/scoringContextFormSchemas.ts` | A |
| `frontend/src/lib/scoringContextFormSchemas.test.ts` | A |
| `frontend/src/components/recruiter/ModalBase.tsx` | A |
| `frontend/src/components/recruiter/ConfirmReplaceFormModal.tsx` | A |
| `frontend/src/components/recruiter/ProseContextModal.tsx` | A |
| `frontend/src/components/recruiter/StructuredContextFormModal.tsx` | A |
| `frontend/src/components/recruiter/TagInput.tsx` | A |
| `frontend/src/components/recruiter/ScoringContextIngress.tsx` | M |
| `frontend/src/components/recruiter/ScoringContextDrawer.tsx` | M |
| `FEEDBACK.md` | M |

## Test Commands & Results

```text
cd frontend && npm test -- --run
→ 29 passed (5 files)

cd frontend && npm run build
→ success

python -m pytest -q
→ 209 passed, 2 skipped
```

## Risks, Deviations, Blockers

- **No blockers.**
- **Scope respected:** No `_validate_materialized_payload` / fingerprint / materialize prompt changes.
- **Job form:** uses recruiter-answers API; additionally appends `form://job` to top-level `source_refs` for `Saved Via Form` detection.

## PM Manual Acceptance (stub LLM)

**Setup:** `$env:LLM_PROVIDER = "stub"`；重启 API；可选删 `data/app.db`。

1. Open `/app/` List; Scoring context button opens drawer; overlay/X closes drawer (Esc closes modals first when open).
2. Each dimension panel has **Describe / Edit**, divider **Or**, and **Fill The Form / Edit The Form** (Title Case).
3. Use **Fill The Form** for Organization/Preferences/Job and Confirm each → refresh to `ready` → Create candidate PDF enabled.
4. Tags: adding >8 or >120 chars is blocked with red inline message; chips removable.
5. `Saved Via Form` shows when top-level `source_refs` includes `form://...`.
6. Open **Edit** on a form-saved dimension → confirmation modal shows `Replace Form Answers?` → proceed to prose modal; Cancel does nothing.
7. Job PDF upload remains usable: Choose File + Confirm; `pdf://` shows inline `From PDF`.
8. Regression smoke (R-014.1): checklist scroll still opens drawer and scrolls to dimension; create PDF gate unchanged.

**Builder verification:** `LLM_PROVIDER=stub` via pytest autouse; structured route tests cover form-only ready path.

## Suggested Next Round

- After UAT passes: `advance-major` → R-015.
