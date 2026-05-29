# FEEDBACK — R-010 (Major)

## Round

- **Round ID:** R-010
- **Status:** `done`

## PLAN step mapping

| Step | Status | Notes |
|------|--------|-------|
| 1. Detail header / pane structure | done | `CandidateDetailPage` + `HeaderBar` |
| 2. Job Title + Organization + Recruiter Identity in header | done | From `scoring_context` on candidate view |
| 3. List Stage/Status tags, Score %, Actions buttons | done | `CandidateListPage` |
| 4. Actions: `available_actions` only | done | No disabled placeholders |
| 5. Profile pane full fields + key labels | done | `ProfilePane.tsx` |
| 6. Scores pane layers + evaluation blocks + progress bars | done | `ScoresPane.tsx` |
| 7. Remove detail Scoring Context; add list panel | done | `ScoringContextPanel` + `GET /scoring-context` |
| 8. Remove TD-API-007 hint; label formatting | done | `lib/format.ts` |
| 9. Types cleanup | done | `api/types.ts` |
| 10. UI enhancements (tags, 2-col, expand) | done | Shared recruiter components |
| 11. Backend DTO/projection | skipped | Existing API already exposes profile, evaluation, scores, scoring_context |
| 12–13. Tests + smoke | done | Automated; manual smoke recommended locally |
| 14. FEEDBACK | done | this file |

## File changes

| Path | Change |
|------|--------|
| `frontend/src/pages/CandidateDetailPage.tsx` | M |
| `frontend/src/pages/CandidateListPage.tsx` | M |
| `frontend/src/api/types.ts` | M |
| `frontend/src/api/client.ts` | M |
| `frontend/src/lib/format.ts` | A |
| `frontend/src/lib/format.test.ts` | A |
| `frontend/src/hooks/useRecruiterActions.ts` | A |
| `frontend/src/components/recruiter/*.tsx` | A (8 files) |
| `FEEDBACK.md` | M |

## Tests

```text
cd frontend && npm test
→ 7 passed (3 files)

cd frontend && npm run build
→ OK

python -m pytest -q
→ 179 passed, 2 skipped
```

## Acceptance criteria (summary)

- [x] Detail header: `Candidate Details`, large `full_name`, `Candidate ID: …`, pipeline merged (no Pipeline pane).
- [x] Job Title / Organization / Recruiter Identity in white header bar.
- [x] Stage/Status tag-like styling (list + detail aligned).
- [x] Scores as percent (`formatScorePercent`, no rounding; null → `— —`).
- [x] Overall score + type in header; list Score column percent + type tag.
- [x] List Actions = clickable buttons; same dialog flow as detail (`useRecruiterActions`).
- [x] Profile full key-value; Scores three layers + hard_filter/light/deep meta + progress bars.
- [x] Detail: no Scoring Context panel; list: panel below table via `/scoring-context`.
- [x] TD-API-007 recruiter hint removed.
- [x] No backend contract / state-machine changes this round.

## Debt

- **TD-PERSISTENCE-008** — deferred per PLAN (no change).
- **TD-ORCHESTRATOR-012**, **TD-PERSISTENCE-012**, **TD-API-010** — deferred per PLAN.

## Risks / deviations

- List `Scoring Context` uses global `GET /scoring-context` (not per-row); matches “list testing surface” intent.
- List row actions share one dialog instance with `candidateId` passed on open (ref-synced hook).

## Suggested next-round focus

- **R-011** — OrchestrationState linkage cleanup + legacy compatibility branch removal (per roadmap queue).
