# BlueOcean Recruitment Agent — Development Roadmap

Purpose: preserve long-term development continuity, keep future AI agents and human developers aligned on **what the system can do today**, and record **capability milestones** (not open-ended “phase maturation”). Priority is shifting from **capability completeness on the reference runtime** to **single-tenant usability**—state that survives use, not just demos.

## Project vision

Build a deterministic, AI-native **human evaluation infrastructure** for recruitment workflows:

- **Programs control workflow** (deterministic orchestration, verifiable transitions).
- **LLMs provide cognition** (semantic understanding, extraction, generation) under strict interfaces—when that capability is switched on; the **reference vertical slice** today uses **deterministic fakes** instead of live models.
- **Humans govern outcomes** (override, approval, calibration) with audit logs.

## System posture (architecture)

- **Deterministic-first control plane** with explicit schemas, transition validation, and event ingress.
- **Single-process, in-memory reference runtime** (bus + store + orchestrator + planner + bounded fake skills): this describes the **current reference implementation and proving environment**—how the repo runs today to validate contracts and orchestration semantics. It is **not** a statement of **intended final production topology** (which may use different persistence, messaging, ingress, process boundaries, and hosting).
- **Replay and inspection** are harness-backed and read-only projections; they prove control-plane semantics **before** a persisted event product exists.
- **Governance** enters as **typed, event-carried ingress** validated by the same transition engine as system events—not as ad-hoc state edits.
- **Governance of change**: ADRs and `tech_debt.md` record deliberate deferrals (persistence, brokers, typed payload graduation, semantic replay profiles).

**Proving environment vs platform vision:** the **current repo** is intentionally a **deterministic proving runtime**: fast feedback, tests, and demos without standing up production infrastructure. **Long-term production** for a talent intelligence posture may replace or split **where** state lives, **how** events are transported, and **how** ingress scales—while **preserving** the same **orchestration semantics** (validated transitions, immutable-event discipline, skill contracts, governance payloads) as those layers mature.

### Evolution framing (usability vs reference)

Parallel to the numbered capability stages below—this is **delivery priority**, not extra scope:

| Stage | Meaning |
| ----- | -------- |
| **Stage A — Deterministic reference runtime** | Contracts, orchestrator, transition engine, harness replay, in-memory vertical slice—**completed** as a proving baseline. |
| **Stage B — Single-tenant usable system** | **Current focus:** persistent workflow state, multiple candidates in one process/deployment, recruiter-visible progression **across sessions**. Not multi-tenant product infra yet. |
| **Stage C — Multi-tenant + production infra** | Isolation, brokers/auth/SLO-grade ops—when Stage B behaviors are proven on durable state. |
| **Stage D — Controlled cognition (LLM layer)** | Real `skills/llm/` / hybrid semantics behind contracts—**after** artifact and persistence paths exist; orchestration unchanged. |

**Stage B goal:** A recruiter can **use the system across sessions**, **manage multiple candidates**, and **observe consistent workflow state**—same deterministic rules, **surviving restart**.

---

## Capability stages (milestones, not maturation)

Stages describe **acquired or partial system capabilities**—things a recruiter, operator, or integrator can rely on when they are marked *Acquired* or *Partial*. They are **cumulative**: later stages assume earlier ones.

**Stage 4 vs Stage 5 (boundary):** Stage **4** is **visibility and operability of the workflow itself**—driving progression, seeing phase and scores, reading timelines and evidence summaries in a demo or harness. Stage **5** is the **post-evaluation human governance lifecycle**—explicit human decisions (approve, reject, bounded override), escalation-style policy hooks, calibration narratives, and **audit-grade** treatment of those actions **after** the slice has produced evaluatable artifacts (not “running the pipeline” per se).

| Stage | What it means | Status |
| ----- | ---------------- | ------ |
| **1. Canonical contracts** | Versioned schemas (state, events, candidate), skill/event interfaces, pipeline registry vocabulary. | **Acquired** (payloads still largely `Dict[str, Any]`; graduation is debt-tracked). |
| **2. Deterministic runtime** | Synchronous orchestrator loop, in-memory bus and store, registered fake skills, emission ordering discipline. | **Acquired** (reference runtime only). |
| **3. Replayable orchestration** | Structural replay harnesses, negative paths, replay flags through engine/orchestrator; byte-stable artifacts where tests require them. | **Partial** — harness replay **yes**; append-only **store-backed replay runner** **no** (see `tech_debt.md`). |
| **4. Recruiter-operable vertical slice** | **Recruiter- / operator-visible workflow execution**: end-to-end progression through the slice (e.g. to `deep_scored`), ingress that **drives** the bus (`POST /events`, `POST /demo/run`), read APIs for **phase and progression** (`GET /state/{id}`, `GET /timeline/{id}`, `GET /demo/candidate`), thin demo surface (`GET /demo`) so filter/scoring output and timeline text are **legible** in one sitting. **Stage B** extends this with **durable state** and **multiple candidates**; **then** bounded **real CV / text** ingress (**deterministic** projection, **artifact evidence refs**—**not** LLM cognition). | **Partial** — reference demo today; **Stage B** makes it **session-survivable** and **multi-candidate**. |
| **5. Human governance lifecycle** | **Post-evaluation human governance**: bounded `recruiter_*` (and related) ingress for **approve / reject / override** with typed payloads; **audit narratives** on transition records (who, why, evidence refs); inspection helpers that surface **governance lines** alongside decisions—not the same problem as “can I run and see the pipeline?” (Stage **4**). Durable long-term audit archives and full operator products remain **platform / hardening** scope. | **Partial** — **bounded** events and audit lines on the reference store; not a full operator product or production archive. |
| **6. Controlled cognition** | **After** Stage 4 artifact ingress exists: real **`skills/llm/`** or **hybrid** skills for **semantic CV extraction / analysis** behind the same contracts (orchestration unchanged)—**LLM understands** the artifact; programs still validate transitions. | **Not started** (directory structure / principles only until first merged skill). |
| **7. Talent intelligence platform** | Long-lived talent pool, cross-requisition matching, durable timelines, multi-aggregate orchestration, production-grade operations. | **Vision / not started** as an integrated platform (see Executive Overview for business direction). |

**Honest snapshot:** stages **1–3** are strong in code and tests. **4–5** are proven **in-memory** on a **single aggregate**; **Stage B** work makes that recruiter journey **durable** and **multi-candidate** without changing scope into cognition or multi-tenant production. **6–7** remain **principles and architecture** until Stage B exits are met.

---

## Repository topology (concise)

- **`schemas/`**, **`interfaces/`**, **`state_machine/`** — contracts and deterministic transition rules.
- **`orchestrator/`** — planning policy (e.g. `vertical_slice_planner.py`); **no** LLM calls.
- **`runtime/`** — reference wiring (`bootstrap_vertical_slice.py`), in-memory bus/store, **inspection** (`runtime/inspection/`), **demo fixture** (`demo_candidate_fixture.py`).
- **`modules/recruitment/`** — application boundary (DDD-lite): **`policies.py`** (ingress allowlist, governance detection, single-tenant checks), **`use_cases.py`** (publish ingress, demo sequence), **`projection.py`** (recruiter read models). Does **not** own runtime lifecycle or HTTP.
- **`skills/deterministic/`** — vertical-slice fakes; **`skills/llm/`**, **`skills/hybrid/`** — reserved for cognition when stage **6** begins.
- **`integrations/api/`** — thin FastAPI ingress, HTTP models, runtime holder (`session.py`), demo HTML; delegates business actions to **`modules/recruitment`**.
- **`tests/`** — contract, replay, governance, API, inspection, module boundary tests.

---

## Implementation vs Executive Overview (reconciliation)

Aligned with the original vision:

- Human-in-the-loop and explicit governance hooks.
- AI as **bounded evaluator** (when enabled)—orchestration and ranking stay in programs.
- Event-driven lifecycle and audit-oriented transition history.
- Modular, reusable evaluation posture.

**Expanded in code beyond the short Executive Overview:**

- **Questionnaire pipeline**: the canonical `PipelinePhase` model includes explicit **`questionnaire_pending`**, **`questionnaire_sent`**, and **`questionnaire_completed`** (not only “questionnaire sent” as a single bucket). The reference slice exercises a **subset** of those transitions plus an orchestrator **emission** (`questionnaire_requested`) where the scripted sequence requires it.
- **Governance semantics**: recruiter actions are **separate ingress event types** with **validated payloads** (`schemas/governance_schema.py`); outcomes appear on **transition records** and in **inspection** text—tighter than “override exists” alone.
- **Replay / inspection**: **deterministic harness replay** and **read-only** timelines, decision summaries, and operator navigation (`runtime/inspection/`)—engineering capabilities the overview did not spell out.

**Still missing relative to the overview (by design in the reference slice):**

- JD generation, Telegram distribution, real CV parsing, adaptive questionnaire content, ranking/shortlisting **products**, talent pool persistence, continuous learning pipelines.
- Those remain **business direction**; they land as **later capability stages** and **platform evolution**, not as claims of the current repo.

**Superseded wording in planning sense:**

- Treating “confidence” or “workflow confidence” as a **phase name**—replaced here by **concrete capabilities** (replay harness depth, semantic assertion profiles, durable replay)—with details in `tech_debt.md` where needed.

---

## Immediate next capabilities (engineering)

Ordered for **Stage B — single-tenant usability** (not expanded scope): durable state first, then multi-candidate, then bounded real input—still thin adapters; **no** workflow policy in HTTP handlers.

1. **Persistent orchestration state (SQLite first)** (**Stage B**): replace **in-memory-only** runtime state with **durably stored** snapshots (SQLite as first implementation); **goal: system survives restart** with the same orchestration semantics and contracts. Event/immutability discipline preserved.
2. **Multiple `candidate_id` aggregates** (**Stage B**, immediately after persistence): today the reference API/runtime is a **single aggregate**; next step is **several candidates** in one deployment with **isolation per candidate** (state + API routing)—still single-tenant, not Stage C multi-tenant product infra.
3. **Bounded real CV / text artifact ingress** (**Stage 4 / B**): **only once** the workflow is **persistent**—thin **paste/upload** of CV-like **text**; **deterministic** projection into existing structured skill inputs; timelines and **evidence refs** carry **artifact provenance**. **Not** LLM parsing, **not** complex ingestion pipelines—bounded input path only. Demo fixture remains **fallback** when no artifact is supplied. Ingress **idempotency / dedupe** stay secondary unless a milestone requires them.
4. **Deeper post-evaluation governance** where demos expose gaps—still event-sourced and transition-validated (Stages **4–5**); distinct from “more demo UI.”

**Later-stage enhancements** (explicitly deprioritized vs Stage B usability—keep in backlog, no removal):

- Structured inspection exports (typed JSON projections).
- Layered replay assertions (structural vs semantic vs governance) per `tech_debt.md`.
- First controlled cognition skill (**Stage 6** / **Stage D**): LLM/hybrid **semantic** extraction or analysis **after** bounded artifact + durable paths exist—not LLM-driven routing.
- Persistence abstraction **beyond** SQLite (pluggable backends, migration story)—after SQLite proves restart-safe usage.

---

## Operational hardening (parallel tracks)

These are **not** capability stages; they are **reliability and scale** work, scheduled when need is proven. Details live in **`docs/architecture/tech_debt.md`**.

Examples: durable event store and replay runner, outbox/idempotent consumers, multi-tenant isolation, observability/SLO signals, production ingress auth, deployment playbooks. **Stage B** uses SQLite-backed state first; **Stage C** is broader production infra—not the same milestone as single-tenant durability.

---

## Longer-term platform evolution

Cross-cutting evolution (after cognition and persistence foundations):

- Deterministic policy packs and org-wide vocabulary for rejections and scores (debt: canonical decision/scoring governance).
- Multi-aggregate orchestration (many candidates/requisitions) without losing audit clarity.
- Operator-facing investigation products built on **stored** envelopes + projections—not a substitute for today’s harness and text inspection.

Executive/business framing of long-horizon value remains in **`Recruitment Agent Design Doc.md`**.

---

## Engineering constraints

- **Deterministic-first** control and routing; **no** LLM-driven orchestration.
- **No** autonomous uncontrolled agents for workflow or ranking.
- **Schema validation** at boundaries (event / state / skill IO).
- **Event immutability** (corrections via new events).
- **Explainability** for scoring and gates (evidence references; structured reason codes where applicable).
- **Human override** paths remain available in contracts and events; **no claim of production readiness** for the reference API or demo page.

## AI-native development principles

- **Stable architecture > smart prompts**.
- **Programs control; LLMs understand** (when cognition is enabled).
- **Critical behaviors must be verifiable** (tests + harness).
- **Prefer explicit typing**; use `extensions` intentionally, then graduate fields with version discipline.
