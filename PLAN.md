# R-012 (Major) — Real Ingress Baseline for Cognition Quality

## Round Goal

在 recruiter 前端建立真实 ingress 闭环：用户先完成 Scoring Context 输入并触发 processing，context ready 后再允许创建 candidate；candidate 创建流程支持“一次性上传 PDF 即创建+提交”，并在 UI 中展示 processed context 内在字段用于质量测试。

## Round Type

- `major`

## PM-Frozen Scope Decisions

- `TD-ORCHESTRATOR-011` hard-filter restoration：**无限期延期，不分配 round**。
- R-012 聚焦：**real ingress 基线 + UI 可测性**（非 hard-filter 功能）。
- 本轮 context PDF ingress 仅做 **job pdf**；`organization/recruiter_actor` PDF ingress 暂不做。
- candidate 直接上传 PDF 时，必须支持**一次性创建并上传 PDF**（单 API 调用完成）。
- “后续招聘平台自动 ingress”原则：**语义同一、边界可分**（本轮先不实现平台专用 endpoint；后续可加）。
- 单步 candidate ingress API 本轮冻结为：`POST /candidates/cv/pdf`（服务端创建 candidate_id 并提交 PDF）。
  - 请求体：`pdf_base64`、`file_name`、`correlation_id?`
  - 响应体必须包含：`candidate_id`、`ingress_accepted`、`publish_status`、`event_id`、`event_type`、`publish_result`、`state_summary?`
- Context ready 判定口径冻结：以后端枚举 `ScoringContextStatus` 为准，只有 `READY` 允许 candidate 创建；`COLLECTING` / `STALE` 统一视为 non-ready（HTTP 层按现有字符串枚举值透传）。
- 删除关键 context（organization / recruiter_actor / job）任一后，状态迁移按后端既有语义执行：若原本 `READY`，先进入 `STALE`；refresh 后在未重新产出有效 criteria 前保持 non-ready（通常为 `COLLECTING`）。前端只消费后端状态，不做本地推断。
- `TD-API-011` 本轮仅做 `POST /candidates/cv/pdf` 范围内 idempotency；全局 ingress idempotency 留待 API hardening round。
- 原子语义冻结：`POST /candidates/cv/pdf` 必须先完成 `context-ready` 校验与 idempotency 决策，再执行 create/ingress 写入；**ready 校验或 idempotency 决策阶段失败**时不得分配/写入新 candidate；**写入阶段失败**后允许已有 `candidate_id`，同 `Idempotency-Key` 且无 `SUCCEEDED` 时复用该 id 重试。

## Scope In

1. **Candidate ingress：单步 create+upload PDF**
  - 新增候选人 ingress API：一次请求完成 candidate 创建 + CV PDF 提交（替代前端两步串联 `candidate_created` + `/cv/pdf`）。
  - 保持与现有 candidate ingress 语义一致（同 use-case 语义，不引入平行业务逻辑）。
2. **Scoring Context ingress：三类文本 + job PDF + 编辑/删除**
  - 前端提供三类 context 文本输入：
    - organization
    - recruiter_actor
    - job text
  - 前端提供 job PDF 输入并调用现有 `job/pdf` ingress。
  - 三类 context（organization / recruiter_actor / job）均需支持：
    - 创建/提交（create）
    - 编辑后再提交（edit/update）
    - 删除（delete/clear）
  - 契约冻结（最小改动）：
    - upsert 继续使用现有 POST 路由（create/update 同路由，不新增 PATCH/PUT）。
    - clear 新增 DELETE 路由：`/scoring-context/organization`、`/scoring-context/recruiter-actor`、`/scoring-context/job`。
    - 上述 mutation 统一返回完整 `ScoringContextResponse`。
  - upsert 去重策略冻结：本轮不新增 upsert idempotency/dedup 机制，沿用 last-write-wins；去重仅针对 `POST /candidates/cv/pdf`。
  - 删除/清空语义（后端）必须是“清空该 context 的 authoring + structured + derived 影响并重算状态”，不是仅隐藏前端显示。
  - `DELETE` clear 的 HTTP 响应必须返回反映清空后的完整 `ScoringContextResponse`（必要时在 use case 内串联 `refresh_active_scoring_context` 重算后再返回）；**不要求**客户端在 clear 后再单独点 Refresh。
  - **Confirm 交互冻结（List 页 Scoring Context）**：用户在文本框中编辑既有 context 文案，点击 **Confirm** 时：
    - 非空文案 → `POST` upsert（对应维度路由）→ **自动** `POST /scoring-context/refresh`（同一次 Confirm 内完成，无需用户再点 Refresh）。
    - 清空文案并 Confirm（或等价 clear 语义）→ 对应 `DELETE` clear → 响应体须已反映清空/重算后的状态（同上，服务端可在 use case 内完成 refresh）。
  - job PDF ingress 仍走 `POST /scoring-context/job/pdf`；提交后同样**自动** refresh（不要求额外 Refresh 按钮）。
3. **Context-ready gating（与内部逻辑一致）**
  - 在 scoring context ready 前，前端不允许 candidate 创建入口提交。
  - 用户流程固定为：编辑 context → Confirm（upsert/clear + 自动 refresh）→ `READY` 后允许创建 candidate。
  - 前端需明确显示“未 ready 的阻塞状态/提示”。
  - 后端必须强校验 gating：当 `ScoringContextStatus != READY` 时，单步 candidate ingress API 返回可判定错误（推荐复用 `scoring_context_not_ready` 语义）。
4. **Create+upload API idempotency（R-012 bounded）**
  - 仅针对 `POST /candidates/cv/pdf` 落地 `TD-API-011` 的有界实现，不扩散到全部 ingress API。
  - 术语冻结（避免与 inspection 混淆）：
    - 本轮 **HTTP idempotency replay** = 同 `idempotency_key` 的重复 HTTP 请求返回首次成功时的 **HTTP 响应快照**（status code + JSON body）。
    - **禁止**在 API/文档/UI 中把该能力称为 inspection 的 event replay、timeline replay 或 audit trail replay。
    - inspection 的 timeline / run_history / envelope catalog 仍属既有只读观测能力，不在本轮实现范围。
  - `Idempotency-Key`（HTTP header，**必填**；错误体字段仍用 `idempotency_key_required`）：
    - 由**调用方**在发起一次“逻辑上传操作”时生成（推荐 UUID），**不是** `sha256(pdf_bytes)`，也**不是** `candidate_id` / `event_id`。
    - 缺失时返回 `422`，错误码 `idempotency_key_required`。
    - 与 payload 指纹是**两个独立维度**：`idempotency_key` = “这是不是同一次客户端操作”；payload 指纹 = “这次操作带的 PDF 内容是否相同”。
  - payload 指纹（服务端计算，用于冲突判定）：`sha256(pdf_bytes) + file_name`（不包含 `correlation_id`）。
  - 前端同一次上传复用同一 key（冻结行为，Builder 按此实现）：
    - 用户选定文件并触发上传时，**立即生成一次** `idempotency_key` 并存入本次上传会话状态（React ref/state），在**成功、用户取消、或用户重新选择另一文件**之前不得更换。
    - 同一会话内的网络超时重试、自动重试、用户连点（在 in-flight 期间应禁用提交按钮）均复用该 key 再 `POST`。
    - 用户重新选择文件或再次点击“新建上传”视为**新逻辑操作**，必须生成**新** `idempotency_key`。
  - 同 `idempotency_key` + 同 payload 指纹：执行 **HTTP idempotency replay**——严格返回首次成功的同 HTTP status code + 同 JSON body（字节级一致，存于 SQLite 响应快照）。
  - 同 `idempotency_key` + 不同 payload 指纹：返回 `409`，错误码 `idempotency_key_conflict`。
  - idempotency 生命周期冻结：
    - scope：`method + path + idempotency_key`。
    - SQLite 持久化状态至少包含：`IN_PROGRESS`、`SUCCEEDED`（及 payload 指纹、首次响应快照、`candidate_id`（分配后）、`created_at`）。
    - 同 key 命中 `IN_PROGRESS`：返回 `409`，错误码 `idempotency_key_in_progress`。
    - 失败重试：同 `Idempotency-Key` 且**尚无** `SUCCEEDED` 记录时，允许重新执行 create+upload（**非** HTTP replay）；应复用已分配的 `candidate_id`（若已写入 idempotency 记录），从失败点继续而非新建第二个 candidate。
    - TTL 固定为 **24 小时**（自记录 `created_at` 起）；清理对象为 **idempotency 索引表中的过期行**（非 candidate、非 orchestration 事件、非 audit trail）。
    - 清理策略冻结为**请求时惰性清理**：在处理 `POST /candidates/cv/pdf` 时删除 `created_at` 早于 24h 的记录；不引入独立 cron/后台任务。
    - TTL 过期后：相同 `idempotency_key` 不再命中 replay；若再次上传同 PDF，按**新请求**执行（可能创建新 candidate，除非业务层另有 dedup，属 `R-013`）。
5. **Processed context 可视化（测试面）**
  - UI 展示 `GET /scoring-context` 返回的**全部字段**（不仅 summary）用于验证 processing 结果。
  - 至少覆盖并可见：authoring texts、structured context objects、derived criteria、source refs、status/version、created/updated/ready/stale 时间字段。
6. **后续平台 ingress 兼容策略（本轮只定边界，不实现平台入口）**
  - 记录并保持“语义同一、边界可分”原则：未来招聘平台自动 ingress 可走独立 endpoint，但必须复用同一应用层语义。
7. **回归与稳定性验证**
  - 保证现有 recruiter list/detail/action surface 契约不回退。
  - 保证 deterministic orchestration 边界不被 LLM 接管（LLM 只做理解/抽取/生成）。

## Scope Out

- 不实现 hard-filter capability（已延期）。
- 不做 dedup merge policy（`R-013`）；含 **incomplete/orphan candidate** 治理（create+upload 已占位但 ingress 未成功且用户放弃重试时的残留记录）——见 `docs/architecture/ROADMAP.md` R-013。
- create+upload 中途失败：不补偿删除；同 `Idempotency-Key` 且无 `SUCCEEDED` 时复用已分配 `candidate_id` 重试补完；用户放弃重试导致的 orphan 残留不在本轮清理。
- 不做 full demo phase-out（`R-019`）。
- 不实现 `organization/recruiter_actor` PDF ingress endpoint。
- 不在本轮实现招聘平台自动 ingress endpoint。

## Constraints / Architecture Boundaries

- 程序控制流程；LLM 不控制状态迁移、路由、排序或重试策略。
- candidate create+upload 的新 API 仅是边界整合，不得引入第二套业务语义。
- context-ready gating 必须由可判定字段驱动（基于 scoring context 状态），不得靠前端猜测。
- 删除任一关键 context 后，`status` 必须回到 non-ready（以后端返回为准）；前端只消费后端状态，不做本地推断。
- `POST /candidates/cv/pdf` 必须按“ready 校验 -> idempotency 决策 -> 写入执行”的顺序实现，禁止先写后判。
- `correlation_id` 仅用于追踪/关联，不参与 idempotency payload 判定。
- `Idempotency-Key` header 必填；header key ≠ payload 指纹；HTTP idempotency replay ≠ inspection event replay。
- `POST /admin/reset`（dev reset 路径）必须同时清空 idempotency 索引表，避免本地测试出现“数据已 reset 但旧 key 仍 replay”。
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
    - Handling: 建立真实 candidate PDF ingress 主路径，避免测试注入路径主导质量判断。
  - `TD-PERSISTENCE-009 + Single active scoring_context store (not requisition-scoped yet)`
    - Handling: 固化 context ingress -> refresh -> ready -> scoring 消费链路，并在 UI 可观察。
  - `TD-API-011 + HTTP ingress idempotency and replay-safe retries`
    - Handling: 仅在 `POST /candidates/cv/pdf` 落地 idempotency key 契约、冲突判定与 SQLite 持久化，其他 ingress 留待 API hardening。
  - `TD-API-012 + API boundary coupling to bootstrap helpers (_envelope, fixed clock)`
    - Handling: 在本轮范围内做最小必要 API 边界整合（create+upload），保持应用语义单一。
- **Explicitly deferred**
  - `TD-ORCHESTRATOR-011 + Canonical hard-filter stage is not restored on recruiter ingress path`（无限期延期）

## Ordered Execution Steps

1. 盘点现有 candidate ingress 与 scoring-context ingress 调用链，确定复用路径。
2. 后端新增“单步 create+upload PDF” candidate ingress API（`POST /candidates/cv/pdf`，复用既有 use-case 语义）。
3. 为 `POST /candidates/cv/pdf` 实现执行顺序：`ready` 校验 -> `Idempotency-Key` 决策（含指纹计算）-> create+ingress 写入；**ready 校验或 idempotency 决策阶段失败**时不得分配/写入新 candidate；**写入阶段失败**后允许已有 `candidate_id`，同 `Idempotency-Key` 且无 `SUCCEEDED` 时复用该 id 重试。
4. 为 `POST /candidates/cv/pdf` 落地 idempotency（必填 `Idempotency-Key` header、payload 指纹、无 `SUCCEEDED` 时允许重试并复用 `candidate_id`、`SUCCEEDED` 时 HTTP 响应快照 replay、conflict/in-progress、SQLite 持久化、24h 惰性 TTL 清理）；`dev_reset` 清空 idempotency 表。
5. 前端 Candidate List 页新增 “Create new candidate by uploading PDF” 按钮与上传交互，并接入新 API；实现“每选定文件一次 key、会话内重试复用、换文件换新 key、提交中禁用连点”。
6. 前端新增/完善 scoring context 三类文本输入与 job PDF 输入，接入对应 API。
7. 为三类 context 实现文本框编辑 + **Confirm** 交互（非空 upsert、清空/等价 clear → DELETE）；Confirm 内自动 refresh（见 Scope In §2），删除后状态按后端既有语义（`STALE`/`COLLECTING` 等）更新 gating。
8. 新增并接入 clear 路由（3 个 DELETE）及 use case 清空+重算；保留现有 POST upsert 契约，不新增 upsert dedup 机制。
9. 以 mutation 响应 + 自动 refresh 后的 `ScoringContextStatus` 驱动 ready gating（未 ready 禁止 candidate 创建）；不要求用户 Confirm 后再手动点 Refresh。
10. 扩展 Scoring Context UI 展示 `GET /scoring-context` 全字段（authoring + structured + derived + refs + status/version + 时间字段）。
11. 增补/更新回归测试（API + frontend 交互 + edit/delete + gating 行为 + context 显示 + idempotency + 原子语义）。
12. 运行验证矩阵并覆写 `FEEDBACK.md`。

## Acceptance Criteria

- 提供并通过 `POST /candidates/cv/pdf` 单步 ingress API（一次调用创建 candidate 并提交 PDF），且响应包含 `candidate_id`。
- `POST /candidates/cv/pdf` 满足原子顺序：**ready 校验或 idempotency 决策阶段失败**时不得分配/写入新 candidate；**写入阶段失败**后允许已有 `candidate_id`，同 `Idempotency-Key` 且无 `SUCCEEDED` 时复用该 id 重试。
- `POST /candidates/cv/pdf`：`Idempotency-Key` header 必填（缺失 `422 idempotency_key_required`）；与 `sha256(pdf_bytes)+file_name` 指纹分离判定；无 `SUCCEEDED` 时同 key 可重试（复用已分配 `candidate_id`，非 replay）；有 `SUCCEEDED` 时同 key+同指纹严格 HTTP replay（同 status + 同 JSON body）；同 key+不同指纹 `409 idempotency_key_conflict`；处理中 `409 idempotency_key_in_progress`；SQLite 持久化 + 24h 惰性清理；`POST /admin/reset` 清空 idempotency 表。
- 前端上传：选定文件后生成并固定一个 key，会话内重试复用；换文件或新一次上传生成新 key；提交中禁用连点。
- Candidate List 页面可直接通过按钮上传 PDF 创建 candidate（不要求用户手工先创建 candidate）。
- Scoring Context 三类文本输入与 job PDF 输入可在 UI 提交并生效。
- Scoring Context 三类 context 均支持文本框编辑 + **Confirm**；契约为“POST upsert + DELETE clear”；Confirm 后**自动** refresh（用户无需再点 Refresh）；删除/clear 后 UI 与 gating 与后端 `ScoringContextResponse` 一致。
- `DELETE` clear 响应须反映清空并重算后的状态（可在 use case 内完成 refresh）；删除任一关键 context 后状态按后端枚举回到 non-ready（`STALE`/`COLLECTING`）；前端仅消费后端状态并阻止 candidate 创建。
- 后端在 `ScoringContextStatus != READY` 时拒绝单步 candidate ingress（可判定错误码/错误语义稳定）。
- UI 可展示 `GET /scoring-context` 返回的全部字段（含 authoring、context objects、derived criteria、source refs、状态/版本、全部时间字段）。
- 现有 recruiter list/detail/action API surface 无契约回退。
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

