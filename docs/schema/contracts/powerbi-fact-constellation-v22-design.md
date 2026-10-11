# Power BI 事實星座 v22 設計

## 目前狀態（2026-10-10）

語意模型目前載入九張資料表。`FactJobSnapshot` 與
`FactSalaryObservation` 沒有報表視覺物件引用，且 v21 Gold 合約保留了查詢序列／批次造成的重複，仍暫停匯入。v22 的資料庫 migration 025–040 已由受控 runner 依序套用；v21 Gold views 與 Silver 資料仍保留。現行 Power Query 將 `目前職缺` 接到 `pbi_fact_jobs_report_v22`、將 `dim_地區` 接到 v22，其餘相容讀取器維持 v21。

`目前職缺`仍是報表使用中的現職資料表。其欄位與 PBIR 報表引用維持原狀。兩張職缺橋接表的關聯已設定雙向篩選；四個 measure 不再重複寫入相同的 `CROSSFILTER(..., BOTH)`。

唯讀 catalog 查詢確認兩個平台都提供以最新完整批次為基礎的 `gold.latest_job_snapshots` 與 `gold.latest_job_salary_observations`。yes123 的薪資 view 會連接其最新快照 view，因此目前來源具備可沿用的批次資格規則。v22 FactJob 現在包含 104 的 155,940 列與 yes123 的 39,392 列，共 195,332 列。

## 目標資料責任

三張事實表的粒度不同，應分開保留，並以共用職缺維度連接；不要建立事實表彼此之間的關聯。

| 物件 | 建議粒度 | 必要合約 |
|---|---|---|
| `dim_職缺` | 每個帶平台前綴的 `sourceJobKey` 一列 | 由現職、每日快照與薪資觀測出現過的所有職缺鍵取聯集。提供平台、原生 ID、職缺編號、名稱、連結、首次／最後觀測日與現職旗標；所有事實表的職缺鍵都必須能對應。不得以公司名稱或職稱作為識別鍵。 |
| `目前職缺` | 每個目前符合資格的職缺一列 | 保留既有報表欄位及相容鍵；先讓報表繼續使用此表，之後再另行評估整併。 |
| `FactJobDaily` | 每個 `sourceJobKey × snapshotDate` 一列 | 先篩選各平台最新完整批次，再跨查詢序列選出確定性代表列。提供 `seriesHitCount` 與觀測時間。不得用原始序列列數代表職缺數。 |
| `FactSalaryObservation` | 每個 `sourceJobKey × snapshotDate × sourceKind × observationIndex` 一列 | 各平台先篩選最新完整批次，再跨序列去重。提供職缺／公司／地區鍵、代表序列、觀測數、衝突旗標／數量、幣別、給薪週期與解析狀態；公司／地區鍵取自代表列對應的同一快照。 |
| 現職技能／職類橋接表 | 每個 `sourceJobKey × code` 一列 | 關聯到職缺維度。現有橋接表只描述目前關聯，不得暗示它們代表歷史日期的技能或職類。 |
| 歷史技能／職類橋接表 | 若來源歷史足夠，則每個職缺日期代碼組合一列 | 只有在來源能提供日期粒度或有效期間時，才能用來篩選歷史事實；否則相關切片器須明確視為現況條件。 |

日期維度、公司維度與地區維度應分別直接連到每張事實表。v22 薪資列的公司／地區鍵取自同一筆代表快照，避免事實表彼此相連。公司、地區與職缺鍵都要帶平台前綴；不能只因名稱相同就合併跨平台實體。公司 ID 缺漏時保留未解析狀態，不要製造共用的合成公司。

`DimArea` 提供 `jobCounty`，從觀測到的 `jobAddrNoDesc` 與 `jobAddress` 擷取明確出現的臺灣縣市名稱，並統一「台／臺」異體。地址未命中或同一地址命中不同縣市時保留空值，不推測位置。`jobLocationScope` 沿用現有報表值 `國內`、`國外(台灣地區之外)` 與 `未判定`，避免切換 v22 後既有切片器失效；在沒有座標時，migration 035 只依明確來源縣市／海外區域標籤分類，未命中白名單的值仍保留 `未判定`，且不新增座標。報表可依 `jobLocationScope` 先選國內，再用 `jobCounty` 篩選縣市；地圖採縣市 → 地區 (`jobAddrNoDesc`) → 地址鍵 (`areaKey`) 鑽研，最後只在單一地區載入地址級點位。這條路徑已通過 Desktop 驗證：`國內` 顯示 193,341 筆並繪製點位，`國內 + yes123` 顯示 39,317 筆並繪製有座標的台灣點位。

## 資料品質與指標規則

- 產生分析 view 前，先套用各來源最新完整批次規則。104 本地分支須以 `COALESCE(source_platform, '104') = '104'` 篩選；yes123 須沿用其 Gold 最新完整批次 views。
- 去重必須在批次資格篩選之後進行。同一自然鍵若內容不同，依最新 `snapshot_datetime` 選代表值，並保留衝突數量／旗標。Silver 原始列不得刪除。
- v22 薪資列的公司／地區鍵取自該薪資代表列相同的來源快照，讓三張事實表都能直接使用平台限定的共用維度鍵。
- 薪資不能跨幣別或給薪週期加總或平均。指標必須要求單一幣別和週期，或依兩者分組。
- 不可透過事實表關聯重用日期、職缺、公司或地區篩選；每張事實表須直接連到適用的共用維度。
- 現有技能／職類橋接是現況資料。歷史趨勢須另有日期粒度的橋接，否則只能以現況關係解讀。

## 唯讀來源證據（2026-10-10）

### 快照

| 來源集合 | 最新完整快照列數 | 不重複職缺日期 | 職缺數 | 日期數 |
|---|---:|---:|---:|---:|
| `jobwant_104` 中的 104 列 | 263,798 | 203,137 | 156,007 | 4 |
| `jobwant_104` 中的 yes123 列 | 4,497 | 4,497 | 4,497 | 1 |
| `jobwant_yes123` 中的 yes123 列 | 148,290 | 39,392 | 39,392 | 1 |

Migration 021 的 `pbi_fact_job_snapshots_v21` 本地分支未篩選 `source_platform`，並把所有列標為 104。因此它回報的 104 組合包含前兩列，共 268,295 列、207,634 個職缺日期、160,504 個職缺與 5 個日期。104 現職範圍有 155,940 個合格職缺；本地 104 快照中的另 67 個職缺沒有符合資格的非關鍵字職類觀測。

先前回報的 4,564 個快照對不到現職職缺，可由 4,497 筆被錯標為 104 的 yes123 列，加上 67 個缺少合格職類觀測的 104 職缺解釋。此分解來自 view 定義與分組計數；完整 anti-join 超過 25 秒唯讀查詢逾時，因此不能當成 anti-join 的直接結果。

唯讀 catalog 也確認兩個 Gold 最新快照 view 的關鍵欄位型別一致：`series_key`、`batch_id`、`job_no`、`source_job_key` 為 `text`，`snapshot_date` 為 `date`，`snapshot_datetime` 為 `timestamp with time zone`，`cust_no`、`area_key` 為 `text`；薪資金額為 `numeric`。最新薪資 view 的 `source_kind` 為 `text`、`observation_index` 為 `integer`、`quality_flags` 為 `jsonb`、`currency_code` 為 `CHAR(3)`。在兩個來源查到的 `source_job_key` 均無空值或錯誤平台前綴。

yes123 目前職類來源仍保留原生代碼與語意。現有 FDW 的職類快照只有 25 筆舊資料，與目前 v22 scope 沒有可用的 join；Golden L1 bridge 改以 yes123 current job 的原生 `source_jobcat` 連接已保存 crosswalk。現況 25 筆可對應確認 mapping，39,367 筆仍維持 `UNMAPPED`／`待對照`；未猜測 yes123 到 104 的 `jobcat` 對應，也未把已儲存批次狀態描述成即時佇列。

### yes123 地區預覽

以 yes123 最新快照和其自己的 `area_dimension` 做唯讀檢查，migration 035 後 v22 有 410 個 `國內` area rows（64 個有座標）、8 個 `國外(台灣地區之外)` area rows，沒有 `未判定` area rows；職缺數分別為 39,317 個 `國內`、75 個國外、0 個 `未判定`。這項分類只使用來源明確的縣市／海外區域文字，不會把無座標職缺送進地圖；Desktop 已驗證 yes123 + 國內的 KPI 與有座標的台灣地圖點位同步更新。

### 薪資觀測

| 來源集合 | 列數 | 自然鍵數 | 跨序列額外列 | 衝突自然鍵 |
|---|---:|---:|---:|---:|
| 104 本地 Gold | 361,232 | 277,897 | 83,335 | 9（8 組 API 欄位、1 組描述欄位） |
| 104 Gold 中的本地 yes123 副本 | 8,992 | 8,992 | 0 | 0 |
| yes123 來源 Gold | 296,358 | 78,723 | 217,635 | 0 |

本地 yes123 副本可由已驗證的 `yes123:` `job_no` 前綴識別，不可併入 104 分支。按平台正確篩選後，完整批次薪資資料共 657,590 列、356,620 個自然鍵；跨序列去重可減少 300,970 列，並保留 9 個 104 衝突鍵供報表檢視。薪資對現職職缺的完整 anti-join 仍逾時，剩餘孤兒數及原因標記為 `BLOCKED`，不得推測。

Migration 021 的 v21 薪資 view 直接讀 Silver，沒有套用最新完整批次篩選，也沒有去除跨序列重複；本地 yes123 副本還會被標成 104。先前唯讀稽核曾回報 v21 有 3,020 列不屬於最新完整批次，該數值尚未在本輪重新計算。

## Migration 026／v22 發布閘門與目前結果

1. 104 與 yes123 都必須維持各自最新完整批次規則。yes123 已驗證的 Gold 最新完整 view 不可替換成原始 Silver 讀取。
2. 先用有界查詢確認剩餘薪資孤兒數；目前完整 anti-join 逾時，原因仍為 `BLOCKED`。
3. 建立 v22 欄位合約後，逐平台、日期驗證欄位型別、鍵唯一性、列數、去重差異、衝突旗標、空值語意與孤兒鍵。
4. 受控 runner 已套用 025–040；`python tools/check_migration_state.py --require-ready` 應回報 migration history contiguous、沒有 pending 或缺檔，並確認 v21/v22 Gold objects 存在。
5. `tools/sync_lake_to_postgres.py --write` 仍會執行 version 19 schema script，可能覆蓋 Gold views；不得使用它或 `--direct-postgres` 寫入目前 reporting database。
6. Power Query 已將 FactJob 與 DimArea 接到 v22；更新後須在 Desktop 重新整理、儲存、關閉、重開，再檢查 model inventory、DAX、slicer 與地圖行為。PBIR 頁面調整另行處理。

Migration 026 位於 [`tools/sql/migrations/026_pbi_fact_constellation_v22.sql`](../../../tools/sql/migrations/026_pbi_fact_constellation_v22.sql)，定義 `pbi_fact_jobs_v22`、`pbi_dim_job_v22`、`pbi_dim_company_v22`、`pbi_dim_area_v22`、技能／職類橋接與維度，以及 `pbi_fact_job_daily_v22`、`pbi_fact_salary_observations_v22`。它保留 v21 views，加入批次資格、平台限定鍵、跨序列去重及衝突欄位；026 初始標記為 DRAFT，已在 gate review 後由 runner 以 `--allow-draft` 套用。027–035 依序完成 area lookup 去重、目前 scope 最佳化、代表列保留、地址標籤 fallback 與明確來源地區分類；036 調整本機 reporting role 的排序記憶體，037 讓已驗證等價的小型技能維度直接讀 Silver；038 讓活動職類橋接只讀關聯鍵欄位；039 讓活動技能橋接只讀關聯鍵欄位；040 讓 active FactJob 讀取僅含報表欄位的投影，canonical v22 view 保留完整 lineage。資料庫 migration history 為 1–40 且沒有 pending migration。

FactJob 與 DimArea 已匯入 v22；快照與薪資事實仍暫停匯入，避免將查詢序列／批次重複帶進目前報表。這不代表快照或薪資資料已從 Gold／Silver 刪除。單次 Desktop 重新整理或約 8.8 秒的 area view 觀察不能證明完整刷新速度已改善；要宣稱效能提升，仍需可比較的刷新前後基準。
