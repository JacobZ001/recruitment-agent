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

# AI Coding Constraints

AI assistants must:

- preserve architecture boundaries
- avoid unnecessary abstraction
- avoid hidden coupling
- avoid modifying canonical schemas without approval

Prefer:

- small bounded tasks
- explicit typing
- deterministic behavior
- modular implementation
- approved cutovers that remove obsolete compatibility paths instead of preserving silent dual semantics

Avoid:

- large uncontrolled refactors
- autonomous architecture rewrites
- implicit assumptions
- compatibility-shim creep after a PM-approved cutover unless the current `PLAN.md` explicitly requires a migration window

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
- Reviews `FEEDBACK.md` and codebase changes, then proposes the next round.
- Does not bypass PM approval for scope-changing work.

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
- Purpose: implementation status, file changes, tests, risks, and deviations.

## Development Round Protocol

Each round follows this sequence:

1. Architect Agent proposes a light high-level structured plan for PM review.
2. PM reviews and confirms scope, risks, and acceptance criteria.
3. Architect Agent overwrites `PLAN.md` with executable round instructions.
4. Builder Agent executes `PLAN.md` in a separate implementation session.
5. Builder Agent overwrites `FEEDBACK.md` with round execution feedback.
6. Architect Agent reads `FEEDBACK.md` (and validates critical diffs when needed), then proposes next round.

## Plan and Feedback Standards

### `PLAN.md` must include

- Round ID and one-sentence goal.
- Scope in / scope out.
- Explicit constraints and architecture boundaries.
- Ordered execution steps.
- Acceptance criteria (testable checklist).
- Required Builder feedback format reminder.

### `FEEDBACK.md` must include

- Round ID and execution status (`done` / `partial` / `blocked`).
- Step-by-step completion mapping against `PLAN.md`.
- Full file change summary (`A` / `M` / `D`).
- Test commands and results.
- Risks, deviations, and blockers.
- Suggested next-round focus (short).

## Governance and Guardrails

- `PLAN.md` is the only execution instruction source for Builder Agent.
- Builder Agent should avoid opportunistic scope expansion.
- Schema or state-machine contract changes require explicit PM approval in the current round scope.
- If implementation reality conflicts with `PLAN.md`, Builder reports in `FEEDBACK.md` and pauses further out-of-scope changes.
- Approved cutovers are real removals: Builder and Architect should not preserve or reintroduce legacy compatibility readers/writers unless the current `PLAN.md` explicitly authorizes that compatibility window.

