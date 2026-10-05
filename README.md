# 104 Power BI Job Intelligence

Power BI 專案，用於將已驗證的 104 職缺搜尋 API 資料逐步整理成可分析的模型與報表。

## 目前狀態

- 專案入口：`PBI_104.pbip`
- 已驗證來源：Python + `pandas` + `cloudscraper` + Windows system proxy
- `00_Parameters` 至 `03_Staging` 已完成並持久化；`fx104GetPage` 只有 `baseUrl` 必填，其餘參數 optional
- `04_Model` 已載入 `FactJob`、`FactJobSnapshot`、`DimCompany`、`DimArea`、`DimSkill`、`DimJobCategory`、`BridgeJobSkill`；`DimDate` 為 semantic-model calculated table
- Semantic Model 已建立 6 條新 relationships 與 7 個有 description/format/display folder 的 measures
- 既有 `查詢` 表仍保留；報表已建立四頁 PBIR：職缺市場總覽、薪資市場分析、技能需求分析、職缺搜尋器
- 報表已完成去重：移除四頁重複靜態側欄與職缺搜尋器中的重複 KPI/排行榜，保留原生頁籤導覽與查詢專用篩選器
- PBIR visual-container 已修正 `drillFilterOtherVisuals` 的巢狀位置，重開 Desktop 不再產生 root-property 警告
- 報表使用 `report-design/` 的四張核准參考圖與 page design briefs；percentile、experience、skill trend/pair 等未被模型支持的元素明確標記 `BLOCKED`
- 最新驗證：重開 PBIP 後 Model partitions 可刷新至 `Ready`；DAX smoke query 回傳 FactJob 55 rows、55 jobs、35 companies、salary coverage 100%、48 jobs with skills、skill share 87.27%

## 開始工作

依序閱讀：

1. `AGENTS.md`
2. `README_TASKS.md`
3. `docs/architecture.md`
4. 當前唯一要執行的 `tasks/TASK-*.md`

每次只執行一個 TASK，完成獨立驗證並由人工確認後，才進入下一個 TASK。未確認的 API Schema 或商業定義一律標記 `BLOCKED`，不得猜測。
