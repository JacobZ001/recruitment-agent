# R-014.2 (Minor) — Scoring Context Structured Q&A (V1)

**PM Approved:** 2026-06-02

**Parent major round:** R-014

## Round Goal

在 R-014.1 drawer 内为 **Organization / Preferences / Job** 三维各提供 **两条确定性录入路径**：**Describe / Edit（prose 弹窗）** 或 **Fill The Form / Edit The Form（固定字段 Q&A 弹窗）**；Q&A 直写 typed context，stub 下可稳定 `ready`，**不**做 checklist stub 范例、**不**开 R-015。

**UI copy rule（冻结）：** 用户可见英文按钮、标签、Example 前缀等采用 **Title Case**（每个单词首字母大写，含 `Or` 分隔符；专有名词如 PDF 保持大写）。**范围：** 仅 drawer + prose/Q&A modal + Q&A 表单（**不**强制改 checklist / Not Ready badge，除非 Builder 顺带触及）。

## PM AskQuestion 确认（批准前）


| 议题                      | PM 选择                                                  |
| ----------------------- | ------------------------------------------------------ |
| `Edit The Form` 无 typed | **禁用** + 短提示                                           |
| `Saved Via Form`        | `source_refs` 含 `**form://…`**；structured POST 带对应 ref |
| Title Case 范围           | drawer + modals + Q&A only                             |
| Acceptance 优先级          | **不拆分** — PLAN 内 acceptance 均为 blocking                |
| Esc                     | **先关 modal，再关 drawer**                                 |

### PM AskQuestion 确认 — 补充（2026-06-02）

| 议题 | PM 选择 |
|------|---------|
| Job Q&A API | 复用 `POST /scoring-context/job/recruiter-answers`（tags → newline strings） |
| Job `Saved Via Form` | 追加顶层 `form://job` 到 `scoring_context.source_refs` |
| Job PDF 区块 | 始终保留（与 Describe/Form 并列） |
| Form→Prose 覆盖 | 覆盖前弹确认：`This Replaces Your Form Answers` |
| Job Success 控件 | tags only |
| Tag 上限 | FE 强制：最多 8 tags、每条 ≤120 字符；超限给明确提示 |
| Modal overlay | 点击遮罩关闭 modal（等同 Cancel，不保存） |
| Prose 验收 | Blocking：至少一维 Describe→Confirm 成功 |
| `Saved Via Form` 判定 | 看 scoring_context 顶层 `source_refs` 是否含 `form://…` |
| `Edit The Form` 启用 | 仅当 GET typed context 非空且可解析时启用；否则禁用+提示 |
| Refresh 模型 | 保持：三维都 Confirm 后才 refresh/materialize→ready |
| R-014.1 回归 | 全部 blocking（drawer 关闭、checklist scroll、PDF 直传、Create PDF 门控等） |

### PM AskQuestion 确认 — UX 细节补充（2026-06-02）

| 议题 | PM 选择 |
|------|---------|
| Modal 关闭按钮 | 两个 modal 右上角提供 **X**（Esc/overlay/Cancel 仍保留） |
| 覆盖确认弹窗文案 | Title：`Replace Form Answers?`；Body：`This Replaces Your Form Answers.`；Buttons：`Replace And Continue` / `Cancel` |
| Tag 超限提示 | 超过 8 或单条 >120：**阻止添加**，在该题下显示明确红字提示 |
| Job Success 控件 | 强制 tags-only；删除/禁止 textarea 备选（修正 PLAN 笔误） |


## Round Type

- `minor` (corrective under R-014; follows R-014.1)

---

## PM UX Decisions (frozen)

### Drawer 维度 panel（替换 R-014.1 内联 textarea）

每个维度 panel **仅保留**：

1. **标题行**：`Describe Your …`（Title Case，见下表）+ 右侧 compact 状态（可与 panel 样式并存）。
2. `**saved_locked` 整段视觉（冻结，须明显）**：
  - 整个维度 panel：**emerald** 强调（例如 `border-emerald-300` `bg-emerald-50/80`；Builder 可微调，但须一眼区分于空态白/灰底）。
  - 标题行或 panel 左上角：**✓**（checkmark，accessible label 如 “Saved”）。
  - 空态 `empty_locked`：**不**使用 emerald 满幅样式（保持中性 slate/white）。
3. **主操作行**（无 inline textarea）：
  - **空态**：`**Describe`** → prose 弹窗（空白）。
  - **已保存**：`**Edit`** → prose 弹窗（预填 GET prose）。
  - Prose 弹窗内 **Confirm** / **Cancel** 逻辑不变。
  - **分隔**：水平线 + `**Or`**（Title Case）。
  - **空态**：`**Fill The Form`** → Q&A 弹窗。
  - **已保存**：`**Edit The Form`** → Q&A 弹窗，**预填 GET `organization_context` / `recruiter_actor_context` / `job_context`**。
  - **无 typed 时（PM 确认）：** **禁用** `Edit The Form`，显示短提示（如 *Use Edit For Text, Or Fill The Form To Add Structured Fields*）；不以空表冒充可编辑 structured。
4. **已保存摘要**（可选一行 truncate）：若该维 `source_refs` 含对应 `**form://…`** → 显示 `**Saved Via Form**`；否则公司名 / prose 首行 truncate。
5. **Delete**（`saved_locked` 时保留，行为同 R-014.1）。
6. **Job 维** 在 panel 下方仍保留 **Upload Job Description**（PDF 直传 + Confirm，R-014.1 行为不变）。

### Prose 弹窗（`Describe` / `Edit`）

- 由 `**Describe`**（空态）或 `**Edit**`（已保存）打开；同一 modal 组件。
- Modal：`textarea` + **Confirm** + **Cancel**（Title Case 按钮文案）。
- Confirm 成功 → `saved_locked` + 既有 `maybeRefreshAfterPersist` / invalidate 链。
- 关闭：Cancel、Esc、overlay（与 drawer 一致）。
- **Esc 顺序（PM 确认）：** modal 打开时 **先关最上层 modal**，再关 drawer。

### Q&A 弹窗（`Fill The Form` / `Edit The Form`）

- 由 `**Fill The Form`**（空态）或 `**Edit The Form**`（已保存）打开；同一 modal 组件。
- Modal：见下方 **固定问题表**；每题 **Label** + **Example**（样式区分：label `font-medium`，example 行以 `**Example:`** 开头 + muted italic，避免用户把 example 当答案粘贴）。
- 多值字段：**tag 输入**（`+` 添加、chip 删除）；提交前 FE 校验至少条数；**tag 限制**：最多 8 个、每条 ≤120 字符（超限阻止添加并在该题下显示红字提示）；POST 时合并为 backend 可消费的 list 或 bounded string（job answers API 用 `_split_items` 兼容 newline/comma）。
- Confirm → 调用 **typed authoring API**（见 Scope In）→ 同 prose 路径 invalidate / 第三维齐则 refresh。
- Cancel 丢弃弹窗草稿，不改服务端。

### 路径关系

- 三维 **各自独立** 选 prose 或 form（不要求全局统一模式）。
- Form 成功后仍写入 `*_authoring_text`（`organization_context_to_authoring_text` 等），refresh/materialize 行为不变。
- **L2 / L3 criteria：本 round 不让用户填** — 由 `refresh` + materialize 后 `derive_l2_labels` / `derive_l3_labels` 确定性生成；Q&A 只需收集 org / recruiter / job typed 必填信号。

---

## Q&A V1 — 固定问题（英文 UI，Title Case 标签）

问题设计目标：满足 `_validate_materialized_payload` 与 typed-context 必填信号。Example 行内容可为 sentence case；**Label 与按钮必须 Title Case**。

### Organization — `Fill The Form` / `Edit The Form`


| #   | Label (UI)                       | Maps to                 | Control           | Required | Example (muted)                                        |
| --- | -------------------------------- | ----------------------- | ----------------- | -------- | ------------------------------------------------------ |
| 1   | Company Name                     | `company_name`          | single-line       | yes      | `BlueOcean Recruitment`                                |
| 2   | Industry                         | `industry`              | single-line       | no       | `Recruitment`                                          |
| 3   | Team Name                        | `team_name`             | single-line       | no       | `Talent Ops`                                           |
| 4   | How Does Your Team Work?         | `environment_signals[]` | tags (+)          | yes ≥1   | `Fast-paced recruiter workflow`                        |
| 5   | What Do You Value In Candidates? | `preference_signals[]`  | tags (+)          | yes ≥1   | `Clear communication`, `Structured follow-through`     |
| 6   | Short Summary (Optional)         | `summary`               | textarea 2–3 rows | no       | `Boutique recruitment firm focused on ops excellence.` |


### Preferences (Recruiter Actor) — `Fill The Form` / `Edit The Form`


| #   | Label                           | Maps to                | Control     | Required | Example                                  |
| --- | ------------------------------- | ---------------------- | ----------- | -------- | ---------------------------------------- |
| 1   | Your Name Or Recruiter ID       | `actor_id`             | single-line | yes      | `Jane-recruiter`                         |
| 2   | Your Role (Optional)            | `actor_role`           | single-line | no       | `Lead Recruiter`                         |
| 3   | What You Look For In Candidates | `preference_signals[]` | tags        | yes*     | `Ownership`, `Stakeholder communication` |
| 4   | What You Want To Avoid          | `avoid_signals[]`      | tags        | yes*     | `Unclear communication`                  |


At least **one** tag total across rows 3 **or** 4 (matches backend recruiter validation).

### Job — `Fill The Form` / `Edit The Form`


| #   | Label                   | Maps to                                   | Control            | Required | Example                                           |
| --- | ----------------------- | ----------------------------------------- | ------------------ | -------- | ------------------------------------------------- |
| 1   | Job Title               | `title` / `role_title`                    | single-line        | yes      | `Recruiting Operations Specialist`                |
| 2   | Must-Haves              | `hard_requirements` / `must_haves_answer` | tags               | yes ≥1** | `Stakeholder communication`, `Process ownership`  |
| 3   | Nice-To-Have (Optional) | `preferred_requirements`                  | tags               | no       | `ATS familiarity`                                 |
| 4   | What Success Looks Like | `success_signals`                         | tags               | yes**    | `Keep candidate flow organized`                   |
| 5   | Main Responsibilities   | `responsibilities`                        | tags               | yes**    | `Coordinate interviews`, `Surface blockers early` |


Backend requires **title + at least one** of hard / preferred / success / responsibilities signals; FE 校验：title 非空且 (2) 或 (4) 或 (5) 至少一项非空。

**Job implementation note (frozen):** Use `POST /scoring-context/job/recruiter-answers` with FE joining tag arrays to newline-separated strings (no new job/structured route this round). Also append top-level `form://job` for `Saved Via Form` detection.

---

## Scope In

### Backend（bounded）

1. **New HTTP + use-case wiring**（typed body → existing `author_organization_context` / `author_recruiter_actor_context`）:
  - `POST /scoring-context/organization/structured` — body: `OrganizationContext` fields; `**source_ref` 必填** `form://organization`（PM：用于 `Saved Via Form` 判定）。
  - `POST /scoring-context/recruiter-actor/structured` — body: `RecruiterActorContext` fields; `**source_ref` 必填** `form://recruiter_actor`。
  - Job form 路径：`form://job` 或沿用 `normalized://recruiter_answers/job_context` 之一 — **须在 FEEDBACK 写明** 与 panel 摘要判定一致。
2. **Job (frozen):** reuse `POST /scoring-context/job/recruiter-answers` (tags → newline strings). No `job/structured` route this round.
3. API tests for structured org/recruiter (+ job path if changed).
4. **No** change to `_validate_materialized_payload`, fingerprint, or materialize skill prompts.

### Frontend

1. Refactor `ScoringContextIngress.tsx` panels per PM UX（`saved_locked` emerald + ✓；Describe/Edit + Or + Fill The Form/Edit The Form；移除 panel 内 textarea）。
2. New components（命名 Builder 自定）：`ProseContextModal`, `StructuredContextFormModal`（或三维共用一个 shell + config）。
3. `frontend/src/lib/scoringContextFormSchemas.ts`（或类似）— 问题定义、校验、tag ↔ API payload 映射（确定性）。
4. `api/client.ts` + types for structured POSTs.
5. Vitest：form validation + payload mapping；不强制 e2e。
6. `FEEDBACK.md` + stub 手工验收（**三条均可用 form 达到 ready**）。

### Unchanged from R-014.1

- List：Scoring context 按钮、readiness checklist、drawer Esc/overlay/X、Create PDF 门控、blocker 友好映射、Job PDF 直传、双 Confirm 消歧、Cancel 竞态修复。

## Scope Out

- **R-015** 及 timeline / `source_ref` lineage（**本轮不做**）。
- Checklist org **stub copy-paste 范例**（取消原 R-014.2 草案）。
- LLM 生成问卷、对话式 Q&A（**R-024** 以后）。
- 用户直接编辑 **derived_l2_criteria / derived_l3_criteria**。
- Stub `normalize_*_from_text` 规则放宽。
- 全站 design system 翻新。

## Constraints

- 验收：`/app/` List + drawer；`**LLM_PROVIDER=stub`**。
- Q&A 文案与 example **静态**（repo 常量），禁止运行时 LLM 生成题目。
- Programs 控制 refresh/ready；FE 不伪造 `ready`。

## Acceptance Criteria

- 三维 panel：**无** inline textarea；`saved_locked` 整段 **emerald + ✓** 明显区别于空态。
- 空态：**Describe** + **Fill The Form**；已保存：**Edit** + **Edit The Form**；分隔 **Or**；全部 Title Case。
- **Stub UAT：** 仅用 **Fill The Form** 完成 org + preferences + job → refresh → `**ready`** + Create PDF enabled。
- 已保存维再次点 **Edit The Form** 可改字段并 Confirm。
- Prose 路径仍可用（Describe modal）且 R-014.1 回归不回归（PDF、Cancel、checklist、inline status）。
- Structured POST org/recruiter 返回更新后的 GET；`materialization_blockers` 在填足字段后清除。
- `pytest -q` 通过（含新 route tests）；`npm test -- --run` + `npm run build` 通过。
- FEEDBACK 含逐步 stub 清单：form-only happy path + 一条 prose 路径 smoke。

## Debt Triage

- **Partial:** Recruiter workflow onboarding — structured Q&A v1 覆盖三维；prose 仍依赖 LLM/stub materialize 质量。
- **Deferred:** R-015；R-024 LLM-guided Q&A；golden prose fixtures（post-R-020 queue）。

## Architect Notes (for Builder)

- Typed org/recruiter POST 应调用已有 `author_*_context(OrganizationContext|RecruiterActorContext)`，自动生成 stub-friendly `*_authoring_text`。
- Prose：**空态 `Describe`，已保存 `Edit`**；Form：**空态 `Fill The Form`，已保存 `Edit The Form`**。
- `**saved_locked` panel：** emerald 背景/边框 + checkmark（勿仅靠小 badge）。
- **Title Case** 仅 drawer / modals / Q&A（见上表）。
- `**Edit The Form` disabled** when GET typed context for that dim is null/empty.
- **Esc:** modal first, then drawer.
- `editing` 维状态可收敛为「prose modal 打开中」或保留仅用于 Job PDF 路径；避免 `useEffect([context])` 覆盖 modal 草稿（延续 R-014.1 Cancel 修复模式）。
- Job PDF 区块仍在 job panel 内，与 Describe/form 并列，不放进 prose modal。

## Builder Feedback Reminder

`FEEDBACK.md` 须 mapping PLAN 步骤、文件清单、测试命令、**stub form-only ready** 手工步骤、R-014.1 回归 smoke 简要复验。