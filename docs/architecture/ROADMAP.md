# BlueOcean Recruitment Agent — Development Roadmap

Purpose: preserve long-term development continuity, keep future AI agents and human developers aligned on **what the system can do today**, and record **capability milestones** (not open-ended “phase maturation”).

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

---

## Capability stages (milestones, not maturation)

Stages describe **acquired or partial system capabilities**—things a recruiter, operator, or integrator can rely on when they are marked *Acquired* or *Partial*. They are **cumulative**: later stages assume earlier ones.

**Stage 4 vs Stage 5 (boundary):** Stage **4** is **visibility and operability of the workflow itself**—driving progression, seeing phase and scores, reading timelines and evidence summaries in a demo or harness. Stage **5** is the **post-evaluation human governance lifecycle**—explicit human decisions (approve, reject, bounded override), escalation-style policy hooks, calibration narratives, and **audit-grade** treatment of those actions **after** the slice has produced evaluatable artifacts (not “running the pipeline” per se).

| Stage | What it means | Status |
| ----- | ---------------- | ------ |
| **1. Canonical contracts** | Versioned schemas (state, events, candidate), skill/event interfaces, pipeline registry vocabulary. | **Acquired** (payloads still largely `Dict[str, Any]`; graduation is debt-tracked). |
| **2. Deterministic runtime** | Synchronous orchestrator loop, in-memory bus and store, registered fake skills, emission ordering discipline. | **Acquired** (reference runtime only). |
| **3. Replayable orchestration** | Structural replay harnesses, negative paths, replay flags through engine/orchestrator; byte-stable artifacts where tests require them. | **Partial** — harness replay **yes**; append-only **store-backed replay runner** **no** (see `tech_debt.md`). |
| **4. Recruiter-operable vertical slice** | **Recruiter- / operator-visible workflow execution**: end-to-end progression through the slice (e.g. to `deep_scored`), ingress that **drives** the bus (`POST /events`, `POST /demo/run`), read APIs for **phase and progression** (`GET /state/{id}`, `GET /timeline/{id}`, `GET /demo/candidate`), thin demo surface (`GET /demo`) so filter/scoring output and timeline text are **legible** in one sitting. | **Partial** — **demonstration-grade**, single aggregate, no auth, no persistence. |
| **5. Human governance lifecycle** | **Post-evaluation human governance**: bounded `recruiter_*` (and related) ingress for **approve / reject / override** with typed payloads; **audit narratives** on transition records (who, why, evidence refs); inspection helpers that surface **governance lines** alongside decisions—not the same problem as “can I run and see the pipeline?” (Stage **4**). Durable long-term audit archives and full operator products remain **platform / hardening** scope. | **Partial** — **bounded** events and audit lines on the reference store; not a full operator product or production archive. |
| **6. Controlled cognition** | Real `skills/llm/` or hybrid skills behind the same contracts; orchestration unchanged. | **Not started** (directory structure / principles only until first merged skill). |
| **7. Talent intelligence platform** | Long-lived talent pool, cross-requisition matching, durable timelines, multi-aggregate orchestration, production-grade operations. | **Vision / not started** as an integrated platform (see Executive Overview for business direction). |

**Honest snapshot:** stages **1–3** are strong in code and tests. **4** proves **visible, operable workflow execution** on one reference candidate; **5** proves **human decision ingress and audit hooks** on top of that slice—both narrow and in-memory. **6–7** remain **principles and architecture**, not shipped product capabilities.

---

## Repository topology (concise)

- **`schemas/`**, **`interfaces/`**, **`state_machine/`** — contracts and deterministic transition rules.
- **`orchestrator/`** — planning policy (e.g. `vertical_slice_planner.py`); **no** LLM calls.
- **`runtime/`** — reference wiring (`bootstrap_vertical_slice.py`), in-memory bus/store, **inspection** (`runtime/inspection/`), **demo fixture** (`demo_candidate_fixture.py`).
- **`skills/deterministic/`** — vertical-slice fakes; **`skills/llm/`**, **`skills/hybrid/`** — reserved for cognition when stage **6** begins.
- **`integrations/api/`** — sync FastAPI ingress and demo HTML; **not** a production frontend claim.
- **`tests/`** — contract, replay, governance, API, inspection tests.

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

Ordered by **dependency and demo value**; each item should have a **testable exit** or debt entry when work starts.

1. **Richer ingress and idempotency** (optional CLI, dedupe keys)—still thin adapters; **no** policy in HTTP handlers.
2. **Deeper post-evaluation governance** (richer approve/reject/override narratives, calibration hooks) where demos expose gaps—still event-sourced and transition-validated; distinct from “more demo UI” (Stage **4**).
3. **Structured inspection exports** (typed JSON projections) when an integration needs machine-stable rows—not a replacement for read-only text timelines.
4. **Layered replay assertions** (structural vs semantic vs governance projections) per `tech_debt.md` — reduce false churn as instrumentation grows.
5. **First controlled cognition skill** behind existing skill contracts (`skills/llm/` or hybrid)—orchestrator and planner unchanged.
6. **Persistence abstraction** when restarts or cross-process audit **require** durable facts—immutable-event discipline preserved.

---

## Operational hardening (parallel tracks)

These are **not** capability stages; they are **reliability and scale** work, scheduled when need is proven. Details live in **`docs/architecture/tech_debt.md`**.

Examples: durable event store and replay runner, outbox/idempotent consumers, multi-tenant isolation, observability/SLO signals, production ingress auth, deployment playbooks.

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
