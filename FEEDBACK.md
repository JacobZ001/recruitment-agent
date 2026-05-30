# FEEDBACK — R-014.1

## Round ID + Status

- **Round:** R-014.1 (minor, parent R-014)
- **Status:** `done`

## Step Completion Mapping

| PLAN step | Status | Notes |
|-----------|--------|-------|
| 1. `CandidateListPage` — header button, checklist, drawer, remove inline ingress | done | Scoring context button + Not ready badge; checklist above Create PDF; table下无 ingress |
| 2. `ScoringContextIngress` — Cancel, labels, inline status, Job PDF Confirm, drawer layout | done | Per-dim inline; Cancel 恢复服务端文案；editing 时 skip context hydrate |
| 3. Blocker mapping util + unit tests (8 known + fallback) | done | `frontend/src/lib/scoringContextBlockers.ts` + `.test.ts` |
| 4. npm test / build + FEEDBACK | done | 21 vitest passed; build success |

## Acceptance Criteria Traceability

| PLAN acceptance criterion | Verification |
|---------------------------|--------------|
| Job PDF: Confirm beside Choose file; empty_locked 直传 | `ScoringContextIngress` Upload Job Description 区；Choose + Confirm；无 Create 前置 |
| 已选 PDF / `pdf://` → Job 文本维 Confirm 隐藏 | `jobUsesPdfPath` disables text Confirm |
| 四维 label（含 Upload Job Description） | `DIMENSION_LABEL` + PDF section title |
| 无顶部全局绿/黄；无 drawer 内 Server materialization blockers 黄框 | Removed `successMsg`/`warnMsg`/blocker panels from ingress |
| 维度标题行 inline 状态；无 per-dim Materialization issue | `renderDimensionHeader` Saved / Needs confirm / Saving… / From PDF |
| Checklist 点击 → drawer + scroll 到维 | `ScoringReadinessChecklist` + `scrollToTarget` + section ids |
| Drawer Esc / overlay / X 关闭 | `ScoringContextDrawer` |
| formError per-dimension inline | `dimFormErrors` on header row |
| Job PDF `pdf://` 仅 inline（无 emerald 横幅） | ✓ From PDF on job header / PDF section |
| Cancel 无闪回（editing 不随 invalidate 覆盖） | `useEffect` skips dims in `editing` |
| Blocker 映射单测 8 + fallback | `scoringContextBlockers.test.ts` |
| Scoring context 仅 drawer 编辑 | Removed table-bottom ingress |
| Checklist 合并 collecting + blockers | `ScoringReadinessChecklist` |
| R-014 regression smoke (stub 手工) | PM manual checklist below |
| npm test + build | 21 passed; build OK |

## File Change Summary

| Path | Change |
|------|--------|
| `frontend/src/lib/scoringContextBlockers.ts` | A |
| `frontend/src/lib/scoringContextBlockers.test.ts` | A |
| `frontend/src/components/recruiter/ScoringReadinessChecklist.tsx` | A |
| `frontend/src/components/recruiter/ScoringContextDrawer.tsx` | A |
| `frontend/src/components/recruiter/ScoringContextIngress.tsx` | M |
| `frontend/src/components/recruiter/ScoringContextPanel.tsx` | M |
| `frontend/src/pages/CandidateListPage.tsx` | M |
| `FEEDBACK.md` | M |

## Test Commands & Results

```text
cd frontend && npm test -- --run
→ 21 passed (4 files)

cd frontend && npm run build
→ success

python -m pytest -q
→ 208 passed, 2 skipped (no backend changes)
```

## Risks, Deviations, Blockers

- **No blockers.**
- **Scope respected:** No backend / fingerprint / version changes.
- **Accepted:** Org prose 过严导致 materialization blocker 仍为 stub 行为；checklist 映射 + 点击跳转 Organization 为 R-014.1 验收定义。
- **Note:** Job 维在 `pdf://` source 或已选 PDF 时文本 Confirm 禁用；改 job 文本需 Delete 或重新 PDF Confirm（PM 冻结双 Confirm 消歧）。

## PM Manual Acceptance (stub LLM)

**Setup:** `$env:LLM_PROVIDER = "stub"`；重启 API；可选删 `data/app.db`。

1. **Layout:** Candidates 标题行右上角 **Scoring context**（collecting 时 **Not ready** badge）；其下 **Scoring readiness** checklist；再下 Create PDF；表格下 **无** ingress 大卡片。
2. **Drawer:** 点 Scoring context → 右侧 drawer；Esc / 点遮罩 / ✕ 关闭；focus 在 drawer 内。
3. **Checklist:** 四项 ✓/○/⚠；collecting + org materialization blocker 时第 4 项 ⚠ 显示人话（非 raw 英文堆叠）；点击 Organization 项 → drawer 打开并 scroll 到 Organization 区。
4. **Labels:** Describe Your Organization / Describe Your Preferences / Describe Who You're Hiring / Upload Job Description。
5. **Inline status:** Confirm 后标题行 **Saved**；editing 时 **Needs confirm**；Job PDF 成功后 **From PDF**（无 emerald 大横幅）。
6. **Cancel:** Create → 改草稿 → Cancel → 恢复服务端文案或 empty；invalidate 后草稿不被覆盖。
7. **Job PDF:** `empty_locked` 下 Choose file + **Confirm**（无需 Job Create）；已选 PDF 时 Job 文本行无 Confirm。
8. **No global banners:** drawer 内无顶部绿/黄 success；无 Server materialization blockers 黄框。
9. **formError:** 空 Confirm → 错误在该维标题旁 inline 显示。
10. **R-014 smoke:** 三维 Confirm（org 写足 company/environment/values）→ ready → Create PDF 可用；collecting 时 Create PDF disabled；Confirm 后 checklist / Processed（details 折叠）与 GET 一致。

**Builder verification:** `LLM_PROVIDER=stub` via pytest autouse; frontend vitest for blocker mapping.

## PM Closeout (Architect, 2026-05-30)

- **PM UAT:** Manual steps **1–9 passed**; overall satisfaction **high**.
- **Residual:** Org **materialization** blocker still blocks `ready` / Create PDF when prose lacks stub-parseable company / environment / values — expected per R-014.1 scope (FE readability only); PM requests **explicit format example on checklist item 1**.
- **PM routing (confirmed):** **`corrective-minor`** → **R-014.2** (org format guidance in checklist); then **`advance-major`** → **R-015** if R-014.2 UAT passes.

## Debt Handling

- **Deferred:** Org prose 解析过严 / stub normalize 引导 → FEEDBACK 建议后续 round（非 R-014.1 scope）。
- R-015 / R-016 queue unchanged per PLAN.

## Suggested Next Round

- **PM routing (confirmed):** **`corrective-minor`** → **R-014.2** — checklist Organization item shows stub-proven format (bullets + copy example) when org materialization blocker active.
- **Then:** **`advance-major`** → **R-015** (timeline + `source_ref` lineage slice) after R-014.2 UAT.
