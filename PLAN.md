# R-010 (Major) — Candidate Detail UI Field Curation Fix

## Round Goal

在不改变状态机与核心编排语义的前提下，完成 `CandidateDetail` 的 recruiter-facing UI 字段收敛与信息层级修正，使详情页展示与当前 Candidate canonical read model 一致，并形成可验收的前端交互基线。

## Round Type

- `major`
- Parent major: `R-010`

## Scope In

1. **Detail 页面字段取舍与层级重排（主任务）**
   - 目标文件：`frontend/src/pages/CandidateDetailPage.tsx`
   - 输出：明确并实施字段显示策略（保留/弱化/隐藏），重点覆盖：
     - 头部身份与当前状态（`full_name` / `stage` / `status`）
     - Profile 信息去噪（只保留 recruiter 决策所需字段）
     - Scores 区块聚焦（总体分与关键 criteria，避免信息淹没）
     - Recruiter actions 区块可读性提升（分组、文案、错误提示一致性）

2. **前端类型与消费字段一致性校准**
   - 目标文件：`frontend/src/api/types.ts`
   - 要求：移除 Detail 页不再消费的冗余类型字段（仅限前端本地类型层），确保类型定义反映实际消费面。

3. **必要时的小幅后端 projection/DTO 协同（可选）**
   - 仅当 UI 取舍后确认存在“当前 DTO 不利于清晰展示”的阻塞时启用。
   - 目标文件（按需最小改动）：`modules/recruitment/projection.py`、`integrations/api/schemas_http.py`
   - 约束：仅做 recruiter read-model 展示友好化；不得引入 state-machine 语义变化。

4. **回归与验收**
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

1. 基于当前 `CandidateDetailPage` 输出“字段保留/隐藏/弱化”清单并实现页面重排。
2. 同步清理 `frontend/src/api/types.ts` 中与 Detail 实际消费不一致的冗余类型字段。
3. 若出现展示阻塞，再做最小后端 projection/DTO 协同改动并保持向后安全。
4. 跑前端测试与构建；再跑受影响后端回归。
5. 完成 list/detail/action smoke，并记录前后差异证据。
6. 覆盖 `FEEDBACK.md`，按本轮格式汇报执行事实与风险。

## Acceptance Criteria

- [ ] Detail 页字段展示完成收敛：信息层级清晰、噪声字段显著减少。
- [ ] 页面仅消费并展示“已批准字段集合”，不存在隐式/遗留字段泄漏。
- [ ] 若发生 DTO/projection 调整，保持 recruiter read surfaces 向后安全。
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
