# FEEDBACK (Round R-005)

## Execution Status

- status: done
- blocker: none

## Plan Step Mapping

- Step 1: done - Added prose-first authoring contract for organization, recruiter, and job context. `ScoringContext` now persists authored prose alongside normalized typed context and derived criteria.
- Step 2: done - Added bounded LLM materialization skill `recruitment.scoring_context.materialize_from_prose` that converts prose into typed canonical context plus candidate `derived_l2_criteria` / `derived_l3_criteria`.
- Step 3: done - Preserved typed canonical `OrganizationContext`, `RecruiterActorContext`, and `JobContext` as the control-plane contract; internal typed authoring helpers now synthesize authoring prose so they still flow through the same refresh materialization path.
- Step 4: done - Kept `refresh` as the only materialization gate: it now normalizes stored prose into typed context, persists canonical derived criteria, and establishes `ready`.
- Step 5: done - Updated downstream light-scoring to consume persisted `ScoringContext.derived_l2_criteria` / `derived_l3_criteria` instead of locally re-deriving labels from context.
- Step 6: done - Updated API response shape and persistence behavior so authored prose, normalized typed context, and derived criteria are all inspectable and reload correctly in both in-memory and SQLite modes.
- Step 7: done - Added focused tests for prose authoring acceptance, bounded normalization output, refresh semantics, persistence, and score-time consumption of canonical persisted criteria.

## Full File Change List

- M `docs/architecture/tech_debt.md` - Updated `TD-SKILLS-001`, `TD-PERSISTENCE-008`, and `TD-PERSISTENCE-009` to reflect prose-first authoring and persisted canonical criteria consumption.
- M `integrations/api/app.py` - Switched public organization/recruiter authoring routes to prose-first use cases.
- M `integrations/api/schemas_http.py` - Changed organization/recruiter authoring request bodies to `raw_text` + `source_ref` and exposed authored prose fields in `ScoringContextResponse`.
- M `modules/recruitment/__init__.py` - Exported new prose-first authoring use cases.
- M `modules/recruitment/scoring_context_service.py` - Added authored-prose helpers, prose normalization helpers, synthesized prose renderers, materialized-payload validation, and freeform job parsing improvements.
- M `modules/recruitment/use_cases.py` - Added prose authoring use cases, refresh-time LLM materialization path, optional injected materializer for tests, and typed-authoring synthesis into authored prose.
- M `schemas/state_schema.py` - Added `organization_authoring_text`, `recruiter_actor_authoring_text`, and `job_authoring_text` to `ScoringContext`.
- M `skills/llm/cv_llm_score_candidate.py` - Switched score-time L2/L3 inputs to persisted derived criteria only.
- A `skills/llm/scoring_context_materialize_from_prose.py` - New bounded LLM skill for prose normalization and criteria materialization.
- M `skills/llm/llm_provider.py` - Added stub-provider support for scoring-context prose materialization.
- M `tests/api/test_cv_ingest.py` - Updated weak-context setup to prose-first public authoring payloads.
- M `tests/api/test_cv_pdf_ingest.py` - Updated weak-context setup to prose-first public authoring payloads.
- M `tests/api/test_scoring_context_routes.py` - Reworked route coverage for prose-first authoring and refresh-time normalization/materialization.
- M `tests/conftest.py` - Updated ready-context fixture to use prose-first authoring and explicit stub materializer injection.
- M `tests/modules/test_scoring_context.py` - Added prose authoring materialization coverage and authored-text assertions.
- M `tests/persistence/test_sqlite_cv_extensions.py` - Added persistence assertions for authored prose and derived criteria.
- M `tests/skills/test_llm_provider.py` - Added stub coverage for scoring-context materialization payload shape.
- A `tests/skills/test_cv_llm_score_candidate.py` - Added direct proof that score-time uses persisted derived criteria.
- A `tests/skills/test_scoring_context_materialize_skill.py` - Added normalization/materialization skill output-shape coverage.

## Exact Authoring Inputs Added / Changed

### Public API authoring inputs

- `POST /scoring-context/organization`
  - before: structured typed organization fields
  - after:
    ```json
    {
      "raw_text": "BlueOcean is a recruitment company ...",
      "source_ref": "optional://source"
    }
    ```
- `POST /scoring-context/recruiter-actor`
  - before: structured typed recruiter fields
  - after:
    ```json
    {
      "raw_text": "Recruiter Maya is a lead recruiter ...",
      "source_ref": "optional://source"
    }
    ```
- `POST /scoring-context/job/text`
  - still accepts `raw_text` + `source_ref`, but semantics changed:
    - before: deterministic normalization into typed `job_context` happened immediately
    - after: prose is staged as authored text and normalized during `refresh`
- `POST /scoring-context/job/recruiter-answers`
  - retained as a compatibility/helper route
  - now converts structured answers into prose-first authored text before refresh-time materialization

### Persisted authored prose fields on `ScoringContext`

- `organization_authoring_text`
- `recruiter_actor_authoring_text`
- `job_authoring_text`

These are now part of the canonical persisted active context and exposed by `GET /scoring-context`.

## Exact Canonical Typed Fields / Signals Retained

The following normalized typed fields remain the internal canonical control-plane semantics:

- `OrganizationContext`
  - `company_name`
  - `industry`
  - `team_name`
  - `environment_signals`
  - `preference_signals`
  - `summary`
  - `source_refs`
- `RecruiterActorContext`
  - `actor_id`
  - `actor_role`
  - `hiring_focus`
  - `preference_signals`
  - `avoid_signals`
  - `summary`
  - `source_refs`
- `JobContext`
  - `title`
  - `summary`
  - `responsibilities`
  - `hard_requirements`
  - `preferred_requirements`
  - `success_signals`
  - `source_refs`

How they are populated now:

- public prose-first routes stage authored prose only
- `refresh` calls the new materialization skill
- the skill returns normalized typed context objects
- deterministic program validation then decides whether those outputs are sufficient for `ready`

Internal typed authoring use cases remain available and now synthesize prose from typed inputs so they still enter the same refresh-time materialization path.

## Exact Bounded LLM Skill Inputs / Outputs

### New skill

- file: `skills/llm/scoring_context_materialize_from_prose.py`
- skill name: `recruitment.scoring_context.materialize_from_prose`

### Skill input payload

```json
{
  "vertical_slice.planner_path": "scoring_context_refresh",
  "organization_authoring_text": "...",
  "recruiter_actor_authoring_text": "...",
  "job_authoring_text": "..."
}
```

### Skill output payload

```json
{
  "organization_context": { "...typed organization fields..." },
  "recruiter_actor_context": { "...typed recruiter fields..." },
  "job_context": { "...typed job fields..." },
  "derived_l2_criteria": ["..."],
  "derived_l3_criteria": ["..."],
  "explanation": "..."
}
```

### Stub behavior

- `StubLLMProvider` now recognizes the materialization prompt and deterministically:
  - normalizes organization prose
  - normalizes recruiter prose
  - normalizes job prose
  - derives candidate L2/L3 criteria

## Exact `refresh` Semantics Before / After

### Before `R-005`

- public authoring primarily stored typed context objects directly
- `refresh_active_scoring_context(...)` deterministically validated the already-stored typed context
- `refresh` itself generated `derived_l2_criteria` / `derived_l3_criteria` from typed context using local deterministic derivation helpers
- there was no persisted authored prose on `ScoringContext`

### After `R-005`

- authoring routes store prose on `ScoringContext` first
- `refresh_active_scoring_context(...)` now:
  1. gathers stored authored prose (or synthesized prose for internal typed authoring helpers)
  2. calls `ScoringContextMaterializeFromProseSkill`
  3. validates the returned typed context and derived criteria deterministically
  4. persists:
    - normalized `organization_context`
    - normalized `recruiter_actor_context`
    - normalized `job_context`
    - canonical `derived_l2_criteria`
    - canonical `derived_l3_criteria`
  5. marks the context `ready`

`ready` now means all of the following are simultaneously true:

- authored prose exists for organization, recruiter, and job authoring
- prose has been materialized into typed canonical context
- materialized L2/L3 criteria were persisted on `ScoringContext`
- the stored ready payload is sufficient for later scoring without hidden re-derivation

Failed refresh:

- still leaves the context non-ready
- still keeps `derived_l2_criteria` / `derived_l3_criteria` empty on failed materialization
- still preserves deterministic `context_version` / stale behavior from prior rounds

## Exact Downstream Scoring Behavior Before / After

### Before `R-005`

`CvLlmScoreCandidateSkill` built required L2/L3 layers by locally calling:

- `derive_l2_labels(job_context, organization_context)`
- `derive_l3_labels(organization_context, recruiter_actor_context)`

That meant score-time still had a hidden second source of truth for criteria.

### After `R-005`

`CvLlmScoreCandidateSkill` now reads:

- `scoring_context.derived_l2_criteria`
- `scoring_context.derived_l3_criteria`

and fails validation if those persisted criteria are missing.

Implication:

- `refresh` materializes criteria
- scoring consumes persisted criteria
- score-time no longer silently rebuilds L2/L3 labels from context

## Exact Persistence Changes

- `ScoringContext` JSON persistence now includes:
  - `organization_authoring_text`
  - `recruiter_actor_authoring_text`
  - `job_authoring_text`
  - normalized typed context objects
  - persisted `derived_l2_criteria`
  - persisted `derived_l3_criteria`
- `InMemoryScoringContextStore`
  - no structural code changes required beyond schema-copy behavior
  - now retains authored prose and derived criteria as part of the stored model
- `SQLiteScoringContextStore`
  - no table migration was needed because the store already persists the full context as JSON
  - reload tests now confirm authored prose and derived criteria survive round-trip

Single active-context scope remains unchanged.

## Exact Tests Added / Updated

### Added

- `tests/skills/test_scoring_context_materialize_skill.py`
  - validates bounded materialization skill output shape from prose
- `tests/skills/test_cv_llm_score_candidate.py`
  - proves score-time uses persisted derived criteria, not local re-derivation

### Updated

- `tests/api/test_scoring_context_routes.py`
  - prose-first route acceptance
  - refresh-time normalization/materialization
  - inspectable authoring text
  - weak-context refresh failure
- `tests/conftest.py`
  - ready-context fixture now uses prose-first authoring and explicit stub materializer injection
- `tests/modules/test_scoring_context.py`
  - prose authoring materialization path
  - authored-text assertions
- `tests/persistence/test_sqlite_cv_extensions.py`
  - authored prose / derived criteria persistence on reload
- `tests/skills/test_llm_provider.py`
  - stub-provider materialization payload support
- `tests/api/test_cv_ingest.py`
  - weak-context public setup aligned to prose-first contract
- `tests/api/test_cv_pdf_ingest.py`
  - weak-context public setup aligned to prose-first contract

## Technical Debt Updates

Full-file `docs/architecture/tech_debt.md` review was already completed in planning (`Last full registry sweep: 2026-05-26`). Builder executed only the debt actions frozen into `PLAN.md`.

Updated entries:

- `TD-SKILLS-001`
  - clarified that scoring-context authoring is now prose-first
  - clarified that `refresh` materializes canonical persisted criteria
  - clarified that score-time no longer re-derives those criteria
- `TD-PERSISTENCE-008`
  - clarified that evaluation precedence now sits on top of canonical persisted scoring inputs rather than stage-local label derivation
- `TD-PERSISTENCE-009`
  - clarified that the single active context now stores richer draft state:
    - authored prose
    - normalized typed context
    - persisted derived criteria

Deferred / unchanged:

- no requisition-scoped context redesign
- no deep-scoring cognition redesign
- no broader API hardening or idempotency work

## Explicit No-Second-Source-of-Truth Confirmation

- Canonical materialization point: `refresh_active_scoring_context(...)`
- Canonical persisted criteria fields:
  - `ScoringContext.derived_l2_criteria`
  - `ScoringContext.derived_l3_criteria`
- Canonical score-time consumer:
  - `CvLlmScoreCandidateSkill`

After this round, score-time no longer calls local derivation helpers to build its own L2/L3 criteria set.

The remaining deterministic derivation helpers are now part of:

- stub-provider materialization support
- bounded normalization/test support

not the live score-time consumption path.

## Tests and Validation

- command: `python -m pytest tests/skills/test_scoring_context_materialize_skill.py tests/skills/test_cv_llm_score_candidate.py tests/skills/test_llm_provider.py tests/modules/test_scoring_context.py tests/api/test_scoring_context_routes.py tests/persistence/test_sqlite_cv_extensions.py -q`
  - result: pass
  - notes: `23 passed`
- command: `python -m pytest tests/api/test_cv_ingest.py tests/api/test_cv_pdf_ingest.py -q`
  - result: pass
  - notes: `10 passed, 1 skipped`
- command: `python -m pytest -q`
  - result: pass
  - notes: `168 passed, 2 skipped, 13 warnings`
- command: `ReadLints` on changed files
  - result: pass
  - notes: no linter errors found

## Deviations, Risks, and Explicit Confirmations

- deviation from `PLAN.md`:
  - none in capability scope
- explicit confirmations:
  - no hidden second source of truth for L2/L3 criteria remains on the score-time path
  - debt handling remained Architect-planned and PM-approved; Builder did not perform execution-time debt replanning
  - no out-of-scope capability work was added to `R-005`
- remaining risks:
  - single active `scoring_context` is still a runtime singleton, not requisition-scoped
  - refresh-time materialization now depends on bounded LLM/provider availability
  - deep scoring remains deterministic/fake rather than real bounded cognition
  - provider/config/runtime failures in scoring/materialization still collapse to coarse `scoring_failed` behavior

## Architect Post-Execution Review

### Roadmap Reconciliation

- no `docs/architecture/ROADMAP.md` change was required during closeout
- `R-005` delivered the planned prose-first `scoring_context` authoring slice and can advance without reopening the selected roadmap item in-place

### Debt Review Addendum

- newly identified / confirmed during Architect review:
  - `TD-CONTRACTS-015`
    - public prose-first authoring accepts `source_ref`, but refresh-time materialization does not yet preserve those recruiter-authored refs on the resulting nested typed contexts
    - current provenance is only partially retained via aggregated `ScoringContext.source_refs` plus normalized component refs
- deferred by closeout decision:
  - `TD-CONTRACTS-015` hardening is deferred to a later round and is not treated as a blocker for closing `R-005`

## Lightweight Round Closeout (Architect / PM)

- proposed routing outcome: `advance-major`
- PM confirmed routing: `advance-major`
- major-round snapshot needed: `yes`
- closeout rationale: `R-005` achieved the planned major capability cutover to prose-first `scoring_context` authoring, refresh-owned materialization, and canonical persisted L2/L3 criteria consumption. The remaining `source_refs` provenance gap is real but bounded, has been recorded under `TD-CONTRACTS-015`, and does not justify holding the round open or forcing a corrective minor round.

## Suggested Next-Round Focus

- open the next major round from the roadmap queue; keep `source_refs` provenance hardening deferred unless auditability or evidence-tooling requirements make it urgent

