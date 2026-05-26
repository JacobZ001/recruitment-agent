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

- hard filter
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
- remain backward compatible
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

# Engineering Workflow

Preferred workflow:

1. Define spec
2. Define schema
3. Define interface
4. Implement deterministic logic
5. Add tests
6. Add LLM cognition
7. Validate behavior

Do NOT start with autonomous agent behavior.

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
- Reviews `FEEDBACK.md` and codebase changes, reconciles roadmap / debt / ADR updates when needed, then proposes the next round.
- Does not bypass PM approval for scope-changing work.
- Must not smuggle speculative scope, unapproved contract changes, or autonomous architecture rewrites into `PLAN.md`.
- Must treat `docs/architecture/ROADMAP.md`, `docs/architecture/tech_debt.md`, and `FEEDBACK.md` as the canonical planning inputs for round design.
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

## Single Source of Truth Files

### `PLAN.md` (Execution plan source)

- Location: repository root.
- Ownership: Architect Agent (after PM approval).
- Write mode: overwrite per round (keep only current approved round).
- Purpose: concrete implementation instructions for Builder Agent.

### `FEEDBACK.md` (Execution report source)

- Location: repository root.
- Ownership: Builder Agent.
- Write mode: overwrite per round (keep only current round report).
- Purpose: implementation status, file changes, tests, risks, deviations, and round-closeout routing metadata.
- Builder owns the execution report content; Architect may append or refresh the closeout-routing fields during post-execution review.

### Artifact routing

- `docs/architecture/ROADMAP.md`: project direction, current operating posture, capability progress, and near-term upcoming actions.
- `docs/architecture/tech_debt.md`: deferred work, architecture risk, scaling limits, and explicit debt decisions.
- `docs/architecture/ADR.md`: durable architecture decisions and cutover choices that should remain true beyond a single round.
- `PLAN.md`: frozen round scope, constraints, ordered execution steps, and acceptance criteria.
- `FEEDBACK.md`: execution facts, test results, deviations, blockers, and suggested next-round signals.
- Do not leave durable decisions or deferred-risk ownership only inside `PLAN.md` / `FEEDBACK.md`; promote them into `ADR.md`, `ROADMAP.md`, or `tech_debt.md` as appropriate.

## Development Round Protocol

Each round follows this sequence:

1. Architect Agent proposes a light high-level structured plan for PM review.
2. Architect Agent performs a full `docs/architecture/tech_debt.md` registry sweep in planning phase and proposes debt handling for this round (`close` / `partial` / `defer` with rationale).
   - Triage uses the canonical debt registry format in `docs/architecture/tech_debt.md`, including stable `Debt ID` references (`TD-<SCOPE>-<NNN>`).
   - Architect updates the file-level `Last full registry sweep` date when a full sweep is performed.
   - Architect updates per-entry `Last reviewed` when an entry is explicitly triaged in planning (review date, not just edit date).
   - If sweep finds status drift, Architect may correct debt status/priority (`OPEN` / `IN_PROGRESS` / `RESOLVED` / `SUPERSEDED`) before freezing the round plan.
3. Architect Agent reviews `docs/architecture/ROADMAP.md` during planning.
   - `Current Operating Posture` is reviewed every round, but updated only when repo posture materially changes; keep it to a maximum of three sentences.
   - `Capability Roadmap Layer` is updated when capability reality or stage status changes.
   - `Upcoming (Action Queue)` is refreshed from capability gaps plus debt priorities.
   - Architect proposes the best-fit upcoming action(s) for the round rather than mechanically loading the next listed item.
4. PM reviews and confirms scope, risks, acceptance criteria, debt handling decisions, and proposed roadmap-aligned action selection.
5. Architect Agent overwrites `PLAN.md` with executable round instructions.
6. Builder Agent executes `PLAN.md` in a separate implementation session.
7. Builder Agent overwrites `FEEDBACK.md` with round execution feedback.
8. Architect Agent reads `FEEDBACK.md` (and validates critical diffs when needed), then explicitly reconciles `docs/architecture/ROADMAP.md` to reflect execution reality before planning the next round.
9. Architect Agent updates `docs/architecture/tech_debt.md` and `docs/architecture/ADR.md` when execution materially changes debt posture or produces a durable architecture decision not already recorded.
10. Architect Agent performs lightweight round closeout by recommending the next-round routing decision to PM.
11. PM confirms the routing decision:
   - continue within the same major round,
   - run a corrective minor round within the same major round,
   - or advance to the next major round.
12. Architect Agent proposes next round using the updated roadmap / debt / ADR context and the confirmed routing decision.

### Round naming convention

- **Major rounds** (`R003`, `R004`, ...): add scope/capabilities.
- **Minor rounds** (`R004.1`, `R004.2`, ...): stabilization/hardening within a parent major round; no new capability scope.

### Lightweight round closeout and routing

- Round closeout is a routing checkpoint, not a heavyweight release gate.
- After reviewing `FEEDBACK.md`, Architect recommends one of these routing outcomes to PM:
  - `continue-major`: the current major-round objective is still in progress; the next round stays within the same major round.
  - `corrective-minor`: the current baseline is usable, but the next round should first be a corrective / hardening minor round inside the same major round.
  - `advance-major`: the current major-round objective is sufficiently achieved, and the next round should open the next major round.
- PM confirms the routing outcome; this confirmation means "valid baseline for next iteration", not "all concerns are permanently closed".
- Residual issues that do not block forward progress should flow into the next round scope and/or `docs/architecture/tech_debt.md`, not force a heavyweight reopen process.
- If the current state is not a valid baseline for continued iteration, use the `Blocked escalation protocol` or route to `corrective-minor`; do not silently treat it as major-round completion.
- Major/minor naming must follow the confirmed routing decision:
  - `continue-major` -> next round remains within the same major round.
  - `corrective-minor` -> next round uses the next minor suffix under the same major round.
  - `advance-major` -> next round starts the next major round number.

### Debt registry discipline

- `docs/architecture/tech_debt.md` is the canonical debt registry.
- Debt entries use stable `Debt ID` references in the form `TD-<SCOPE>-<NNN>`; IDs are never renumbered or reused.
- `PLAN.md` and `FEEDBACK.md` should reference debt items by `Debt ID`, not only by title text.
- Each planning round's debt sweep should distinguish:
  - file-level full registry sweep (`Last full registry sweep`)
  - per-entry explicit review (`Last reviewed`)
- Removing a debt from active concern requires an explicit status change to `RESOLVED` or `SUPERSEDED`; do not silently let stale OPEN entries drift.

### Roadmap discipline

- `docs/architecture/ROADMAP.md` is the canonical project roadmap.
- `Project Vision Layer` is static background and should change only when business direction or architectural thesis changes.
- `Current Operating Posture` is reviewed every planning round, but edited only when runtime posture or primary delivery focus materially changes; keep it under three sentences.
- `Capability Roadmap Layer` tracks major capability areas and status, not round-by-round implementation detail.
- `Upcoming (Action Queue)` is the near-term queue derived from capability gaps plus debt priorities; it is not a second independent roadmap.
- Planned round scope should normally be selected from `Upcoming`, unless PM explicitly reprioritizes or a corrective round is required.
- After each execution round, Architect must reconcile `ROADMAP.md` against `FEEDBACK.md` before proposing the next round, even when the result is "no roadmap change required".

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

### Major-round git snapshot discipline

- Governance requires a formal git snapshot only when a major round is being closed and the next round is advancing to the next major round.
- Intermediate engineering commits are optional local/team checkpoints; they are allowed, but they do not replace the formal major-round governance snapshot.
- Create a round-governance commit when all of the following are true:
  - the current round is the closing round of a major round (for example, `R-005.3` closes `R-005`),
  - Architect recommends `advance-major`,
  - PM confirms that the next round should open the next major round,
  - and the repo state is coherent enough to snapshot code plus governance artifacts together.
- Minor rounds inside an open major round do not require their own governance commit unless PM explicitly asks for an intermediate snapshot.
- The major-round snapshot commit should include the relevant code changes plus synchronized governance artifacts (`PLAN.md`, `FEEDBACK.md`, `ROADMAP.md`, `tech_debt.md`, `ADR.md`) when they were part of the round outcome.
- Commit messages should follow conventional commit style:
  - title format: `<type>(<scope>): <summary>`
  - choose `feat`, `fix`, `refactor`, `docs`, `test`, or another conventional type that best matches the dominant outcome of the completed major round
  - keep the title concise and outcome-oriented
  - if a commit body is present, leave exactly one blank line after the title before starting the body
  - write the commit body as flat bullet points rather than prose paragraphs
  - use the commit body for the major round context, such as the major round ID, capability outcome, roadmap/debt updates, and notable cutovers
- Example title: `feat(agents): close R-005 governance refinements`
- Example body topics:
  - `Major round: R-005`
  - capability or architecture milestone reached
  - debt / roadmap / ADR updates synchronized in the snapshot

## Plan and Feedback Standards

### `PLAN.md` must include

- Round ID and one-sentence goal.
- Round type (`major` or `minor`) and parent major round when applicable.
- Round routing context from the prior closeout:
  - `proposed routing outcome`
  - `PM confirmed routing`
  - `major-round snapshot needed: yes/no`
- Scope in / scope out.
- Explicit constraints and architecture boundaries.
- Planning-phase roadmap alignment summary from `docs/architecture/ROADMAP.md`:
  - capability areas this round is intended to advance,
  - upcoming action(s) selected for this round (or explicit rationale when deviating).
- Planning-phase debt triage summary from `docs/architecture/tech_debt.md`:
  - debt IDs selected for this round,
  - debt IDs explicitly deferred this round (with rationale),
  - any debt status corrections made during sweep (e.g. `RESOLVED` / `SUPERSEDED` / priority change).
- Ordered execution steps.
- Acceptance criteria (testable checklist).
- Required Builder feedback format reminder.

### `FEEDBACK.md` must include

- Round ID and execution status (`done` / `partial` / `blocked`).
- Step-by-step completion mapping against `PLAN.md`.
- Full file change summary (`A` / `M` / `D`).
- Test commands and results.
- Risks, deviations, and blockers.
- Lightweight closeout routing fields:
  - `proposed routing outcome`
  - `PM confirmed routing`
  - `major-round snapshot needed: yes/no`
- Roadmap updates made this round (capability status changes, posture changes, or upcoming queue changes) if any.
- Debt IDs touched, resolved, deferred, or newly identified during execution/review.
- Suggested next-round focus (short).
- If status is `blocked`, the exact blocked step, required unblock decision, and whether PM re-approval is needed.

## Governance and Guardrails

- `PLAN.md` is the only execution instruction source for Builder Agent.
- Builder Agent should avoid opportunistic scope expansion.
- Builder Agent does **not** perform independent debt planning during execution.
- Builder Agent does **not** perform independent roadmap planning during execution.
- Debt handling scope is Architect-planned, PM-approved, and frozen in `PLAN.md` before Builder execution starts.
- Schema or state-machine contract changes require explicit PM approval in the current round scope.
- Architect Agent must not freeze contract-changing round scope into `PLAN.md` without that explicit PM approval.
- If implementation reality conflicts with `PLAN.md`, Builder reports in `FEEDBACK.md` and pauses further out-of-scope changes.
- Blocked execution follows the explicit `Blocked escalation protocol`; Builder must not self-authorize workaround scope.
- Approved cutovers are real removals: Builder and Architect should not preserve or reintroduce legacy compatibility readers/writers unless the current `PLAN.md` explicitly authorizes that compatibility window.

