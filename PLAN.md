# R-012 (Major) — Real Ingress Baseline for Cognition Quality

## Round Goal

建立“真实输入优先”的评估基线：以真实 PDF ingress 与真实 scoring-context ingress 驱动候选人评估，替代测试数据/fixture 主导路径，用于后续系统化评估 cognition layer 质量。

## Round Type

- `major`

## PM-Frozen Scope Decisions

- `TD-ORCHESTRATOR-011` hard-filter restoration：**无限期延期，不分配 round**。
- R-012 聚焦：**真实 ingress 基线**（而非新增 hard-filter 功能）。
- 本轮不做 full demo phase-out（`R-019` 再做）。

## Scope In

1. **真实 PDF ingress 主路径化**
  - 确保候选人评估主路径可由真实 PDF 文件输入驱动（非 fixture payload 注入）。
  - 评估链路中必须保留 Candidate canonical 写入与可审计输出。
2. **真实 scoring-context ingress 主路径化**
  - 使用真实 context authoring/refresh ingress（组织/岗位/招聘者文本）生成并持久化 active scoring context。
  - 评分阶段消费持久化 context（含版本/陈旧状态语义），不依赖 demo 默认值兜底。
3. **测试数据主导路径降级为辅助**
  - 保留必要测试工具与 seed 能力，但不再作为“默认评估质量验证路径”。
  - 清理/隔离会影响真实质量评估结论的 demo-first 注入行为（在本轮范围内做最小必要收口）。
4. **质量评估基线与证据输出**
  - 增加可复现实验入口（脚本/命令/最小文档）用于跑真实 ingress 样本并产出可比对结果。
  - 输出至少包含：candidate identity/profile 摘要、overall score/type、关键解释信号、context version/stale 指示。
5. **回归与稳定性验证**
  - 保证现有 recruiter list/detail/action surface 契约不回退。
  - 保证现有 deterministic orchestration 边界不被 LLM 接管（LLM 只做理解/抽取/生成）。

## Scope Out

- 不实现 hard-filter capability（已延期）。
- 不做 dedup merge policy（`R-013`）。
- 不做 full demo phase-out（`R-019`）。
- 不进行 state-machine 契约级重构。

## Constraints / Architecture Boundaries

- 程序控制流程；LLM 不控制状态迁移、路由、排序或重试策略。
- 所有质量评估结果必须可复现（同输入、同配置、同输出语义）。
- Builder 只能决定 `how`，不能改变已冻结 `what`。

## Roadmap Alignment (Planning Phase)

- Selected action: `R-012 — Real ingress baseline for cognition quality evaluation`
- Capability advance:
  - `Controlled Cognition`
  - `Recruiter Workflow Operation`
  - `Operational Readiness`

## Debt Triage (Planning Phase)

- **Selected for this round**
  - `TD-SKILLS-001 + CV ingestion evolution (MVP cv_submitted)`
    - Handling: 强化真实 PDF ingress 作为评估主路径，避免测试注入路径主导质量判断。
  - `TD-PERSISTENCE-009 + Single active scoring_context store (not requisition-scoped yet)`
    - Handling: 明确真实 scoring-context ingress -> 持久化 active context -> 评分消费链路的一致性与可见性。
  - `TD-API-012 + API boundary coupling to bootstrap helpers (_envelope, fixed clock)`
    - Handling: 在本轮范围内做最小必要降耦，避免质量评估链路隐式依赖 bootstrap/demo 形态。
- **Explicitly deferred**
  - `TD-ORCHESTRATOR-011 + Canonical hard-filter stage is not restored on recruiter ingress path`（无限期延期）
  - `TD-PERSISTENCE-012 + Candidate deduplication and merge policy`（`R-013`）

## Ordered Execution Steps

1. 盘点当前 `cv_submitted` 与 scoring-context authoring/refresh 主链路，标记 demo/test 注入点。
2. 在 runtime/orchestrator/use_cases 层完成“真实 ingress 优先”最小改造：真实 PDF + 真实 context ingress 成为标准验证路径。
3. 限定 demo/test 注入行为作用域（测试/演示专用），防止污染真实质量评估结果。
4. 校准 Candidate/Projection/API 输出，确保质量评估关键信号可观察且契约不回退。
5. 提供可复现实验入口（脚本/命令）并给出最小运行说明。
6. 增补/更新回归测试（ingress 链路、context 消费、API 可见面稳定性）。
7. 运行验证矩阵并覆写 `FEEDBACK.md`。

## Acceptance Criteria

- 真实 PDF ingress 可独立驱动候选人评估全链路（非 fixture 主导）。
- 真实 scoring-context ingress 可生成并持久化 active context，评分链路消费该 context。
- 评估输出包含可审计关键字段（score/type、context version/stale、解释信号）。
- demo/test 注入路径被限定为辅助用途，不再作为质量评估默认路径。
- recruiter list/detail/action API surface 无契约回退。
- `python -m pytest -q` 通过。
- `frontend` 的 `npm test` 与 `npm run build` 通过。
- `FEEDBACK.md` 完整记录步骤映射、测试结果、风险/偏差与下一轮建议。

## Builder Feedback Reminder

`FEEDBACK.md` 必须覆盖：

- Round ID + status (`done` / `partial` / `blocked`)
- PLAN step-by-step completion mapping
- Full file change summary (`A` / `M` / `D`)
- Test commands + results
- Risks / deviations / blockers
- Debt handling result（`Debt ID + title`）
- Suggested next-round focus

