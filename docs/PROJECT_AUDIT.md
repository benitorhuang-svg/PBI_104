# PBI_104 專案稽核與優化建議

## 1. 專案基本資訊

- 稽核日期：2026-10-05，Asia/Taipei。
- 範圍：現有磁碟上的 PBIP、PBIR、TMDL、27 份 M 查詢、樣本、九份 TASK 與設計／驗證文件。僅新增本文件。
- 入口：`PBI_104.pbip` → `PBI_104.Report/definition.pbir` → `PBI_104.SemanticModel/`。
- 技術：Power BI Desktop、PBIR、TMDL、Import model、Power Query M、內嵌 Python、pandas、cloudscraper、Windows system proxy。
- 套件管理：未發現 requirements／環境鎖定檔；不是 npm 專案，沒有前端 build 或 test scripts。
- 本次 shell Python 環境：Python 3.13.14、pandas 2.3.3、cloudscraper 1.2.71。套件 import 成功；未確認 Desktop 設定使用相同 interpreter。
- 開啟：`Start-Process .\PBI_104.pbip`。依既有規則，實作 TASK 後須在 Desktop 刷新、儲存、關閉、重開。
- Git 現況：已有 `.git/`，最新 commit 為 `162a193`；大量模型／報表修改與新增檔案尚未納入該 baseline。`AGENTS.md`、`README_TASKS.md` 的「沒有 Git」描述已過時。本次未 commit、stage 或改動 Git 設定。

本次執行的唯讀檢查：

| 檢查 | 結果 | 能證明的範圍 |
|---|---|---|
| JSON／PBIP／PBIR／PBISM 解析 | 60 份通過 | UTF-8 與 JSON 語法 |
| M 匯出與 TMDL named expressions 比對 | 27／27 一致 | 扣除 TMDL 外層縮排與行尾空白後，原始碼一致 |
| 模型靜態 inventory | 12 tables、210 columns、7 measures、8 relationships | 磁碟定義；不代表已載入資料的實際狀態 |
| PBIR inventory | 四頁、47 visuals；欄位／measure 引用無缺失、容器無超出畫布 | 靜態欄位引用及矩形邊界 |
| page-1 fixture | 20 unique jobs、15 companies、107 unique skill pairs、52 unique category pairs | 已保存樣本的資料形狀與鍵 |
| fixture SHA-256 | 與 `docs/api-schema.md:11` 一致 | 既有證據未被改寫 |
| `fx104GetPage` 內嵌 Python | AST 解析通過 | Python 語法，不含網路執行 |
| Python 依賴 | import 通過 | 本次 shell 環境可找到套件 |

**未執行 Desktop 刷新、即時 API 擷取、DAX 執行或報表點選。** Modeling MCP 回報需先接受 EULA，本次未變更授權狀態；環境未安裝 jsonschema，本次未安裝套件，故未宣稱完整 PBIR JSON Schema 或 TMDL parser 驗證。既有文件的 55 rows／Ready／87.27% 是先前驗證紀錄，不能當成本次即時結果。

## 2. 專案目錄結構

```text
PBI_104/
├─ PBI_104.pbip                  專案入口
├─ PBI_104.Report/               四頁 PBIR、47 個 native visuals、theme
├─ PBI_104.SemanticModel/        TMDL、關聯、DAX、model metadata
├─ powerquery/
│  ├─ 00_parameters/            8 個參數
│  ├─ 01_functions/             3 個函式
│  ├─ 02_source/                3 個 Source queries
│  ├─ 03_staging/               6 個 Staging queries
│  └─ 04_model/                 7 個 mdl_ queries 的完整 M 匯出
├─ docs/                        架構、schema、品質、模型與歷次驗證
├─ tasks/                       九份正式工作規格
├─ samples/raw/                 一份保存的 page-1 JSON fixture
├─ report-design/               四張核准參考圖及對應 design briefs
├─ 104-powerbi-codex-task-pack/  另一份任務文件副本
├─ .github/                     Copilot／Mermaid instructions，未見 CI workflow
└─ AGENTS.md / README*.md        工作規則與專案導覽
```

`.pbi/` 與 `cache.abf` 是 local state，未檢查或修改。任務包副本中五份 Markdown 與正式文件完全相同，另五份已有差異；應指定 `tasks/` 為工作規格來源，將副本標記為歷史參考，避免雙向維護。這次不刪檔。

## 3. 核心功能推測

由來源與 PBIR 可確認的功能配置：

- 使用八個參數擷取 104 職缺搜尋 API，保留 raw nested JSON、請求 metadata 與擷取時間。
- 正規化職缺、公司、地點、技能、職類代碼，輸出 Fact／Dimension／Skill bridge。
- 建立職缺市場總覽、薪資原始值分析、技能關聯分析、職缺探索四個報表頁。
- 七個 explicit measures 提供職缺數、公司數、原始薪資界限覆蓋率、API applyCnt 總和與技能職缺數／比例。

上述是配置與計算定義；使用者互動是否符合畫面名稱，仍需 runtime 驗證。薪資單位／特殊值語意、職類名稱映射、歷史趨勢仍是明確的 `BLOCKED`。`Active Jobs` 實際為本次載入的 distinct jobNo，不能據此判定職缺的歷史有效狀態。

## 4. 架構分析

### 查詢與載入

目前主路徑是 `Parameters → fx104GetAllPages → src_104Result → Source projections → Staging → mdl_ → imported tables → relationships/measures → PBIR`。`expressions.tmdl` 共有五個 query groups、27 個 expressions；七張 M partitions 引用 `mdl_` expressions。`DimDate` 為 DAX calculated table，並非第八個 M query。磁碟定義符合非 Model 層不建立 loaded tables 的方向；Desktop 的 Enable Load 仍須在實作 TASK 後驗證。

分層大致清楚，但 `FactJob.pq:37-76` 還在轉換 snapshot 日期、建立 areaKey 與解析 link JSON；`DimArea.pq:4-19` 重複建立 areaKey。這些應在獨立 Staging 重構 TASK 中集中，Model 保留投影與 grain/key gates。areaKey 是目前可證明重複且穩定的規則，適合有明確輸入／輸出的共用 fx。

### API 與刷新

`fx104GetPage.pq:113-146` 保留 cloudscraper、系統代理、30 秒 timeout 與 HTTP error；`155-174` 檢查 data／metadata 的外層型別。`fx104GetAllPages.pq:24-55` 驗證第一頁 pagination，後續頁面只呼叫並合併（`61-79`），未對每頁 currentPage／count／total 做 reconciliation。

`查詢.tmdl:958-1049` 仍有另一段 Python API 擷取，硬編碼 page 1 與原參數；新報表的靜態 query references 沒有引用這張表。保留此 loaded partition 會讓刷新保留一條獨立擷取路徑，也增加舊／新資料不一致的可能。

多個 loaded model queries 都參照同一個 Source，這能共用程式碼，不能保證每次刷新只打一次 API。Microsoft 說明 referenced queries 各自求值，Table.Buffer 也不會跨查詢共用結果；實際 HTTP 次數需量測。參考：[Power Query referenced queries](https://learn.microsoft.com/en-us/power-bi/guidance/power-query-referenced-queries)。

### Semantic Model 與日期

新關聯主要為單向 dimension → fact → bridge；`DimJobCategory` 因多值分類尚無橋接關聯。`DimDate` 同時連到 FactJob.appearDate 與 FactJobSnapshot.snapshotDate，但日曆只依 FactJob.appearDate 的 MIN／MAX 建立（`DimDate.tmdl:43`），沒有覆蓋 snapshotDate 的保證。`__PBI_TimeIntelligenceEnabled = 1` 與舊 auto-date tables 仍保留。

`FactJobSnapshot.pq` 每次只取 `stg_Jobs`，沒有 append store，故目前只有當次快照。`docs/data-model.md:96-110` 已如實記錄此限制，方向正確。

### 報表、狀態與導覽

PBIR 是四個 1280×720 pages，採原生頁籤導覽。沒有前端 router、PWA、Service Worker 或瀏覽器 localStorage；這些前端項目不適用此專案。

目前資料來源與擷取參數由 Power Query 決定；Import 報表中的 slicer 只篩選已載入資料，不會送出新的 104 API 查詢。來源關鍵字、日期角色、raw 薪資數值應在產品文案中清楚標示。

## 5. 目前風險

| 優先 | 類別 | 證據與問題 | 影響／驗證邊界 |
|---|---|---|---|
| P1 | 篩選正確性 | `relationships.tmdl:19-25` 沒有 bridge → FactJob 回傳路徑；Page04 skill_slicer 用 DimSkill，matched_jobs_card／job_list 用 FactJob | 依磁碟拓撲推論，技能選擇不會篩選 FactJob KPI／清單；需以單選、多選、與地區交集做 DAX／Desktop 驗證 |
| P1 | 資料品質 | `stg_JobSkills.pq:13-15,48`、`stg_JobCategories.pq:13-15,30-33` 將 malformed JSON／錯誤形狀當空集合，並排除無效鍵 | API 漂移會被誤看成沒有技能／分類；Model 的 duplicate/null 檢查無法看到已排除的資料 |
| P1 | 擷取完整性 | fx104GetAllPages 只檢查首頁，後續直接合併 | 後續頁碼錯誤、提早空頁或 metadata 漂移可能形成不完整批次；現有程式不能保證完整性，不代表已發生遺漏 |
| P1 | 日期契約 | DimDate 只涵蓋 appearDate，但也關聯 snapshotDate；沒有明確空資料策略 | 擷取日晚於最大來源日期時可能有日期 orphan；合法空結果時日曆／資料型別能否刷新，尚未驗證 |
| P2 | 搜尋行為 | Page04 keyword_slicer 綁 `FactJob.sourceKeyword`，標題為「搜尋 / Search Jobs」 | 此欄是擷取參數，不能搜尋職稱／公司／描述；單一 keyword 批次通常只有一個可選值 |
| P2 | 指標語意 | Jobs with Salary 只判兩個 bounds 非 blank；page-1 fixture 有 8 筆 (0,0)、4 筆含 9999999 | 目前覆蓋率代表原始數值完整性，不能稱為薪資揭露率；不應直接新增平均／中位數 |
| P2 | 刷新／維護 | 舊查詢仍 loaded，114 欄占磁碟定義 210 欄的一半以上；新模型有七條引用來源的載入路徑 | 可避免的模型寬度與獨立擷取；實際記憶體／API 呼叫次數／刷新耗時尚未量測 |
| P2 | 報表粒度 | Page04 job_list／preview 為 pivotTable，Rows 未含 jobNo；Page03 skill_count_card 是 DimSkill.skillDescription 的 CountNonNull | 無明確 jobNo 粒度保障；技能卡是描述筆數，且 fact 篩選無法回傳到 DimSkill，可能不隨地區／產業更新 |
| P2 | 報表可讀性 | 職類以 jobCatRaw JSON array 作 slicer／分組；Top Skills 未配置明確 Top N 或排序 | 是分類集合而非逐職類統計；「Top」名稱與實際排序／截取需確認 |
| P2 | 文件／重現 | architecture、README_TASKS、powerquery README 仍描述早期狀態；沒有環境鎖定與自動驗證入口 | 後續工作可能依舊前置條件重複實作；新機器的 Desktop runtime 是否可重現未知 |

`docs/semantic-model.md:44-45` 把單向篩選寫成 fact → dimension，與 Power BI 的 one-side → many-side 規則不符；這是文件方向錯誤，不能照此文字修改模型。[Microsoft relationship filtering](https://learn.microsoft.com/en-us/power-bi/transform-model/desktop-relationships-understand)。

安全邊界：未讀取 cookies／credentials／proxy values，也未做全面 secret scan。來源資料與 jobLink 是外部輸入，應在 Staging 對錯誤形狀、URL scheme／host 做可診斷的契約檢查，保留 API 原值而非猜測連結規則。沒有 RLS 本身不是本機公開職缺專案的缺陷；部署到多使用者環境後再依需求決定。

驗證缺口：本次的 JSON 語法、欄位存在與 M 原始碼比對均通過，仍不足以證明 filter context、selection → preview、URL 點擊、字體／可讀性或 live API 完整性。現有 runtime 文件主要記錄正常資料與總量，缺少完整的互動交集及 malformed／空結果 gates。

## 6. 優化建議

### 立即，先降低結果錯誤的風險

1. 補技能選擇到職缺清單／KPI 的 filter contract。先決定多技能為 OR 或 AND，再使用必要且有限的 filter 回傳，或專用 DAX measures／visual filters；避免把所有關聯改雙向。`Skill Share %` 的分母也要一起驗證，不能因 filter 路徑改變而退化為 100%。Microsoft 建議盡量減少全域雙向篩選，也提供 measure 內 CROSSFILTER 的做法。[Bi-directional filtering guidance](https://learn.microsoft.com/en-us/power-bi/guidance/relationships-bidirectional-filtering)。
2. 區分合法空 list、缺欄、null、無效 JSON 與錯誤型別；在 Staging 給明確錯誤或品質記錄。可選欄位缺少時依既有 TASK 保持 null-safe；必要鍵失敗不可無聲丟資料。
3. Source 對每頁做 requested/current page、count／rows、pagination 一致性檢查。遇到 API 在翻頁中變動，回報不一致的批次，不湊齊假資料；起始頁不是 1 時須使用明確的子範圍契約，不直接拿其筆數等同 total。
4. 日期涵蓋 appearDate 與 snapshotDate，並測試整批無結果。讓報表日期角色可辨識；若未來需要 time intelligence，再依使用方案補足日曆年度與 date-table 設定。[Date table guidance](https://learn.microsoft.com/en-us/power-bi/guidance/model-date-tables)。
5. 同步文件現況，指定唯一工作規格來源與最新驗證日期。保留先前驗證紀錄為歷史證據，補當前狀態索引，不把舊數字寫成最新 live 結果。

### 中期，縮短刷新與降低維護成本

- 先量測完整刷新時間、每頁 HTTP 次數與各表來源批次。檢查舊查詢的 DAX／PBIR／外部依賴後，在獨立相容性 TASK 中退役其 loaded 路徑；先保留可恢復的原始碼。
- 如果量測證實每張表重複擷取，採一次完整擷取後供各表讀取的固定批次。仍保留 cloudscraper＋Windows proxy；新的讀取路徑先與現有結果逐鍵比對，避免未測試替換。
- areaKey、jobLink 與日期 parsing 集中到 Staging；對 Fact／Dimension 做同批次 orphan reconciliation。把數字代碼、座標與技術欄位設為適當的非加總／隱藏欄位，保留 raw 值可回溯。
- 報表 TASK 單獨處理：來源關鍵字改正確名稱；需要文字搜尋時再定義職稱／公司／描述範圍；清單與選取加入 jobNo 粒度；薪資卡標為「原始界限欄位完整率」；技能數改以當前 bridge 的 distinct skillCode；排行榜明確排序／Top N。
- 職類需求若成立，先用已確認的 jobNo × jobCatCode 建 bridge；名稱映射繼續 `BLOCKED`，不強迫多值職類成為單一 fact key。
- 建立簡單唯讀檢查入口：JSON 語法／schema、M↔TMDL 原始碼一致、模型欄位引用、fixtures、關聯拓撲。實作中只測該層契約，Desktop gate 仍獨立保留。
- 紀錄並鎖定「Desktop 實際使用」的 Python 與必要套件版本；不因 shell import 成功而認定 Service 可刷新。

### 長期，產品需要趨勢或部署時再擴充

- 若需要職缺／技能趨勢，先建立可持久化且可重跑的批次與 snapshot store。定義一日多次刷新、keyword／area 多批次及同職缺跨查詢去重規則，再加入 period-over-period measures。
- 外部固定批次也可改善不同表於不同時間看到資料的問題。這一步應有獨立 storage／刷新契約與失敗保留策略，無須先遷移整套技術。
- 若要 Power BI Service 排程，先做最小刷新驗證；目前 Python in Power Query 的官方說明要求 Personal Gateway 與 Python 所在機器可用。部署成功不能由 Desktop 成功推定。[Python in Power Query](https://learn.microsoft.com/en-us/power-bi/connect-data/desktop-python-in-query-editor)。

## 7. 下一步任務建議

以下恰為五個可獨立排程的工作單元；是建議，這次未建立新 TASK 或實作。每項先 inventory，只改指定層；後續交付 M 時提供所有必要 queries 的完整碼，保留 IDs／lineage tags。

### OPT-001：技能篩選的 Semantic Model 契約

- 目標：讓選定技能與地區／產業的交集有可驗證的職缺集合，維持技能比例分母定義。
- 範圍：relationships、必要 DAX 與 `docs/semantic-model.md`；不改 PBIR 或 Power Query。
- 驗收：未選、單選、多選、與地區交集，與 bridge 去重職缺集合一致；排除未選技能的職缺；原有總量與比例定義保持正確。若方案需新 measure／visual filter，明列供 OPT-005 接線的契約。
- 驗證：`Start-Process .\PBI_104.pbip`；Desktop DAX view 執行 `EVALUATE ROW("Jobs", [Active Jobs], "SkillJobs", [Skill Job Count], "Share", [Skill Share %])`，另用真實 skillCode／area 的 CALCULATETABLE 交集 query 比對 jobNo 集合。保存各 filter case，不只保存未篩選總量。

### OPT-002：Source 每頁完整性驗證

- 目標：後續頁異常不能成功載入成完整批次。
- 範圍：fx104GetAllPages／必要 Source function 與 `docs/api-schema.md`；不改 Staging、DAX 或報表。
- 驗收：每頁 currentPage／count 對得上 request／rows；正常三頁、合法零結果、後續頁碼錯誤、total 漂移與途中 HTTP 失敗有明確結果。保留已驗證的 cloudscraper／system-proxy 路徑及所有 raw 值。
- 驗證：`python -B -c "import pandas, cloudscraper; print('ok')"`；`Start-Process .\PBI_104.pbip`，在 Power Query 對完整 src_104Result 與 metadata 做同批次對帳，再 save／close／reopen。異常頁面用 mock／sanitized fixture，不增加任意 live requests。

### OPT-003：Staging 不再吞掉技能／分類解析失敗

- 目標：保留合法空資料，讓形狀漂移與被排除資料可診斷。
- 範圍：stg_JobSkills／stg_JobCategories 及必要重複解析 fx、品質文件；不改 Model、DAX 或 PBIR。
- 驗收：正常 fixture 仍有 107 unique skill pairs／52 unique category pairs；空 list 是零子項；malformed JSON、object 取代 list、缺鍵與非法 item 有明確 error／quality outcome，不能當成零技能成功；非載入設定維持正確。
- 驗證：`Start-Process .\PBI_104.pbip`；Power Query 以 page-1 fixture 和隔離的異常 fixtures 執行解析／pair count／duplicate gates，再 save／close／reopen。M parsing 必須用 M runtime 驗證，Python 重新模擬不算替代。

### OPT-004：日期維度的覆蓋與空結果

- 目標：日期關聯對來源日期、擷取日期與合法空資料有明確契約。
- 範圍：DimDate 與必要日期關聯／metadata、模型文件；不改 Source、Staging 或報表。
- 驗收：所有非 blank appearDate／snapshotDate 都在日期維度中；擷取日超過最大 appearDate 仍有零日期 orphan；空 FactJob 時不因 MIN／MAX 無有效值而失敗。未知來源日期不被補成虛構日期。
- 驗證：`Start-Process .\PBI_104.pbip`；DAX view 執行 `EVALUATE EXCEPT(SELECTCOLUMNS(FILTER(FactJobSnapshot, NOT ISBLANK(FactJobSnapshot[snapshotDate])), "Date", FactJobSnapshot[snapshotDate]), SELECTCOLUMNS(DimDate, "Date", DimDate[Date]))`，預期零 rows；對 appearDate 另做同類檢查，並在隔離測試副本驗證零資料／較晚擷取日期。

### OPT-005：報表篩選與職缺粒度

- 目標：Page04 的技能選擇、清單、preview、Matched Jobs 一致；畫面名稱對應真實功能。
- 範圍：Page04 PBIR／design brief；其他頁只允許既有薪資標籤的明確命名修正。不新增未確認薪資／趨勢／文字搜尋能力。
- 前置：OPT-001 的模型契約完成；修改前 inventory Git baseline 與目前未提交成果，依核准參考圖。不得自行 commit。
- 驗收：jobNo 保證選取粒度；技能與其他 slicers 交集同時更新清單／KPI；選一筆只顯示該職缺 preview；sourceKeyword 顯示為來源關鍵字；原始 jobLink 可用。將新增文字搜尋與職類 bridge 留給獨立 TASK。
- 驗證：`Start-Process .\PBI_104.pbip`；執行四頁 JSON syntax／official schema 驗證，再點選 single/multi skill、地區交集、清除篩選與職缺選取，保存 screenshot；save／close／reopen 後重跑 Page04 互動。schema 通過不能代替點選驗證。
