# 104 Power BI Job Intelligence — Codex 任務包

## 專案目標

將已驗證可讀取的 104 職缺搜尋 API，逐步建構成：

**104 API → Power Query 分層 → Model Tables → Semantic Model → Power BI Report**

目前已確認：

- API endpoint：`https://www.104.com.tw/jobs/search/api/jobs`
- Power BI 已可透過 `Python.Execute + pandas + cloudscraper + Windows system proxy` 讀取資料。
- 測試參數：`area=6001008007,6001008006`、`keyword=powerbi`、`mode=s`、`order=15`、`page=1`、`pagesize=20`。
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
Commit
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
- Source / Staging / Function 預設不載入 Data Model；Model Tables 才載入。
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
