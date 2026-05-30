# AGENTS.md

# BlueOcean Recruitment Agent — AI Engineering Rules

## System Philosophy

This project is NOT a simple AI recruitment chatbot.

It is a deterministic AI-native Human Evaluation Infrastructure.

Core principle:

Deterministic orchestration
+
LLM cognition layer
+
Harness validation system

Programs control workflow.
LLMs provide semantic understanding.

---

# Architecture Principles

## Principle 1

Stable architecture > smart prompts

## Principle 2

AI handles understanding.
Programs handle control.

## Principle 3

All critical behaviors must be verifiable.

## Principle 4

Do NOT allow LLMs to directly control:

- state transitions
- ranking
- workflow routing
- retries
- orchestration logic

---

# Repository Structure Rules

## /schemas

Canonical contracts.

Schemas are system-critical and must remain stable.

Do NOT modify schemas without explicit approval.

---

## /state_machine

Contains:

- states
- transitions
- validation rules

All transitions must be deterministic.

---

## /skills/deterministic

Pure programmatic logic.

No LLM calls allowed.

Examples:

- hard filter (deferred)
- ranking
- deduplication
- retry logic

---

## /skills/llm

Semantic reasoning layer.

Used only for:

- understanding
- extraction
- generation

---

## /skills/hybrid

Combines:

- LLM signal extraction
- deterministic policy logic

---

## /tests

All deterministic logic must have tests.

Critical systems requiring tests:

- state transitions
- ranking
- schema validation
- hard filter

---

# State Machine Rules

The system is event-driven.

LLMs may suggest signals but may NOT directly mutate states.

All state transitions must:

- pass validation
- be deterministic
- be logged

---

# Schema Rules

All schemas must:

- use explicit typing
- avoid silent structural drift

Use:

- Pydantic
- Enums
- Explicit validation

---

# Prompt Rules

Prompts are NOT business logic.

Business logic belongs in deterministic systems.

Do NOT encode:

- ranking logic
- orchestration logic
- hard filtering
inside prompts.

---

# Human Override Rules

Human operators always retain authority.

The system must support:

- force approve
- force reject
- manual score adjustment
- state override

All overrides must be logged.

---

# Harness Rules

Every critical subsystem must be verifiable.

Required validation layers:

- schema validation
- state transition validation
- skill IO validation
- ranking consistency tests

---

# Shared Engineering Constraints

These rules apply to both Architect Agent and Builder Agent:

- preserve architecture boundaries
- avoid unnecessary abstraction
- avoid hidden coupling
- prefer small bounded changes
- prefer explicit typing
- prefer deterministic behavior
- prefer modular implementation
- avoid large uncontrolled refactors
- avoid autonomous architecture rewrites
- avoid implicit assumptions

---

# Collaboration Operating Model (PM / Architect / Builder)

## Role Ownership

### Project Manager (Human)

- Owns final product and scope decisions.
- Approves or rejects each development round proposal.
- Performs QA alignment and requirement confirmation.

### Architect Agent (session name: `Architect Agent`)

- Produces high-level architecture guidance and round plans.
- Converts approved round scope into executable `PLAN.md`.
- Handoff behavior is governed by `Plan mode artifact discipline` (single rule source for post-approval Architect/Builder boundary).
- Reviews `FEEDBACK.md` and codebase changes, reconciles roadmap / debt / ADR updates when needed, then proposes the next round.
- Does not bypass PM approval for scope-changing work.
- Must not smuggle speculative scope, unapproved contract changes, or autonomous architecture rewrites into `PLAN.md`.
- Must treat `docs/architecture/ROADMAP.md`, `docs/architecture/tech_debt.md` (canonical debt sweep/index), `docs/architecture/tech_debt/resolved.md` (resolved/superseded detail archive), and `FEEDBACK.md` as the canonical planning inputs for round design.
- Should prefer approved cutovers that remove obsolete compatibility paths instead of preserving silent dual semantics.

### Builder Agent (session name: `Builder Agent`)

- Executes only the currently approved `PLAN.md`.
- Implements bounded changes in the codebase.
- Reports outcomes by overwriting `FEEDBACK.md`.
- Must not redefine architecture boundaries without explicit PM approval.
- If a change is not explicitly listed in PLAN.md:
  - DO NOT IMPLEMENT
  - report in FEEDBACK.md instead
- Builder must not modify:
  - schema
  - state transitions
  - API contracts
- unless explicitly listed in PLAN.md
- Must avoid compatibility-shim creep after a PM-approved cutover unless the current `PLAN.md` explicitly requires a migration window.
- May update roadmap/debt artifacts only when the current `PLAN.md` explicitly includes those updates in round scope; otherwise report suggested updates in `FEEDBACK.md`.

## Session Naming Convention

- Architecture/planning session name: `Architect Agent`.
- Implementation/execution session name: `Builder Agent`.

## Development Round Protocol

Each round follows this sequence:

1. Architect Agent performs round planning directly in root `PLAN.md` (default workflow; no Plan mode artifact required).
 - If there are meaningful scope/contract trade-offs, Architect must explicitly call `AskQuestion` to collect PM selection before freezing `PLAN.md`.
2. Architect Agent reviews `docs/architecture/ROADMAP.md` during planning.
  - Follow `Roadmap discipline` as the single normative rule source for posture/capability/upcoming reconciliation.
3. Architect Agent performs a full `docs/architecture/tech_debt.md` sweep in planning phase and proposes debt handling for this round (`close` / `partial` / `defer` with rationale).
  - Debt triage, ID allocation, status correction, and archive handling must follow `Debt registry discipline` (single rule source).
  - Architect updates the file-level `Last full registry sweep` date when a full sweep is performed and updates per-entry `Last reviewed` for explicitly triaged items.
4. PM reviews and confirms scope, risks, acceptance criteria, debt handling decisions, and proposed roadmap-aligned action selection.
5. If planning was done through a Plan mode artifact, Architect Agent completes `PLAN.md` handoff for the approved round.
  - approval/build transition does **not** start Builder implementation directly in this repository workflow.
  - Behavior and boundary constraints: see `Plan mode artifact discipline` and `Single Source of Truth Files`.
6. Builder Agent executes the approved round plan in the corresponding implementation session.
  - Execution boundaries and scope constraints: see `Governance and Guardrails`.
7. Builder Agent completes round execution reporting.
  - `FEEDBACK.md` ownership/write mode/content requirements: see `Single Source of Truth Files` and `Plan and Feedback Standards`.
8. Architect Agent reads `FEEDBACK.md` (and validates critical diffs when needed), then explicitly reconciles `docs/architecture/ROADMAP.md` to reflect execution reality before planning the next round.
9. Architect Agent updates `docs/architecture/tech_debt.md`, `docs/architecture/tech_debt/resolved.md`, and `docs/architecture/ADR.md` when execution materially changes debt posture or produces a durable architecture decision not already recorded.
10. Architect Agent performs lightweight round closeout by explaining the execution reality, evaluating the effectiveness of current round execution, explicitly checking for remaining risks/vulnerabilities after reading `FEEDBACK.md`, and recommending the next-round routing decision to PM.
11. PM confirms the routing decision:
  - continue within the same major round,
  - run a corrective minor round within the same major round,
  - or advance to the next major round.
12. Architect Agent executes a round-level git snapshot commit for every completed round (major or minor), then proposes the next round using the PM-confirmed routing decision.
13. Architect Agent proposes the next round by updating root `PLAN.md` directly using the updated roadmap / debt / ADR context and the confirmed routing decision.

### Artifact routing Protocol

- `docs/architecture/ROADMAP.md`: project direction, current operating posture, capability progress, and near-term upcoming actions.
- `docs/architecture/tech_debt.md` + `docs/architecture/tech_debt/resolved.md`: debt registry artifacts (rules/source-of-truth defined in `Debt registry discipline`).
- `docs/architecture/ADR.md`: durable architecture decisions and cutover choices that should remain true beyond a single round.
- `PLAN.md`: frozen round scope, constraints, ordered execution steps, and acceptance criteria.
- `FEEDBACK.md`: execution facts, test results, deviations, blockers, and suggested next-round signals.
- Do not leave durable decisions or deferred-risk ownership only inside `PLAN.md` / `FEEDBACK.md`; promote them into `ADR.md`, `ROADMAP.md`, or `tech_debt.md` as appropriate.

### Blocked escalation protocol

- If Builder encounters plan ambiguity, a prerequisite gap, a material architecture conflict, or any required change that is outside the currently approved `PLAN.md`, Builder must stop further out-of-scope implementation.
- Builder must overwrite `FEEDBACK.md` with `status: blocked` when handing control back due to a blocked escalation, including:
  - the blocked execution step,
  - the concrete blocker,
  - what was completed before the stop,
  - the smallest known unblock path.
- Architect then decides whether the blocker can be resolved by clarification within the already approved scope or requires a revised `PLAN.md`.
- If Architect changes scope, acceptance criteria, debt handling, contracts, or cutover decisions, PM must re-approve before Builder resumes.
- If the resolution is only a clarification that stays within the already approved scope, Architect may refresh `PLAN.md` and return execution to Builder without a new PM approval.
- A blocked escalation is a control-flow pause, not permission for Builder to improvise around governance boundaries.

## Single Source of Truth Files

### `PLAN.md` (Execution plan source)

- Location: repository root.
- Ownership: Architect Agent (after PM approval).
- Write mode: overwrite per round (keep only current approved round).
- Purpose: concrete implementation instructions for Builder Agent.
- Content checklist and required sections: see `Plan and Feedback Standards`.

### `FEEDBACK.md` (Execution report source)

- Location: repository root.
- Ownership: Builder Agent.
- Write mode: overwrite per round (keep only current round report).
- Purpose: implementation status, file changes, tests, risks, deviations, and suggested next-round signals.
- Builder owns the execution report content.
- PM-confirmed routing should directly govern per-round snapshot execution and next-round numbering (see `Round-level git snapshot discipline`).
- Architect may append closeout notes to `FEEDBACK.md` only when PM explicitly wants round-local archival context, but this is optional rather than protocol-required.
- Content checklist and required sections: see `Plan and Feedback Standards`.

## Plan and Feedback Standards

Ownership and write mode for `PLAN.md` / `FEEDBACK.md` are defined in `Single Source of Truth Files`; this section defines required content structure only.

### `PLAN.md` must include

- Round ID and one-sentence goal.
- Round type (`major` or `minor`) and parent major round when applicable.
- Scope in / scope out.
- Scope must be deterministic at the `what` level: do not leave Builder-facing feature/scope options inside `PLAN.md`.
- If multiple scope options exist, Architect must explicitly ask PM to choose (and may provide recommendations) **before** freezing `PLAN.md`.
- Only PM-selected options may be written into `PLAN.md`; unselected alternatives should be excluded rather than left as optional Builder choices.
- Explicit constraints and architecture boundaries.
- Planning-phase roadmap alignment summary from `docs/architecture/ROADMAP.md`:
  - capability areas this round is intended to advance,
  - upcoming action(s) selected for this round (or explicit rationale when deviating).
- Planning-phase debt triage summary from `docs/architecture/tech_debt.md`:
  - debt entries selected for this round (**`Debt ID` + title**),
  - debt entries explicitly deferred this round (with rationale, **ID + title**),
  - any debt status corrections made during sweep (e.g. `RESOLVED` / `SUPERSEDED` / priority change).
  - for each debt marked `close` / `partial`, include concrete implementation handling in the plan (specific modules/files/behaviors/tests), not generic wording such as "stability hardening partial" without execution detail.
- Ordered execution steps.
- Acceptance criteria (testable checklist).
- Required Builder feedback format reminder.

### `FEEDBACK.md` must include

- Round ID and execution status (`done` / `partial` / `blocked`).
- Step-by-step completion mapping against `PLAN.md`.
- Full file change summary (`A` / `M` / `D`).
- Test commands and results.
- Risks, deviations, and blockers.
- Roadmap updates made this round (capability status changes, posture changes, or upcoming queue changes) if any.
- Debt entries touched, resolved, deferred, or newly identified during execution/review (**`Debt ID` + title** when referring to registry items).
- Suggested next-round focus (short).
- If status is `blocked`, the exact blocked step, required unblock decision, and whether PM re-approval is needed.

## Disciplines

### Plan mode artifact discipline

- Plan mode artifacts are Architect planning / PM review artifacts, not execution instruction sources.
- This discipline is **optional fallback** only when PM explicitly requests a separate Plan mode artifact; it is not the default planning path for this repository.
- In this repository, a plan artifact's purpose is to help Architect and PM converge on the next round before `PLAN.md` is overwritten.
- **Every development-round plan artifact must include an explicit handoff note stating:** "After PM approval, Architect only overwrites root `PLAN.md` and then stops; Builder implementation must run in a separate `Builder Agent` session."
- Plan artifacts may be written in Chinese by default for PM readability; use English only when PM explicitly requests it.
- When a plan artifact is created for a development round, its todo list should contain only the Architect handoff action:
  - overwrite `PLAN.md` with the approved round instruction
- Do **not** use plan-artifact todos as a direct implementation task list for Builder work.
- **PM approval of a plan artifact is not permission for Architect to execute that round.** Treat "approve plan" / "implement the plan" in a planning session as: freeze scope into `PLAN.md` only; open a **separate Builder Agent session** for code changes.
- In the collaboration workflow for this repo, approving a plan artifact and entering build/agent execution means:
  1. Architect first overwrites `PLAN.md` (and may apply only the small governance doc edits explicitly listed in the approved plan, such as a one-line `AGENTS.md` clarification)
  2. Architect **stops**; Builder-oriented implementation work begins only in a **new** session named **Builder Agent**, reading the frozen `PLAN.md`
- This is a repository workflow convention layered on top of Cursor Plan mode; `PLAN.md` remains the only execution instruction source for Builder Agent.

### Direct `PLAN.md` planning discipline (default)

- Default planning path: Architect writes/refines round scope directly in root `PLAN.md`, then waits for PM approval.
- Architect must not start Builder implementation after PM approval; Architect only hands off by freezing `PLAN.md` and stopping.
- When planning contains alternative scope/contract choices, Architect must use `AskQuestion` for PM choice capture before freezing `PLAN.md`.
- `PLAN.md` must contain only PM-selected options; do not leave Builder-facing optional scope branches.
- If PM explicitly asks for a separate Plan mode artifact, follow `Plan mode artifact discipline`; otherwise do not create one.

### Roadmap discipline

- `docs/architecture/ROADMAP.md` is the canonical project roadmap.
- `Project Vision Layer` is static background and should change only when business direction or architectural thesis changes.
- `Current Operating Posture` is reviewed every planning round, but edited only when runtime posture or primary delivery focus materially changes.
- `Current Operating Posture` write format is fixed to **two sentences**:
  - sentence 1 = **Macro-as-is** (stable current operating baseline; no future queue/debt detail)
  - sentence 2 = **Round-as-is** (latest completed round's realized posture change only)
- `Capability Roadmap Layer` tracks major capability areas and status, not round-by-round implementation detail.
- `Upcoming (Action Queue)` is the near-term queue derived from capability gaps plus debt priorities; it is not a second independent roadmap.
- `Upcoming` entries are **not** numbered lists; the **round ID** (e.g. `R-014`) is the stable identifier. Add/remove/reorder rows without renumbering; priority is top-to-bottom until PM reprioritizes.
- Keep round-scoped actions in the same `Upcoming (Action Queue)` list; do **not** create a separate `Round-scoped` subsection in `ROADMAP.md`.
- If future-round execution detail is temporarily parked in `ROADMAP.md`, Architect must later extract that detail into the active round `PLAN.md` when the round is opened.
- `Upcoming` items must advance named capability areas; `Debt ID` references are optional and used when the item is debt-driven, not required for capability-only queue entries.
- During each planning-phase roadmap reconciliation, Architect must remove completed actions/rounds from `Upcoming`; `Upcoming` tracks only current and not-yet-completed work.
- Planned round scope should normally be selected from `Upcoming`, unless PM explicitly reprioritizes or a corrective round is required.
- After each execution round, Architect must reconcile `ROADMAP.md` against `FEEDBACK.md` before proposing the next round, even when the result is "no roadmap change required".

### Debt registry discipline

- `docs/architecture/tech_debt.md` is the canonical debt sweep/index file (active debt full entries + resolved/superseded summary stubs).
- `docs/architecture/tech_debt/resolved.md` is the canonical resolved/superseded detail archive (full historical rationale/details).
- Debt entries use stable `Debt ID` references in the form `TD-<SCOPE>-<NNN>`; IDs are never renumbered or reused.
- No index file/script mode: uniqueness is enforced by an explicit manual assignment protocol:
  - before adding a new debt ID, Architect must run a full ID scan in `docs/architecture/tech_debt.md` for the target scope prefix (this file is the allocation source of truth).
  - Architect must assign the next numeric suffix as `max(existing_suffixes_in_scope) + 1`; do not fill historical gaps.
  - Architect must verify the chosen ID appears zero times in `docs/architecture/tech_debt.md` before writing the new entry.
  - if any duplicate ID is found, stop and resolve the conflict first; do not add or renumber entries until conflict is cleared.
  - when archiving resolved/superseded entries, preserve the original `Debt ID` and heading text verbatim.
- Agent behavior when creating a new debt entry (mandatory):
  - perform the `tech_debt.md` sweep first,
  - propose the exact new `Debt ID + title`,
  - only then append the entry using the standard registry template.
- `PLAN.md`, `docs/architecture/ROADMAP.md`, and `FEEDBACK.md` should reference concrete debt items as **`Debt ID` + registry title** (title must match the active/archived registry heading line), not `Debt ID` alone or title alone.
- Each planning round's debt sweep should distinguish:
  - file-level full registry sweep (`Last full registry sweep`)
  - per-entry explicit review (`Last reviewed`)
- Removing a debt from active concern requires an explicit status change to `RESOLVED` or `SUPERSEDED`, a summary stub retained in `docs/architecture/tech_debt.md`, and full detail archived in `docs/architecture/tech_debt/resolved.md`; do not silently let stale OPEN entries drift.

### Lightweight round closeout and routing

- Round closeout is a routing checkpoint, not a heavyweight release gate.
- After reviewing `FEEDBACK.md`, Architect recommends one of these routing outcomes to PM:
  - `continue-major`: the current major-round objective is still in progress; the next round stays within the same major round.
  - `corrective-minor`: the current baseline is usable, but the next round should first be a corrective / hardening minor round inside the same major round.
  - `advance-major`: the current major-round objective is sufficiently achieved, and the next round should open the next major round.
- PM confirms the routing outcome; this confirmation means "valid baseline for next iteration", not "all concerns are permanently closed".
- PM-confirmed routing directly governs:
  - next-round numbering,
  - the next planning direction; it does not waive the per-round snapshot commit requirement.
- Residual issues that do not block forward progress should flow into the next round scope and/or `docs/architecture/tech_debt.md`, not force a heavyweight reopen process.
- If the current state is not a valid baseline for continued iteration, use the `Blocked escalation protocol` or route to `corrective-minor`; do not silently treat it as major-round completion.
- Major/minor naming must follow the confirmed routing decision:
  - `continue-major` -> next round remains within the same major round.
  - `corrective-minor` -> next round uses the next minor suffix under the same major round.
  - `advance-major` -> next round starts the next major round number.

### Round naming convention

- **Major rounds** (`R003`, `R004`, ...): add scope/capabilities.
- **Minor rounds** (`R004.1`, `R004.2`, ...): stabilization/hardening within a parent major round; no new capability scope.

### Round-level git snapshot discipline

- Governance requires a formal git snapshot commit for every completed round (major and minor).
- Intermediate engineering commits are optional local/team checkpoints; they are allowed, but they do not replace the formal round snapshot commit.
- Create the round snapshot commit after Builder overwrites `FEEDBACK.md` and Architect reconciles roadmap/debt artifacts for that round.
- The round snapshot commit should include the relevant code changes plus synchronized governance artifacts (`PLAN.md`, `FEEDBACK.md`, `ROADMAP.md`, `tech_debt.md`, `tech_debt/resolved.md`, `ADR.md`) when they were part of the round outcome.
- If the repo is not coherent enough to snapshot, Architect must obtain explicit PM approval to defer and record the defer reason in the round closeout context.
- Commit messages should follow conventional commit style:
  - title format: `<type>(<scope>): <summary>`
  - choose `feat`, `fix`, `refactor`, `docs`, `test`, or another conventional type that best matches the dominant outcome of the completed round
  - keep the title concise and outcome-oriented
  - if a commit body is present, leave exactly one blank line after the title before starting the body
  - write the commit body as flat bullet points rather than prose paragraphs
  - use the commit body for round context, such as the round ID, capability outcome, roadmap/debt updates, and notable cutovers
- Example title: `feat(agents): close R-005 governance refinements`
- Example body topics:
  - `Round: R-005`
  - - capability or architecture milestone reached
  - - debt / roadmap / ADR updates synchronized in the snapshot

## Governance and Guardrails

- `PLAN.md` is the only execution instruction source for Builder Agent.
- Builder may choose `how` (implementation technique) only within approved scope; Builder must not choose `what` (scope/features) from optional branches left in `PLAN.md`.
- Builder Agent should avoid opportunistic scope expansion.
- Builder Agent does **not** perform independent debt planning during execution.
- Builder Agent does **not** perform independent roadmap planning during execution.
- Debt handling scope is Architect-planned, PM-approved, and frozen in `PLAN.md` before Builder execution starts.
- Schema or state-machine contract changes require explicit PM approval in the current round scope.
- Architect Agent must not freeze contract-changing round scope into `PLAN.md` without that explicit PM approval.
- If implementation reality conflicts with `PLAN.md`, Builder reports in `FEEDBACK.md` and pauses further out-of-scope changes.
- Blocked execution follows the explicit `Blocked escalation protocol`; Builder must not self-authorize workaround scope.
- Approved cutovers are real removals: Builder and Architect should not preserve or reintroduce legacy compatibility readers/writers unless the current `PLAN.md` explicitly authorizes that compatibility window.