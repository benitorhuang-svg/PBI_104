# Power Query Source Files

此目錄保存與 PBIP/TMDL 同步的 active M expressions。Power Query 僅讀取 PostgreSQL Gold views；擷取、解析、正規化、去重、彙整和品質規則在 Python/PostgreSQL ETL。

## Active query groups

- `00_parameters/`: PostgreSQL server/database 參數。
- `01_functions/`: `fxReadGoldView`，只負責連線與選取 Gold view。
- `02_source/`: 九個 `src_Pbi*` PostgreSQL view readers。
- `03_staging/`: 空；模型載入路徑不經 M staging。
- `04_model/`: 九個 `mdl_*` pass-through，對應九張 Import 表。

Source、Function、Parameter expressions 均 Disable Load；只有 `04_Model` 的九張模型表 Enable Load。DAX measures 維持在 Semantic Model，`DimDate` 也由 PostgreSQL Gold view 提供。

用 `python tools/sync_queries.py` 檢查 M/TMDL 完整同步；有意同步時使用 `python tools/sync_queries.py --write`。舊 API/JSON/staging M 查詢及其來源診斷 probe 保存在 `archive/pre-db-etl/`，不屬於 active PBIP expressions。擷取 CLI 仍使用既有 `cloudscraper`、Windows system proxy 和不可變批次驗證。

刷新前執行 `python tools/sync_lake_to_postgres.py --write`，將通過 manifest、頁面 checksum、分頁與 Silver 正規化檢查的批次載入資料庫。接著在 Desktop 執行「全部重新整理」、儲存並關閉/重開 PBIP。舊 keyword 快照保留在 `FactJobSnapshot`；目前 `FactJob` 從已匯入的完整職業類別批次按 `jobNo` 選最新觀測。資料庫現有完整職類批次仍是雙地區舊資料；不限地區採集需按 `docs/category-acquisition-probe.md` 的頁數限制逐步完成。
