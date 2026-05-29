# R-010 (Major) — Candidate Detail UI Field Curation Fix

## Round Goal

在不改变状态机与核心编排语义的前提下，完成 `CandidateDetail` 的 recruiter-facing UI 字段收敛与信息层级修正，使详情页展示与当前 Candidate canonical read model 一致，并形成可验收的前端交互基线。

## Round Type

- `major`
- Parent major: `R-010`

## Scope In

1. **Detail 页面字段取舍与层级重排（主任务）**
   - 目标文件：`frontend/src/pages/CandidateDetailPage.tsx`
   - 输出：按 PM 指定 UI 冻结实现，具体如下：
     - 顶部标题从 `Candidate` 改为 `Candidate Details`。
     - 标题下新增大号 `full_name` 展示（字体大于标题）；`Profile` pane 不再重复显示 `full_name`。
     - 顶部 `candidate_id` 改为带 key 的文案：`Candidate ID: <value>`。
     - 当前招聘 `Job Title` 放入最顶部白色头部区域（与 Candidate Details 同层信息区）。
     - 取消独立 `Pipeline` pane；将 pipeline 信息并入顶部信息区。
     - 删除顶部 `Pipeline` label 与顶部 `Summary`（`Profile` pane 内 `Summary` 保留）。
     - `Stage` / `Status` 在顶部增强视觉权重（字号增大），value 使用 tag-like 样式（参考 skills 标签风格，配色需语义清晰且协调）。
     - `Organization` 与 `Recruiter Identity` 放入 `Header Bar`（顶部白色头部区）并作为同层信息元素展示；交互入口也统一放在 `Header Bar` 内。
     - `full_name` 旁新增 `Overall Score` label，并突出显示 overall 分值；overall 的 `score type` 继续保留在 overall 旁边。
     - `Recruiter Actions` pane 移除提示文案：`Labels and availability come from the API only (TD-API-007).`
     - 所有字段展示名去下划线并首字母大写（`Summary` 保持原命名）。
     - `Candidate Detail` 页面不保留独立 `Scoring Context` panel（该信息仅允许临时在 list view 侧用于测试，后续移除）。

2. **前端类型与消费字段一致性校准**
   - 目标文件：`frontend/src/api/types.ts`
   - 要求：移除 Detail 页不再消费的冗余类型字段（仅限前端本地类型层），确保类型定义反映实际消费面。

3. **List view 与 Detail 关键展示语义对齐（新增）**
   - 目标文件：`frontend/src/pages/CandidateListPage.tsx`、`frontend/src/pages/CandidateDetailPage.tsx`
   - 要求：
     - `Stage` / `Status` 在 list 列中采用与 detail 一致的 tag-like 样式与语义配色体系。
     - `Score` 列数字从 `0.x` 改为百分比显示（例如 `0.82 -> 82%`）；detail 页同样改为百分比口径并统一显示规则。
     - 百分比显示规则：精度维持原值精度，不执行四舍五入；`null` 显示 `- -`；overall 的 `score type` 显示策略保持不变。
     - `Actions` 列从“数量”改为可操作 action button，并复用 detail 现有 action 执行流（同一行为与提交结果）。
     - 仅显示 `available_actions`；不展示 disabled/inactive actions。

4. **Profile pane 完整字段呈现（candidate_profile 全量）**
   - 目标文件：`frontend/src/pages/CandidateDetailPage.tsx`
   - 要求：
     - 展示 `candidate_profile` 的完整信息集合（当前 API 返回的 profile 字段均可见）。
     - 每个 value 前必须有明确 key label（例如 `Seniority: mid`），禁止“裸 value”。
     - 排版采用简约、高级、留白充分的布局（避免字段拥挤堆叠）。
     - list/array 字段（skills、languages、industries、roles、external_profile_urls）采用统一可扫描样式，不与标量字段混排混乱。

5. **Scores pane 按 candidate aggregate evaluation 全结构穿透**
   - 目标文件：`frontend/src/pages/CandidateDetailPage.tsx`
   - 要求：
     - 以 candidate aggregate `evaluation` 为主数据源进行完整结构展示（而非仅摘要视图）。
     - 采用“两层结构（Layer / Criteria）”展示：
       - 第一层（Layer）：按 criteria scoring level 分三段
         - `universal` -> `Universal Competencies`
         - `role specific` -> `Role Specifics`
         - `recruiter preference` -> `Recruiter Preferences`
       - 第二层（Criteria）：criteria 本身结构不变，只按上述 Layer 分段归类展示（score/confidence/reason/source 等字段保持可读展开）。
     - 每个 score 数值后必须提供可视化能力值横槽（progress bar），与百分比数值同步，便于快速比较。
     - 同时保留非 criteria 的 aggregate evaluation 结构块（如 deep/hard_filter 元信息）并与上述三段并列或折叠呈现，避免信息丢失。
     - 字段命名遵守本轮展示规范（去下划线、首字母大写；`Summary` 例外）。
     - 为后续 confidence 展示预留规则：当 confidence 可用时，使用 tag-like 语义色阶呈现（本轮先完成样式规则与落位，不改变现有后端语义）。

6. **后端 projection/DTO 协同边界（明确触发条件）**
   - 触发条件（PM 选择 A）：若前端按本计划实现时，出现任一“必显示字段”缺失或结构不满足展示要求，必须执行最小后端协同；不允许前端降级隐藏该字段。
   - 目标文件（最小改动）：`modules/recruitment/projection.py`、`integrations/api/schemas_http.py`
   - 约束：仅做 recruiter read-model 展示友好化；不得引入 state-machine 语义变化。

7. **UI 视觉与可读性增强（本轮必做）**
   - `Stage` / `Status` tag 使用轻量语义色阶（active/inactive/hired）并统一圆角、间距、字号体系。
   - `profile` / `scores` 区块采用字段组分隔线与响应式两列布局（窄屏自动回落单列）。
   - 长文本与长数组实现截断+展开策略，保证首屏可读性与信息可达性。
   - score progress bar 的颜色与标签体系需与语义色阶保持一致，不与 `Stage/Status` 标签冲突。
   - 对 `Profile` 复杂字段（如 `extensions`、长数组、长链接）本轮先完整上屏并保证可读，字段细化策略留待下一轮。
   - 在 list view 页面下方加入 `Scoring Context` panel，复用现有结构，不改信息组织。

8. **回归与验收**
   - 前端：`cd frontend && npm test`、`cd frontend && npm run build`
   - 后端最小回归：`python -m pytest -q`（至少覆盖受影响 read surfaces）
   - 手工 smoke：list -> detail -> action 提交 -> 刷新后状态可见且文案一致

## Scope Out

- 不进入 OrchestrationState linkage cleanup（该项顺延至 `R-011`）。
- 不移除 `candidate_sync.py`，不做 dual-write/convergence 机制重构。
- 不改 schema/state transition contracts（除非为本轮展示阻塞的最小只读 DTO 协同，且保持向后安全）。
- 不引入新的 workflow 动作语义或评分策略。

## Constraints / Architecture Boundaries

- 保持“程序控制流程、LLM 仅做语义”的架构边界，不把业务控制逻辑迁入 prompt。
- `Candidate` 仍为 candidate-owned 数据唯一可信读源；Detail UI 不得回退到 legacy snapshot profile/evaluation 语义。
- 仅允许 bounded change：前端页面与必要的读模型映射；禁止扩散为大范围 API/存储重构。

## Roadmap Alignment (Planning-phase)

- Selected upcoming action:
  - `R-010 — Candidate Detail UI field curation fix (major)`（当前轮）
- Capability advance:
  - `Recruiter Workflow Operation`（详情页可读性与操作可达性）
- Queue routing note:
  - 原“OrchestrationState linkage cleanup + compatibility branch removal”顺延至 `R-011`，避免 UI 基线未冻结时提前进入存储/链接清理。

## Debt Triage Summary (Planning-phase)

- Selected for this round:
  - 无 registry debt 作为主实施对象；本轮为 capability-first UI 收敛。
- Explicitly deferred this round:
  - `TD-PERSISTENCE-008 Evaluation precedence semantics`
    - defer reason: 属于 evaluation 语义与持久化一致性深水区，非本轮 UI 收敛目标。
  - `TD-PERSISTENCE-012 Candidate deduplication and merge policy`
    - defer reason: 与 dedup/merge 策略相关，和本轮 detail 展示改造解耦。
  - `TD-ORCHESTRATOR-012 Decision/communication domains on OrchestrationState`
    - defer reason: 属于治理域存储边界评估，不在本轮 UI 范围。
  - `TD-API-010 Recruiter action list ordering and grouping (UI)`
    - defer reason: 本轮仅做 detail 页面可读性收敛，不扩展为 action policy/ordering 体系重定义。
- Debt status corrections in this planning sweep:
  - none

## Ordered Execution Steps (Builder)

1. 按本计划“UI 冻结清单”重构 `CandidateDetail` 顶部信息区与 pane 结构（含 Candidate Details/full_name/Candidate ID/Pipeline 合并）。
2. 在顶部白色头部区加入 `Job Title`，并将 `Organization` / `Recruiter Identity` 统一纳入 `Header Bar` 信息区与交互入口。
3. 重构 list 关键列：`Stage/Status` tag-like、`Score` 百分比、`Actions` 按钮化（替代数量显示）。
4. list 与 detail actions 区域统一仅渲染 `available_actions` 按钮集合，不显示不可用动作占位。
5. 完整重构 `Profile` pane：全字段可见、key-value 明确、排版去拥挤。
6. 重构 `Scores` pane：按三段两层式 + aggregate evaluation 非 criteria 结构块进行全量穿透展示，并统一百分比显示口径与 progress bar 可视化。
7. 移除 `Candidate Detail` 的 `Scoring Context` panel，并将同结构面板迁移到 list view 下方。
8. 清理 `Recruiter Actions` pane 指定文案并统一展示命名风格（去下划线 + 首字母大写，`Summary` 例外）。
9. 同步清理 `frontend/src/api/types.ts` 冗余字段，保证类型与消费面一致。
10. 实施本轮必做 UI 增强：语义色阶、两列响应式布局、长内容截断+展开。
11. 若出现“任一必显示字段缺失/结构不满足展示要求”，执行最小后端 projection/DTO 协同并保持向后安全（不得前端降级隐藏）。
12. 跑前端测试与构建；再跑受影响后端回归。
13. 完成 list/detail/action smoke，并记录前后差异证据。
14. 覆盖 `FEEDBACK.md`，按本轮格式汇报执行事实与风险。

## Acceptance Criteria

- [ ] Detail 页字段展示完成收敛：信息层级清晰、噪声字段显著减少。
- [ ] 顶部信息区符合指定文案与层级：`Candidate Details`、大号 `full_name`、`Candidate ID: <value>`、`Job Title` 在顶部白色头部区、无独立 Pipeline pane。
- [ ] `Organization` / `Recruiter Identity` 已纳入 `Header Bar` 顶部信息区（非独立右上角悬挂区）。
- [ ] `Stage` / `Status` 以 tag-like 样式展示，视觉权重提升且配色协调。
- [ ] list 页 `Stage` / `Status` 列与 detail 使用一致的 tag-like 视觉语义。
- [ ] list 与 detail 的 score 数值统一按百分比展示（不再显示 `0.x`），且精度不做四舍五入，`null` 显示 `- -`。
- [ ] 顶部 `full_name` 区域已加入并突出 `Overall Score` label，且 overall `score type` 仍保持原展示策略。
- [ ] list 页 `Actions` 列展示可点击 action buttons（不再仅显示数量）。
- [ ] list 与 detail actions 仅显示 `available_actions`（不显示 disabled/inactive actions）。
- [ ] 页面仅消费并展示“已批准字段集合”，不存在隐式/遗留字段泄漏。
- [ ] `Profile` pane 提供 `candidate_profile` 全量字段并全部显式 key-value 展示，不出现裸 value。
- [ ] `Scores` pane 采用三段两层式（Universal Competencies / Role Specifics / Recruiter Preferences）并保留 aggregate evaluation 其它结构块。
- [ ] 每个 score 后均有 progress bar 可视化能力槽，且与对应百分比数值一致。
- [ ] confidence 展示规则已预埋：当 confidence 可用时使用 tag-like 语义色阶展示。
- [ ] `Candidate Detail` 页面不再出现 `Scoring Context` panel；list view 下方已加入复用结构的 `Scoring Context` panel。
- [ ] 本轮 UI 增强全部落地：语义色阶标签、profile/scores 响应式两列、长内容截断+展开。
- [ ] `Recruiter Actions` pane 已移除 `TD-API-007` 提示语句。
- [ ] 展示字段命名符合规则：去下划线 + 首字母大写（`Summary` 例外）。
- [ ] 若发生 DTO/projection 调整，保持 recruiter read surfaces 向后安全，且由“必显示字段缺失”触发，不允许前端降级隐藏替代。
- [ ] `frontend` tests/build 通过，且 list/detail/action smoke 通过。
- [ ] 无 state-machine/contract 非批准变更，无存储语义越界改造。

## Required Builder Feedback Format Reminder

`FEEDBACK.md` 必须覆盖：
- Round ID + status (`done` / `partial` / `blocked`)
- PLAN step-by-step completion mapping
- Full file change summary (`A` / `M` / `D`)
- Test commands + results
- Risks / deviations / blockers
- Roadmap updates (if any)
- Debt entries touched/deferred/newly identified（使用 `Debt ID + title`）
- Suggested next-round focus
