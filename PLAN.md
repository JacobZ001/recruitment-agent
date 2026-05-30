# R-013.2 (Corrective Minor) — Dedup Index Cutover & Post-Parse Duplicate Detection

## Round Goal

在 R-013.1 基线上关闭两项残余偏差：  
1) SQLite dedup 索引列采用 **本地 DB 文件删除 cutover**（仅删 `data/app.db`），不再依赖运行时 `ALTER` + backfill；  
2) `POST /candidates/cv/pdf` 在 **cv_parse 持久化之后** 增加 deterministic 二次 high-confidence dedup，避免 pre-create 正则漏检 email 导致静默重复候选人。

## Round Type

- `minor` (parent: `R-013`)

## Scope In

### 1. SQLite dedup 索引 — 重置 cutover（PM 选定：删库，不做 formal migration）

**1.1 本地 cutover（冻结，无 Builder 选项）**

- 本地 / 单租户开发环境：**不保留** 无 `dedup_*` 列的旧库。
- **唯一**升级步骤（文档与 README 均写此条，不得写 `POST /admin/reset` 作为等价替代）：
  1. 停止 API 进程；
  2. 删除仓库根下 `data/app.db`；
  3. 若存在则一并删除 `data/app.db-wal`、`data/app.db-shm`；
  4. 重启 API（由现有启动逻辑创建含 dedup 列的新库）。
- **Scope out**：本轮不实现 versioned migration runner、不扩展 `TD-PERSISTENCE-001` 正式迁移框架（仍归 R-016）；不修改 `/admin/reset` 语义。

**1.2 代码改造（必须）**

- 从 `SQLiteCandidateStore` **移除** `_migrate_dedup_columns()` 与 `_backfill_dedup_columns()` 及对它们的 `__init__` 调用。
- 依赖 canonical `runtime/persistence/sqlite_candidate_schema.sql`（已含 `dedup_email` / `dedup_phone` / `dedup_cv_fingerprint` 与索引）在 **新建 DB** 时通过现有 `executescript` 创建完整 schema。
- `create` / `replace` 路径继续同步写入 `dedup_*` 列（R-013.1 行为保持不变）。
- 在 `frontend/README.md`（Database reset 小节）将 **R-013.2 cutover** 写为上述四步（仅删 `data/app.db`）；旧库不保证兼容。

**1.3 测试（必须）**

- 调整/移除依赖运行时 `ALTER`+backfill 的测试（若有）；保留「新 store + schema 含 dedup 列 + indexed lookup」覆盖。
- 可选：新增测试断言 **无** `_migrate_dedup_columns` 方法（或等价：打开仅含旧三列的 DB 会失败/不自动修复——若实现为 fail-fast 则测 fail-fast；若仅删迁移则旧 DB 由运维负责删除，测试只用 tmp_path 新库）。

### 2. Post-parse 二次 high-confidence dedup（PM 选定：方案 A）

**2.1 触发点（冻结）**

- 仅 `create_and_submit_cv_pdf` 路径，在 `submit_cv(...)` **成功返回且** orchestrator 已将 `candidate.dedup_signals` 持久化之后执行（从 store `get` 最新 `Candidate`）。
- **不在** pre-create 阶段重复调用 LLM；二次判定输入必须来自 **已持久化的** `candidate.dedup_signals`（及既有 normalize 规则），不得新增 LLM 调用。

**2.2 判定逻辑（冻结）**

- 从 `Candidate.dedup_signals` 构造 `DedupIngressSignals`（email / phone / fingerprint 字段映射与 R-013 一致）。
- 调用 `evaluate_dedup_high_confidence_from_ingress_signals(store, signals, exclude_candidate_ids=[new_candidate_id])`。
- 若 `outcome == HIGH_CONFIDENCE_DUPLICATE`：
  - **不** 删除已创建 candidate、**不** 回滚 idempotency 成功态、**不** 改 HTTP 200 整体语义（请求已完成 ingress）。
  - 调用新 helper（命名冻结）：`_mark_candidate_post_ingress_duplicate(runtime, candidate_id, dedup_eval)`，写入 `candidate.extensions.dedup`：
    - `status`: **`post_ingress_duplicate`**（新枚举值，不得复用 `suspected_duplicate`）
    - `pending_resolution`: `true`
    - `matches`: 与 R-013 相同 JSON 形状（`dedup_matches_to_json`）
    - `detected_at`: 真实 UTC（与 R-013.1 `_dedup_now_utc()` 一致）
    - `audit`: `[]`（初始为空；后续 link/keep-separate 追加）
  - 若 create+upload 响应体已含 `dedup` 字段，在 **同一次响应** 中补充/覆盖为 post-ingress 语义（`status: post_ingress_duplicate`，`pending_resolution: true`，含 `matches`）；**必须与库内 `extensions.dedup` 最终状态一致**（在 `mark_succeeded` 之前写入）。

**2.2.1 `suspected_duplicate` 与 `post_ingress_duplicate` 叠加（PM 冻结，Builder 不得改语义）**

同一次 create+upload 可能同时出现：pre-create fingerprint → `suspected_dedup`；post-parse email/phone → high-confidence。

- **最终 `status`（单一）**：若 post-parse 命中 high-confidence → **`post_ingress_duplicate`**（优先于 `suspected_duplicate`）；仅 fingerprint 且 post-parse 未命中 → **`suspected_duplicate`**。
- **禁止**两种 status 并存；禁止 post-parse 静默丢弃 suspected 信号。
- **`matches` 合并**：若两阶段均有 matches，写入 **并集**（按 `candidate_id` 去重）；同一候选人的 `match_kinds` 合并（如同时含 fingerprint 与 `normalized_email`）。实现可复用确定性 helper（命名建议：`_merge_dedup_matches`）。
- **`create_and_submit_cv_pdf` 执行顺序（冻结）**：
  1. `submit_cv(...)` 成功且 candidate 已持久化；
  2. post-parse 评估；若 high-confidence → `_mark_candidate_post_ingress_duplicate`（合并 suspected matches，若有）；
  3. **仅当** 步骤 2 未命中且 pre-create 存在 `suspected_dedup` → `_mark_candidate_suspected_duplicate`；
  4. 组装 `response_body["dedup"]`（反映步骤 2/3 最终态）；
  5. `mark_succeeded`（idempotency 快照含最终 `dedup`）。

**2.2.2 In-flight 重试与 post-parse 幂等（PM 冻结）**

- `is_retry` 路径（同一 `Idempotency-Key`、`IN_PROGRESS`、已分配 `candidate_id`）在 `submit_cv` 之后 **仍须**执行 post-parse（pre-create 不再跑，但 parse 后 signals 仍可能首次暴露 email 冲突）。
- 对同一 `candidate_id`，post-parse 标记须 **幂等**：
  - 若已为 `post_ingress_duplicate` + `pending_resolution: true`，且 matches 与本次评估一致（归一化后）→ 不重复追加 `audit`、不改变语义；
  - 允许 `replace` 为等价状态；禁止每次重试堆叠 audit 或翻转 `status`。
- 模块测试须覆盖：对同一 candidate 连续两次 post-parse 标记，断言 `extensions.dedup` 与 `audit` 条数稳定。

**2.3 与 pre-create 路径关系（冻结）**

- pre-create：保持 R-013.1 顺序（email/phone 索引 → block；fingerprint → suspected）。
- post-parse：仅补 **high-confidence**（email/phone）；**不** 在 post-parse 阶段新增 fingerprint suspected（fingerprint suspected 仍仅 pre-create）。

**2.4 API / 投影 / 前端（必须）**

- `governance_flags` / OpenAPI / `frontend/src/api/types.ts`：`dedup_status` 允许新值 `post_ingress_duplicate`。
- `CandidateGovernancePanel`：将 `post_ingress_duplicate` 与 `suspected_duplicate` 同等对待——展示治理条、`pending_resolution` 时展示 link / keep-separate（**无 auto-merge**）。
- `link_candidate_dedup` / `keep_separate_candidate_dedup`：须接受 source 状态为 `post_ingress_duplicate`（与 suspected 相同治理流）。

**2.5 测试（必须，PM 冻结分层）**

**说明**：post-parse 读取的是 **cv_parse 持久化后的** `candidate.dedup_signals`，不是 pre-create 正则。API 端到端路径依赖测试环境内 **StubLLMProvider**（`tests/conftest.py`）的解析输出；**不**为 post-parse 新增 LLM 调用。

| 层级 | 职责 | 要求 |
|------|------|------|
| **模块测试（主覆盖）** | 规则、合并、幂等 | 不依赖 LLM：`InMemoryCandidateStore` seed A；对 B 直接 `replace` 带 `dedup_signals` 或调用 use-case/post-parse helper；覆盖 post-parse 标记、**suspected+post-parse matches 并集**、**重复 post-parse 幂等** |
| **API 测试（接线）** | 至多 **1** 条 happy-path | `POST /candidates/cv/pdf` 后 `GET /candidate/{id}` → `dedup_status == post_ingress_duplicate`；须 **显式设计** PDF 文本 + stub 行为：PDF 正文避免 regex 提前 block，且 stub 对应该 CV 返回与 A 冲突的 `primary_email`；若 stub 无法稳定产出 email，在 `FEEDBACK.md` 记录偏差，不得假绿 |
| **回归** | R-013 / R-013.1 | pre-create high-confidence block 不变；indexed lookup 测试仍绿 |

**模块测试最低清单：**

- A 已索引 email；B parse 后同 email → `post_ingress_duplicate`，matches 含 A。
- pre-create 无 regex email、B 仅有 parse 后 email 冲突 → post-parse 补洞。
- 同请求 pre-create fingerprint suspected + post-parse email 冲突 → 最终 `post_ingress_duplicate`，matches 并集含 fingerprint 与 email kinds。
- 同一 candidate 连续两次 post-parse 标记 → dedup 状态与 audit 稳定（幂等）。

## Scope Out

- 正式 SQLite schema migration / `schema_migrations` 表（R-016）
- post-parse 硬 block / 自动删除重复 candidate / 自动 merge
- 扩展 dedup 判定矩阵（balanced/hybrid 规则不变）
- R-014 timeline、R-015 全局 idempotency / `FIXED_CLOCK` 全路径 cutover

## Constraints / Architecture Boundaries

- 判定逻辑保持 deterministic；post-parse 不得引入 LLM。
- 人类治理：仅 flag + link/keep-separate，与 R-013 一致。
- 旧本地 DB 由 PM 选定 **重置 cutover** 处理；Builder 不得实现 silent ALTER 回填作为替代方案。

## Roadmap Alignment (Planning Phase)

- Routing: `corrective-minor` (parent R-013), after R-013.1 snapshot
- Selected action: close R-013 dedup residual deviations before R-014
- Capability advance: `Human Governance`, `Operational Readiness`

## Debt Triage (Planning Phase)

- **Selected for this round — target `RESOLVED` after verification**
  - `TD-API-016 + Candidate deduplication, merge/link, and orphan governance`（见下方「TD-API-016 关账标准」；R-013.2 交付 post-parse + 删库 cutover 后 Architect 在关账时将条目标为 `RESOLVED` 并归档至 `tech_debt/resolved.md`）
- **Optional doc-only touch（不扩 scope）**
  - `TD-PERSISTENCE-001`：在条目 `Current decision` 增加一句「当前本地 dedup 列升级 = 删除 `data/app.db`」，**不**标 RESOLVED（正式 migration 仍归 R-016）
- **Explicitly deferred（不得在本轮实现）**
  - `TD-API-004`（list 仍 store-driven）、`TD-API-011`、`TD-API-012`、`TD-API-015`
  - typed `extensions.dedup` / cross-candidate merge（见 TD-API-016 关账时的 intentional non-goals）

### TD-API-016 关账标准（R-013.2 完成后 Architect 核对）

视为 **RESOLVED** 当且仅当以下 **已全部** 为真（剩余项记入 resolved 归档的 intentional non-goals，不阻止关账）：

| 必须已交付 | 轮次 |
|------------|------|
| balanced/hybrid 判定 + create+upload pre-create block / suspected | R-013 |
| link / keep-separate + extension audit + 真实 UTC 时间戳 | R-013 / R-013.1 |
| `ingress_in_progress` vs stale `orphan_ingress` | R-013.1 |
| 索引 dedup lookup + email/phone pre-check | R-013.1 |
| post-parse high-confidence → `post_ingress_duplicate` + UI 治理 | **R-013.2** |
| dedup 索引 schema：新库靠 `sqlite_candidate_schema.sql`；本地升级文档 = 删 `data/app.db` | **R-013.2** |

**Intentional non-goals（关账时写入 resolved 归档，不算未清债务）：**

- 无 cross-candidate **数据 merge**（仅 link 元数据，产品决策）
- `extensions.dedup` 仍为 dict，无独立 Pydantic 契约（后续 `TD-CONTRACTS-004` / 专债）
- 其他 ingress 路径仍可能用 `FIXED_CLOCK`（`TD-API-012` / R-019）
- 候选人 list 仍 store-driven（`TD-API-004`）

## Ordered Execution Steps

1. 移除 SQLite 运行时 `ALTER`+backfill；确认新库 schema 与 `create`/`replace` 索引写入正确；更新 README（仅 `data/app.db` 删除四步）。  
2. 实现 `_mark_candidate_post_ingress_duplicate`、matches 合并 helper，及 `create_and_submit_cv_pdf` 冻结顺序（§2.2.1）与 retry 幂等（§2.2.2）。  
3. 同步 API schema、projection、`governance_flags`、前端治理面板。  
4. 补齐模块 + API 测试；运行 `python -m pytest -q`、`frontend` test + build。  
5. 覆写 `FEEDBACK.md`。

## Acceptance Criteria

- 文档明确：R-013.2 后本地升级**仅**通过删除 `data/app.db`（及 WAL/SHM）；代码路径无 `_migrate_dedup_columns` / `_backfill_dedup_columns`。  
- parse 后 email/phone 与既有候选人 high-confidence 冲突时，新候选人标记 `post_ingress_duplicate` + `pending_resolution`，list/detail 可见。  
- link / keep-separate 对 `post_ingress_duplicate` 可用；无 auto-merge。  
- suspected + post-parse 同请求：最终 status 与 matches 符合 §2.2.1；idempotency 响应体与库一致。  
- in-flight 重试 post-parse 幂等符合 §2.2.2；模块测试覆盖。  
- 测试分层符合 §2.5（模块主覆盖 + 至多一条可控 API 接线测）。  
- pre-create block 与 R-013.1 索引行为无回归。  
- 全量测试与前端构建通过；`FEEDBACK.md` 完整。

## Builder Feedback Reminder

`FEEDBACK.md` 必须覆盖：Round ID + status、PLAN 步骤映射、文件变更、测试结果、风险/偏差、债务处理（`Debt ID + title`）、下一轮建议。
