# JobWant 資料庫 Schema 契約 v1（提案）

## 目的與狀態

本文件定義多平台資料進入 Power BI 前的資料庫責任、鍵、粒度與欄位契約。它仍是目標契約；本機 `jobwant_104` 已由受控 runner 套用 migrations 20–41，其中 v22 FactJob／DimArea 已接入 PBIP，快照與薪資觀測仍暫停匯入。legacy version-19 write path 維持阻擋，不能把目前 migration history 解讀成所有資料使用、分類映射或完整 ETL 閘門均已解除。

本機目錄與資料庫盤點日期：2026-10-10。Power Query 的正式輸入仍限定為集中報表資料庫中的 `gold.pbi_*` views；來源 JSON、Bronze、Silver 不直接提供給語意模型。

## 目標拓樸

```text
jobwant_104               jobwant_yes123              其他 jobwant_<platform>
Bronze → Silver           Bronze → Silver             Bronze → Silver
          \                   |                         /
           \---- 驗證後 ETL／唯讀聯邦讀取 ----------------/
                                  ↓
                       集中報表資料庫：Gold
                                  ↓
                      Power BI Import / PBIR
```

- 每個平台保留自己的來源代碼、原始批次與平台專屬正規化規則。來源資料庫可在同一 PostgreSQL cluster 中，但以資料庫和權限界定來源責任。
- 集中報表資料庫只發布共用 Gold 契約。Power BI 不在資料庫間切換；平台選擇是 Gold `sourcePlatform` 欄位上的 slicer。
- FDW 可作為唯讀取數方式。本機 migration 23 透過 yes123 的 Gold scope view 一次投影職缺，避免逐筆遠端 join；來源快照與薪資觀測仍經 FDW 讀取。需要來源離線時仍可報表或進一步控制查詢成本時，再評估 ETL 增量落地到集中資料庫。
- 目前 `jobwant_104` 同時承載 104 資料與報表 Gold，是過渡狀態。可評估 `jobwant_warehouse` 作為集中報表資料庫名稱；本規範不改資料庫名稱或連線參數。

## 命名與共同型別

| 範圍 | 規則 |
|---|---|
| 資料庫 | 來源資料庫採 `jobwant_<platform>`；集中報表資料庫用中立名稱。平台代碼固定使用小寫識別碼，例如 `104`、`yes123`。 |
| PostgreSQL schema | `bronze` 保存來源證據，`silver` 保存正規化資料，`gold` 發布消費者契約；FDW foreign tables 放 `fdw_<platform>`，不得和本地 Silver 混放。 |
| Bronze/Silver 欄位 | `snake_case`；保留來源原始代碼為 `text`，不可將有前導零、底線或其他符號的代碼轉成數字。 |
| Power BI Gold 欄位 | 欄位名稱與型別固定對齊 TMDL；既有 `FactJob` 使用 camelCase 欄名。改名或改型別須當成模型破壞性變更處理。 |
| 時間 | Bronze/Silver 使用 `timestamptz` 保存時間點；Gold `snapshotDateTime` 若轉成台灣本地時間，必須在欄位說明固定註明 `Asia/Taipei`。日期欄用 `date`。 |
| 缺值 | `NULL` 表示來源缺值或尚無可確認值；零、空字串、`unknown` 哨兵值不得代替缺值。若缺值有不同成因，另存品質狀態或原因碼。 |

平台代碼應由一份中央平台登錄規則管理，避免每張表都用固定平台清單的 `CHECK`；新增平台時不應需要逐表改 constraint。展示名稱可另行維護，不可把展示名稱當資料鍵。

## 鍵與資料粒度

### Bronze

| 物件 | 一列代表 | 身分與必要欄位 |
|---|---|---|
| `bronze.capture_batches` | 一次來源查詢批次 | `batch_id`；另保存 `source_platform`、`series_key`、日期時間、`code_kind`、原始搜尋代碼、請求、manifest/hash、列數與明確狀態。 |
| `bronze.capture_pages` | 一批次的一個來源頁面 | `(batch_id, source_page)`；保存來源 checksum、HTTP/擷取 metadata、頁列數。 |
| `bronze.raw_job_rows` | 一批次一頁中的一個來源列 | `(batch_id, source_page, row_index)`；原始 payload 不因 Silver 修正而覆寫。來源職缺 ID 可空，因解析失敗資料也須可追查。 |

擷取條件身分至少包含 `(source_platform, code_kind, native_search_code)`；不同平台的代碼即使字串相同也不是同一代碼。完整性未通過或 normalization 被阻擋的批次可留在 Bronze，但不可進入目前職缺 Gold。

### Silver

| 物件 | 目標粒度／鍵規則 | 契約 |
|---|---|---|
| 目前職缺 | 每一 `(source_platform, native_job_id)` 一列 | 兩欄均為來源身份；`source_job_key` 是 ETL 產生的穩定、無碰撞字串鍵。不得只靠裸 `native_job_id` 跨平台關聯。 |
| 職缺快照 | 每一來源、查詢系列、日期、批次、職缺一列 | 身分包含 `(source_platform, series_key, snapshot_date, batch_id, source_job_key)`；重抓批次不覆寫舊觀測。 |
| 技能／分類橋接 | 每筆觀測中一個職缺與一個來源技能／分類一列 | 保存來源原碼與批次；跨平台共用分析只透過有證據、可追溯的 crosswalk。 |
| 公司／地點 | 一個來源實體或一個已確認的跨來源實體一列 | 公司名稱相同不等於同一公司；地址相似不等於同一地點。跨平台合併須有明確 matching provenance。 |
| Crosswalk | 一個來源代碼系統中的一個原碼對一個候選標準碼 | 主鍵需包含平台、代碼種類／taxonomy 與原碼；保存 `CONFIRMED`、`PENDING_REVIEW`、`UNMAPPED` 或 `BLOCKED` 狀態、證據與覆核紀錄。 |

目前 Semantic Model 的橋接關聯使用 `jobNo`，所以兼容期間 Gold `jobNo` 必須是全平台唯一鍵，且值與穩定 `sourceJobKey` 一致；保留獨立的 `sourcePlatform` 和 `nativeJobId` 欄位。後續若改成 `sourceJobKey` 關聯，須同步更新 Fact、bridge、TMDL 關聯和 measures，不能只改 SQL。

若來源未提供公司 ID，不得把所有這類職缺寫成同一個 `unknown` 公司鍵。應保留事實列、標記公司身份未解析，且不能製造跨職缺的假關聯。

### Gold / Power BI

所有視圖都必須記錄欄位、型別、資料粒度、唯一鍵、來源資格條件與缺值語意。Gold views 不執行來源 API 擷取，也不掩蓋 Silver 的品質錯誤。

| Power BI／Gold 邏輯表 | Gold view | 一列代表／唯一性要求 |
|---|---|---|
| `FactJob` | `gold.pbi_fact_jobs_v21` | 每個平台來源職缺的最新合格觀測一列；模型以 namespaced `jobNo` 作相容鍵並宣告 `sourcePlatform`。DB view 的 `nativeJobId`、`sourceJobKey` 尚未宣告在 TMDL。yes123 的 `salaryLow`、`salaryHigh` 維持 null，避免未知給薪週期混算。 |
| `FactJobSnapshot`（暫停匯入） | `gold.pbi_fact_job_snapshots_v21` | 一個來源職缺的一次已保存快照；Gold 保留批次、系列、日期及職缺鍵。自 2026-10-10 起不載入語意模型；v21 本地分支未篩選 `source_platform`，把 4,497 筆 yes123 列標成 104，且查詢序列粒度不適合作為職缺每日趨勢的直接列數。 |
| `FactSalaryObservation`（暫停匯入） | `gold.pbi_fact_salary_observations_v21` | 每一來源／查詢系列／日期／批次／職缺／薪資來源類型／提及序號一列；保留原始值、幣別、週期和解析狀態。自 2026-10-10 起不載入語意模型；v21 未篩選各來源最新完整批次或跨序列重複，本地分支也把 yes123 前綴列標成 104。 |
| `BridgeJobCategory` | `gold.pbi_bridge_job_category_keys_v21` | 每個 `jobNo × confirmed canonical job category` 一列。 |
| `BridgeJobSkill` | `gold.pbi_bridge_job_skill_keys_v21` | 每個 `jobNo × confirmed canonical skill` 一列；active PBIP 只載入關聯鍵，技能描述由 `gold.pbi_dim_skill_v21`／`dim_技能` 解析；來源沒有技能時維持無橋接列，不推測技能。 |
| `DimCompany` | `gold.pbi_dim_company_v21` | 每個模型公司鍵一列；不能因同名自動跨平台合併。 |
| `DimArea` | `gold.pbi_dim_area_v22` | 每個平台與原生位置鍵一列；`jobRegion` 保留來源／外國區域標籤，`jobCounty` 僅填可辨識的台灣縣市，`jobTownship` 填縣市後的鄉鎮市區；未能標準化的位置保留未知狀態。 |
| `DimJobCategory` | `gold.pbi_dim_job_category_v21` | 每個 canonical 職類鍵一列；附 `goldenL1Code`／`goldenL1Name`，以已驗證 104 目錄的 18 個根類別作 Golden L1 baseline；只有 crosswalk `CONFIRMED` 的來源分類才可歸入，未映射來源碼進入 `待對照／BLOCKED`。 |
| `DimSkill` | `gold.pbi_dim_skill_v21` | 每個確認的標準技能鍵一列。 |
| `DimDate` | `gold.pbi_dim_date_v21` | 每個日曆日期一列，日期範圍涵蓋事實日期。 |
| `FactAcquisitionCategory` | `gold.pbi_acquisition_categories` | 每個來源平台與原生職類一列；保留 104 佇列狀態及 yes123 已記錄批次狀態，另帶 `sourcePlatform`、`batchCount`。yes123 的 `STALE`、`NOT_CAPTURED` 表示最新批次日期上的觀測狀態，不是即時佇列狀態；原生分類碼不跨平台合併。 |

PBI view 的欄位契約以目前 TMDL 欄位為相容基準；DB view 多出的 lineage 欄位需明確列為內部欄位，不能默認已存在於 Semantic Model。新增模型欄位只可追加；移除、改名、改型別或改粒度都需先升版並同步 TMDL。Power Query 保持 Import reader：只導航 Gold view，不做欄位修正、聯結、正規化或資料品質補救。

Fact 之間共用 `dim_職缺` 的後續粒度、鍵與批次驗收設計見 [Power BI fact constellation v22 design](powerbi-fact-constellation-v22-design.md)。該設計尚未發布為資料庫 migration。

目前每個模型表的公開欄位名稱與語意型別，以 `PBI_JobWant.SemanticModel/definition/tables/*.tmdl` 中的 `column`、`dataType`、`sourceColumn` 為準；Gold SQL view 的名稱與 SQL 型別須逐欄映射至此契約。不可因資料庫 view 回傳額外欄位，就視為該欄已進入 Semantic Model。例：目前 `FactJob` TMDL 有 `sourcePlatform`，尚無 `nativeJobId` 或 `sourceJobKey`；模型實際關聯仍使用 `jobNo`。

## 薪資與品質欄位

- 原始薪資文字保存在 Bronze/Silver；只有單位、幣別、上下限與給薪週期有可追溯證據時，才填入正規化薪資數值。
- 尚未解析、未揭露、面議、平台哨兵值及格式錯誤須有不同狀態；不可把它們改成 0 或偽造上下限。
- Gold 需能區分「來源未提供」、「來源不適用」、「解析待覆核」和「已確認數值」。單純 `NULL` 不可被解讀成零。
- 每列 Silver/Gold 事實保留足以追到 `batch_id`、`series_key`、`snapshot_datetime`、`source_platform` 的 lineage。Gold 最新值的挑選規則必須 deterministic，並只考慮合格批次。

## Migration 與發佈規則

1. Migration 必須有單一可重播的權威順序；已套用版本不可只靠手動插入版本號宣稱完成。所有平台資料庫應可比較實際 DDL，不只比較最大版本號。
2. Migration 不得把密碼或其他憑證寫入 SQL。FDW user mapping 使用執行環境的 secret 管理；foreign tables 置於平台專用 schema。
3. 不用 `DROP SCHEMA ... CASCADE` 刪除正在被 Gold 引用的 foreign tables。需替換 FDW 物件時使用先建立、驗證、切換、後清理的順序，並在交易失敗時保留舊契約。
4. 原始 Bronze 批次不可由 schema migration 重寫或刪除；改鍵須先有可回復的 backfill、孤兒檢查和舊新鍵對照。
5. 新增或修改契約時，先列出 Gold view 存在性、欄位/型別、grain、鍵唯一性、bridge orphan 和每平台筆數驗收條件。通過後才刷新 Desktop、儲存並重開 PBIP。

## 本機現況與差距（2026-10-09）

| 資料庫 | Schema 登記 | `gold.pbi_*` 實況 |
|---|---:|---|
| `jobwant_104` | migration 1–41 | 資料庫 Gold 保留 v21 相容 projections，並提供 v22 FactJob／DimArea、技能／職類橋接與跨平台來源欄位；FactAcquisitionCategory 讀取跨平台 `gold.pbi_acquisition_categories`。截至 2026-10-11，PBIP 載入 9 張模型表；FactJobSnapshot 與 FactSalaryObservation 的 Gold views 保留但模型匯入暫停。Migration 22 修正 salary currency FDW 為 `CHAR(3)`；migration 23 將 yes123 Gold scope 作單次 foreign projection；migrations 025–041 由受控 runner 依序套用，migration 041 發布 `jobRegion`、嚴格 `jobCounty` 與 `jobTownship` 階層；並保留 v21 物件供相容讀取器使用。Active FactJob 讀取 `gold.pbi_fact_jobs_report_v22`，canonical `gold.pbi_fact_jobs_v22` 保留完整 lineage 欄位。
| `jobwant_yes123` | migration 1–19 | 提供平台自己的 Gold PBI views；migration 23 使用 `gold.pbi_fact_job_scope` 作唯讀來源。Power Query 不直接連接此資料庫。 |

2026-10-10 的 PBIP 調整已完成 Desktop 全模型刷新、儲存、關閉及重開；9 個分割區為 `Ready`，模型含 21 個 expressions 與 7 條關聯。Migration 038 將職缺職類對照縮減為關聯鍵欄位，394,580 筆鍵集合完全相同；改版後兩次全模型刷新為 42.17 秒與 39.34 秒，相較先前 64.94 秒與 67.36 秒明顯下降。

目前 `silver.job_current` 在兩個資料庫都以 `job_no` 作單欄主鍵；yes123 loader 使用 `yes123:` 前綴寫入 `job_no` 和 `source_job_key`，目前可避免兩平台常見 ID 碰撞，但資料庫尚未用 `(source_platform, native_job_id)` 唯一約束表達正式身份。需採分階段 migration 保護 `job_snapshots`、兩種 bridge 及 TMDL 關聯。

截至 2026-10-09 的 Desktop 表級刷新（停載前歷史紀錄），模型曾載入 39,392 筆 yes123 FactJob、216,488 筆 yes123 FactJobSnapshot、430,812 筆 yes123 FactSalaryObservation。來源庫仍在寫入；刷新後讀到的 Silver 原始快照和薪資數高於模型載入快照，因此這些數字不是持續即時值，也不是 2026-10-10 之後的載入狀態。接入數量不代表資料使用授權、分類 mapping、薪資週期比較或技能涵蓋已解除阻擋。

`tools/sql/init_postgres_schema.sql` 建立原有單平台 PBI view set；受控 runner 現已管理 migrations 020–041，並以交易、連續版本及實際 Gold object 檢查作為 gate。Migration 020 的舊 FDW lifecycle 不安全，不可盲目重播；credential 必須只透過環境 secret 管理。FactJob 已由 migration 23 改成讀取來源 Gold scope view，v22 FactJob／DimArea 再以 026–041 完成去重、平台隔離、地區標籤、嚴格縣市／鄉鎮市區階層、橋接鍵縮減與 active report projection。`tools/sync_lake_to_postgres.py --write` 仍會重套 version-19 schema，維持 blocked。

### 尚未解除的導入閘門

- yes123 資料批次的保存、分析及展示權限仍須依 [yes123 導入盤點](../../data-reference/yes123-category-acquisition-probe.md) 記載的證據閘門確認。
- yes123 的 `WcodeList`、`JcodeList` 與候選 JSON 目錄彼此映射未完成；既有 crosswalk seed 必須重新對照來源證據，確認前不得當成全平台 taxonomy。
- yes123 已確認欄位目前不足以建立技能橋接；沒有技能資料時維持空橋接，不補猜值。
- 來源資料庫與報表資料庫的正式複合職缺鍵、公司/地點跨平台 matching 與完整時區契約仍須列入後續 migration；薪資觀測的原始幣別與週期欄位已接入，但正規化和跨週期比較仍未完成。

## 實作順序

1. 以本文件核准的鍵、粒度和 view 欄位為準，建立兩個現有資料庫的欄位、constraint、view 定義差異表。
2. 決定遷移步驟：讓來源 DB 只保存平台 Bronze/Silver，集中報表 DB 發布唯一 Gold PBI 契約；保留相容鍵直到 TMDL 完成遷移。
3. 先修正 migration runner 與 FDW lifecycle，建立不含憑證且不使用 cascade 刪除契約的 migration。
4. 補齊及驗收中央 Gold views 和已知欄位/鍵問題；未通過授權或語意證據的 yes123 分類、技能、薪資仍維持明確的未映射/空值狀態。
5. 最後刷新 Power BI Desktop、保存、關閉並重開 PBIP，核對兩平台筆數和關聯完整性。
