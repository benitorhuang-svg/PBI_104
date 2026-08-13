# 104 Power BI Job Intelligence

Power BI 專案，用於將已驗證的 104 職缺搜尋 API 資料逐步整理成可分析的模型與報表。

## 目前狀態

- 專案入口：`PBI_104.pbip`
- 已驗證來源：Python + `pandas` + `cloudscraper` + Windows system proxy
- 目前模型仍由單一 `查詢` 同時處理擷取、展開、型別化與載入
- 報表目前只有一個空白頁
- 本次 Bootstrap 只建立文件、TASK 與目錄骨架，未修改 Power Query、TMDL 或 PBIR

## 開始工作

依序閱讀：

1. `AGENTS.md`
2. `README_TASKS.md`
3. `docs/architecture.md`
4. 當前唯一要執行的 `tasks/TASK-*.md`

每次只執行一個 TASK，完成獨立驗證並由人工確認後，才進入下一個 TASK。未確認的 API Schema 或商業定義一律標記 `BLOCKED`，不得猜測。
