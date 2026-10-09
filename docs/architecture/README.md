# JobWant — 台灣職缺市場分析架構

## 目標責任邊界

資料取得、原始資料保存、驗證、清理、型別轉換、正規化、去重、關聯與彙整都由 Python/PostgreSQL ETL 處理。Power Query 僅連接 PostgreSQL 並讀取 Gold 模型輸出；Semantic Model 維持關聯與 DAX measures；報表視覺從模型欄位和 measures 呈現結果。

```text
104 source ─┐
            ├→ immutable source capture batches → Bronze → Silver ETL → PostgreSQL Gold views
yes123 ─────┘  (onboarding; capture contract pending)
                                                        ↓
                                          Power Query Import → Semantic Model
                                                        ↓
                                                  DAX measures → PBIR visuals
```

104 是目前既有資料來源；yes123 是正在啟動的第二來源。每個平台由自己的 adapter 管理擷取代碼，批次以平台、代碼種類及原始字串共同識別；104 的 `jobcat`、yes123 搜尋頁的 `JcodeList` 與 yes123 候選目錄代碼不會互相替代。yes123 分類代碼與搜尋條件的對應、資料使用授權，以及來源職缺識別鍵仍須釐清。現有 `capture_category_matrix.py`、Bronze 批次欄位與 Silver job loader 以 104 `jobcat`／`jobNo` 契約為基礎；yes123 不會直接套用這些來源假設或併入現有 Gold，需先建立帶有來源識別的 Bronze/Silver 契約。進度見 `docs/data-reference/yes123-category-acquisition-probe.md`。

平台專屬擷取與載入實作分置於 `tools/acquisition/platforms/jobwant_104/` 和 `tools/acquisition/platforms/yes123/`。104 程式再依 client、capture、distributed、persistence、reporting 分組；平台中立的地理編碼、薪資解析及 schema SQL 工具位於 `tools/acquisition/shared/`。現有 `tools/*.py` 命令入口保留為相容啟動器，轉呼叫對應平台套件。

## 多平台資料隔離契約（目標）

目標是由各平台資料庫保存來源 Bronze/Silver，經驗證後由 ETL 匯入單一報表 Gold；Power BI 不直接切換或連接平台來源資料庫。來源職缺鍵以 `(source_platform, native_job_id)` 表達，Gold 另提供全域唯一 `sourceJobKey` 供模型關聯。擷取代碼保留 `code_kind` 和原始文字；跨平台分類 crosswalk 必須有可審核證據，不改寫來源原碼。詳細鍵、粒度、欄位型別及 migration 規則見 [database schema contract](../schema/contracts/database-schema-contract-v1.md)。

截至 2026-10-09，本機資料庫屬於部分聯邦化的過渡狀態：`jobwant_104` 已登記 migration 20，`jobwant_yes123` 登記至 19；Power BI 所連的 `jobwant_104` 缺少技能橋接和多個維度 Gold views。兩邊登記版本和實際 view set 不一致，因此目前尚未達到可完整刷新狀態。yes123 本機 Gold 有 25 筆職缺，但既有接入盤點所列的授權與代碼映射閘門仍適用；資料已存在不等於導入閘門已解除。

磁碟上的 TMDL 目前定義 10 張模型表；最近一次記錄的 Desktop 刷新驗收仍是 2026-10-06 的 9 表模型。2026-10-09 catalog 顯示 `jobwant_104` 缺 6 個模型 Gold views，因此 10 表版本尚無成功 Desktop 刷新證據。請將模型檔案盤點與 Desktop 刷新驗收分開理解。

## 資料庫拓樸與 Power BI 效能

目前 Power Query 讀取 PostgreSQL Gold views，語意模型使用 Import。Import 模式的報表互動查詢已匯入語意模型的資料；PostgreSQL 主要影響資料刷新，而不是報表視覺每次互動的讀取時間。[Power BI Import 與刷新說明](https://learn.microsoft.com/en-us/power-bi/connect-data/refresh-data)

把 yes123 建在另一個 PostgreSQL database 可提供 database 層級的名稱空間和權限邊界；初期預計與 `jobwant_104` 由同一個 PostgreSQL server cluster 管理，因此這項拆分本身不等同於獨立運算資源，也不保證刷新變快。PostgreSQL 建議彼此相關、需要共享資源的專案使用同一 database 的不同 schemas；一個 client connection 也只能連到一個 database。[PostgreSQL database 管理說明](https://www.postgresql.org/docs/current/manage-ag-overview.html) ETL 會分別連接來源庫與集中 Gold，經驗證後寫入 Gold；Power BI 仍只讀集中 Gold。

若目標是隔離擷取寫入負載對 PBI 刷新的影響，應評估獨立 PostgreSQL instance 或 read replica，再以刷新時間、Gold 查詢計畫和資源使用量做前後比較。這是基於目前 Import 架構與 PostgreSQL 拓樸的效能假設；在量測前不視為已證實改善。

yes123 的目標 schema/loader 契約仍未完成：目前 `job_current.job_no` 是單欄主鍵，平台身份靠 namespaced 值承載，分類維度仍以 104 的 `BIGINT` 代碼為主。雖然本機已有 25 筆 yes123 列，但這不表示保存、分析或展示授權與分類 crosswalk 已通過；依 [yes123 導入盤點](../data-reference/yes123-category-acquisition-probe.md)，未取得必要證據前不可擴大擷取，也不可把未映射代碼當成 104 分類。

擷取工具會保留可驗證的不可變批次檔，再由 `tools/sync_lake_to_postgres.py` 驗證 manifest、頁面 checksum、分頁完整性和資料品質後寫入 PostgreSQL。這些檔案是 ETL 的原始證據；Power Query 不讀取它們，也不直接呼叫 104 API。

## Power Query 邊界

| Query Group | 責任 | Enable Load |
|---|---|---|
| `00_Parameters` | PostgreSQL host/database | 否 |
| `01_Functions` | 共用 Gold view navigation | 否 |
| `02_Source` | 讀取 `gold.pbi_*` 模型 views | 否 |
| `03_Staging` | 不參與目前載入路徑；轉換屬於資料庫 ETL | 否 |
| `04_Model` | 一對一引用 Gold view，名稱對應模型表 | 是 |

依賴只往下：Parameters/Functions → Source → Model。目前 10 張 Import 表都以 PostgreSQL Gold view 為來源。Power Query 不做 API 呼叫、JSON 展開、欄位改名、型別轉換、合併、去重或資料品質檢查。

## PostgreSQL Bronze/Silver/Gold

- Bronze 保存官方職類目錄、原始 API 頁面、請求條件、manifest 與批次狀態。失敗、頁數封頂或 API total 不一致的批次留在 Bronze，不發布到模型 Gold views。
- Silver 由 ETL 建立職缺觀測、歷史快照、公司／地點／技能／職類維度和橋接資料；鍵、數值、日期與複合欄位規則都在此處執行。
- Gold 提供模型契約：`pbi_fact_jobs`、`pbi_fact_job_snapshots`、各 `pbi_dim_*`、`pbi_bridge_*` 和 `pbi_dim_date`。Gold 負責範圍選擇、最新觀測去重、座標有效值選取與日期日曆計算。

`FactJob` 只由帶有 104 官方 `jobcat` 查詢條件的完整批次組成。跨職類重複職缺按 `jobNo` 選一筆最新觀測；該觀測所屬批次的技能與回傳職類形成橋接。查詢不限定 `area`，因此新匯入的全區職類批次可自動進入 Gold。歷史快照保留完整來源系列，舊 keyword 快照不刪除，但不作為目前 `FactJob` 的來源。

## 目前資料覆蓋限制

目前 PostgreSQL 已有完整職類批次，但都是先前兩個地區的資料；全區職類 page-1 規模檢查估計完整抓取需約 42,466 次頁面請求，且多個職業代碼達到 150 頁上限。未完成的批次維持 Bronze-only。Gold views 不會合成缺頁資料，也不會把目前資料標示為全台完整；全區資料會在後續官方職類批次通過 ETL 後逐步增加。詳見 `docs/data-reference/category-acquisition-probe.md`。

## Semantic Model 與報表

Semantic Model 維持既有表關聯、欄位格式、DAX measures、階層和 RLS。`DimDate` 現在由 PostgreSQL Gold 輸出；DAX measures 專注於視覺呈現時的篩選與度量。PBIR 是獨立報表層，不由資料擷取或 ETL 任務重建。

## 刷新順序

1. 使用 `tools/capture_category_matrix.py` 依官方類別擷取到本機檔案；不提供 `--area` 即為不限地區。對超過 API 頁數上限的類別，先拆到更細官方職類並記錄未覆蓋項目。
2. 目前不要對報表資料庫執行 `--write` 或 `--direct-postgres`：兩者會套用版本 19 的 schema 腳本，而報表資料庫已是版本 20。待 migration runner 與 Gold view set 完成對齊後，才可匯入通過驗證的批次。
3. Gold views 通過 schema 契約檢查後，Power BI Desktop 才執行全部重新整理；核對 10 張模型表、鍵粒度與關聯，再儲存並重開 PBIP。新版 10 表模型目前尚無 Desktop 刷新驗收紀錄。

Power Query 的資料來源認證儲存在 Power BI Desktop；M、TMDL、SQL 與文件不包含資料庫密碼。`.pbi/`、`cache.abf`、`.env` 和原始擷取檔仍是本機狀態或資料，不納入版本控制。
