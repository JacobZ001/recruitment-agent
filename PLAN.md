# R-013 (Major) — Candidate Deduplication and Merge Policy

## Round Goal

在 recruiter product path 上建立**可判定、可审计、非静默自动合并**的候选人去重治理：
- ingress 阶段识别重复风险并给出确定性分流
- 为 recruiter 提供明确的 link/保留决策入口
- 将 R-012 遗留的 incomplete/orphan candidate 纳入可运营治理

## Planning Assumption (Default)

- 由于 PM 尚未明确选择分叉策略，本方案采用默认基线：
  - dedup trigger = **balanced**
  - duplicate behavior = **hybrid**
- 如 PM 在冻结 `PLAN.md` 前指定其他基线（strict/aggressive/custom），按 PM 选择替换规则矩阵即可。

## Round Type

- `major`

## Scope In

- 定义并实现 R-013 dedup 判定矩阵（deterministic）：
  - `normalized_email` 或 `normalized_phone` 命中 = 高置信重复
  - 仅 `cv_content_fingerprint` 命中 = 待人工确认
- create+upload (`POST /candidates/cv/pdf`) 重复分流：
  - 高置信重复：阻断新建，返回可判定 duplicate 响应，并附候选匹配信息用于 link
  - 仅指纹命中：允许继续创建，但标记为 suspected duplicate（进入待处理）
- 引入 recruiter 可执行的人工治理动作（不做自动 merge）：
  - link 到既有 candidate
  - 保留为独立 candidate（带理由）
- 将 R-012 orphan/incomplete candidate 纳入 R-013 治理：
  - 增加可检测规则（例如 create+upload 已占位但未达到 `SUCCEEDED`）
  - 在 list/detail 或专用视图提供可见标记与处置入口
- 补齐 API + 前端 + 用例 + 测试闭环

## Scope Out

- 不做 silent auto-merge / background auto-delete
- 不把全局 ingress idempotency 扩展到所有 endpoint（保留 R-015）
- 不做 timeline/history 产品化改造（保留 R-014）
- 不做 hard-filter 恢复（`TD-ORCHESTRATOR-011` 仍 deferred）

## Constraints / Architecture Boundaries

- 判定逻辑必须 deterministic（程序逻辑，不依赖 LLM）
- merge/link 决策权归 human operator；系统仅给出命中证据与可选动作
- 所有 duplicate/link 关键动作必须可审计（who/when/why）
- 不引入第二套 candidate 语义来源；继续以 canonical Candidate + 既有 orchestration 关系为基础

## Roadmap Alignment (Planning Phase)

- Selected action: `R-013 — Candidate deduplication and merge policy`
- Capability advance:
  - `Recruiter Workflow Operation`
  - `Operational Readiness`

## Debt Triage (Planning Phase)

- **需在本轮 planning 先完成 debt registry 对齐**：
  - 新增并分配：`TD-API-016 + Candidate deduplication, merge/link, and orphan governance`（标题可微调但需稳定）
  - 更新 `ROADMAP.md` R-013 条目为 `Debt ID + title` 形式
- **Selected for this round**:
  - `TD-API-016 + Candidate deduplication, merge/link, and orphan governance`（新建）
  - `TD-API-004 + Candidate list is store-driven (not domain-driven)`（partial，补充 dedup/orphan 可见性）
  - `TD-API-011 + HTTP ingress idempotency and replay-safe retries`（partial，与 dedup 分流协同）
- **Explicitly deferred this round**:
  - `TD-API-012 + API boundary coupling to bootstrap helpers (_envelope, fixed clock)`（R-015）
  - `TD-INSPECTION-002 + Timeline rendering format (plain text vs structured projections)`（R-014）
  - `TD-INSPECTION-003 + Timeline is global, not candidate-scoped (multi-candidate safety)`（R-014）

## Ordered Execution Steps (for Builder after PM approval)

1. 盘点并固化 dedup 输入来源与规范化口径（email/phone/fingerprint）及命中优先级。
2. 在 application/use-case 层实现 dedup 判定与分流结果模型（deterministic，含证据字段）。
3. 改造 `POST /candidates/cv/pdf`：在既有 idempotency 流程中接入 dedup 分流（高置信阻断、低置信标记）。
4. 新增/扩展 recruiter 决策 API（link / keep-separate）及审计记录。
5. 前端新增 duplicate 命中反馈与操作入口（List/create flow + 必要的 detail/list 标记）。
6. 纳入 orphan/incomplete candidate 检测与处置入口（不自动删除）。
7. 补齐测试矩阵：dedup 判定、分流行为、人工决策、orphan 治理、回归不破坏 R-012 ingress。
8. 更新 `FEEDBACK.md` 并记录 debt handling 结果。

## Acceptance Criteria

- create+upload 在 dedup 命中时行为可判定且与基线矩阵一致（高置信阻断、低置信标记）。
- 系统不执行 silent auto-merge；所有 link/保留决策由 recruiter 触发并可追溯。
- orphan/incomplete candidate 在产品路径中可见且可处置，不再仅靠 DB 手工排查。
- `POST /candidates/cv/pdf` 既有 idempotency 语义不回退。
- 关键测试通过（API + 前端 + 回归）。

## Handoff Note

After PM approval, Architect only overwrites root `PLAN.md` and then stops; Builder implementation must run in a separate `Builder Agent` session.
