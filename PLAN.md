# R-013.1 (Corrective Minor) — Dedup Governance Hardening

## Round Goal

在不扩展 R-013 功能边界的前提下，修复三项关键治理缺口：  
1) dedup 审计时间戳使用真实时钟；  
2) orphan 判定去除 in-flight 误报；  
3) dedup 热路径全量扫描性能硬化（保持 deterministic 语义）。

## Round Type

- `minor` (parent: `R-013`)

## Scope In

1. **Dedup 审计时间戳可信度修复**
   - 禁止在 dedup 治理审计中使用 `modules/recruitment/ingress.FIXED_CLOCK`（demo 固定 clock）。
   - `_dedup_audit_entry()` 与 suspected duplicate 的 `detected_at` 必须使用 `datetime.now(timezone.utc)`。
   - 保持字段名不变：`recorded_at`、`detected_at`。
   - 新增/更新测试：证明审计时间随真实时间变化，不再恒定为 `2026-05-12 14:00:00Z`。

2. **Orphan 误报修复（in-progress vs abandoned 分离）**
   - 冻结判定口径（Builder 不得自行改阈值语义）：
     - `ingress_in_progress=true`：idempotency 记录存在且 `status=IN_PROGRESS`，且未超过阈值。
     - `orphan_ingress=true`：idempotency 记录存在且 `status=IN_PROGRESS`，且 `now - created_at > ORPHAN_INGRESS_STALE_SECONDS`。
   - 默认阈值：`ORPHAN_INGRESS_STALE_SECONDS = 86400`（24h，可配置常量，测试 可覆盖）。
   - `governance_flags` 必须同时暴露：
     - `ingress_in_progress: bool`
     - `orphan_ingress: bool`（保留现有字段语义）
   - 前端 List/Detail 必须区分展示文案（processing vs orphan）。

3. **Dedup 查询性能硬化（规则不变，查询路径改造）**
   - 判定矩阵保持 R-013 不变：
     - email 或 phone 命中 => `HIGH_CONFIDENCE_DUPLICATE`
     - 仅 fingerprint 命中 => `SUSPECTED_FINGERPRINT`
   - 禁止 Builder 改判定规则，只改查询实现。

   **3.1 CandidateStore 查询接口（必须实现）**
   - 在 candidate store 抽象层新增只读方法（命名冻结）：
     - `find_candidate_ids_by_normalized_email(email) -> list[UUID]`
     - `find_candidate_ids_by_normalized_phone(phone) -> list[UUID]`
     - `find_candidate_ids_by_cv_fingerprint(fp) -> list[UUID]`
   - 方法必须排除 `exclude_candidate_ids`（与 `find_candidate_ids_by_dedup_signals` 语义一致）。

   **3.2 SQLite 实现（必须）**
   - 在 `runtime/persistence/sqlite_candidate_schema.sql` 增加 dedup 索引列（若尚未存在）：
     - `dedup_email TEXT`
     - `dedup_phone TEXT`
     - `dedup_cv_fingerprint TEXT`
   - 索引：
     - `idx_candidate_dedup_email ON candidate(dedup_email)`
     - `idx_candidate_dedup_phone ON candidate(dedup_phone)`
     - `idx_candidate_dedup_cv_fingerprint ON candidate(dedup_cv_fingerprint)`
   - 写入/更新 candidate 时同步填充 dedup_* 列（来源 `candidate.dedup_signals`）。
   - `SQLiteCandidateStore` 实现上述 `find_*` 方法，使用 indexed lookup，不再 `list_candidate_ids()` 全扫。

   **3.3 In-memory 实现（必须）**
   - `InMemoryCandidateStore` 维护内存索引（email/phone/fingerprint -> candidate_id set），在 `create/replace` 时更新索引，在 `get/list` 时走索引查询。
   - 结果必须与旧全扫语义一致（同输入同输出）。

   **3.4 Dedup 评估入口改造（必须）**
   - 新增 `evaluate_dedup_from_ingress_signals(store, signals, exclude=...)`：
     1) 若 `signals.normalized_email` 非空：查 email 索引候选集；
     2) 若 `signals.normalized_phone` 非空：查 phone 索引候选集；
     3) 若仅 fingerprint 有值：查 fingerprint 索引候选集；
     4) 合并候选集后按 R-013 规则分类 outcome。
   - `evaluate_dedup()` 内部改为调用 store 查询（可保留为兼容包装，但 create+upload 必须走 `evaluate_dedup_from_ingress_signals`）。

   **3.5 可选预热（本轮纳入，提升阻断效率）**
   - 在 `POST /candidates/cv/pdf` 的 create 路径中：
     - 先执行 email/phone 索引查询；
     - 若命中 high-confidence，立即 block（不创建 candidate）；
     - fingerprint 仅在未命中 high-confidence 时作为第二段校验并可能标记 suspected。
   - 该顺序必须写入 use case，避免 Builder 自行调整顺序。

4. **回归测试补齐**
   - 覆盖三项修复：  
     - 审计时间非固定时钟；  
     - in-progress 不误报 orphan，超阈值才 orphan；  
     - 优化路径结果与旧判定语义一致（无行为回退）。

## Scope Out

- 不扩展 dedup 新业务规则（不改 balanced/hybrid）
- 不引入 silent auto-merge / auto-delete
- 不扩展全局 ingress idempotency 到其他 endpoint（仍归 `R-015`）
- 不做 timeline/history 产品化改造（仍归 `R-014`）

## Constraints / Architecture Boundaries

- 保持 deterministic first：判定/阈值规则必须代码化且可测试。
- 不改变已对外暴露的核心 dedup 决策语义（只做硬化，不做策略改写）。
- 任何新增 flag/状态需前后端契约一致并可回归验证。

## Roadmap Alignment (Planning Phase)

- Selected action: `R-013 corrective-minor hardening before next major`
- Capability advance:
  - `Human Governance`
  - `Operational Readiness`

## Debt Triage (Planning Phase)

- **Selected for this round**
  - `TD-API-016 + Candidate deduplication, merge/link, and orphan governance`（partial close：修复审计时间与 orphan 判定语义）
  - `TD-API-004 + Candidate list is store-driven (not domain-driven)`（partial close：治理 flags 语义清晰化）
- **Explicitly deferred**
  - `TD-API-011 + HTTP ingress idempotency and replay-safe retries`（全局扩展仍归 `R-015`）
  - `TD-API-012 + API boundary coupling to bootstrap helpers (_envelope, fixed clock)`（`R-015`）

## Ordered Execution Steps

1. 修复 dedup 审计时间写入逻辑（真实 UTC），并补对应测试。  
2. 重构 orphan 判定：新增/区分 `ingress_in_progress` 与 `orphan_ingress`，定义阈值并实现后端判定。  
3. 同步 projection/API/frontend 的 governance flags 展示与文案。  
4. 为 dedup lookup 增加优化路径（SQLite + in-memory），确保结果语义与现有规则一致。  
5. 补齐 API/模块/前端回归测试并运行验证矩阵。  
6. 覆写 `FEEDBACK.md` 记录执行结果、偏差与后续建议。  

## Acceptance Criteria

- dedup 审计记录不再使用固定时钟；`recorded_at` / `detected_at` 为真实 UTC。  
- in-progress 请求不会被标记为 orphan；仅超阈值未完成记录标记 `orphan_ingress`。  
- list/detail 能区分并展示 `ingress_in_progress` 与 `orphan_ingress`（或等价语义字段）。  
- create+upload 使用 email/phone 索引预查；fingerprint 仅作第二段校验；high-confidence 在 allocate 前阻断。
- dedup 优化路径上线后，判定结果与 R-013 规则一致，不出现行为回退。  
- `python -m pytest -q`、`frontend` 测试与构建通过。  
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
