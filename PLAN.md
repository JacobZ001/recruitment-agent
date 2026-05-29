# R-011.1 (Corrective Minor) — Write/Sync Consolidation + Full-Repo Tail Cleanup

## Round Goal

在 `R-011` 主链路收敛基础上，完成过渡模块 consolidation 与全仓尾部语义收口，消除旧数据可见性断层风险，并删除 demo-phase 遗留 fixture，使 read/write model 与 ideal architecture 在仓库层面一致。

## Round Type

- `corrective-minor`
- Parent major: `R-011`

## Scope In

1. **`candidate_writes` / `candidate_sync` consolidation（本轮核心）**
   - 目标：把仍需保留的稳定逻辑吸收到稳定归属模块（`bootstrap` / `use_cases` / `projection` / runtime 层），关闭过渡模块扩散。
   - 约束：行为不变（no behavior change）；以回归一致性为判据。
   - 硬要求：本轮结束时删除文件本体 `modules/recruitment/candidate_writes.py` 与 `modules/recruitment/candidate_sync.py`（不得以空壳/转发模块保留）。

2. **全仓 read/write model 尾部清理（不仅主路径）**
   - 目标：清理剩余 legacy 语义引用面（schema/inspection/docs/辅助路径）中与 `R-011` 主链路不一致的候选人数据读取假设。
   - 要求：主路径之外的仓库尾部实现也需与 Candidate canonical + explicit `candidate_id` 语义一致。

3. **旧数据可见性断层风险清零（强制执行）**
   - Builder 必须执行：
     - 停止 API（确保 DB 文件可删除）
     - 删除 `data/app.db`
     - 运行 `python scripts/seed_testing_candidate_from_pdf.py`
     - 重启 API 并验证 list/detail/action 正常
   - 目的：确保不存在 `links-only` 历史行导致的可见性偏差。

4. **删除 demo-phase 旧 fixture（强制执行）**
   - 目标：删除 `modules/recruitment/fixtures.py` 中 demo candidate profile 旧 fixture（`DEMO_CANDIDATE_DISPLAY`）及相关依赖路径。
   - 约束：删除后不得引入新的 demo-first 数据兜底语义；如需保留 demo 路由，必须改为非 fixture 的明确数据来源。
   - 硬要求：`DEMO_CANDIDATE_DISPLAY` 常量定义与引用路径一并删除，不保留兼容别名。

5. **最小必要 DTO/Projection 校准（按需）**
   - 仅当 consolidation/清理影响 recruiter read surfaces 时执行最小校准。
   - 目标文件（按需）：`modules/recruitment/projection.py`、`integrations/api/schemas_http.py`、`integrations/api/app.py`

6. **验证矩阵（balanced+）**
   - `python -m pytest -q`
   - `cd frontend && npm test`
   - `cd frontend && npm run build`
   - DB reset/reseed 后的 list/detail/action smoke

## Scope Out

- 不进入 R-012 新 capability（hard-filter restoration）。
- 不实现 dedup merge policy（R-013）。
- 不扩展新的 UI 功能面。
- 不改变 state-machine 业务语义与治理决策边界。

## Constraints / Architecture Boundaries

- Builder 只能在已批准 scope 内决定 `how`，不得扩展 `what`。
- 不允许保留“可选保留旧分支”的实现；本轮目标是收口而不是共存。
- 若出现阻塞，必须在 `FEEDBACK.md` 按 `blocked` 升级并给最小 unblock path。

## Roadmap Alignment (Planning-phase)

- Selected upcoming action:
  - `R-011.1 — Candidate write/sync consolidation and transitional module closure (current corrective minor under R-011)`
- Capability advance:
  - `Deterministic Foundation`
- Round-specific hard gates:
  - full-repo tail cleanup
  - DB delete + reseed verification
  - demo fixture removal

## Debt Triage Summary (Planning-phase)

- Selected for this round:
  - `TD-PERSISTENCE-008 Evaluation precedence semantics` — `partial`
    - handling: consolidation 后保持 Candidate canonical precedence，不回退 snapshot legacy semantics。
  - `TD-DX-002 Compatibility shim sprawl and demo-first residue` — `partial/close candidate`
    - handling: 删除 demo fixture 及其依赖路径，缩减 demo-first 残留面。
- Explicitly deferred this round:
  - `TD-PERSISTENCE-012 Candidate deduplication and merge policy`
  - `TD-ORCHESTRATOR-012 Decision/communication domains on OrchestrationState`
  - `TD-INSPECTION-003 Timeline is global, not candidate-scoped`
- Debt status corrections in this planning sweep:
  - none

## Ordered Execution Steps (Builder)

1. Consolidate `candidate_writes` / `candidate_sync` 逻辑到稳定归属模块，移除过渡重复路径。
2. 删除 `modules/recruitment/candidate_writes.py` 与 `modules/recruitment/candidate_sync.py` 文件本体，修复所有引用并保持行为一致。
3. 清理全仓尾部 legacy 语义引用（含 schema/inspection/辅助模块中的不一致读取假设）。
4. 删除 demo fixture（`DEMO_CANDIDATE_DISPLAY`）及相关依赖；保持路由行为不回退到 demo-first 兜底。
5. 如有必要，执行最小 projection/DTO 校准，保证 recruiter surfaces 行为不变。
6. 停 API -> 删除 `data/app.db` -> 运行 seed -> 重启 API，完成定向可见性验证。
7. 执行完整验证矩阵（pytest + frontend test/build + smoke）。
8. 覆写 `FEEDBACK.md`，逐步映射本计划并记录 residual 风险（若有）。

## Acceptance Criteria

- [ ] `candidate_writes` / `candidate_sync` 过渡重复路径完成 consolidation，行为与回归一致。
- [ ] `modules/recruitment/candidate_writes.py` 与 `modules/recruitment/candidate_sync.py` 文件本体已删除（`git` 变更为 `D`）。
- [ ] 全仓层面的 read/write model 语义与 R-011 主链路一致（不只主路径通过）。
- [ ] 必须完成“停 API + 删除 DB + reseed + 重启 + smoke”并给出结果证据。
- [ ] `DEMO_CANDIDATE_DISPLAY` 常量定义及其依赖引用已删除（`git` 变更包含 fixture 清理），无 demo-first 兜底残留。
- [ ] recruiter list/detail/action 行为保持稳定，无契约回归。
- [ ] 验证矩阵全部通过：pytest、frontend test/build、DB reset/reseed smoke。
- [ ] `FEEDBACK.md` 明确记录本轮完成状态与后续是否可 `advance-major`。

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
