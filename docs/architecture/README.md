# JobWant — 台灣職缺市場分析架構

## 目標責任邊界

資料取得、原始資料保存、驗證、清理、型別轉換、正規化、去重、關聯與彙整都由 Python/PostgreSQL ETL 處理。Power Query 僅連接 PostgreSQL 並讀取 Gold 模型輸出；Semantic Model 維持關聯與 DAX measures；報表視覺從模型欄位和 measures 呈現結果。

```text
104 source → immutable capture batches → Bronze → Silver ETL ──────────┐
                                                                         ├→ report Gold views
yes123 source → Bronze/Silver ETL → yes123 Gold → read-only FDW projection ┘
                                                                         ↓
                                                   Power Query Import → Semantic Model
                                                                         ↓
                                                           DAX measures → PBIR visuals
```

104 與 yes123 各自使用平台 adapter 和來源資料庫。批次以平台、代碼種類及原始字串識別；104 的 `jobcat`、yes123 搜尋頁的 `JcodeList` 與候選目錄代碼不互相替代。報表 Gold 目前以唯讀 FDW 投影接入 yes123 自己的 Gold scope、快照與薪資觀測，不在 Power Query 合併兩個資料庫。yes123 分類代碼與搜尋條件的 crosswalk、資料使用授權，以及技能關聯仍須釐清。進度見 `docs/data-reference/yes123-category-acquisition-probe.md`。

平台專屬擷取與載入實作分置於 `tools/acquisition/platforms/jobwant_104/` 和 `tools/acquisition/platforms/yes123/`。104 程式再依 client、capture、distributed、persistence、reporting 分組；平台中立的地理編碼、薪資解析及 schema SQL 工具位於 `tools/acquisition/shared/`。現有 `tools/*.py` 命令入口保留為相容啟動器，轉呼叫對應平台套件。

## 多平台資料隔離契約（目標）

目標是由各平台資料庫保存來源 Bronze/Silver，經驗證後由 ETL 匯入單一報表 Gold；Power BI 不直接切換或連接平台來源資料庫。來源職缺鍵以 `(source_platform, native_job_id)` 表達，Gold 另提供全域唯一 `sourceJobKey` 供模型關聯。擷取代碼保留 `code_kind` 和原始文字；跨平台分類 crosswalk 必須有可審核證據，不改寫來源原碼。詳細鍵、粒度、欄位型別及 migration 規則見 [database schema contract](../schema/contracts/database-schema-contract-v1.md)。

截至 2026-10-09，本機 `jobwant_104` 已套用 migration 21–24，`jobwant_yes123` 為 migration 19。報表模型有 11 張表：十張使用 versioned `_v21` Gold projections，FactAcquisitionCategory 透過 migration 24 合併 104 佇列與 yes123 原生分類批次狀態。Migration 23 改讀 yes123 自己的 Gold scope，避免 FDW 逐筆遠端查詢。yes123 狀態來自已持久化批次，不代表即時佇列；跨平台分類碼不做推測映射。此接入不代表資料使用授權、官方類別 crosswalk 或 yes123 技能資料已通過。

磁碟上的 TMDL 目前定義 11 張模型表。FactJob、FactJobSnapshot、FactSalaryObservation 在本次各自完成目標表刷新；三表刷新約為 16 秒、10 秒內、20 秒。這些是表級量測，其餘表原已 Ready，不能當成全模型從空快取開始的完整刷新基準。刷新期間 yes123 擷取仍在寫入，來源筆數與模型快照可能有差異。

## 資料庫拓樸與 Power BI 效能

目前 Power Query 讀取 `jobwant_104` 中 PostgreSQL Gold views，語意模型使用 Import。薪資觀測已進入 `FactSalaryObservation`，但現有薪資頁仍以 FactJob 的 salaryLow/High 為主；yes123 的期間化薪資觀測尚未納入該頁的比較指標。Import 模式互動讀取已匯入模型的資料；PostgreSQL 主要影響刷新時間。[Power BI Import 與刷新說明](https://learn.microsoft.com/en-us/power-bi/connect-data/refresh-data)

把 yes123 建在另一個 PostgreSQL database 可提供 database 層級的名稱空間和權限邊界；若兩庫仍在同一 PostgreSQL cluster，這項拆分本身不等同獨立運算資源。Power Query 改成兩個直接連線可能避開 FDW，但會把跨庫整併推入 Power Query，增加連線憑證與共享維度處理，和目前 Import reader 邊界不符。舊 FactJob scope 曾逐筆透過 FDW 查遠端職缺與維度；改由 FDW 讀取 yes123 Gold scope 後，39,392 筆 yes123 FactJob 約 16 秒完成表級刷新。因此目前不需要拆成兩條 Power BI 連線。這是本機這次量測，完整全模型刷新仍需另行記錄。

若目標是隔離擷取寫入負載對 PBI 刷新的影響，應評估獨立 PostgreSQL instance 或 read replica，再以刷新時間、Gold 查詢計畫和資源使用量做前後比較。這是基於目前 Import 架構與 PostgreSQL 拓樸的效能假設；在量測前不視為已證實改善。

yes123 的完整標準化契約仍未完成：本機 `job_current.job_no` 是單欄主鍵，平台身份以 namespaced 值承載；官方類別 crosswalk 與技能關聯仍有缺口。FactSalaryObservation 保留原始薪資值、幣別與週期狀態；yes123 薪資不填入 FactJob 的 salaryLow/High。這次本機接入不表示保存、分析或展示授權已通過；未取得必要證據前不可擴大擷取，也不可把未映射代碼當成 104 分類。

擷取工具會保留可驗證的不可變批次檔，再由 `tools/sync_lake_to_postgres.py` 驗證 manifest、頁面 checksum、分頁完整性和資料品質後寫入 PostgreSQL。這些檔案是 ETL 的原始證據；Power Query 不讀取它們，也不直接呼叫 104 API。

## Power Query 邊界

| Query Group | 責任 | Enable Load |
|---|---|---|
| `00_Parameters` | PostgreSQL host/database | 否 |
| `01_Functions` | 共用 Gold view navigation | 否 |
| `02_Source` | 讀取 `gold.pbi_*` 模型 views | 否 |
| `03_Staging` | 不參與目前載入路徑；轉換屬於資料庫 ETL | 否 |
| `04_Model` | 一對一引用 Gold view，名稱對應模型表 | 是 |

依賴只往下：Parameters/Functions → Source → Model。目前 11 張 Import 表都以 PostgreSQL Gold view 為來源。Power Query 不做 API 呼叫、JSON 展開、欄位改名、型別轉換、合併、去重或資料品質檢查。

## PostgreSQL Bronze/Silver/Gold

- Bronze 保存官方職類目錄、原始 API 頁面、請求條件、manifest 與批次狀態。失敗、頁數封頂或 API total 不一致的批次留在 Bronze，不發布到模型 Gold views。
- Silver 由 ETL 建立職缺觀測、歷史快照、公司／地點／技能／職類維度和橋接資料；鍵、數值、日期與複合欄位規則都在此處執行。
- Gold 提供模型契約：`pbi_fact_jobs`、`pbi_fact_job_snapshots`、`pbi_fact_salary_observations`、各 `pbi_dim_*`、`pbi_bridge_*` 和 `pbi_dim_date`。Gold 負責範圍選擇、最新觀測去重、座標有效值選取與日期日曆計算。yes123 職缺 scope 在來源資料庫的 Gold view 完成 join，再由 FDW 作單次投影讀取。

`FactJob` 只由帶有 104 官方 `jobcat` 查詢條件的完整批次組成。跨職類重複職缺按 `jobNo` 選一筆最新觀測；該觀測所屬批次的技能與回傳職類形成橋接。查詢不限定 `area`，因此新匯入的全區職類批次可自動進入 Gold。歷史快照保留完整來源系列，舊 keyword 快照不刪除，但不作為目前 `FactJob` 的來源。

## 目前資料覆蓋限制

目前 PostgreSQL 已有完整職類批次，但都是先前兩個地區的資料；全區職類 page-1 規模檢查估計完整抓取需約 42,466 次頁面請求，且多個職業代碼達到 150 頁上限。未完成的批次維持 Bronze-only。Gold views 不會合成缺頁資料，也不會把目前資料標示為全台完整；全區資料會在後續官方職類批次通過 ETL 後逐步增加。詳見 `docs/data-reference/category-acquisition-probe.md`。

## Semantic Model 與報表

Semantic Model 維持既有表關聯、欄位格式、DAX measures、階層和 RLS。`DimDate` 現在由 PostgreSQL Gold 輸出；DAX measures 專注於視覺呈現時的篩選與度量。PBIR 是獨立報表層，不由資料擷取或 ETL 任務重建。

## 刷新順序

1. 使用 `tools/capture_category_matrix.py` 依官方類別擷取到本機檔案；不提供 `--area` 即為不限地區。對超過 API 頁數上限的類別，先拆到更細官方職類並記錄未覆蓋項目。
2. 目前不要對報表資料庫執行 `--write` 或 `--direct-postgres`：兩者會套用版本 19 的 schema 腳本，而報表資料庫已是版本 23。該腳本可能替換 versioned federated Gold views；待 migration runner 對齊後，才可匯入通過驗證的批次。
3. 契約檢查後以 Power BI Desktop 刷新；本次 FactJob、FactJobSnapshot、FactSalaryObservation 表級刷新成功，11 張模型表皆為 `Ready`。儲存並重開 PBIP 後，再記錄全模型刷新基準。

Power Query 的資料來源認證儲存在 Power BI Desktop；M、TMDL、SQL 與文件不包含資料庫密碼。`.pbi/`、`cache.abf`、`.env` 和原始擷取檔仍是本機狀態或資料，不納入版本控制。
