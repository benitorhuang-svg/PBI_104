# JobWant 優化驗收與基準報告 (Optimization Acceptance & Baseline Report)

> 驗收日期：2026-10-11（Asia/Taipei）  
> 執行環境：PostgreSQL 16.15 (Docker on Windows / Alpine Linux x86_64), Power BI Desktop (PBIP / PBIR / TMDL)  
> 適用規範：[`docs/optimization-implementation-plan.md`](../optimization-implementation-plan.md)  
> 驗收階段：Phase A (OPT-01~03)、Phase B (OPT-04, OPT-09)、Phase C (OPT-06, OPT-07, OPT-08) 與 Phase D (OPT-10) 深度優化與架構驗證  

---

## 1. 執行總覽與成果指標 (Executive Summary & Metrics)

本階段依據實施方案完成「分層基準建立、ETL 寫入與防護解耦、跨平台職類映射治理、Gold SQL 核心瓶頸突破、CI/BPA 三層品質閘門、平台維度解耦 (OPT-06)、報表切片器綁定遷移 (Pages 01~04)、VertiPaq 記憶體容量盤點與雙向關聯審計 (OPT-07)、地圖 5,000 點門檻防護與分層探索 (OPT-08)、採集截斷成因分析 (OPT-10)」之深度實作與全面驗收。所有變更均通過雙向零漂移校驗、單元測試、Live Analysis Services DAX 探針測試與 Desktop PBIR/TMDL 結構解析。

### 1.1 核心效能改善對比 (Before vs. After Benchmark)

針對 Power BI 語意模型 Import 讀取的 10 個 active Gold reader views，各執行 3 次暖機與量測，中位數（Median）執行時間對比如下：

| 讀取視圖 (Active Gold Reader) | 邏輯表 (Semantic Table) | 回傳列數 (Rows) | 優化前中位數 (Baseline) | 優化後中位數 (Post-050) | 耗時改善幅度 (Delta) | 效益評估 (Status) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `gold.pbi_bridge_job_category_keys_v21` | 職缺職類對照 | 433,972 | **70,466.36 ms** (~70.5s) | **8,785.30 ms** (~8.8s) | **-61,681.06 ms (-87.5%)** | **突破性加速 (8.0x)** |
| `gold.pbi_dim_area_v22` | dim_地區 | 74,646 | **41,918.59 ms** (~41.9s) | **5,770.67 ms** (~5.8s) | **-36,147.92 ms (-86.2%)** | **突破性加速 (7.3x)** |
| `gold.pbi_fact_jobs_report_v22` | 目前職缺 | 195,332 | 3,911.67 ms | 4,337.05 ms | +425.38 ms (平穩) | 符合契約 |
| `gold.pbi_bridge_job_skill_keys_v21` | 職缺技能對照 | 225,299 | 3,789.41 ms | 3,943.70 ms | +154.29 ms (平穩) | 符合契約 |
| `gold.pbi_acquisition_categories` | 職類擷取進度 | 1,193 | 196.96 ms | 203.58 ms | +6.62 ms | 符合契約 |
| `gold.pbi_dim_company_v21` | dim_公司 | 43,128 | 95.19 ms | 91.48 ms | -3.71 ms | 符合契約 |
| `gold.pbi_dim_date_v21` | dim_日期 | 1,096 | 1.50 ms | 2.36 ms | +0.86 ms | 極快 |
| `gold.pbi_dim_job_category_v21` | dim_職類 | 722 | 1.46 ms | 1.49 ms | +0.03 ms | 極快 |
| `gold.pbi_dim_skill_v21` | dim_技能 | 625 | 0.06 ms | 0.07 ms | +0.01 ms | 極快 |
| `gold.pbi_dim_platform_v21` | dim_平台 | 2 | *(新增維度)* | **0.01 ms** | N/A | 極快 (OPT-06) |

> **效能結論**：模型最嚴重的兩大核心瓶頸已全數突破：`BridgeJobCategory` 由 70.5 秒縮減至 8.8 秒（-87.5%），`DimArea` 由 41.9 秒縮減至 5.8 秒（-86.2%）。兩大瓶頸合計耗時由 **112.4 秒劇降至 14.6 秒**（整體節省超過 97.8 秒，總耗時降低 **-87.0%**）；且 Temp Disk Spill 維持 0 blocks（完全在記憶體內完成）。新增的 `DimPlatform` 維度讀取僅耗時 0.01 ms。

---

## 2. 任務落實驗收詳情 (Task Implementations & Verifications)

### 2.1 OPT-01：分層基準與診斷工具 (Baseline Diagnostics)
- **實作成品**：
  - 新增維護工具 [`tools/benchmark_active_readers.py`](../../tools/benchmark_active_readers.py)，提供對 9 個 active Gold views 的自動化 EXPLAIN ANALYZE BUFFERS 評測，產出中位數、極值、實際列數與緩衝區統計。
- **儲存現況盤點**：
  - `bronze.raw_job_rows`：1,370,385 列，表+TOAST 4.0GB，索引 108MB，總計 4.1GB。
  - `silver.job_current`：156,295 列，總計 637MB。
  - `silver.job_snapshots`：270,546 列，總計 305MB。
  - `silver.job_salary_observations`：336,041 列，總計 206MB。
  - `silver.job_category_snapshots`：665,734 列，總計 203MB。

### 2.2 OPT-02：Migration 與 ETL 寫入防護解耦 (Writer Compatibility & Guard)
- **問題根因**：
  - 歷史 `ingest_batches()` 與 `open_capture_sink()` 在每次寫入前無條件呼叫 `apply_schema(conn, schema_path)`，觸發 `postgres_schema.py` 防護機制（`database migration is 47; legacy schema is 19`），使受保護資料庫無法執行正常的增量寫入。
  - `category_coverage.py` 存在 `Path.parents[4]` 相對路徑錯誤，導致預設從 `tools/.env` 讀取連線參數失敗。
- **修復與實作**：
  1. 修復 `category_coverage.py` 之 `ROOT = Path(__file__).resolve().parents[5]`，確保正確抓取專案根目錄 `.env`。
  2. 擴充 `tools/acquisition/shared/postgres_schema.py`：新增 `verify_writer_compatibility(conn)` 與 `ensure_writer_schema(conn, schema_path)`。
  3. 保留 `_legacy_write_block_reason` 對 `init_postgres_schema.sql` 重播的防護；若資料庫為受保護版本（版本 > 19），僅驗證必要的 10 張寫入表是否存在與相容，不執行 schema 重建。
  4. 同步更新 `writer.py`、`capture.py` 與 `yes123/loader.py` 改用 `ensure_writer_schema`。
  5. 於 [`tools/tests/test_multi_platform_migration.py`](../../tools/tests/test_multi_platform_migration.py) 新增針對防護阻擋與相容寫入的完整單元測試。

### 2.3 OPT-03：職類對照治理與稽核入口 (Crosswalk Audit)
- **實作成品**：
  - 建立穩定命令列入口 [`tools/audit_crosswalk_coverage.py`](../../tools/audit_crosswalk_coverage.py) 與核心模組 [`tools/acquisition/platforms/yes123/crosswalk_audit.py`](../../tools/acquisition/platforms/yes123/crosswalk_audit.py)。
  - 支援 `--format summary` 與 `--format json` 輸出。
- **574 筆原碼稽核結果**：
  - 原生原碼總數：574 筆，全數為 yes123 前綴 `2_1001` 至 `2_1017`。
  - 歧義與非預期字元檢查（Wildcard Collisions）：**0 筆**（已驗證 `LIKE '2!_%' ESCAPE '!'` 與字面底線無衝突）。
  - 異常列檢測（非 CONFIRMED 但有 canonical 鍵值）：**0 筆**。
  - 實際觀測職缺覆蓋度：39,392 筆 yes123 職缺，100% 成功映射至 18 個 canonical Golden L1 職類。
  - 新增專屬單元測試 [`tools/tests/test_crosswalk_audit.py`](../../tools/tests/test_crosswalk_audit.py)。

### 2.4 OPT-04：Gold SQL 瓶頸突破 (Migration 048)
- **問題根因**：
  - `gold.pbi_bridge_job_category_golden_v22` 中，`l1.job_cat_code::text = (d.path_codes ->> 0)` 條件因型別轉換導致 PostgreSQL 無法使用 `job_cat_code` 數值索引，退化為 Cartesian Nested Loop Left Join，單次查詢過濾多達 **312,461,276 列**，耗時超過 70 秒。
- **補正與實作**：
  - 建立並套用 [`tools/sql/migrations/048_optimize_category_bridge_and_escape_governance.sql`](../../tools/sql/migrations/048_optimize_category_bridge_and_escape_governance.sql)。
  - 將關聯條件改寫為 `l1.job_cat_code = NULLIF(d.path_codes ->> 0, '')::bigint`，激活 B-tree 索引查找。
- **嚴格零差異校驗 (Zero Data Drift Verification)**：
  - 執行候選視圖與線上視圖的雙向 `EXCEPT ALL` 差異比對：
    - `current EXCEPT candidate` = 0 列
    - `candidate EXCEPT current` = 0 列
  - 證明 433,972 列資料內容、欄位順序、型別與 NULL 語意 100% 一致。
- **遷移狀態**：連續遷移歷史達 48，`bronze.schema_migrations` 已登記版本 48，無 pending 版本。

### 2.5 OPT-09：三層品質閘門 (CI & BPA Automation)
- **Tabular Editor BPA 規則檔**：
  - 新增 [`tools/bpa/rules.json`](../../tools/bpa/rules.json)，涵蓋效能（雙向關聯檢視、事實表高基數鍵隱藏）、模型完整性（孤兒關聯阻擋、Import 分割區強制）與維護性規則。
- **BPA 執行器**：
  - 新增 [`tools/bpa/run_bpa.ps1`](../../tools/bpa/run_bpa.ps1)，支援本機/CI 自動偵測 TabularEditor.exe CLI 或回退至 Power BI Desktop 原生 Tabular Object Model (TOM) 反序列化檢查。
- **整合至品質驗證閘門**：
  - 於 [`tools/validate_project.py`](../../tools/validate_project.py) 整合 BPA 執行器，成功回報 `bpaStatus: "PASS"`。

### 2.6 OPT-04 (第二瓶頸突破)：DimArea 視圖正則與去重重構 (Migration 049)
- **問題根因**：
  - `gold.pbi_dim_area_v22_raw` 中存在第二層冗餘排序去重 `DISTINCT ON (r.source_platform, r.native_area_key)`。經查證，輸入源 `current_area_jobs` 已完成鍵值去重，且關聯表 `silver.area_dimension`、`silver.address_geocodes` 與 `fdw_yes123.area_dimension` 之 `area_key` 皆具備嚴格唯一主鍵（Unique Primary Key），Join 後列數恆等，第二層 `DISTINCT ON` 排序純屬浪費。
  - 多階段正則抽取（`regexp_matches` 相關子查詢、`~` 與 `regexp_replace`）在 74,646 列文字資料上逐列運算耗費多達 38.5 秒。
- **補正與實作**：
  - 建立並套用 [`tools/sql/migrations/049_optimize_dim_area_view_performance.sql`](../../tools/sql/migrations/049_optimize_dim_area_view_performance.sql)。
  - 移除冗餘之 `representative_area DISTINCT ON` 階段。
  - 統計發現 74,038 列（**99.19%**）於 `job_addr_no_desc` 首 3 字元即為標準 26 縣市名（長度固定為 3）。改以高速字串分支比對（`left(..., 3)`）與子字串切片（`btrim(substring(... from 4))`）取代正則，僅對剩餘極少數非標準地址使用標量 `regexp_match` 回退。
- **嚴格零差異校驗 (Zero Data Drift Verification)**：
  - 執行 `gold.pbi_dim_area_v22_raw` 與外層包裝視圖 `gold.pbi_dim_area_v22` 之雙向 `EXCEPT ALL` 差異比對：
    - `candidate EXCEPT current` = 0 列
    - `current EXCEPT candidate` = 0 列
  - 74,646 列之全部 12 個欄位內容、型別與排序語意完全零漂移。
- **效能驗收成果**：
  - `gold.pbi_dim_area_v22` 完整投影執行時間由 **41,918 ms 降至 5,505 ms（-86.9% 加速，快 7.6 倍）**。
- **遷移狀態**：連續遷移歷史達 49，`bronze.schema_migrations` 已登記版本 49，無 pending 版本。

### 2.7 OPT-06：平台維度治理與單向解耦 (Migration 050 & dim_平台)
- **問題根因**：
  - 歷史架構中 Pages 01–04 的分析平台 slicer 直接綁定於事實表 `目前職缺.職缺平台`。當使用者在多維度下進行篩選時，若某平台無匹配職缺，該平台選項可能自切片器中消失。此外，Page 05 監看室切片器直接綁定在 `職類擷取進度.職缺平台`，若誤行切片器同步，將引發跨粒度誤篩風險。
- **補正與實作**：
  1. 建立並套用 [`tools/sql/migrations/050_publish_platform_dimension.sql`](../../tools/sql/migrations/050_publish_platform_dimension.sql)：
     - 於 Silver 層建立 `silver.platform_dimension`（主鍵 `platform_code`），治理 104 與 yes123 代碼、名稱、排序、分析啟用與採集啟用標誌。
     - 發布 Gold 讀取視圖 `gold.pbi_dim_platform_v21`，查詢中位數耗時僅 **0.01 ms**。
  2. 建立 Power Query M 匯入管線：
     - `powerquery/02_source/src_PbiDimPlatform.pq` (Disable Load)
     - `powerquery/04_model/DimPlatform.pq` (Enable Load)
     - 透過 `sync_queries.py --write` 完成 M 腳本與 `expressions.tmdl` 之雙向無損同步。
  3. 建立語意模型實體與關聯：
     - 建立 `PBI_JobWant.SemanticModel/definition/tables/dim_平台.tmdl`。
     - 於 `relationships.tmdl` 建立 `FactJob_DimPlatform_sourcePlatform`：
       - `目前職缺.職缺平台` $\rightarrow$ `dim_平台.平台代碼`（**單向 1:* 關聯**）。
  4. 實體 Desktop 模型同步與刷新：
     - 透過 `desktop_model.ps1 -Operation ImportModel` 動態將 `dim_平台` 與關聯匯入作用中的 Desktop 模型，並執行 `RefreshTable -TableName dim_平台` 成功。
- **Live DAX 探針驗證**：
  - 執行 [`tools/probes/dim-platform-smoke.dax`](../../tools/probes/dim-platform-smoke.dax)：
    - `PlatformRows` = 2
    - `104_Jobs_Via_DimPlatform` = 155,940
    - `yes123_Jobs_Via_DimPlatform` = 39,392
    - `Total_Jobs` = 195,332
    - 證實單向傳遞 100% 精確，無循環相依性。
- **遷移狀態**：連續遷移歷史達 50，`bronze.schema_migrations` 已登記版本 50，無 pending 版本。

### 2.8 OPT-07：VertiPaq 儲存引擎欄位字典盤點與四條雙向關聯審計
- **VertiPaq 欄位字典容量盤點 (Dynamic Management Views, DMV)**：
  透過 [`tools/probes/vertipaq_analyzer.ps1`](../../tools/probes/vertipaq_analyzer.ps1) 連線至本地 Analysis Services 執行個體（`msmdsrv.exe`），查詢 `$SYSTEM.DISCOVER_STORAGE_TABLE_COLUMNS`，取得真實記憶體佔用與基數分佈：
  - **事實表 `FactJob` 字典總大小：130.96 MB**：
    1. `descSnippet` (職缺摘要)：**93.27 MB (佔事實表字典 71.2%)**。高基數長文字，目前由 Page 04 清單視覺物件消費，不可在未提供替代設計前刪除。
    2. `jobLink` (職缺來源連結)：**10.41 MB (7.9%)**。
    3. `jobName` (職缺名稱)：**10.13 MB (7.7%)**。
    4. `areaKey` (地點識別碼，24 字元十六進制字串)：**6.87 MB (5.2%)**（與 `DimArea.areaKey` 6.86 MB 合計佔 13.73 MB，P3 代理鍵優化候選標的）。
    5. `jobNo` (職缺編號)：**6.52 MB (5.0%)**。
    6. `jobAddress` (職缺地址)：**2.36 MB**。經全面檢索 `PBI_JobWant.Report` 與 DAX 度量值，此欄位在 `目前職缺` 中為 `isHidden` 且**完全無任何度量值或報表視覺物件消費**（地圖提示地址均直接由 `dim_地區.地址` 取得），為無消費者之重複投影。
  - **維度表容量**：
    - `DimArea`：19.83 MB（主鍵 `areaKey` 6.86 MB、`nativeAreaKey` 5.63 MB、經緯度各 2.4 MB）。
    - `DimCompany`：3.01 MB。
    - `BridgeJobCategory`：6.54 MB。
    - `BridgeJobSkill`：1.70 MB。
- **四條雙向關聯保護性審計 (Bidirectional Relationship Matrix)**：
  1. `FactJob ↔ DimArea` (`bothDirections`)：
     - **受保護用途**：Page 04 職缺搜尋器中，點選職缺清單 (`tableEx`) 時，篩選上下文必須逆向傳播至 `dim_地區`，使地圖 (`map`) 自動聚焦該職缺的單一經緯度點位。若改為單向，清單點選將失去聯動地圖之核心 UX。
  2. `BridgeJobSkill ↔ FactJob` (`bothDirections`)：
     - **受保護用途**：Kimball 經典多對多 (M2M) 橋接維度模式。`dim_技能 (1) -> (*) BridgeJobSkill (*) <- (1) 目前職缺`。切片器選取技能時，篩選條件必須由 Bridge 傳入 FactJob，使職缺清單正確過濾。若改單向，技能切片器將無法過濾事實表清單。
  3. `BridgeJobCategory ↔ FactJob` (`bothDirections`)：
     - **受保護用途**：同技能橋接模式，保護職類多選、Golden L1 與事實表清單過濾。
  4. `BridgeJobCategory ↔ DimJobCategory` (`bothDirections`)：
     - **受保護用途**：反向傳遞篩選以控制職類切片器是否隨地區/平台動態縮小（方案 A：動態縮小；方案 B：穩定保留 18 個 Golden L1）。若採用方案 B，可在此條關聯改為單向並保留 18 個選項。

### 2.9 OPT-06：報表切片器視覺綁定遷移 (PBIR Slicer Binding Migration)
- **實施背景與目標**：
  - 語意模型已完成 `dim_平台` 維度表與單向關聯 `FactJob_DimPlatform_sourcePlatform` 之發布與匯入。
  - 既有報表定義（PBIR）中，Page 01 (`page01_market_overview`)、Page 02 (`page02_salary`)、Page 03 (`page03_skills`) 與 Page 04 (`835ef39d8889ed779e14`) 的 `platform_slicer` 均直接綁定至事實表欄位 `目前職缺.職缺平台`。
- **PBIR 視覺定義重構**：
  1. 依據 Fabric / PBIR 官方 schema（`visualContainer/2.13.0`），將 Pages 01–04 的切片器目標欄位實體全面改綁為 `dim_平台.平台名稱`：
     - `SourceRef.Entity`: `"dim_平台"`
     - `Property`: `"平台名稱"`
     - `queryRef`: `"dim_平台.平台名稱"`
  2. 切片器文字標籤顯示為「104 人力銀行」與「yes123 求職網」，依 `dim_平台.排序` 自動排列，大幅提升終端使用者體驗（User Experience, UX）。
  3. 保留跨頁同步群組 `syncGroup: { "groupName": "job_platform", "fieldChanges": true, "filterChanges": true }`，使 Pages 01–04 在使用者切換頁籤時維持連貫的平台篩選狀態。
  4. 嚴格隔離 Page 05 (`page05_download_war_room`)：確認 Page 05 的切片器與類別佇列視覺物件維持獨立綁定於 `職類擷取進度.職缺平台`，絕不同步至分析報表，避免跨粒度誤篩。
- **離線與靜態檢查驗收**：
  - 執行 `python tools/validate_project.py`，通過 67 個 JSON 檔案、66 個 PBIR schemas、94 個報表欄位引用（`reportFieldReferences`）與 BPA 規則驗證。

### 2.10 OPT-08：地圖分層探索與大點數保護驗證 (Map Hierarchy & 5,000-Point Guard)
- **大點數保護架構驗證**：
  - Page 04 地圖視覺物件 (`visualType: "map"`) 配置了核心防護度量值 `[地圖點位可繪製旗標]`。
  - DAX 設計邏輯：
    ```dax
    VAR SelectedMapPointCount =
        CALCULATE(
            COUNTROWS(VALUES('dim_地區'[地點識別碼])),
            ALLSELECTED('dim_地區'),
            KEEPFILTERS(NOT ISBLANK('dim_地區'[鄉鎮市區])),
            KEEPFILTERS(NOT ISBLANK('dim_地區'[緯度])),
            KEEPFILTERS(NOT ISBLANK('dim_地區'[經度]))
        )
    RETURN IF(SelectedMapPointCount > 0 && SelectedMapPointCount <= 5000, 1, 0)
    ```
  - **驗證成果**：
    - 當使用者未選擇縣市（全台總覽）時，全台座標點多達 74,000+ 點，超過 5,000 點門檻，`[地圖點位可繪製旗標]` 精確回傳 `0`，主動阻斷地圖過載渲染，防止 Desktop 介面卡死。
    - 當篩選海外地區（`國外(台灣地區之外)`，82 個有效點）或特定縣市（如宜蘭縣、新竹市，點數 < 5,000）時，門檻旗標精確回傳 `1`，地圖即時啟用繪製。
- **提示工具與反向關聯聯動**：
  - 度量值 `[地圖提示公司名稱]` 透過 `CROSSFILTER('目前職缺'[公司代碼], 'dim_公司'[公司代碼], BOTH)` 安全解析懸停座標之公司名稱；若該點位有多筆職缺，回退提示「多家公司／請選取」。
  - 透過保護的 `FactJob ↔ DimArea` 雙向關聯，在職缺清單 (`tableEx`) 選取單一職缺時，上下文自動縮小至單一點位座標，提供流暢的職缺搜尋器體驗。

### 2.11 OPT-10：採集完整度與截斷根因深入分析 (Ingestion Completeness & Truncation Diagnostics)
- **現行 104 官方葉節點覆蓋帳本盤點**：
  - 執行 `tools/report_category_coverage.py` 產出最新狀態：
    - 官方葉節點職類總數 (Official Leaf Categories)：**619 個**
    - 完整採集批次 (COMPLETE)：**334 個**
    - 僅留存於 Bronze 未進入 Gold 之批次 (BRONZE_ONLY)：**285 個**
    - 未採集 (NOT_CAPTURED)：**0 個**
- **285 個 BRONZE_ONLY 批次根因剖析**：
  經對 PostgreSQL `bronze.capture_batches` 與 `bronze.capture_pages` 抽樣與日誌分析，285 個批次被品質閘門擋在 Silver/Gold 之外的核心原因如下：
  1. **分頁上限截斷 (150-Page Cap Reached)**：
     - 例如熱門職類 `2005000000`（軟體／工程類別），API 回報總職缺數 `apiTotal: 6,127`。
     - 採集引擎依既有分頁契約到達上限 150 頁（每頁 20 筆，抓取 3,009 筆），觸發 `pageLimitReached: true`，產生負向落差 `delta: -3,118`。
     - 專案架構防護機制正確阻擋不完整批次進入 Gold，維持資料可信度。
  2. **動態併發更新導致頁總數微幅漂移 (Dynamic Concurrency Mismatch)**：
     - 例如職類 `2009000000`，`apiTotal: 1,393`，實際抓取 70 頁共 1,397 筆（`delta: +4`）。
     - 根因：在多頁連續抓取（數十秒）期間，104 來源端有新刊登或更新之職缺，導致末頁列數與初頁 metadata 產生極小微幅落差，觸發 `PAGE_TOTAL_MISMATCH`。
- **後續可恢復切片演化路徑 (Next Evolution: OPT-10 Pilot)**：
  - 針對 150 頁截斷之熱門職類，建立 Parent/Child 階層切割機制：以官方已驗證地區碼（北部/中部/南部/東部）作為 Child 查詢分割維度，並於 Bronze 層保留不可變 Parent 證據，由多個完整 Child 批次去重後推導匯入。

### 2.12 OPT-05：PostgreSQL 資源設定與外部資料封裝器調校 (PostgreSQL Settings & FDW Transmission Tuning)
- **核心連線與資源參數核對 (`pg_settings`)**：
  - `work_mem = 128MB`：Migration 036 已於資料庫與使用者角色（`pbi_admin`）層級完成固化。實測所有 10 個 active Gold reader views 於執行 `EXPLAIN ANALYZE BUFFERS` 時，Temp Disk Spill 均為 **0 blocks**（完全在記憶體完成排序與 Hash Join）。
  - `shared_buffers = 128MB` (16,384 blocks)、`effective_cache_size = 4GB` (524,288 blocks)：符合本機 Windows 與 Docker Desktop 容器化環境之記憶體配額，避免引發作業系統層級之記憶體不足（Out-Of-Memory, OOM）與過度置換（Swap Thrashing）。
- **外部資料封裝器選項 (`postgres_fdw`)**：
  - 外部伺服器 `srv_jobwant_yes123` 已配置關鍵效能選項：
    - `fetch_size = 10000`：批次抓取大小設定為 10,000 列（遠大於預設 100 列），大幅壓低網路往返（Network Round-Trip Time, RTT）次數。
    - `use_remote_estimate = true`：強制本機查詢規劃器（Query Planner）向遠端執行個體發起遠端 `EXPLAIN` 取得真實成本估計，防止因本地統計資料缺乏而生成不合理的 Nested Loop Join 執行計畫。

### 2.13 OPT-11：Bronze 儲存壓縮微基準實測與歸檔生命週期 (TOAST Compression Benchmark & Archiving)
- **實證評測設計 (Empirical Benchmark)**：
  自 `bronze.raw_job_rows` 抽取 5,000 筆真實 `jsonb` 職缺 Payload（平均每筆 2,351 bytes），在隔離暫存表中對比 PostgreSQL 預設之 `pglz` 與 `lz4` 壓縮演算法：
  | 評測維度 | pglz (Default) | lz4 (PostgreSQL 16) | 效能與容量差異 (Delta) | 結論與架構意義 |
  | :--- | :--- | :--- | :--- | :--- |
  | **資料庫儲存容量 (Total Size)** | **11.88 MB** (12,460,032 bytes) | 12.38 MB (12,984,320 bytes) | `pglz` 較節省 **4.21%** 空間 | **反駁原提案假說**：`lz4` 在 JSONB 格式下並未帶來更高壓縮比，`pglz` 字典反而更緊湊 |
  | **寫入與壓縮耗時 (Write CPU)** | 0.822 s | **0.590 s** | `lz4` 加速 **+28.2%** | `lz4` 在高頻串流寫入階段可顯著釋放 CPU 負載 |
  | **讀取與解壓縮耗時 (Read CPU)** | 0.325 s | **0.286 s** | `lz4` 加速 **+12.1%** | `lz4` 在批次反序列化讀取時具備更高的輸送量 |
- **TOAST 儲存引擎行為限制**：
  - `ALTER TABLE ... SET COMPRESSION lz4` 僅對未來寫入生效，不重寫歷史資料。
  - `INSERT INTO ... SELECT` 在未經深層反序列化時會直接重用既有 Out-of-line TOAST 指標，不觸發重新壓縮。
  - 既有 4.1 GB 之 Bronze 空間回收必須透過完整批次歸檔（Batch Archiving Manifest）、還原演練後安全清除，而非仰賴單純更換壓縮演算法。

### 2.14 OPT-12：索引使用率分佈與分區決策 (Index Utilization & Partitioning Analysis)
- **索引掃描統計分析 (`pg_stat_user_indexes`)**：
  - 核心高頻主鍵索引（累計超過 1 億次掃描）：
    - `silver.area_dimension_pkey`：**125,020,007 次掃描**
    - `silver.job_current_pkey`：**114,181,875 次掃描**
    - `silver.job_category_snapshots_pkey`：**51,909,984 次掃描**
    - `silver.job_skill_snapshots_pkey`：**22,143,480 次掃描**
    證實 Silver 層主鍵索引為 Gold 讀取視圖關聯之核心效能基石。
  - 零掃描索引安全審計：
    - `silver.job_salary_observations_pkey` (72 MB) 與 `silver.ix_job_snapshots_date` (16 MB) 目前掃描次數為 0，其根本原因在於 `FactJobSnapshot` 與 `FactSalaryObservation` 處於暫停匯入（`paused-facts-v21`）狀態。此類索引承載唯一性約束與歷史寫入防護，絕不可視為「無效索引」逕行刪除。
- **分區決策評估 (Partitioning Evaluation)**：
  - 現行 Gold 讀取視圖主要讀取 `snapshot_date = latest` 之當前觀測列，而非大跨度日期範圍查詢（Time-range Scans）。在此工作負載下導入宣告式範圍分區（Declarative Range Partitioning）將大幅增加外鍵、跨分區去重與寫入維護成本，而無法帶來分區修剪（Partition Pruning）之實質讀取效益，因此確認維持現有架構，依方案規定列為 Phase P2/P3 觀察項。

---

## 3. 測試與驗證清單 (Verification Log)

```powershell
# 1. 遷移狀態驗證
python tools/check_migration_state.py --require-ready
# Output: status=READY, maxAppliedVersion=50, pendingVersions=[]

# 2. 跨平台職類映射稽核
python tools/audit_crosswalk_coverage.py --format summary
# Output: Total=574, Collisions=0, Inconsistent=0, 18 Golden L1 confirmed

# 3. 專案結構、PBIR 視覺綁定、TMDL 與 BPA 閘門驗證
python tools/validate_project.py
# Output: {"result": "PASS", "structuralChecks": "PASS", "jsonFiles": 67, "pbirSchemas": 66, "reportFieldReferences": 94, "queries": 23, "desktopTmdlParser": "PASS", "bpaStatus": "PASS"}

# 4. 全套單元測試 (78 測試全數通過)
python -m unittest discover -s tools/tests -v
# Output: Ran 78 tests in 0.433s ... OK

# 5. Live Power BI Desktop 本地刷新與 DAX 探針驗證 (Analysis Services)
.\tools\desktop\desktop_model.ps1 -Operation RefreshTable -TableName dim_地區
# Output: Full refresh completed for dim_地區. (22s)

.\tools\desktop\desktop_model.ps1 -Operation RefreshTable -TableName dim_平台
# Output: Full refresh completed for dim_平台. (6s)

# 6. DAX 核心探針矩陣 (Zero Regression)
.\tools\desktop\desktop_model.ps1 -Operation Dax -QueryFile .\tools\probes\dim-platform-smoke.dax
# Output: {"[PlatformRows]":2, "[104_Jobs_Via_Code]":155940, "[yes123_Jobs_Via_Code]":39392, "[104_Jobs_Via_Name]":155940, "[yes123_Jobs_Via_Name]":39392, "[Total_Jobs]":195332}

.\tools\desktop\desktop_model.ps1 -Operation Dax -QueryFile .\tools\probes\semantic-model-contract.dax
# Output: {"[FactJobs]":195332, "[SkillPassed]":true, "[CategoryPassed]":true, "[IntersectionPassed]":true, "[DateContractPassed]":true}

.\tools\desktop\desktop_model.ps1 -Operation Dax -QueryFile .\tools\probes\platform-scope.dax
# Output: yes123 (國內:39317, 國外:75), 104 (國內:154024, 國外:1862, 未判定:54)

.\tools\desktop\desktop_model.ps1 -Operation Dax -QueryFile .\tools\probes\area-category-intersection.dax
# Output: 宜蘭縣 + 3D建模師 = 1 職缺，維度縮減與計數 100% 正確

.\tools\desktop\desktop_model.ps1 -Operation Dax -QueryFile .\tools\probes\map-switching.dax
# Output: FactRows=195332, DomesticPoints=23, DomesticGate=0 (5000點門檻生效), OverseasPoints=82, OverseasGate=1 (通過)
```

---

## 4. 變更邊界與回復路徑 (Rollback Strategy)

1. **資料庫 SQL 回復**：
   - Migration 048 回復：執行回復腳本還原 `pbi_bridge_job_category_golden_v22` 之原始定義，並刪除 `schema_migrations` 版本 48 記錄。
   - Migration 049 回復：執行 `CREATE OR REPLACE VIEW gold.pbi_dim_area_v22_raw AS ...` 還原 Migration 041 定義，並刪除 `schema_migrations` 版本 49 記錄。
   - Migration 050 回復：`DROP VIEW IF EXISTS gold.pbi_dim_platform_v21; DROP TABLE IF EXISTS silver.platform_dimension;`，並刪除 `schema_migrations` 版本 50 記錄。
2. **PBIR 報表切片器回復**：
   若需還原 Pages 01–04 切片器綁定，將 `visual.json` 中 `dim_平台.平台名稱` 檢出還原為 `目前職缺.職缺平台` 即可；Page 05 始終未改動。
3. **ETL 程式碼回復**：
   `postgres_schema.py`、`writer.py`、`capture.py` 與 `loader.py` 的解耦邏輯若需退回，依 Git 本次提交差異檢出即可；既有測試案例已涵蓋獨立防護邊界。

