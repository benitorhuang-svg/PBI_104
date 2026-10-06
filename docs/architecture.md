# 104 Power BI Job Intelligence 架構

## 目標責任邊界

資料取得、原始資料保存、驗證、清理、型別轉換、正規化、去重、關聯與彙整都由 Python/PostgreSQL ETL 處理。Power Query 僅連接 PostgreSQL 並讀取 Gold 模型輸出；Semantic Model 維持關聯與 DAX measures；報表視覺從模型欄位和 measures 呈現結果。

```text
104 API → immutable capture batches → Bronze → Silver ETL → PostgreSQL Gold views
                                                        ↓
                                          Power Query Import → Semantic Model
                                                        ↓
                                                  DAX measures → PBIR visuals
```

擷取工具會保留可驗證的不可變批次檔，再由 `tools/sync_lake_to_postgres.py` 驗證 manifest、頁面 checksum、分頁完整性和資料品質後寫入 PostgreSQL。這些檔案是 ETL 的原始證據；Power Query 不讀取它們，也不直接呼叫 104 API。

## Power Query 邊界

| Query Group | 責任 | Enable Load |
|---|---|---|
| `00_Parameters` | PostgreSQL host/database | 否 |
| `01_Functions` | 共用 Gold view navigation | 否 |
| `02_Source` | 讀取 `gold.pbi_*` 模型 views | 否 |
| `03_Staging` | 不參與目前載入路徑；轉換屬於資料庫 ETL | 否 |
| `04_Model` | 一對一引用 Gold view，名稱對應模型表 | 是 |

依賴只往下：Parameters/Functions → Source → Model。所有 9 張 Import 表都以 PostgreSQL Gold view 為來源。Power Query 不做 API 呼叫、JSON 展開、欄位改名、型別轉換、合併、去重或資料品質檢查。

## PostgreSQL Bronze/Silver/Gold

- Bronze 保存官方職類目錄、原始 API 頁面、請求條件、manifest 與批次狀態。失敗、頁數封頂或 API total 不一致的批次留在 Bronze，不發布到模型 Gold views。
- Silver 由 ETL 建立職缺觀測、歷史快照、公司／地點／技能／職類維度和橋接資料；鍵、數值、日期與複合欄位規則都在此處執行。
- Gold 提供模型契約：`pbi_fact_jobs`、`pbi_fact_job_snapshots`、各 `pbi_dim_*`、`pbi_bridge_*` 和 `pbi_dim_date`。Gold 負責範圍選擇、最新觀測去重、座標有效值選取與日期日曆計算。

`FactJob` 只由帶有 104 官方 `jobcat` 查詢條件的完整批次組成。跨職類重複職缺按 `jobNo` 選一筆最新觀測；該觀測所屬批次的技能與回傳職類形成橋接。查詢不限定 `area`，因此新匯入的全區職類批次可自動進入 Gold。歷史快照保留完整來源系列，舊 keyword 快照不刪除，但不作為目前 `FactJob` 的來源。

## 目前資料覆蓋限制

目前 PostgreSQL 已有完整職類批次，但都是先前兩個地區的資料；全區職類 page-1 規模檢查估計完整抓取需約 42,466 次頁面請求，且多個職業代碼達到 150 頁上限。未完成的批次維持 Bronze-only。Gold views 不會合成缺頁資料，也不會把目前資料標示為全台完整；全區資料會在後續官方職類批次通過 ETL 後逐步增加。詳見 `docs/category-acquisition-probe.md`。

## Semantic Model 與報表

Semantic Model 維持既有表關聯、欄位格式、DAX measures、階層和 RLS。`DimDate` 現在由 PostgreSQL Gold 輸出；DAX measures 專注於視覺呈現時的篩選與度量。PBIR 是獨立報表層，不由資料擷取或 ETL 任務重建。

## 刷新順序

1. 使用 `tools/capture_category_matrix.py` 依官方類別擷取；不提供 `--area` 即為不限地區。對超過 API 頁數上限的類別，先拆到更細官方職類並記錄未覆蓋項目。
2. 執行 `python tools/sync_lake_to_postgres.py --write`，把通過驗證的批次送入 Bronze/Silver 並更新 Gold 輸出。
3. Power BI Desktop 執行全部重新整理，確認 9 個 Gold 載入表、鍵粒度與關聯，再儲存並重開 PBIP。

Power Query 的資料來源認證儲存在 Power BI Desktop；M、TMDL、SQL 與文件不包含資料庫密碼。`.pbi/`、`cache.abf`、`.env` 和原始擷取檔仍是本機狀態或資料，不納入版本控制。
