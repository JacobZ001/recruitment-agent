# R-011.2 (Corrective Minor) — No-Tail Cutover Completion

## Round Goal

在 `R-011` / `R-011.1` 基线上完成“无尾巴”收口：删除本轮指定 shim 与 legacy schema 字段，清理运行时 legacy 读取；同时保持 seed candidate 测试链路可用，不提前触发 full demo phase-out。

## Round Type

- `corrective-minor`
- Parent major: `R-011`

## Scope In

1. **删除 `candidate_aggregate.py`（强制）**
   - 吸收必要逻辑到稳定归属模块（`bootstrap` / `use_cases` / `projection` / `orchestrator` / runtime）。
   - 验收：`modules/recruitment/candidate_aggregate.py` 文件本体删除（`git` 为 `D`），且无替代 shim 文件。

2. **删除 `runtime/demo_candidate_fixture.py`（强制）**
   - 验收：文件本体删除（`git` 为 `D`），且无等价运行时 fallback 新路径。

3. **删除 `OrchestrationState` legacy 字段（强制）**
   - 删除字段：`links`、`ingress_profile`、`evaluation`。
   - 删除/重挂相关承载定义（最小必要范围），禁止继续把上述字段保留为 schema contract。

4. **清理所有 legacy 读引用（强制）**
   - 清理对 `state.links` / `state.ingress_profile` / `state.evaluation` 的运行时读取（`orchestrator/*`、`runtime/*`、`modules/*`、`tests/*`）。

5. **最小必要校准（按需）**
   - 仅处理删除导致的导入断裂与测试修复，禁止扩 scope。

6. **验证矩阵（balanced）**
   - `python -m pytest -q`
   - `cd frontend && npm test`
   - `cd frontend && npm run build`
   - list/detail/action smoke

## Scope Out (hard)

- 不进入 `R-012` hard-filter capability。
- 不在本轮删除 `VERTICAL_SLICE_DEFAULT_CANDIDATE_ID` / default candidate（延期到 `R-019`）。
- 保留 seed candidate 测试链路（`scripts/seed_testing_candidate_from_pdf.py` + `TESTING_DESKTOP_CANDIDATE_ID`）。
- 不新增任何 contract-changing capability。

## Constraints / Architecture Boundaries

- Builder 只能决定 `how`，不得增加 `what`。
- 本轮目标是“硬删收口”，不是“改名保留兼容层”。
- 若受阻，必须 `blocked` 升级并给出最小 unblock path。

## Roadmap Alignment (Planning Phase)

- Capability area: `Deterministic Foundation`
- Selected action: `R-011.2 — Residual shim + legacy schema tail removal`
- Why now: `R-011.1` 后仍有 shim 与 legacy schema/inspection 读尾巴；先收口再进入 `R-012`。

## Debt Triage (Planning Phase)

- **Selected for this round**
  - `TD-PERSISTENCE-008 + Candidate/snapshot write ownership still split across transitional helpers`
    - 实施：删除 `candidate_aggregate.py`，逻辑回归稳定 owner。
  - `TD-DX-002 + Demo-era fixture/profile assumptions still leak into runtime path`
    - 实施：删除 `runtime/demo_candidate_fixture.py`，但不提前执行 full demo phase-out。

- **Explicitly deferred**
  - `TD-ORCHESTRATOR-011 + Hard filter still represented as scoring preference`（`R-012`）
  - `TD-API-012 + Demo bootstrap paths still mixed into API surface`（`R-019`）
  - `TD-INSPECTION-003 + Timeline is global, not candidate-scoped`（`R-019`）

## Ordered Execution Steps

1. 盘点并吸收 `candidate_aggregate.py` 的 API/调用点。
2. 删除 `modules/recruitment/candidate_aggregate.py` 并修复引用。
3. 删除 `runtime/demo_candidate_fixture.py` 并修复 shim 相关测试/导入。
4. 在 `schemas/state_schema.py` 删除 `links` / `ingress_profile` / `evaluation` 字段。
5. 清理仓库内对上述 legacy 字段的运行时读取引用。
6. 最小必要更新受影响测试（不改业务语义）。
7. 运行验证矩阵并记录结果。
8. 覆写 `FEEDBACK.md` 并标记 `done/partial/blocked`。

## Acceptance Criteria

- [ ] `modules/recruitment/candidate_aggregate.py` 已删除（`git` 为 `D`），且无替代 shim。
- [ ] `runtime/demo_candidate_fixture.py` 已删除（`git` 为 `D`），且无等价 fallback 新路径。
- [ ] `schemas/state_schema.py` 不再包含 `links` / `ingress_profile` / `evaluation` 字段。
- [ ] 全仓运行时代码不存在对 `state.links` / `state.ingress_profile` / `state.evaluation` 的读取引用。
- [ ] 未删除 `VERTICAL_SLICE_DEFAULT_CANDIDATE_ID` / default candidate 路径（该项明确延期 `R-019`）。
- [ ] `scripts/seed_testing_candidate_from_pdf.py` 默认 seed candidate 测试链路保持可用。
- [ ] `python -m pytest -q` 通过。
- [ ] `frontend` 的 `npm test` 与 `npm run build` 通过。
- [ ] `FEEDBACK.md` 完整记录步骤映射、文件清单、测试结果、风险/偏差与下一轮建议。

## Builder Feedback Reminder

`FEEDBACK.md` 必须覆盖：

- Round ID + status (`done` / `partial` / `blocked`)
- Ordered Steps 逐项完成映射
- 完整文件变更清单（`A` / `M` / `D`）
- 全部测试命令与结果
- 风险、偏差、阻塞
- Debt 处理结果（按 `Debt ID + title`）
- 下一轮建议（短句）

