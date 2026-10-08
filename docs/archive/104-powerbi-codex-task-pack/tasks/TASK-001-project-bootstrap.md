# TASK-001 — Project Bootstrap

## 背景

專案：**104 Power BI Job Intelligence**。

已成功透過 Power BI `Python.Execute` 讀取 104 搜尋 API：

```text
GET https://www.104.com.tw/jobs/search/api/jobs
```

已知真實欄位包含：

```text
appearDate, applyCnt, coIndustry, coIndustryDesc, custName, custNo,
description, descSnippet, mrtDist, jobAddress, jobAddrNo, jobAddrNoDesc,
jobName, jobNameSnippet, jobNo, jobRo, jobType, lat, lon, link, major,
mrt, mrtDesc, optionEdu, period, remoteWorkType, s10, salaryHigh,
salaryLow, tags, s9, s5, d3, hrBehaviorPR, jobCat, labels,
languageRequirements, acceptRole, employeeCount, pcSkills, pddScore,
custLogo, jobSwitch, isSave, interactionRecord, isApplied, applyDate,
userApplyCount
```

## 目標

建立 Codex 後續可安全執行的專案骨架、規則、目錄與文件。

## 非目標

本 TASK 不得：

- 實作 API collector。
- 實作 Power Query 清洗。
- 建 Model Tables。
- 建 DAX。
- 修改 PBIR。
- 建 Dashboard。

## 修改範圍

允許建立：

```text
AGENTS.md
README.md
docs/
tasks/
powerquery/
samples/
report-design/
powerbi/
.gitignore
```

## 必須採用的架構

```text
00_Parameters
01_Functions
02_Source
03_Staging
04_Model
05_Semantic Model   ← 不在 PQ
06_Report
```

責任：

- Source：只取得資料、保留原始結構與 audit metadata。
- Staging：清理、標準化、正規化、nested data 拆解。
- Model：只建立供 Semantic Model 載入的表。
- Semantic Model：Relationships、Measures、Formatting、Hierarchy、RLS。
- Report：PBIR Pages / Visuals / Slicers / Formatting。

## AGENTS.md 必須包含

1. 不得硬編碼 Cookie / tokens / secrets。
2. 不得猜測 API Schema。
3. 未確認欄位標記 `BLOCKED`。
4. Source / Staging / Functions 預設不 Enable Load。
5. Model Tables 才 Enable Load。
6. 每個 TASK 獨立驗證。
7. 不自行 commit。
8. 修改 PBIR 前需 Git baseline。
9. Report 必須依 `report-design/*.png`，不得手繪風格。
10. 不得跨 TASK 擴大修改範圍。

## 執行步驟

1. 掃描目前 repo。
2. 列出可能衝突。
3. 建立缺少的目錄。
4. 建立 `AGENTS.md`。
5. 建立 `docs/architecture.md`。
6. 不實作任何 Power Query 功能。

## 驗收標準

- [ ] 專案結構完整。
- [ ] `AGENTS.md` 完成。
- [ ] `docs/architecture.md` 完成。
- [ ] 各層責任清楚。
- [ ] 沒有實際 PQ / DAX / PBIR 實作。
- [ ] 沒有 secrets。

## 回報格式

```text
FILES CHANGED
PROJECT TREE
ARCHITECTURE RULES
CONFLICTS FOUND
OPEN QUESTIONS
NEXT TASK
```
