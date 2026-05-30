# R-014.1 (Minor) — List Scoring Context Ingress UX Corrective

**PM Approved:** 2026-05-30

**Parent major round:** R-014

## Round Goal

按 PM stub UAT 反馈，修正 List 页 scoring context **可用性**（侧边栏、就绪清单、维度反馈、Cancel、Job PDF Confirm、文案）；**不**改 R-014 backend version/fingerprint 语义。

## Round Type

- `minor` (corrective under R-014)

---

## PM Decisions (frozen)

### 1. Materialization blocker / ready gate（FE 可读性 — 非 stub bug）

**现象：** 三维 prose 已 Confirm，仍见 `Server materialization blockers` 黄字，例如  
`organization_context must include non-empty company_name plus bounded environment_signals and preference_signals before ready`。

**原因（Architect）：** 与 **stub 有关但不等于 stub 坏了**。Stub materialize 会从 org **prose 规则化**出 typed context；若 prose 里缺可解析的 **公司名、环境信号、偏好信号**，refresh 后 typed `organization_context` 不满足 `_validate_materialized_payload`，GET 会带该 blocker。**三维 prose 齐 ≠ materialize 成功**。

**R-014.1 做法（冻结，FE only）：**

- **不**改 backend 校验规则（scope out）。
- **Stub vs 真实 LLM（PM 问）：** **prose→typed 的「解析严」主要是 stub**（`StubLLMProvider` 走 `normalize_*_from_text` 规则）；**真实 LLM materialize skill** 应从口语 prose **推断** `company_name` / signals。**但** `ready` 前的 `_validate_materialized_payload` **与 provider 无关** — 若 LLM 输出缺 `environment_signals` 等，同样 blocker。R-014.1 **只改 FE 可读性**；org 口语化仍可能 not ready → **accepted**（后续 round 可改 stub/authoring 引导，非本 round）。
- **R-014.1 验收成功定义：** checklist/映射让人看懂 + 可点进 Organization 修；**不**要求「随便写 org 也能 ready」。
- 在 **Create Candidate 上方「就绪清单」** 中，将 `materialization_blockers` + collecting/ready 状态 **合并为 recruiter 可读的 checklist**（见 Layout）。
- 对 `compute_scoring_context_materialization_blockers` **全部已知**英文字符串做 **确定性 FE 映射**（lookup table，非 LLM）；**未知** blocker fallback 展示 backend 原文。已知集含：
  - `organization authoring prose is missing or not confirmed`
  - `recruiter actor authoring prose is missing or not confirmed`
  - `job authoring prose is missing or not confirmed`
  - `organization_context must include non-empty company_name plus bounded environment_signals and preference_signals before ready`
  - `recruiter_actor_context must include actor_id plus at least one recruiter preference or avoid signal before ready`
  - `job_context must include title plus bounded role signals before ready`
  - `materialized L2 criteria must be non-empty before ready`
  - `materialized L3 criteria must be non-empty before ready`
- Checklist 项可点击 → **必测**：打开 drawer **并 scroll** 到对应维度（Organization / Preferences / Job）。

### 2. Dimension state machine — 增加 **Cancel**

- 在 **`editing`** 态增加 **Cancel**（与 Confirm 并列）。
- **Cancel：** 丢弃当前 textarea 草稿；若服务端该维 prose 非空 → 回 **`saved_locked`** 并恢复 GET 文案；否则 → **`empty_locked`**。
- **竞态（PM 确认）：** 若 stub 可复现 Cancel 后草稿被 `useEffect([context])`/invalidate 覆盖，**Builder 须在本 round 修掉**（非 defer R-014.2）。
- Create / Edit / Confirm / Delete / saved_locked / empty_locked 行为保持 R-014 既有逻辑。

### 3. Messages — 维度内联反馈（取消顶部全局绿/黄堆叠）

- **移除** ingress 顶部全局 `successMsg` / `warnMsg` 作为主反馈（collecting 横幅见 Layout 清单，不在 sidebar 顶重复大段黄字）。
- **移除** drawer 内底部 **「Server materialization blockers」** 大段黄框；blocker 只在 **页面 checklist** 表达（映射人话）。
- 每一维 **标题行右侧** 显示 compact **状态反馈**（图标 + 短文案），例如：Saved / Needs confirm / Saving…；**Materialization issue 不在各维 inline**（只在 checklist 第 4 项）。
- **formError**（POST/Confirm 失败）显示在 **触发操作的那一维** inline 旁，非 drawer 顶全局堆叠。
- Job PDF 成功（`pdf://`）：**去掉** emerald 大横幅；并入 Job 维 **标题行 inline**（如 Saved / From PDF）。
- 样式：小 badge 或 icon+text，与标题同一行，避免 scroll 到页顶看反馈。

### 4. 维度 label 文案（冻结）

| 区块 | 新文案 |
|------|--------|
| Organization (text) | **Describe Your Organization** |
| Recruiter actor (text) | **Describe Your Preferences** |
| Job (text) | **Describe Who You're Hiring** |
| Job (PDF) | **Upload Job Description** |

Job PDF 区 subtitle/helper 可保留操作说明（选文件 → Confirm），不与 title 重复。

### 5. Job PDF — Confirm + 直传（冻结，PM AskQuestion 确认）

**PM 验证：** ingress 路径可用；本轮补齐 PDF 区 **可见 Confirm** 与 **直传**。

**修复（最小 diff，冻结）：**

- 在 **Upload Job Description** 区块内、Choose file **旁**（同一行或紧邻）增加 **Confirm** 按钮。
- 行为与 Job 文本维 Confirm **相同**（调用既有 `confirmDimension('job')` / upload + refresh 逻辑）；**不**改 backend。
- **PDF 直传（FE only）：** `empty_locked` 下也可 **Choose file → Confirm** 上传；**不**要求先 Job 维 Create/Edit。未选文件时 Confirm disabled。
- **双 Confirm 消歧：** 已选 PDF 文件（或 Job 维以 `pdf://` 为 source）时，**隐藏/禁用** Job **文本维** Confirm；仅在 **Upload Job Description** 区 Confirm。

### 6. Layout — 侧边栏 + 就绪清单（冻结）

**页面主区（List）：**

- **右上角**（与 Candidates 标题同行或 header 行）：按钮 **`Scoring context`**（可带 badge：未 ready 或 blockers > 0）。
- **Create Candidate (PDF) 上方**：**Scoring readiness checklist** 卡片（略放大、plain language）：
  - 合并原 「Scoring context is collecting…」与 **`materialization_blockers`**
  - Checklist 示例项（状态 icon ✓ / ○ / ⚠）：
    - Organization described & confirmed
    - Your preferences described & confirmed
    - Role described & confirmed
    - Scoring criteria materialized (maps blockers / ready)
  - `ready` 时 checklist 全 ✓ + 简短「Ready to add candidates」；Create PDF 仍 `contextReady` 门控
- **移除** 表格下方的 inline `ScoringContextIngress` 大卡片（ingress 进侧边栏）。

**右侧侧边栏（drawer）：**

- 点击 **Scoring context** 打开；**overlay + 右滑 panel**（宽 ~md/lg，内部 scroll）；**Esc**、**点 overlay**、**右上角 X** 均可关闭；打开时 focus 在 drawer 内。
- 内容：`ScoringContextIngress` 重构体（三维 + Job PDF + 可选折叠 **Processed** panel）。
- Sidebar 内 **不再** 重复页面级 collecting 大横幅（已在 checklist 表达）。

**Scope out：** 全站 design system 翻新；仅本 List 页上述结构。

---

## PM AskQuestion 确认（2026-05-30）

| 议题 | PM 选择 |
|------|---------|
| Job 双 Confirm | 已选 PDF → 隐藏/禁用 Job 文本维 Confirm；仅在 Upload Job Description 区 Confirm |
| Blocker 映射 | 覆盖上述全部已知 backend 字符串；未知 fallback 原文 |
| R-014 回归 smoke | **写入** Acceptance + FEEDBACK 手工清单 |
| 本轮 scope 拆分 | **不拆** — scope 由 PM/Architect 冻结，Builder 一次交付 |
| PDF 直传 | **In（FE only）** — `empty_locked` 可选文件 + Confirm，无需先 Create/Edit |

### PM AskQuestion 确认 — 第二轮（2026-05-30）

| 议题 | PM 选择 / Architect 处理 |
|------|--------------------------|
| Org materialization 验收 | **UX 成功即可** — 见 §1 stub vs LLM 说明；不要求口语 org 必 ready |
| Cancel 竞态 | **本 round 须修**（stub 可复现则 blocking） |
| Drawer 内 blocker 黄框 | **移除** — 仅 checklist |
| Checklist 点击 | **打开 drawer + scroll 到维**（验收必测） |
| Job PDF 绿字 | **仅 inline**，去掉 emerald 横幅 |
| 各维 Materialization inline | **否** — 只在 checklist 第 4 项 |
| Drawer 关闭 | **Esc + overlay + X** |
| formError | **per-dimension** inline |
| Blocker 映射单测 | **Architect 建议：要** — 覆盖 8 条 + fallback（确定性 util） |

## Architect 建议（已纳入上表；未另开 scope）

| 建议 | 处理 |
|------|------|
| Checklist 项点击跳转维度 | **In** — 降低「不懂 blocker 什么意思」 |
| Blocker 英文字符串 FE 映射表 | **In** — 全量已知 + fallback |
| Drawer badge 显示未就绪 | **In** — 与按钮一体 |
| 改 stub/org prose 解析规则 | **Out** — 除非 PM 另批；可先教 PM 在 org 写 `Company:` / environment / values 句 |
| Processed panel 默认折叠 | **In** — 侧边栏底部 `<details>` 或 accordion，减噪 |

---

## Scope In

1. `CandidateListPage.tsx` — header 按钮、readiness checklist、Create PDF 相对顺序、drawer 挂载。
2. `ScoringContextIngress.tsx`（+ 小 UI 组件）— Cancel、label、inline status、Job PDF Confirm、drawer 内布局；移除页内重复 blockers 大段（清单为主，维度 inline 为辅）。
3. 确定性 blocker → 友好文案 mapping（frontend 常量或 util + **单测必覆盖 8 条 + fallback**）。
4. `npm test` / `npm run build`；`FEEDBACK.md` + acceptance traceability；stub 手工验收。

## Scope Out

- Backend schema / `context_version` / fingerprint / materialize 校验逻辑变更。
- Timeline (**R-015**)、demo phase-out (**R-020**)、golden prose pytest fixtures。
- 全页视觉「现代化」大改（色彩/字体系统）— PM 明确后续再做。
- New upload session 产品化。

## Constraints

- 验收路径：`/app/` List + **`LLM_PROVIDER=stub`**。
- Checklist / mapping 须 **确定性**（给定 blocker 字符串 → 固定展示 copy）。

## Acceptance Criteria

- PM 六项决策均可 stub 手工复验通过（见 FEEDBACK 清单）。
- Job PDF：**Upload Job Description** 区 Choose file 旁 **Confirm**；`empty_locked` 可直传；已选 PDF 时 Job 文本维无 Confirm。
- 四维 label 为 PM 指定英文（含 **Upload Job Description**）。
- 无顶部全局绿字夹黄字；无 drawer 内 Server materialization blockers 黄框；维度标题行有 inline 状态（无 per-dim Materialization issue）。
- Checklist 点击 → drawer 打开并 scroll 到对应维；drawer **Esc / overlay / X** 可关。
- formError 出现在触发 Confirm 的维度 inline 旁。
- Job PDF `pdf://` 提示仅 inline，无 emerald 横幅。
- Cancel 在 stub 下无闪回/无效；blocker 映射 util 单测通过。
- `editing` 有 **Cancel** 且恢复服务端文案。
- Scoring context 仅通过 **右上角按钮 → 右侧 drawer** 编辑；表格下无 inline ingress。
- Create PDF 上方 checklist 合并 collecting + blockers，文案 recruiter 可读；blocker 映射覆盖全部已知 backend 字符串。
- **R-014 回归 smoke（stub 手工，FEEDBACK 逐步列出）：**
  - 第三维 Confirm 后（三维 prose 齐且 materialize 成功）→ `ready` + Create PDF 可用。
  - Create PDF 仍 `contextReady` 门控（collecting 时 disabled）。
  - Job 以 PDF 上传且 `source_refs` 含 `pdf://` 时，Job 维 inline/提示仍正确（R-014 绿字语义）。
  - Invalidate / refresh 顺序不回归（Confirm 链路与 GET blockers 一致）。
- `npm test -- --run` + `npm run build` 通过。

## Debt Triage

- **Deferred:** R-015 及以后队列不变；org prose 解析过严 → 可记 FEEDBACK 建议后续 round，**本 round 不改 backend**。

## Builder Feedback Reminder

`FEEDBACK.md` 须含 PM 手工步骤、acceptance traceability、sidebar/checklist 截图或逐步说明。
