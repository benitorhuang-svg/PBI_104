# 104 Power BI Job Intelligence

Power BI 專案，將已驗證的 104 職缺擷取送入 PostgreSQL ETL，再由 Power Query 匯入 Gold 模型表，DAX measures 提供報表呈現。

## 目前狀態

- 專案入口：`PBI_104.pbip`；資料流與模型邊界見 `docs/architecture.md`。
- 擷取工具保存不可變批次；`tools/sync_lake_to_postgres.py` 驗證後載入 PostgreSQL Bronze/Silver，Gold views 負責模型表篩選、去重、彙整與維度關聯。
- Power Query 只讀取 `gold.pbi_*` views；FactJob 以完整職業類別批次為來源，按 `jobNo` 選取最新觀測，地區不由模型查詢限定。
- Semantic Model 維持既有 relationships 與 DAX measures；技能／職類橋接和日期維度也由 Gold ETL 輸出。
- 官方職類覆蓋以 `python tools/report_category_coverage.py` 的唯讀資料庫報表為準；報表逐類顯示最新批次、area 查詢條件、API 頁數／總筆數與 Bronze/Silver 狀態。尚未完整完成的類別或分頁不一致批次不代表全台完整，規模限制見 `docs/category-acquisition-probe.md`。
- 報表依 `report-design/` 核准參考圖維護；職缺清單逐列以 `jobNo` 識別，技能統計與預覽使用正規化 bridge 欄位。
- 捕獲結果、Desktop 實際載入筆數及目前限制記錄在 `docs/optimization-status.md`。歷史驗證文件保留原始日期與數字，不代表今天的資料。
- 本機唯讀入口：`python tools/validate_project.py`；Linux 結構檢查與 Windows Desktop TMDL parser 會分別回報。Desktop 套用、刷新、儲存和重開仍需完成，歷史刷新紀錄見 `docs/optimization-status.md`。
- Service gateway／雲端排程尚未以目標環境驗證。Desktop 成功不代表 Service 可刷新。
- 後續資料擷取以 104 官方職業類別代碼為主；使用 `python tools/capture_category_matrix.py` 檢視各大類筆數，確認規模後以 `--capture` 保存完整批次。

## 專案導覽

| 內容 | 指引 |
| --- | --- |
| 目錄用途與本機資料規則 | [`docs/README.md`](docs/README.md) |
| 擷取、ETL、驗證與 Desktop 工具 | [`tools/README.md`](tools/README.md) |
| 本機 PostgreSQL 與擷取操作 | [`docs/local-database.md`](docs/local-database.md) |
| Active Power Query 與歷史查詢 | [`powerquery/README.md`](powerquery/README.md) |
| 核准的報表設計參考 | [`report-design/README.md`](report-design/README.md) |
| 歷史封存與來源說明 | [`docs/archive/README.md`](docs/archive/README.md) |

## 開始工作

開始修改前，閱讀 `AGENTS.md`、`docs/README.md` 與相關架構文件，並先盤點現有檔案和查詢。未確認的 API Schema 或商業定義一律標記 `BLOCKED`，不得猜測。
