# 104 Power BI Job Intelligence

Power BI 專案，將已驗證的 104 職缺擷取送入 PostgreSQL ETL，再由 Power Query 匯入 Gold 模型表，DAX measures 提供報表呈現。

## 目前狀態

- 專案入口：`PBI_104.pbip`；目前架構工作規格為 `tasks/TASK-011-database-snapshot-aggregate.md`。
- 擷取工具保存不可變批次；`tools/sync_lake_to_postgres.py` 驗證後載入 PostgreSQL Bronze/Silver，Gold views 負責模型表篩選、去重、彙整與維度關聯。
- Power Query 只讀取 `gold.pbi_*` views；FactJob 以完整職業類別批次為來源，按 `jobNo` 選取最新觀測，地區不由模型查詢限定。
- Semantic Model 維持既有 relationships 與 DAX measures；技能／職類橋接和日期維度也由 Gold ETL 輸出。
- 全台職類擷取尚未完成：目前資料庫的完整職類批次仍是舊雙地區批次；不限地區規模檢查顯示大量類別觸及 API 150 頁上限，詳見 `docs/category-acquisition-probe.md`。
- 四頁報表依 `report-design/` 參考圖更新；職缺清單逐列以 `jobNo` 識別，技能統計與預覽使用正規化 bridge 欄位。
- 捕獲結果、Desktop 實際載入筆數及目前限制記錄在 `docs/optimization-status.md`。歷史驗證文件保留原始日期與數字，不代表今天的資料。
- 本機唯讀入口：`python tools/validate_project.py`；Desktop 套用、刷新、儲存和重開仍需完成，刷新錯誤與目前狀態記錄於 `docs/optimization-status.md`。
- Service gateway／雲端排程尚未以目標環境驗證。Desktop 成功不代表 Service 可刷新。
- 後續資料擷取以 104 官方職業類別代碼為主；使用 `python tools/capture_category_matrix.py` 檢視各大類筆數，確認規模後以 `--capture` 保存完整批次。

## 開始工作

依序閱讀：

1. `AGENTS.md`
2. `README_TASKS.md`
3. `docs/architecture.md`
4. 當前唯一要執行的 `tasks/TASK-*.md`

每次只執行一個 TASK，完成獨立驗證並由人工確認後，才進入下一個 TASK。未確認的 API Schema 或商業定義一律標記 `BLOCKED`，不得猜測。
