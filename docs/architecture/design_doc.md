# BlueOcean Recruitment Agent System - Executive Overview (Non-Technical)

## Vision

BlueOcean is building an AI-native recruitment and human evaluation infrastructure designed to automate repetitive hiring workflows while preserving human judgment for final decision-making.

The system is not intended to replace recruiters. Instead, it functions as a structured decision-support engine capable of:

- Reducing manual screening workload
- Standardizing evaluation quality
- Extracting deeper human signals beyond CV keywords
- Building a long-term strategic talent pool
- Creating reusable AI recruitment capabilities across future BlueOcean projects

The long-term direction is broader than recruitment automation. The system is designed as a reusable human evaluation infrastructure that can later support:

- Executive hiring
- Founder evaluation
- Partner assessment
- Investment team formation
- Cross-border project staffing

# Core Principles

## 1 Human-in-the-loop

The system assists decision-making but never fully replaces human authority.

Human operators maintain:

- Final hiring authority
- Manual override capability
- Score adjustment rights
- Candidate progression control
- Interview and offer decisions

AI acts as:

- Information processor
- Signal extractor
- Structured evaluator
- Workflow coordinator

## 2 AI evaluates human signals, not just resumes

Traditional recruitment relies heavily on:

- Degrees
- Company names
- Keywords
- Years of experience

BlueOcean's system instead prioritizes:

- Thinking structure
- Communication style
- Ownership mentality
- Integrity and professionalism
- Handling uncertainty
- Cognitive clarity
- Executive maturity

CVs are treated only as an initial reference layer.

## 3 Cost-efficient AI usage

The system avoids unnecessary AI usage.

Programmatic logic is used whenever possible.

AI is reserved only for:

- Semantic understanding
- Communication analysis
- Signal interpretation
- Language generation

This significantly reduces token consumption and operational cost.

## Reference implementation today (engineering reality)

The **current codebase** includes a **reference vertical slice** used to prove architecture—not a finished recruiting product.

- **Single-process and single-tenant**: the reference API now defaults to a local SQLite-backed runtime so workflow state survives restart in development. It is still a proving environment, not a production deployment claim or multi-tenant architecture.
- **Event-driven progression**: each step is triggered by **events**; a deterministic orchestration layer applies **validated** state changes. **Programs** advance the workflow; **AI is not** choosing the next pipeline state in this reference path.
- **Screening and scoring today**: candidate CV ingress is gated by an explicit typed `scoring_context`. Outside the candidate event bus, bounded APIs author `organization_context`, `recruiter_actor_context`, and `job_context` (text, PDF, or recruiter-answer normalization), then mark that context `ready`. At `cv_submitted`, a constrained `skills/llm/` provider path first parses `ingress_profile`, then scores `cv + scoring_context` into layered `evaluation.light`. Hard filtering, deeper scoring, ranking, and state transitions remain deterministic. Tests/default local runs still use the deterministic `stub` provider unless explicitly overridden.
- **Typed recruiter semantics**: recruiter-facing snapshot/API projections now separate governance `decision` from score/filter `evaluation`, with `profile` and ingress `flags` exposed explicitly instead of encoding current evaluation semantics in `extensions`.
- **Human governance**: recruiter-style **approve / reject** actions exist as **bounded, audited event types** in the reference slice, aligned with the “humans retain authority” principle. Full operator products, persistence, and channel integrations (e.g. Telegram) are **not** implied by this slice.
- **Intentional bounds (not omissions by accident):** there is no migration framework for old local SQLite rows in this cutover stage; local `data/app.db` reset is the accepted developer path when typed-evaluation cutovers land. Multi-tenant orchestration, distributed execution, and production-grade infrastructure remain later platform concerns.

# High-Level Workflow

## Step 1 - JD Generation

The system first interacts with the recruiter to understand:

- Role responsibilities
- Success criteria
- Failure scenarios
- Preferred traits
- Red flags
- Recruiter preferences

The AI then generates:

- External JD
- Internal evaluation framework
- Hard requirements
- Scoring criteria
- Question banks

## Step 2 - Job Distribution

For Phase 1, recruitment posts are automatically distributed through Telegram.

Future phases may expand to:

- LinkedIn
- WhatsApp
- Job boards
- Internal referrals

## Step 3 - Candidate Intake

Candidates may apply through:

- Telegram
- Forms
- Email
- Manual uploads by HR

All applications enter a unified pipeline.

The system also supports manual uploads for channels AI cannot directly access.

## Step 4 - CV Parsing

AI extracts structured information from candidate submissions.

In the **reference implementation today**, `cv_submitted` accepts bounded CV-like text only when the active `scoring_context.status == ready`. The deterministic pipeline persists `cv_received` first, then `cv_parsed`, and only afterwards emits job-aware light scoring. Provider-backed LLM skills may parse typed `ingress_profile` and return per-layer score signals, but deterministic program logic computes final aggregate score/confidence, validates the layered schema, and owns workflow routing. Deterministic `stub` mode remains the default for tests and local dry runs, while `.env` configuration can opt into OpenAI/OpenRouter for live smoke or manual validation.

Examples:

- Work experience
- Languages
- Executive exposure
- Industry background
- Communication quality indicators

## Step 5 - Hard Filtering

Programmatic rules remove clearly unqualified candidates before deeper AI analysis.

Examples:

- Wrong location
- Insufficient experience
- Missing language requirements

This minimizes unnecessary AI cost.

## Step 6 - Initial Scoring

Qualified candidates are evaluated across three dimensions. In the current slice, light evaluation is persisted as typed `evaluation.light` with explicit `l1_universal`, `l2_role_specific`, and `l3_recruiter_preference` layers plus deterministic aggregate score/confidence and `context_version`. Later stages may add `evaluation.hard_filter` and `evaluation.deep` on the same snapshot, with deep following the same layered schema.

### Universal Competencies (`l1_universal`)

- Communication 25%
- Ownership 25%
- Reliability 30%
- Thinking clarity 20%

### Role-Specific Competencies (`l2_role_specific`)

Derived primarily from `job_context`, with `organization_context` allowed to shape how the role is interpreted in the current environment.

- Executive exposure
- Confidentiality handling
- Multitasking capability
- Coordination maturity

### Recruiter Preference Layer (`l3_recruiter_preference`)

Derived from `organization_context` plus `recruiter_actor_context`. This remains a scoring layer only, not a separate canonical preference aggregate.

- Integrity
- Professionalism
- Structured thinking
- Personality compatibility

## Step 7 - Adaptive Questionnaire

Only selected candidates proceed to additional questionnaires.

Questionnaires are triggered based on:

- Candidate ranking
- Information confidence level

The target design is still dynamic and evidence-seeking, but the current reference slice keeps questionnaire orchestration bounded and deterministic; full adaptive content generation is not yet implemented.

Examples:

- Executive coordination scenarios
- Communication exercises
- Judgment and prioritization questions

This stage is designed as a structured information extraction process rather than a chatbot conversation.

Operationally, the system may distinguish **pending**, **sent**, and **completed** questionnaire snapshots so later scoring can rely on an explicit “questionnaire done” state—not only a single “questionnaire sent” label.

## Step 8 - Deep Evaluation

The system combines:

- CV signals
- Questionnaire responses
- Communication patterns
- Risk indicators

To produce:

- Structured scores (`evaluation.deep` when that stage runs)
- Evidence-backed reasoning
- Confidence levels
- Risk analysis

## Step 9 - Ranking & Shortlisting

Candidates are ranked using deterministic scoring logic.

The AI does not make final hiring decisions.

It produces:

- Top candidate lists
- Hiring briefs
- Interview focus areas
- Risk warnings

# State Machine Architecture

The recruitment system operates through a structured candidate lifecycle.

Examples of pipeline stages (the exact set evolves with the product; engineering uses explicit named states for traceability):

- New intake
- CV submitted and light-scored
- Hard filter passed (or closed if rejected)
- Initial (light) scoring persisted as typed evaluation
- Questionnaire pending, sent, and completed
- Deep evaluation / scoring
- Shortlisted
- Interview and offer stages where the workflow requires them
- Inactive / closed when appropriate

This ensures:

- Traceability
- Workflow stability
- Auditability
- Operational clarity

# Talent Pool & Long-Term Value

Candidates are retained in a long-term strategic talent pool.

Even candidates not selected for one role may become valuable for:

- Future projects
- Advisory work
- Portfolio companies
- Strategic partnerships

The system continuously accumulates institutional recruitment intelligence.

# Continuous Learning & Calibration

The system improves over time through recruiter feedback.

Human decisions are recorded and used for:

- Calibration
- Preference learning
- Scoring refinement
- Better future recommendations

Over time, the system increasingly reflects BlueOcean's hiring philosophy and standards.

# Strategic Significance

This project is not merely a recruitment tool.

It represents the foundation of:

- AI-native organizational infrastructure
- Human evaluation systems
- Strategic talent intelligence
- Institutional decision augmentation

The architecture is intentionally modular and reusable across future BlueOcean initiatives.