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

Avoid:

- large uncontrolled refactors
- autonomous architecture rewrites
- implicit assumptions

