# JobWant — Taiwan Job Market Intelligence

JobWant 是台灣職缺市場分析專案。104 是既有來源；目前正啟動 yes123 作為第二來源的接入工作。現有資料流將職缺擷取送入 PostgreSQL ETL，再由 Power Query 匯入 Gold 模型表，DAX measures 提供報表呈現。

## 目前狀態

- 專案入口：`PBI_JobWant.pbip`；資料流與模型邊界見 `docs/architecture/README.md`。
- yes123 adapter 與 capture 已建立；它尚未通過授權及分類代碼對應閘門，也尚未接入中央報表 Gold。本機存在 yes123 資料不代表可分析或發布。進度見 `docs/data-reference/yes123-category-acquisition-probe.md` 與 `docs/schema/`。
- 擷取工具保存不可變批次；`tools/sync_lake_to_postgres.py` 驗證後載入 PostgreSQL Bronze/Silver，Gold views 負責模型表篩選、去重、彙整與維度關聯。
- Power Query 只讀取 `gold.pbi_*` views；FactJob 以完整職業類別批次為來源，按 `jobNo` 選取最新觀測，地區不由模型查詢限定。
- Semantic Model 維持既有 relationships 與 DAX measures；技能／職類橋接和日期維度也由 Gold ETL 輸出。
- 官方職類覆蓋以 `python tools/report_category_coverage.py` 的唯讀資料庫報表為準；報表逐類顯示最新批次、area 查詢條件、API 頁數／總筆數與 Bronze/Silver 狀態。尚未完整完成的類別或分頁不一致批次不代表全台完整，規模限制見 `docs/data-reference/category-acquisition-probe.md`。
- 報表依 `docs/report-design/` 核准參考圖維護；職缺清單逐列以 `jobNo` 識別，技能統計與預覽使用正規化 bridge 欄位。
- 捕獲結果、Desktop 實際載入筆數及目前限制記錄在 `docs/operations/optimization-status.md`。歷史驗證文件保留原始日期與數字，不代表今天的資料。
- 本機唯讀入口：`python tools/validate_project.py`；Linux 結構檢查與 Windows Desktop TMDL parser 會分別回報。Desktop 套用、刷新、儲存和重開仍需完成，歷史刷新紀錄見 `docs/operations/optimization-status.md`。
- Service gateway／雲端排程尚未以目標環境驗證。Desktop 成功不代表 Service 可刷新。
- 既有 `python tools/capture_category_matrix.py` 是 104 專用 adapter，使用 104 官方 `jobcat` 代碼；yes123 會配置獨立搜尋代碼和來源職缺鍵，不共用 104 代碼。yes123 搜尋碼與候選分類目錄的對照及使用授權尚待核實，進度見 `docs/data-reference/yes123-category-acquisition-probe.md`。

## 專案導覽

| 內容 | 指引 |
| --- | --- |
| 目錄用途與本機資料規則 | [`docs/README.md`](docs/README.md) |
| 擷取、ETL、驗證與 Desktop 工具 | [`tools/README.md`](tools/README.md) |
| 多平台採集程式分層 | [`tools/acquisition/README.md`](tools/acquisition/README.md) |
| 本機 PostgreSQL 與擷取操作 | [`docs/operations/local-database.md`](docs/operations/local-database.md) |
| Active Power Query 與歷史查詢 | [`powerquery/README.md`](powerquery/README.md) |
| 核准的報表設計參考 | [`docs/report-design/README.md`](docs/report-design/README.md) |
| 歷史封存與來源說明 | [`docs/archive/README.md`](docs/archive/README.md) |

## 開始工作

開始修改前，閱讀 `AGENTS.md`、`docs/README.md` 與相關架構文件，並先盤點現有檔案和查詢。未確認的 API Schema 或商業定義一律標記 `BLOCKED`，不得猜測。
