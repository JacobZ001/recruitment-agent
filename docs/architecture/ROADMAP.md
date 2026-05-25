# BlueOcean Recruitment Agent — Development Roadmap

Purpose: preserve long-term development continuity, keep future AI agents and human developers aligned on **what the system can do today**, and record **capability milestones** (not open-ended “phase maturation”). Priority is shifting from **capability completeness on the reference runtime** to **single-tenant usability**—state that survives use, not just demos.

## Project vision

Build a deterministic, AI-native **human evaluation infrastructure** for recruitment workflows:

- **Programs control workflow** (deterministic orchestration, verifiable transitions).
- **LLMs provide cognition** (semantic understanding, extraction, generation) under strict interfaces. The **reference vertical slice** now includes a **bounded CV parsing/light-scoring pilot** behind an explicit provider contract, with deterministic `stub` mode kept as the default test path.
- **Humans govern outcomes** (override, approval, calibration) with audit logs.

## System posture (architecture)

- **Deterministic-first control plane** with explicit schemas, transition validation, and event ingress.
- **Single-process reference runtime** with SQLite-backed state, multi-candidate routing, deterministic orchestration, and a bounded LLM CV-ingress skill. It remains a **proving environment**, not a statement of intended final production topology (which may use different persistence, messaging, ingress, process boundaries, and hosting).
- **Replay and inspection** are harness-backed and read-only projections; they prove control-plane semantics **before** a persisted event product exists.
- **Governance** enters as **typed, event-carried ingress** validated by the same transition engine as system events—not as ad-hoc state edits.
- **Governance of change**: ADRs and `tech_debt.md` record deliberate deferrals (persistence, brokers, typed payload graduation, semantic replay profiles).

**Proving environment vs platform vision:** the **current repo** is intentionally a **deterministic proving runtime**: fast feedback, tests, and demos without standing up production infrastructure. **Long-term production** for a talent intelligence posture may replace or split **where** state lives, **how** events are transported, and **how** ingress scales—while **preserving** the same **orchestration semantics** (validated transitions, immutable-event discipline, skill contracts, governance payloads) as those layers mature.

### Evolution framing (usability vs reference)

Parallel to the numbered capability stages below—this is **delivery priority**, not extra scope:

| Stage | Meaning |
| ----- | -------- |
| **Stage A — Deterministic reference runtime** | Contracts, orchestrator, transition engine, harness replay, in-memory vertical slice—**completed** as a proving baseline. |
| **Stage B — Single-tenant usable system** | **Current focus:** harden the persistent, multi-candidate recruiter slice for local repeated use (restart-safe SQLite, provider config, operator-visible progression). Not multi-tenant product infra yet. |
| **Stage C — Multi-tenant + production infra** | Isolation, brokers/auth/SLO-grade ops—when Stage B behaviors are proven on durable state. |
| **Stage D — Controlled cognition (LLM layer)** | Real `skills/llm/` / hybrid semantics behind contracts. The first bounded cognition pilot is CV parsing/light scoring at ingress; orchestration remains unchanged. |

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
| **4. Recruiter-operable vertical slice** | **Recruiter- / operator-visible workflow execution**: end-to-end progression through the slice (e.g. to `deep_scored`), ingress that **drives** the bus (`POST /events`, `POST /demo/run`, bounded PDF CV upload), bounded scoring-context authoring outside the candidate bus, read APIs for **phase and progression** (`GET /state/{id}`, `GET /timeline/{id}`, `GET /demo/candidate`), and recruiter-facing typed projections (`profile`, governance `decision`, score/filter `evaluation`, flags). | **Partial** — durable SQLite state, multiple candidates, bounded CV and job-context PDF ingress, gated job-aware scoring, and layered recruiter projections are in place; operator UX and some stage continuity remain thin. |
| **5. Human governance lifecycle** | **Post-evaluation human governance**: bounded `recruiter_*` (and related) ingress for **approve / reject / override** with typed payloads; **audit narratives** on transition records (who, why, evidence refs); inspection helpers that surface **governance lines** alongside decisions—not the same problem as “can I run and see the pipeline?” (Stage **4**). Durable long-term audit archives and full operator products remain **platform / hardening** scope. | **Partial** — **bounded** events and audit lines on the reference store; not a full operator product or production archive. |
| **6. Controlled cognition** | Real **`skills/llm/`** or **hybrid** skills for bounded semantic extraction / analysis behind the same contracts (orchestration unchanged)—**LLM understands** the artifact; programs still validate transitions. | **Partial** — bounded job-aware cognition now covers CV profile parsing plus layered light scoring against typed `scoring_context`; broader cognition and richer operator products remain unstarted. |
| **7. Talent intelligence platform** | Long-lived talent pool, cross-requisition matching, durable timelines, multi-aggregate orchestration, production-grade operations. | **Vision / not started** as an integrated platform (see Executive Overview for business direction). |

**Honest snapshot:** stages **1–3** are strong in code and tests. **4–5** now run on a durable, single-tenant SQLite-backed reference runtime with multiple candidates, typed recruiter projections, explicit `scoring_context` authoring, and bounded CV/job-context PDF ingress. **6** has started in a deliberately narrow way through job-aware CV parsing and layered scoring cognition. **7** remains architectural vision, not present-day product reality.

---

## Repository topology (concise)

- **`schemas/`**, **`interfaces/`**, **`state_machine/`** — contracts and deterministic transition rules.
- **`orchestrator/`** — planning policy (e.g. `vertical_slice_planner.py`); **no** LLM calls.
- **`modules/recruitment/`** — application boundary: **`policies`**, **`use_cases`**, **`projection`**, **`runtime`** (API holder), **`bootstrap`** (vertical-slice wiring only), **`fixtures`**, **`ranking`**, **`ingress`**, **`inspection/`**, **`domain/`** (multi-candidate aggregate placeholder). Does **not** own HTTP.
- **`runtime/`** — generic infrastructure: bus, store, SQLite persistence, recording bus, **`runtime/inspection/`**. **`bootstrap_vertical_slice.py`**, **`demo_candidate_fixture.py`**, **`vertical_slice_ranking.py`** remain **compatibility shims** to `modules/recruitment` during migration.
- **`skills/deterministic/`** — programmatic policy and scoring/filtering logic; **`skills/llm/`** — bounded cognition entry points (today: CV profile parsing plus job-aware layered light scoring); **`skills/hybrid/`** — reserved for future mixed cognition + deterministic policy layers.
- **`integrations/api/`** — thin FastAPI ingress, HTTP models, demo HTML; imports **`modules/recruitment`** for business actions (API manages lifespan).
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

- JD generation, Telegram distribution, adaptive questionnaire content, ranking/shortlisting **products**, talent pool persistence, continuous learning pipelines, and production-grade cognition operations.
- Those remain **business direction**; they land as **later capability stages** and **platform evolution**, not as claims of the current repo.

**Superseded wording in planning sense:**

- Treating “confidence” or “workflow confidence” as a **phase name**—replaced here by **concrete capabilities** (replay harness depth, semantic assertion profiles, durable replay)—with details in `tech_debt.md` where needed.

---

## Immediate next capabilities (engineering)

Ordered for the **current single-tenant slice**: job-aware backend scoring first, then operator-facing usability and hardening. Still **no** workflow policy in HTTP handlers.

1. **Job-aware three-layer evaluation**: harden the new `scoring_context` lifecycle, keep light/deep layered contracts aligned, and extend deterministic inspection around context-version / re-score semantics.
2. **Operator-grade recruiter surface**: improve candidate list/view/timeline outputs, scoring-context visibility, and inspection exports without reintroducing dual semantics between governance and evaluation.
3. **Provider-hardening for bounded cognition**: make local provider configuration explicit and repeatable, preserve deterministic default tests, and evolve from coarse dependency failures toward deterministic retryability/error semantics.
4. **Questionnaire/deep-evaluation continuity**: carry the typed layered `evaluation` model consistently through later pipeline stages so recruiter-visible progression stays legible beyond light scoring.
5. **Single-tenant operational playbook**: document reset, validation, and deployment expectations for the SQLite-backed local runtime before any Stage C infrastructure work.

**Later-stage enhancements** (explicitly deprioritized vs Stage B usability—keep in backlog, no removal):

- Structured inspection exports (typed JSON projections).
- Layered replay assertions (structural vs semantic vs governance) per `tech_debt.md`.
- Additional controlled cognition skills (**Stage 6** / **Stage D**): expand beyond ingress parsing only when bounded contracts, provider operations, and read-model semantics remain clear.
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
