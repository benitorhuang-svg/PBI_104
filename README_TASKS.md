# 104 Power BI Job Intelligence — Codex 任務包

## 現有專案適配

- 現有 PBIP 已位於專案根目錄；`PBI_104.pbip`、`PBI_104.Report/`、`PBI_104.SemanticModel/` 視為原規劃中的 `powerbi/`，不得為了符合範例樹而搬動。
- `00_Parameters` 至 `04_Model` 是 Power Query Query Groups；`powerquery/` 保存完整 M expressions，應和 Semantic Model 的 TMDL expressions 同步。
- 此 checkout 有 Git baseline `162a193`，並保留使用者未提交的既有修改。不得初始化 Git、commit 或 publish，除非使用者另行要求。
- 原始建置階段依序完成；後續優化與資料來源擴充使用 TASK-007 起的增補規格。

## 專案目標

將 104 官方職業類別擷取送入資料庫 ETL，再建構成：

**104 API → immutable captures → PostgreSQL Bronze/Silver/Gold → Power Query Import → Semantic Model/DAX → Power BI Report**

目前已確認：

- API endpoint：`https://www.104.com.tw/jobs/search/api/jobs`
- 新的主要擷取方式使用 104 官方 `jobcat` 職類代碼；keyword 擷取保留給既有批次與明確的舊式查詢。
- API 擷取由 Python ETL 使用既有 `cloudscraper + Windows system proxy`；Power Query 不呼叫 API。
- 舊 keyword 批次保留供歷史追溯，不作為目前 FactJob 來源。FactJob 以官方 `jobcat` 職類批次為基礎，Gold 不限制地區。
- 職類全台規模仍受 104 API 150 頁上限影響；既有完整職類批次是先前兩地區資料，未完成的全台採集不宣稱為全台完整。
- 禁止把 Cookie、`cf_clearance`、`__cf_bm`、session token、proxy credential 硬編碼進 repo。
- Report Page 已有圖片參考，正式報表不可使用手繪風格。

## 執行順序

1. `tasks/TASK-001-project-bootstrap.md`
2. `tasks/TASK-002-pq-source.md`
3. `tasks/TASK-003-pq-staging.md`
4. `tasks/TASK-004-model-tables.md`
5. `tasks/TASK-005-semantic-model.md`
6. `tasks/TASK-006A-report-page-01.md`
7. `tasks/TASK-006B-report-page-02.md`
8. `tasks/TASK-006C-report-page-03.md`
9. `tasks/TASK-006D-report-page-04.md`
10. `tasks/TASK-007-project-optimization.md`
11. `tasks/TASK-008-category-acquisition.md`（已完成；API 分頁品質限制記錄於擷取檢查文件）
12. `tasks/TASK-009-salary-normalization.md`（已完成；期間不明者保留待檢核，幣別預設 TWD）
13. `tasks/TASK-010-address-geocoding.md`（已完成；schema v7 與 Desktop 全表刷新、儲存、重開均已驗收）
14. `tasks/TASK-011-database-snapshot-aggregate.md`（已完成；所有模型表移至 PostgreSQL Gold，Power Query 僅讀取，FactJob 依職業類別）
15. `tasks/TASK-012-report-filter-repair.md`（已完成；官方職類與職稱切片器通過 Desktop 篩選驗證）
16. `tasks/TASK-013-refresh-performance.md` (completed; Gold view buffer visits reduced; no repeatable full-refresh gain established).
17. `tasks/TASK-014-direct-postgres-capture.md` (PostgreSQL category capture without per-page job JSON files).
18. `tasks/TASK-015-area-key-collation.md` (completed; preserve byte-distinct area keys under Power BI text comparison).

禁止跳階執行。

## 建議工作節奏

```text
TASK
 ↓
Codex inventory / plan
 ↓
Implement
 ↓
Test / Validate
 ↓
/review
 ↓
git diff 人工檢查
 ↓
使用者明確要求後才 Commit
 ↓
Next TASK
```

## 建議專案結構

```text
project-root/
├─ AGENTS.md
├─ README.md
├─ README_TASKS.md
├─ docs/
│  ├─ architecture.md
│  ├─ api-schema.md
│  ├─ data-quality-report.md
│  ├─ data-model.md
│  └─ dashboard-spec.md
├─ tasks/
├─ powerquery/
│  ├─ 00_parameters/
│  ├─ 01_functions/
│  ├─ 02_source/
│  ├─ 03_staging/
│  └─ 04_model/
├─ samples/
├─ report-design/
│  ├─ page-01-market-overview.png
│  ├─ page-02-salary.png
│  ├─ page-03-skills.png
│  └─ page-04-job-explorer.png
└─ powerbi/
   └─ <PBIP project>
```

## Codex 共通規則

- 開始 TASK 前先閱讀 `AGENTS.md` 與本 TASK。
- 先 inventory，再修改。
- 不得猜測未確認的 API Schema。
- 不得跨 TASK 擴大 scope。
- 不得硬編碼 Cookie / token / secret。
- 未確認欄位標記 `BLOCKED`。
- Parameters / Functions / Source 預設不載入 Data Model；只有 Model Tables 載入。Active Power Query 不做 ETL。
- Semantic Model 不屬於 Power Query。
- 修改 PBIR 前先建立 Git baseline。
- 不自行 commit，除非使用者明確要求。

每個 TASK 完成後固定回報：

```text
FILES CHANGED
IMPLEMENTATION
TEST RESULTS
RISKS / BLOCKERS
NEXT TASK
```
