# JobWant 完整優化實施方案

> 文件日期：2026-10-11（Asia/Taipei）
>
> 狀態：Phase A (OPT-01~03)、Phase B (OPT-04, OPT-09)、Phase C (OPT-06 平台維度與切片器改綁, OPT-07 記憶體盤點與關聯審計, OPT-08 地圖探索與 5000 點保護) 與 Phase D (OPT-10 採集截斷成因分析) 實作驗收完成；已套用 Migration 048、049、050，完成雙向零差異驗證、效能實測、PBIR 視覺改綁、Live Power BI Desktop 重新整理與 DAX 探針矩陣驗證。
>
> 適用範圍：104／yes123 採集與 ETL、PostgreSQL Bronze／Silver／Gold、Power Query Import、語意模型、PBIR、品質閘門。
>
> 決策順序：確認資料正確性與可恢復性 → 建立分層基準 → 小範圍實驗 → 契約驗收 → 切換與觀察。
>
> 交付紀錄：參閱 [優化驗收與基準報告](operations/optimization-acceptance-2026-10-11.md)；已交付基準資料包、ETL 寫入與防護解耦、職類映射稽核工具（`tools/audit_crosswalk_coverage.py`）、Migration 048（BridgeJobCategory 70.5s → 8.8s）、Migration 049（DimArea 41.9s → 5.5s）、Migration 050（DimPlatform 平台維度）、PBIR 切片器視覺綁定（Pages 01~04 改綁 `dim_平台.平台名稱`）、BPA 規則與自動化閘門。

## 1. 方案定位與優化目標

本方案整合並修正 [資料庫優化建議](database-optimization-recommendations.md) 與 [系統優化建議](system-optimization-recommendations.md)。兩份原稿保留為提案來源；後續優先順序、實施條件與驗收以本方案為依據。原稿中的「全模型 2 秒」「提升 3～5 倍」「覆蓋率 98%」「文字占 65% 記憶體」均未作為已證實結果或交付承諾。

優化要達成五個可分別驗證的成果：

1. 資料可信：來源範圍、職類映射、完整批次、鍵值與薪資語意不因加速而改變。
2. 刷新可預期：知道時間耗在哪些 Gold 查詢、傳輸與模型處理，改善經重複量測的瓶頸。
3. 報表可使用：平台選項、技能／職類篩選、地圖與職缺清單行為一致，無資料時能解釋原因。
4. 採集可恢復：保留不可變來源證據，支援斷點續作，明確呈現截斷、漂移、阻擋與未知覆蓋範圍。
5. 維護可持續：每項變更有責任邊界、品質閘門、失敗處理、回復路徑與操作文件。

目前是 Import 模型：PostgreSQL 主要服務刷新時的來源查詢；一般報表互動讀取已匯入的模型。資料庫索引或物化改善不能直接當成 DAX、切片器或地圖加速的證據。[Microsoft：語意模型模式](https://learn.microsoft.com/en-us/power-bi/connect-data/service-dataset-modes-understand)

### 1.1 固定架構邊界

- 入口保持 `PBI_JobWant.pbip` → `PBI_JobWant.Report/` → `PBI_JobWant.SemanticModel/`。
- 採集、驗證、正規化、去重、映射、地區整理及彙整由 Python／PostgreSQL 執行。
- Power Query 僅保留 `00_Parameters / 01_Functions → 02_Source → 04_Model`；不恢復 API、JSON 或 `03_Staging` 轉換路徑。
- 只有 Model 查詢 Enable Load；Source、Function、Parameter 均 Disable Load。
- DAX／關聯在語意模型，視覺與互動在 PBIR；資料庫、模型與報表變更分批交付、分別驗證。
- 保留 `data/104/`、各平台來源批次、manifest、原始雜湊、既有 lineage tags 與 visual IDs。
- 保留 `cloudscraper` 與 Windows 系統代理機制，直到替代方案通過同等來源契約驗證。
- 新增或修改的維護性 Python／JS／TS 模組及測試維持每檔不超過 300 行；共用與平台專屬程式遵守 [acquisition package map](../tools/acquisition/README.md)。

## 2. 已核對現況與待確認事項

本節區分 2026-10-11 的磁碟定義與本次唯讀資料庫複核；磁碟定義不等於 Desktop 已載入。已執行 `python tools/check_migration_state.py`，確認 `jobwant_104` 的歷史連續至 47、`pendingVersions=[]`、`status=READY`、`legacyWriteBlocked=true`。另於 14:00（Asia/Taipei）唯讀確認 yes123 crosswalk 有 574 列、574 個不同原碼。這些結果證明版本／數量，不能代替 mapping 正確性、writer 相容性或完整刷新驗收。

| 項目 | 本次可確認的現況 | 實施前仍需確認 |
| --- | --- | --- |
| Git 基線 | 本次 `HEAD` 為 `4dec422`；`AGENTS.md` 記載歷史基線 `162a193` | 記錄實施當下 HEAD、工作目錄差異與未追蹤檔；不能只依歷史 hash 復原 |
| 既有未提交內容 | `docs/README.md` 已修改；兩份建議與 migration 047 尚未追蹤 | 保留其內容；不要重編號、覆寫或自動提交 |
| 模型 | 九張 Import 表、七條關聯，其中四條為雙向 | Desktop 實際載入版本、分割區狀態與數量 |
| FactJob | active reader 使用 `gold.pbi_fact_jobs_report_v22`，14 個來源欄位 | 即時型別、列數、鍵唯一性、來源範圍 |
| 橋接表 | 技能與職類 active reader 都使用只含關聯鍵的 v21 相容投影 | 後續 Gold view 定義與來源映射是否符合契約 |
| 採集 | 預設 `pagesize=30`，程式上限 150 頁；已有共享限速、指數退避與隨機抖動 | API 當下是否接受參數、回應實際頁容量、頁數與 total 一致性 |
| Bronze | schema 有 `payload`、`payload_source_json`；不是原稿的 `raw_payload` | 即時欄位、壓縮方法、各欄位實際占用及可歸檔批次 |
| PostgreSQL 設定 | migration 036 已定義報表角色／資料庫範圍的 `work_mem=128MB` | 實際會話生效值；不可假設所有參數仍是預設值 |
| 寫入路徑 | 舊 sync 路徑仍使用 v19 init schema；共用 schema guard 會阻擋受保護資料庫 | 合格批次的相容 ETL 寫入流程與目前實際執行狀態 |
| migration 047 | 本機已套用（APPLIED）；歷史連續至 47、無待套用版本；列為 OPT-03 治理與補正對象 | 規則與人工確認證據、命中範圍及語意差異；規劃 migration 048 補正，不重播 047 |
| 地圖 | Page 04 實際頁 ID 為 `835ef39d8889ed779e14`；目前 PBIR `visualType` 為 `map`；DAX 有 5,000 點門檻 | Desktop 呈現與核准設計的差異；不能直接沿用舊文件的 Azure／ArcGIS 敘述 |
| CI | Ubuntu 執行 Python 測試與結構檢查；validator 明確區分 Desktop parser 不可用 | Windows／TOM 解析執行環境與 BPA 規則版本 |

主要現況依據：[關聯定義](../PBI_JobWant.SemanticModel/definition/relationships.tmdl)、[目前職缺模型](../PBI_JobWant.SemanticModel/definition/tables/目前職缺.tmdl)、[來源投影](../tools/sql/migrations/040_project_fact_job_report_columns.sql)、[採集限速](../tools/acquisition/platforms/jobwant_104/distributed/pacing.py)、[分頁契約](../tools/acquisition/platforms/jobwant_104/client/pagination.py)、[schema guard](../tools/acquisition/shared/postgres_schema.py)、[實際地圖定義](../PBI_JobWant.Report/definition/pages/835ef39d8889ed779e14/visuals/9e3291bd294b973364d6/visual.json)。

### 2.1 目前應保留的 Gold／Import 契約

下表列的是 active M reader 名稱；v21 名稱可能已由後續 migration 更新內容，不能從名稱推斷仍是舊邏輯。

| 模型邏輯表 | Gold view | 核心粒度／不變量 |
| --- | --- | --- |
| FactJob／目前職缺 | `pbi_fact_jobs_report_v22` | 每個帶平台識別的 `jobNo` 一列最新合格觀測；不代表即時在刊 |
| DimCompany | `pbi_dim_company_v21` | 每個模型公司鍵一列；同名公司不可直接合併 |
| DimArea | `pbi_dim_area_v22` | 每個 `areaKey` 一列；位置範圍、來源地址與真實座標可追溯 |
| DimDate | `pbi_dim_date_v21` | 每個日期一列，覆蓋 active 日期關聯 |
| DimSkill | `pbi_dim_skill_v21` | 每個技能碼一列；來源沒有技能時不推測補值 |
| DimJobCategory | `pbi_dim_job_category_v21` | 每個模型職類鍵一列；Golden L1 與未對照狀態可辨識 |
| BridgeJobSkill | `pbi_bridge_job_skill_keys_v21` | 唯一 `(jobNo, skillCode)` |
| BridgeJobCategory | `pbi_bridge_job_category_keys_v21` | 唯一 `(jobNo, jobCatCode)`；confirmed／未對照規則須核對 |
| FactAcquisitionCategory | `pbi_acquisition_categories` | 每個平台與來源職類的監看列；104 queue 與 yes123 批次狀態分開解讀 |

FactJob 14 欄契約如下；任何相容物化投影都必須保留名稱、型別、NULL 語意與日期時區：

```text
jobNo, custNo, areaKey, jobName, descSnippet, jobAddress, jobAddrNoDesc,
salaryLow, salaryHigh, appearDate, jobLink, snapshotDate,
snapshotDateTime, sourcePlatform
```

`FactJobSnapshot`、`FactSalaryObservation` 維持 [暫停匯入](../powerquery/archive/paused-facts-v21/README.md)。其歷史粒度與來源範圍須另案驗證，不藉本次效能工作自動恢復。

### 2.2 對原建議的正式修正

| 原提案 | 修正後決策 |
| --- | --- |
| 40 個 view 等於每次查詢都有相同高成本 | 只分析九個 active reader 及其相依執行計畫；view 數量不等於瓶頸數量 |
| 參數固定改成 4～8 GB／1.1 即可提升數倍 | 先量測 Docker／WSL／Desktop 共用資源，再一次調整一個變因 |
| `CONCURRENTLY` 是非同步增量更新 | 它允許讀取並行，仍會重算 backing query；排程、增量與一致性需另行設計 |
| BRIN 取代整張表 131 MB 索引 | 先逐索引盤點；BRIN 不取代 PK／UNIQUE 或所有等值查詢索引 |
| 開啟 LZ4 就能回收既有空間 | 設定不重寫既有資料；CPU、壓縮比、重寫成本與磁碟回收分別驗收 |
| 超過 60 天直接清除 Bronze | 保留期依重算、追溯及恢復需求決定；先驗證歸檔與還原，不預設刪除 |
| 所有關聯改單向 | 逐條建立篩選等價證據，特別保護技能、職類及清單→地圖的路徑 |
| 文字搬到 drill-through 即可節省 Import 記憶體 | 同一模型中的 Import 明細表仍占記憶體；先量測欄位容量與消費者 |
| 各頁切片器全部同步 | Pages 01–04 分析篩選與 Page 05 採集監看分開設計，避免跨粒度誤導 |
| 22 縣市切分可保證全台 98% | 先驗證來源地區碼、重疊、海外／未知／遠端工作及時間漂移；無母體證據不報百分比 |
| Ubuntu 直接執行 TE2 的 `dotnet tool ... -BPA` | 保留 Linux 檢查，先建立已驗證的 Windows 解析／BPA 路徑；跨平台 CLI 另作選項評估 |

## 3. 共用量測與驗收規格（OPT-01）

### 3.1 基準資料包

每次實驗建立一個唯一 `run_id`。原始輸出建議存放被忽略的 `.optimization/benchmarks/<run_id>/`；可分享、去識別的摘要放 `docs/operations/optimization-acceptance-<date>.md`。這些是預定產物路徑，本方案尚未建立。

每份資料包至少記錄：

- Git HEAD、dirty diff、未追蹤檔雜湊、候選變更；快照不得包含 `.env`、token 或帳密。
- 本機與容器 CPU／記憶體額度、Docker／WSL 限制、磁碟可用量、PostgreSQL／Desktop 版本。
- migration history、實際 view 定義、九個來源欄位契約、完整批次 ID／來源 watermark。
- 各表列數與鍵數、來源平台比例、NULL、孤兒鍵、職類未對照、來源日期與地區範圍。
- 查詢全文、執行角色、會話設定、開始／結束時間、是否有同時採集／ETL／刷新。
- 每次成功與失敗的原始耗時、資源峰值、錯誤；不只保留最快一次。

基準與候選必須使用相同輸入批次及模型。多次量測列數相同仍不足以證明資料相同，應保存來源批次清單與必要的內容對比。

### 3.2 分層指標

| 層級 | 必測項目 | 不可替代的證據 |
| --- | --- | --- |
| PostgreSQL | 實際投影的 `EXPLAIN (ANALYZE, BUFFERS, VERBOSE, FORMAT JSON)`、估計／實際列數、loops、temp I/O、排序與 FDW SQL | `COUNT(*)` 的快速計畫不代表 14 欄完整讀取速度；EXPLAIN 不包含客戶端完整傳輸成本 |
| 資料傳輸 | 用實際角色／連線取完投影結果的耗時與資料量 | 不只記 execute 或第一列到達時間 |
| Desktop 刷新 | 單表與全模型完成耗時、分割區狀態、記憶體峰值 | SQL 改善不能代替完整 Import、模型處理與刷新證據 |
| DAX／互動 | 固定篩選組合的查詢耗時、Page 04 點選至清單／地圖穩定顯示的耗時 | DAX probe 與滑鼠互動分開報告 |
| 採集／ETL | 有效頁數、唯一職缺、警告批次、429／challenge、重試等待、吞吐與可恢復性 | HTTP 200 或 queue DONE 不能單獨證明完整／正確 |
| 儲存 | heap、TOAST、索引、WAL／暫存與實際檔案系統占用 | relation 變小不必然等於 Windows 上容器虛擬磁碟立刻縮小 |

### 3.3 A／B 比較與採用規則

1. 先完成一輪初次開啟／連線記錄，再對基準與候選各暖機一次、各量測五次；可行時交錯 A／B，固定其他條件。
2. 一般實驗不清除使用者快取、不重啟資料庫製造冷快取；真正冷快取實驗僅在隔離環境另記。
3. 五次結果報中位數、最小／最大值及全部原始樣本；不以五次樣本推論可靠的 P95。長期互動指標累積至少二十次後再觀察 P95。
4. 若資料或背景工作有漂移，標成不可比較；不得刪除慢樣本後重新包裝成成功。
5. 技術正確性先過關，再比較效能。建議第一輪採用門檻為目標 Gold 查詢中位數改善至少 30%，或完整刷新改善至少 20%；這是選案門檻，不是預測值。
6. 未達效能門檻但有獨立可靠性／可維護性價值者，可按該目的交付；不得宣稱效能優化完成。其他關鍵工作負載若退步超過 10%，需分析原因並決定回復或調整。
7. 容量門檻按實際分配額度設定：無 OOM、非預期 swap 壓力及持續暫存耗盡，保留可量測的操作餘裕。

## 4. 分階段工作與依賴

P0 是正確性與安全執行前提；P1 是第一輪有價值的改進；P2／P3 由量測與成長需求觸發。`待量測` 不代表必須購置設備或全面重構。

| ID | 優先級 | 工作／主責 | 前置依賴 | 核心交付 |
| --- | --- | --- | --- | --- |
| OPT-01 | P0 | 分層基準／資料工程＋BI | 可讀取受測環境 | 第 3 節基準資料包與瓶頸排序 |
| OPT-02 | P0 | migration 與 ETL 相容／資料工程 | 實際 catalog、保留現有變更 | Step 1 先交付唯讀稽核；Step 2 才進行 writer 修復與隔離寫入測試 |
| OPT-03 | P0 | 職類映射稽核／資料治理 | 來源 taxonomy、已套用 047 的規則與影響 | 574 原碼稽核、確認／推導分離、migration 048 補正方案 |
| OPT-04 | P1 | Gold SQL／物化實驗／資料工程 | OPT-01；發布前過 OPT-02、03 | 一至兩個瓶頸的 A／B 證據與一致性方案 |
| OPT-05 | P1 | PostgreSQL／FDW 調校／資料工程 | OPT-01 資源與計畫 | 最小設定變更、重啟條件與回復值 |
| OPT-06 | P1 | 平台維度／BI＋資料工程 | 平台顯示規則、OPT-03 | 穩定分析平台選項與獨立監看行為 |
| OPT-07 | P1 | 篩選路徑與 Import 容量／BI | OPT-01、03、06 | 關聯等價矩陣、欄位容量與消費者清單 |
| OPT-08 | P1 | 地圖、清單與篩選 UX／BI | OPT-07、設計參考核對 | 分層探索與可解釋的空狀態 |
| OPT-09 | P1 | CI 與發布閘門／維護者 | 現有 validators／probes | Linux、Windows、live 三層證據 |
| OPT-10 | P1／按截斷程度排程 | 採集完整度／採集維護者 | OPT-02、03；API／地區契約已驗證 | 可恢復切片試點與覆蓋帳本 |
| OPT-11 | P2 | Bronze 壓縮與生命週期／資料工程 | OPT-01 容量證據與恢復試驗 | 壓縮比較、歸檔 manifest、還原結果 |
| OPT-12 | P2 | 索引與分區／資料工程 | 明確 SQL 工作負載與成長證據 | 專用索引或分區試點；不預設全面導入 |
| OPT-13 | P3 | 代理鍵／複製架構／架構維護者 | 現有路徑仍有已量測瓶頸 | 專案決策紀錄；不列入第一輪必要交付 |

建議分四批交付：A 為 OPT-01～03；B 為 OPT-04～05 並建立 OPT-09 閘門；C 為 OPT-06～08；D 為 OPT-10。A 的唯讀基準獨立交付，B 的計畫分析與隔離實驗不必等待人工映射審核；正式發布仍須通過受影響契約的治理／相容閘門。OPT-11～13 依觸發條件另排。若採集截斷已阻礙產品資料正確性，D 在必要前置完成後優先於視覺效能工作。

### 4.1 Phase A 的兩步交付

| 步驟 | 範圍與產物 | 不屬於此步驟的工作 | 時間與通過條件 |
| --- | --- | --- | --- |
| Step 1：自動化唯讀盤點 | OPT-01 的環境／catalog／來源契約／SELECT 計畫與已載入模型 Inventory、DAX；OPT-02 的 migration、guard 路徑與既有純離線檢查。交付第一份 Baseline Snapshot 及缺項清單 | 不呼叫 `--write`、`--apply`、Desktop Refresh／Save；不以正式庫寫入來測 guard，也不把實測覆蓋不到的項目標 PASS | 環境就緒時以半個工作日內交付為目標；缺 Desktop 或有併發工作時，已取得證據先交付，缺項另列，不等待映射審核 |
| Step 2：治理與補正 | OPT-03 的 574 原碼命中清單、覆蓋率、推導／人工確認證據及 048 修復；另追蹤 OPT-02 writer 實作與隔離寫入／恢復驗收 | 不將語法修復當成業務映射獲得確認；不因治理尚未結束而阻擋獨立的只讀效能分析 | 按證據與修復範圍排程，人工確認另列等待項目；每項按自身驗收完成 |

Step 1 只交付 OPT-01／02 的唯讀部分，不能宣稱兩項全部完成。第 3 節的完整 Desktop 刷新基準會重新處理模型，不是純唯讀；它安排在受控驗收窗口。writer 修改、DML 失敗測試、migration 補正也屬 Step 2／隔離驗收，不放入「半天唯讀盤點」承諾。

第一輪規劃估計：A 的工程工作仍約 2～4 工作日，先交付上述 Step 1；B 約 3～5 工作日，C 約 3～6 工作日，D 試點約 3～5 工作日。人工映射審核、環境缺項與來源等待分開列示；時間是工作量預估，完成首份 Snapshot 後重估，不作固定交期。

## 5. migration、寫入與映射治理

### 5.1 OPT-02：讓 migration 與 ETL 各司其職

目前 [local-database.md](operations/local-database.md) 含 migration 43、46 等不同時點敘述；本次實體複核已確認 `jobwant_104` 到 047、無 pending，047 應視為已套用的治理／補正對象。對齊 active 契約後再更新操作文件中的歷史快照；`READY` 不代表 047 映射已獲人工確認，也不解除舊 writer 的防護。

實施步驟：

1. 保存 `bronze.schema_migrations`、Gold 定義、必要 constraints／indexes 與受保護 FDW 物件清單；記錄已套用及待套用版本。
2. 使用既有 [check_migration_state.py](../tools/check_migration_state.py) 與 [apply_migrations.py](../tools/apply_migrations.py)，不另建第二套 runner。不把 `READY` 解讀成零 pending：目前 gate 會列出 pending，但非 DRAFT 的 pending 不一定使其失敗。
3. 以目前連續至 047 的實體狀態，規劃 migration 048 作 OPT-03 補正。正式建立／套用前重查歷史及檔案，若 048 已被其他工作占用，使用下一個連續版本；不重播或修改已套用的 047，也不改寫歷史紀錄。
4. 將受保護資料庫的 ETL 寫入與 schema bootstrap 分離：ETL 啟動只驗證必要欄位、型別、constraint 與相容能力，不重播 `init_postgres_schema.sql`。
5. 保留 [postgres_schema.py](../tools/acquisition/shared/postgres_schema.py) 的阻擋；修復 writer 的呼叫路徑及必要 DML 相容性，不以移除 guard 解決。
6. 先在隔離還原庫測試一批合格 capture：首次載入、同批重跑、hash 衝突、半途失敗、page-cap、正規化失敗與 FDW 不可用。

驗收：合格批次原子提交、同批重跑不重複、失敗不污染合格 Gold；原始 payload 不變；既有 Gold 定義與 FDW 未被 bootstrap 覆寫；不相容 schema 明確失敗。執行 DML 後仍須驗證所有 active reader。

回復：關閉新 writer 入口，維持已保存檔案批次與舊版讀取；若 DDL 已發布，以經驗證的回復 migration 恢復契約。不要重新啟用原本被 guard 阻擋的舊寫入路徑。

### 5.2 OPT-03：先驗證 crosswalk 正確，再談覆蓋率

[migration 047](../tools/sql/migrations/047_direct_job_category_golden_l1_mapping.sql) 已套用，以原碼模式直接寫入 `CONFIRMED` 與 `match_confidence=1.00`，並重定義職類橋接。這些常數不能當作已經人工或官方確認的證據。後續是治理及補正既有狀態，不是重新決定是否套用 047。

實施步驟：

1. 核對 104、yes123 的原生分類樹、code kind、版本／hash、有效日期；保存原碼與來源名稱。
2. 對 047 的每個規則建立來源依據、命中原碼清單與預期 canonical／Golden L1；特別核對來源 L1、L2、L3 是否被誤當成相同粒度。
3. 驗證 `LIKE` 模式的實際命中集合；SQL 的 `_` 是單字元萬用字元，若要求字面底線，需使用適當 escape 或明確鍵集合。例如字面前綴可寫為 `LIKE '2!_1010!_%' ESCAPE '!'`。本次抽查該規則在 574 個現有原碼中額外命中為零，僅限此模式及此快照，不能推論其他規則正確或未來沒有風險。
4. 逐層比較變更前後：原碼指派數、每職缺原碼集合、canonical 集合、Golden L1 集合、未對照與橋接列數。不能只看最終 KPI 不變。
5. 檢查「非 CONFIRMED 但 canonical 欄位非空」的情況，不讓它經 `COALESCE` 自動變成可分析的已確認類別。
6. 在現有 coverage 工具盤點後補稽核入口；`tools/audit_crosswalk_coverage.py` 是候選新工具名稱，實作模組依 package map 歸位。

migration 048 的補正設計須分成兩種規則：機械推導只產生候選映射、規則版本與來源依據；人工確認另保存覆核者、時間與證據，通過後才成為 `CONFIRMED`。不得將規則確定可命中誤解為語意匹配信心 1.00。對原本已有可靠確認證據的列應保留證據，不無差別降級全部 574 列。

048 的產物包含執行前精確資料快照、每條規則的新舊命中差異、預定修改鍵集合、已確認／待審／未知分布、Gold 接受 confirmed 映射的條件，以及回復所需的原值。先輸出 dry-run 報告及隔離測試；本文件不建立或套用 048。

稽核分別報告來源目錄覆蓋、實際觀測原碼覆蓋、至少有一個確認映射的唯一職缺比例、帶有未知／歧義指派的唯一職缺數。多分類職缺可能同時落入已知與未知集合，不把它們當互斥比例相加。母體為零時顯示不適用。

驗收：來源原碼不丟失、未知／歧義明確保留、每個確認規則可追溯、有來源新增碼 fixture 與反例。99.5% 可作待確認的營運告警門檻，但不能透過降低確認標準達成。

回復：保留映射變更前的精確鍵值與版本；回復映射及相關 view，不回寫／刪除來源 capture。若已存在缺乏證據的確認狀態，先恢復其未對照呈現並保留原因。

## 6. PostgreSQL 查詢與資源優化

### 6.1 OPT-04：先消除已量測重工，再試物化

先選九個 active reader 中最慢、最常重算的一至兩個，檢查實際 projection、排序、去重、字串編碼、FDW loops 與 temp spill。既有 migration 027～040 已做過查詢與欄位縮減；應比較現在的計畫，不重新實作相同功能。

候選採用順序：

1. 修正可證明等價的 SQL 重複工作與不必要投影。
2. 在相同資料上比較候選 view，不改動 canonical `gold.pbi_fact_jobs_v22` 的內容契約。
3. 只有重複計算仍占主要成本時，建立內部 reporting mart／materialized view；外部保持原來 `gold.pbi_*` 名稱、欄位與型別。
4. 比較「mart 建置／刷新 + Power BI 載入」總成本、儲存增量與資料新鮮度，而不只比較從 mart 讀取的時間。

`REFRESH MATERIALIZED VIEW CONCURRENTLY` 仍執行 backing query；它不是自動增量，也不會讓 SQL 呼叫自動非同步。其前置檢查分成引擎要求與專案資料契約：

| 檢查層級 | 明確條件 | 失敗處理 |
| --- | --- | --- |
| PostgreSQL 16 引擎 | MV 已 populated，不能搭配 `WITH NO DATA`；執行角色具備 MV 擁有者權限；同一 MV 同時只能刷新一次 | 初次填入先用非並行方式；角色及排程先驗證 |
| 唯一索引資格 | 至少一個有效、立即檢查唯一性的 B-tree UNIQUE index，直接使用一般欄位，沒有 expression 或 `WHERE` 條件，涵蓋所有列 | 查 index 定義與有效狀態；僅名稱含 unique 或存在 partial unique index 均不算通過 |
| 本專案鍵契約 | FactJob 的 namespaced `jobNo` 必須全域唯一且沒有 NULL；橋接的整組關聯鍵須唯一、各鍵值不得 NULL | 建置前、發布前及每次候選刷新後驗證；不合格不發布 |

「鍵值不得 NULL」是本專案比引擎更嚴格的契約，不能寫成 `CONCURRENTLY` 要求欄位必須宣告 `NOT NULL`。引擎的唯一索引資格檢查沒有該條件；有合格索引也不代表新資料沒有重複鍵，仍可能在刷新時因唯一性衝突失敗。[PostgreSQL：REFRESH 要求](https://www.postgresql.org/docs/16/sql-refreshmaterializedview.html)、[PostgreSQL 16：索引資格與刷新實作](https://github.com/postgres/postgres/blob/REL_16_STABLE/src/backend/commands/matview.c)

暫存、磁碟與 WAL 規劃：

- 並行刷新保留舊 MV，另外建立新結果暫存及 diff，再對正式 MV 套用 DELETE／INSERT；排序、hash spill、索引維護與其他背景工作也會占用空間。WAL 增量與正式資料變動等因素有關，不能把整份暫存直接等同整份 WAL。[PostgreSQL 16：match/merge 實作](https://github.com/postgres/postgres/blob/REL_16_STABLE/src/backend/commands/matview.c)
- 可用空間預算至少涵蓋「同時執行工作的新增結果 + diff + spill／工作空間 + WAL 增量 + 維護餘裕」。既有 MV 已在目前已用空間中，不在可用空間估算再次重複計入。
- 「預留受測 MV 大小 2～3 倍的額外空間」僅可作初始試驗預算，需註明大小是否含 TOAST／索引；它不是固定消耗量、引擎保證或上限。正式額度依代表性變動量的峰值量測重估。
- 第一輪將 FactJob 與兩張橋接表的刷新序列化。只有取得各自峰值後才增加並行度，並分別檢查 data／temp tablespace、`pg_wal` 所在磁碟及 Docker 主機實際可用空間。
- 觀察低變動與高變動批次的 temp、WAL、I/O、持續時間及取消後殘留影響；空間不足時不啟動下一項刷新，保留上一個完整發布版本。

相容與一致性設計：

- FactJob 候選完整保留第 2.1 節的 14 欄；唯一鍵使用經核對的帶平台識別 `jobNo`。橋接唯一鍵使用完整鍵組。
- 候選建置固定來源批次／watermark；FDW 跨來源資料不能僅因包在一個本地 transaction 就宣稱具有共同擷取時間。
- 對所有受影響 facts、bridges、dimensions 記錄同一發布版本。若採多個 MV，只有全部建置與檢查完成才一起發布；部分成功不能對外切換。
- 資料庫原子發布仍不足以保證 Power BI 的多個連線跨查詢讀到同一版本。完整刷新期間須固定發布版本，協調器持有發布鎖／lease，或保留不變的來源批次直到刷新結束。
- 第一個試點可採單次受控流程：固定輸入 → 建置候選 → parity → 切換相容 view → 完整刷新 → 驗證 → 解除固定。自動化前需測試 lease 中斷與恢復。
- 記錄最後成功發布時間與來源時間；ETL／mart 失敗時沿用上一個完整版本並顯示過期，不以空資料代替。

驗收：欄位契約完全相同；同批次雙向 `EXCEPT ALL` 差異為零，重複鍵與孤兒鍵為零；薪資 NULL／日期／Unicode 不變；Desktop 完整刷新及語意 probes 通過；中途失敗不混用版本；第 3.3 節效益成立。

回復：保存舊 view 定義與上一個完整 mart；在刷新窗口外把相容 view 切回，對舊版本完整刷新並驗證。保留失敗候選供診斷，不使用 `DROP ... CASCADE` 清除相依物件。

### 6.2 OPT-05：資源設定與 FDW 逐項實驗

先確認主機 RAM、Docker／WSL 額度、PostgreSQL 可用預算，以及 Desktop、ETL、其他服務的同時使用量。PostgreSQL 官方的 `shared_buffers` 約 25% 起點是針對專用資料庫主機，不可直接套用到共用 Windows 工作站。[PostgreSQL：資源設定](https://www.postgresql.org/docs/16/runtime-config-resource.html)

| 參數／項目 | 第一輪策略 | 必要觀察與回復 |
| --- | --- | --- |
| `shared_buffers` | 根據資料庫實際額度試一個保守值，不預填 4～8 GB | 記錄重啟窗口、快取、I/O 與總記憶體；保留原設定並驗證重啟恢復 |
| `work_mem` | 核對 migration 036 的角色範圍及新會話值；有 spill 再試 | 它按操作節點與並行工作分配；計入 hash、並行查詢及 Desktop 刷新並行度，不把 128 MB 當成整庫上限 |
| `effective_cache_size` | 依可用 OS／DB cache 估計 | 它是 planner 估計，不會實際配置該容量；比較計畫與時間 |
| `random_page_cost` | 先用受測 session 比較候選，不先全域固定 1.1 | 全掃描可能是合理選擇；保留有代表性的多種查詢回歸 |
| 維護與 autovacuum | 依 dead tuples、autoanalyze、維護耗時決定 table／session 設定 | 計入 autovacuum workers；不全域直接設成 1～2 GB |
| FDW `fetch_size` | 比較現行值、1,000、10,000 等候選批量 | 比較總傳輸、首批等待及記憶體，不假設越大越好 |
| FDW 成本估計 | 比較 local statistics 與 `use_remote_estimate` | 記錄規劃往返成本、實際 remote SQL／loops，判斷是否值得 |

`use_remote_estimate` 使用遠端 EXPLAIN 的估計，不提供「真實列數」保證；外部表 ANALYZE 也會存取來源並有成本。新增或修改選項前讀取現值，分辨 `ADD` 與 `SET`，回復時保留原本不存在／存在的狀態。[PostgreSQL：postgres_fdw](https://www.postgresql.org/docs/16/postgres-fdw.html)

驗收：相同資料、投影與會話條件下改善，無其他關鍵查詢明顯退步、無記憶體超額；重新連線／必要重啟後生效值與預期一致。FDW 一個失敗來源不可被當成零筆成功資料。

## 7. 語意模型與報表體驗

### 7.1 OPT-06：平台維度與分析／監看分離

建立小型、由資料庫治理的平台維度，經 Gold → Source → Model 匯入；分析平台 slicer 改綁維度。名稱為候選，新增前確認沒有既有等價物件。

- 最小欄位為平台穩定代碼、名稱、排序與是否可供分析；URL 僅在有消費者時加入。
- 維度只包含已治理的平台；不因提案提及其他網站就宣稱已接入或補造職缺。
- `dim_平台 → 目前職缺` 使用單向一對多。平台不存在資料、資料過期與未啟用要有不同呈現。
- 分析 slicer 預設顯示已啟用來源，不因其他 fact 篩選消失；仍需檢查 visual-level filters、互動與「有資料」measure，不能只靠新增維度保證。
- Page 05 維持獨立監看選擇。若業務需要同一平台目錄，可共用治理來源並另設角色維度／互動規則，不直接同步所有頁的事實表 slicer。

驗收：104、yes123、全部平台及零結果組合均可選取並可重設；Pages 01–04 分析與 Page 05 操作狀態不互相誤篩。新增表後更新模型表數基準，不能繼續把「九表」寫成固定永久限制。

回復：回復舊 slicer 綁定與關聯；在所有消費者移回後，才考慮移除候選維度。

### 7.2 OPT-07：逐條驗證四條雙向關聯

| 現有關聯 | 需保護的用途 | 候選評估 |
| --- | --- | --- |
| FactJob ↔ DimArea | 地區篩選職缺、職缺清單選取縮小地圖 | 先測列表→地圖；若改方向，必須補足視覺層資料篩選 |
| BridgeJobSkill ↔ FactJob | 技能選擇傳到職缺 | 不可只修技能數 measure，而讓清單仍顯示全體職缺 |
| BridgeJobCategory ↔ FactJob | 職類選擇傳到職缺 | 保護 Golden L1、多選及未知映射行為 |
| BridgeJobCategory ↔ DimJobCategory | 職類選項隨其他篩選縮小 | 先確定產品需要固定選項或僅顯示有資料項目 |

#### 切片器選項的產品決策與驗收矩陣

開始 OPT-07 關聯實驗前，先記錄選擇 A 或 B；本文件尚未替使用者選定。`BridgeJobCategory ↔ DimJobCategory` 可讓職類選項感知其他維度，也可能參與連鎖修剪；平台消失的實際原因仍需連同 fact 綁定、整條關聯路徑及視覺互動證明，不能只憑這一條關聯定案。

| 決策／情境 | 方案 A：動態縮小 | 方案 B：穩定選項 |
| --- | --- | --- |
| 職類選項規範 | 隨地區等條件隱藏無職缺項目 | 固定保留 18 個 canonical Golden L1；缺資料只影響結果，不移除選項 |
| 候選實作 | 保留經驗證的雙向路徑，或對職類 slicer 使用有資料 measure；檢查效能與篩選循環 | 職類維度 → 橋接採單向，檢查其他反向路徑；職類 slicer 不套用會刪除零結果選項的 measure／visual filter |
| 地區篩選，例如已驗證屬於新竹科學園區的來源範圍 | 只列有匹配工作的職類，且重設後可恢復 | 18 項仍可選；選擇該地區無工作的職類時 KPI／清單呈現可解釋的零結果 |
| 平台選項 | 依 OPT-06 使用穩定平台維度；職類動態縮小不代表平台也必須消失 | 同樣保留啟用平台選項，區分未啟用與目前零結果 |
| 已選職類因其他條件變成零結果 | 清楚顯示仍生效的選擇並可清除，不留下不可見篩選 | 保留選項與已選狀態，顯示零結果原因及重設方式 |
| 未對照／BLOCKED | 額外揭露有多少職缺未進入已確認分類 | 18 個 canonical 選項之外仍需獨立揭露未知狀態；不能為維持恰好 18 項而隱藏資料問題 |

方案 B 另有資料前提：[migration 046](../tools/sql/migrations/046_bound_golden_job_category_dimension.sql) 已將 `pbi_dim_job_category_v21` 改為直接讀取 `silver.category_dimension` 並保留未知成員，不再依橋接出現的鍵縮小維度。應先核對實體 view、已匯入維度及 18 個 canonical L1 是否完整，再處理關聯與 slicer 的零結果選項；不預設需要重建一張 L1 維度。單改關聯方向不會產生來源未載入的選項，也不得為補選項製造事實列。

兩方案都驗證平台 × 地區 × 職類單選／多選、先選地區／先選職類、零結果與重設後恢復。選項集合、選取狀態、職缺鍵集合與 KPI 分別保存預期結果；方案決策及生效日期寫入驗收紀錄。

可評估 measure 內 `CROSSFILTER`／`TREATAS`，但這只作用於使用該 measure 的查詢範圍。必須檢查原始欄位組成的列表、地圖、工具提示與 drill-through。雙向關係應控制使用並驗證，不以數量本身判定模型錯誤。[Microsoft：雙向關聯指引](https://learn.microsoft.com/en-us/power-bi/guidance/relationships-bidirectional-filtering)

固定驗證語意：單一橋接維度的多選維持 OR；技能與職類之間及其他維度之間維持交集。比較顯示的職缺鍵集合、公司、列表、KPI、工具提示，不只比總數。

同時以 VertiPaq 欄位統計盤點 data／dictionary／hierarchy 大小及 cardinality，檢查 `descSnippet`、地址、URL 與鍵欄位實際消費者。先移除無消費者的重複投影；現有 Page 04 使用職缺摘要，不能直接刪掉。

將文字搬到同模型的 Import 明細表不等於延遲載入，也不保證總容量下降。外部按需明細需要新的資料存取、權限、離線與互動契約，列為另案選項。不要把 SQL `pg_trgm` 當作 Import 報表搜尋的加速器。

驗收：既有 [semantic-model-contract.dax](../tools/probes/semantic-model-contract.dax)、[filter-propagation-smoke.dax](../tools/probes/filter-propagation-smoke.dax)、[area-category-intersection.dax](../tools/probes/area-category-intersection.dax) 及實際列表鍵集合相符；單選、多選、清除、無匹配、跨平台與未知分類皆通過。容量／互動改善另按第 3 節量測。

回復：保存完整 TMDL／PBIR 變更前定義，按單項變更回復，不使用整個 worktree reset。每次回復後重驗受影響的篩選路徑。

### 7.3 OPT-08：地圖採分層探索，保留大點數保護

實作前對照 [Page 04 規格](report-design/page-04-spec.md)、[核准參考圖](report-design/page-04-job-explorer.png) 與實際 `map` 定義。不同地圖元件的聚合、群集、登入、資料角色與限制須用目標元件驗證；不能把其中一種元件的設定直接貼到另一種。

| 使用情境 | 建議呈現 | 資料與互動要求 |
| --- | --- | --- |
| 台灣總覽 | 按已確認縣市彙總的氣泡；未定位數另列 | 中心點使用有來源、版本與授權的行政區座標；清楚標成彙總位置 |
| 縣市探索 | 切換所屬行政區彙總 | 經緯度、region key、分組粒度與 distinct job count 一起切換 |
| 行政區／小範圍 | 顯示來源有效位置；必要時群集或提示縮小範圍 | 行政區仍可能超過 5,000 點，不承諾永遠少於 300 點 |
| 單一職缺 | 有可靠座標才定位；保留來源地址與連結 | 同座標多職缺以清單選取辨識，不任意取一家公司 |
| 海外／未知／無座標 | 依來源範圍分開清單與提示 | 不套用台灣中心點，不將缺座標偽裝成有效散點 |

需要新增地理維度／彙總時由 PostgreSQL ETL 發布；與現行任意技能／職類篩選的組合，必須證明預彙總不重複計數。無法等價時保留工作層級 FactJob 關聯，由 DAX 在正確地區粒度計數，不用一張總量表硬套全部篩選。

`ISINSCOPE` 判斷查詢中的階層分組，並不是地圖縮放事件。只切換平均經度不能完成群集；必須同時處理緯度、分組與視覺 drill 行為。[Microsoft：ISINSCOPE](https://learn.microsoft.com/en-us/dax/isinscope-function-dax)

空狀態至少區分：篩選無匹配、沒有有效座標、點數過多、來源已過期、地圖服務／登入失敗。超過點數門檻時保留清單與說明；不單純移除 5,000 點 guard。

Pages 01–04 依分析需求同步平台、職類、地區；Page 05 依 [監看規格](report-design/page-05-spec.md) 保持獨立。各頁重設書籤需實測 slicer、視覺選取與地圖層級，並說明同步篩選的重設範圍。

驗收：已知篩選組合可看見正確點位與清單，總覽／縣市／行政區／職缺可往返；正常與錯誤狀態可辨識；PBIR persisted `visualType`／設定及 Desktop 外觀均符合設計。涉及 ArcGIS 時須在 Desktop 完成登入並驗證可見點與群集，不能以 endpoint 或 DAX 成功取代。

回復：先恢復舊 PBIR 綁定及經驗證的點數保護，保留原始位置資料；候選地理維度無消費者後再處置。

## 8. OPT-09：三層品質閘門

### 8.1 Linux 結構與離線測試

沿用 [.github/workflows/validate.yml](../.github/workflows/validate.yml)、[validate_project.py](../tools/validate_project.py) 及既有 unit tests；檢查 JSON schema、PBIP/PBIR 連結、欄位引用、M/TMDL 同步與 300 行限制。

保留 `STRUCTURE_PASS_DESKTOP_TMDL_UNAVAILABLE` 的明確狀態，不改標成完整語意 PASS。對新規則只補能證明失敗邊界的測試，不用重複實作的測試充數。

### 8.2 Windows 解析與 BPA

優先建立固定版本 Windows 執行環境，使用現有 Desktop parser 或經驗證相容的 TOM parser；託管 Windows runner 不預設已安裝 Desktop。

TE2 的官方參數如下；不要與另行發布的跨平台 `te` CLI 混用：

| TE2 選項 | 實際用途 |
| --- | --- |
| `-A <rules.json>`／`-ANALYZE` | 執行 BPA；指定規則檔時仍可納入模型 annotations 的規則 |
| `-AX <rules.json>`／`-ANALYZEX` | 執行 BPA，但排除模型 annotations 中的規則；不是執行腳本後儲存 |
| `-S <script.cs>`／`-SCRIPT` | 執行 C# 腳本 |
| `-B <output.bim>`／`-BUILD` | 將模型寫成 BIM 輸出；不是 BPA，不能把規則檔放在這個輸出位置 |
| `-V`／`-VSTS` | 輸出 Azure DevOps 日誌格式；不是模型 Validation 開關 |
| `-G`／`-GITHUB` | 輸出 GitHub Actions 日誌格式 |

以上已核對 [TE2 官方命令列](https://docs.tabulareditor.com/en/features/Command-line-Options.html) 與 [官方參數解析程式](https://github.com/TabularEditor/TabularEditor/blob/master/TabularEditor/CommandLineHandler.cs)。先固定 binary／版本／hash、rules、輸入格式與失敗 exit 行為；跨平台 CLI 的預覽／授權條件另依 [該工具文件](https://docs.tabulareditor.com/en/features/te-cli/te-cli.html) 重新確認。

TMDL 輸入以完整 `PBI_JobWant.SemanticModel\definition` 資料夾為候選，驗證所選 TE2 版本能解析所有 tables／expressions／relationships，不把單一 `database.tmdl` 當成已驗證的完整模型入口。若該版本不支援，透過受測 TOM 轉成隔離 BIM 產物再檢查，保留原 TMDL。

下列是 `cmd.exe` 模板，僅在 TE2 已在 PATH、TMDL folder 支援已驗證且 `tools\bpa\rules.json` 已建立後使用；規則檔與 TE2 尚未由本方案安裝。`start /wait` 是 CMD 語法，不可直接視為 PowerShell 的同名命令：

```bat
start "" /b /wait TabularEditor.exe "PBI_JobWant.SemanticModel\definition" -A "tools\bpa\rules.json" -G
if errorlevel 1 exit /b %errorlevel%
```

PowerShell 執行則使用 `Start-Process -Wait -PassThru -WindowStyle Hidden`，檢查程序 `ExitCode` 並保存 stdout／stderr。`-V` 或 `-G` 只選輸出格式，不替代 parser、BPA、DAX 的各自驗收；以已知嚴重規則違反、無效規則檔與正常模型的 fixtures 證明 CI 能失敗／成功。BPA error 的非零退出以固定版本實測，不以多加 `-V` 當作保證。

BPA 對目前必要雙向關係可使用有理由及覆核日期的規則例外；不能自動把全部關係改單向。BPA 不是 DAX 結果正確性的證明。

### 8.3 有資料的整合與 Desktop 驗收

資料庫整合在隔離還原庫或受控驗收環境執行；使用最小、去識別 fixtures 測 migration、ETL 重跑與失敗。正式憑證不交給不受信任的 PR 工作。

涉及 Gold／M／模型的發布：實際 SQL 契約 → Desktop 完整刷新 → Ready／DAX → 儲存 → 關閉／重開 → 再驗證。只改 PBIR 時聚焦受影響互動與保存重開，不無條件重跑不相關效能實驗。

驗收：故意缺欄、重複鍵、未知映射、錯誤 DAX／引用、無法連線與未完成刷新都會產生可分辨的失敗；失敗不自動發布或覆蓋成功版本。CI 失敗先回復新增的管線變更，保留既有有效檢查。

## 9. OPT-10：採集完整度與可恢復切片

完整度先於擷取速度。現有 150 頁與 `pagesize=30` 只是程式設定／歷史已驗證行為；即使名目容量為 4,500，也不能把它當成 API 永久、精確或唯一職缺上限。實施前以當次 request、response、實際 page rows 與 total 確認，不把 total 當成已知 HTTP header。

實施步驟：

1. 先讀現有 queue、worker、共享 gate、批次摘要與 coverage；有未完成 run 就恢復既有 run，不另建重複工作。
2. 沿用官方職類的較細分類；仍截斷的查詢才以經驗證的來源地區碼試切片。先做一個熱門職類的小規模受控試點。
3. 建立持久化 parent／child 查詢清單，保存 request identity、taxonomy hash、來源地區碼、預期／實際頁數、total 漂移、唯一鍵與批次 hash。
4. 證明 child 覆蓋範圍與重疊規則；全台、海外、地區未知、遠端工作等未覆蓋範圍明列。不能默認 22 縣市是來源查詢結果的無遺漏分割。
5. 子查詢也達頁數上限時繼續使用已驗證篩選細分；沒有合法且可證明的切分條件就記 `BLOCKED`，不創造查詢欄位或宣稱完成。
6. parent 完成由所有必要 leaf 的完整與品質結果推導；截斷 parent capture 保留 Bronze，不因 child 成功而改寫原始批次結果。
7. 跨 leaf 用來源職缺身份去重分析，保存每個查詢系列的觀測。動態 total 不能以不同時點子查詢的加總冒充精確母體。
8. 重用現有共享限速／退避。驗證可靠 `Retry-After`、429、challenge、可恢復錯誤、租約逾時及中止；不得以輪替身份或無限制並行跳過來源限制。

需要跨程序的公平排程時，先改善既有 database request state／gate，不重做第二套 Token Bucket。輸出至少包含 completed／incomplete／blocked 數、目前 interval、最後成功時間、延遲原因與資料實際範圍。

驗收：可從中止續作；缺頁、重複、total 漂移、源端 challenge 均不被報成功；去重與原始批次對得上；只有完整合格資料可進入 Gold；覆蓋率有明確時間與分母。不能從 HTTP 200、全部 leaf DONE 或較多資料列推論全台完整。

回復：停止新的切片派工，保留 queue、leases、capture 與已成功批次；沿用上一個可用 Gold 發布版本。不清空來源資料或在 API gate 未解決時重啟高頻工作。

## 10. 有條件的儲存與架構演進

### 10.1 OPT-11：Bronze 壓縮與歸檔

觸發條件為實際磁碟成長、TOAST／CPU 成本或保留需求，不能只因原稿提到 4.1 GB 就排為緊急事件。

1. 分別盤點 `payload` 與 `payload_source_json` 的占用、是否可壓縮、現有 compression；TOAST 存在不等於未壓縮。
2. 確認 PostgreSQL build 支援 LZ4；以相同資料做 pglz／LZ4 大小、載入、讀取與 CPU 比較，不能預設 LZ4 壓縮比更好。
3. `SET COMPRESSION` 不重寫舊資料；若要重壓，另設隔離還原／重寫實驗並驗證實際 compression、WAL、鎖與磁碟峰值。`INSERT ... SELECT` 也不保證已壓縮值重新壓縮。[PostgreSQL：欄位壓縮](https://www.postgresql.org/docs/16/sql-altertable.html)
4. 保留期依追溯、parser 重算、latest scope 引用與使用需求決定；60 天僅為候選，先算實際符合條件批次，不預估固定釋放 2.5 GB。
5. 歸檔單位是完整批次：原始頁面／原文、manifest、hash、來源 metadata、目錄版本與必要重建資料。Parquet 可作查詢副本，不能單獨取代可校驗的原始證據。
6. 在空白隔離庫完成還原與 reprocess，比對原始 hash、列數、身份、NULL／Unicode 及合格 Gold 結果。檔案存在或成功上傳不算恢復完成。

刪除資料與磁碟回收是後續獨立操作；先列出精確批次、依賴與已驗證歸檔位置，再執行明確獲准的保留政策。不可 TRUNCATE 整個 Bronze 或直接操作 TOAST 表。一般 DELETE／VACUUM 主要讓空間可重用，不能承諾立即回收所有 OS 磁碟空間。[PostgreSQL：VACUUM](https://www.postgresql.org/docs/16/routine-vacuuming.html)

驗收：來源可完整恢復、沒有仍被引用批次遭清除、容量與 CPU 改善分別有實測；Docker volume 與 Windows 實體檔案占用分別呈報。只改回 compression 設定不會還原既有資料的儲存格式；資料回復依驗證過的歸檔／備份。

### 10.2 OPT-12：按工作負載採用索引與分區

| 選項 | 採用前證據 | 設計限制與驗收 |
| --- | --- | --- |
| B-tree 調整 | 等值／範圍／排序查詢、索引使用與更新成本 | 先保留 PK／UNIQUE 與 FK 相關用途；移除前核對所有工作負載與重建方法 |
| BRIN | 時間欄位與物理順序有足夠相關性，目標查詢有日期條件 | 只作候選輔助索引，量測 lossy recheck 與實際 I/O；不替代唯一性 |
| `pg_trgm` GIN | 有 PostgreSQL 端的 LIKE／ILIKE／相似搜尋，且慢查詢命中該欄 | 依實際 SQL／expression 建索引；量測中文字串、短關鍵字、無結果與寫入負擔 |
| 日期分區 | 多數昂貴查詢能以日期 pruning，或保留政策需要批次移除歷史 | 最新快照查詢不一定具有可 pruning 的日期條件；不能以總列數直接推導必要性 |

BRIN 適合物理位置與值域相關的大表；`pg_trgm` 是否有效取決於查詢及可萃取 trigrams。[PostgreSQL：BRIN](https://www.postgresql.org/docs/16/brin-intro.html)、[pg_trgm](https://www.postgresql.org/docs/16/pgtrgm.html)

分區試點需完整複製欄位、型別、PK、FK、indexes、grants 與寫入行為，不能採用原稿的簡化幾欄 DDL。分區鍵與唯一約束要相容；預建下一期分區，定義晚到資料、補抓與缺分區的失敗路徑；依保留粒度與計畫比較月／季，不直接固定季度。[PostgreSQL：分區](https://www.postgresql.org/docs/16/ddl-partitioning.html)

驗收：真實 SQL 命中候選、前後資料與 constraints 等價、缺分區不靜默丟資料、歷史與補抓皆可讀寫，且效益超過新增維護成本。回復保留舊表與相容 reader；切換後的新寫入必須可回放，否則不能宣稱可立即切回。

注意現有 migration runner 以單一 transaction 執行；若要 `CREATE INDEX CONCURRENTLY`，需另設可追蹤的非交易式操作程序與失敗殘留處理，不能直接放入目前 runner 的 transaction。

### 10.3 OPT-13：代理鍵與複製只在必要時採用

整數代理鍵：只有鍵欄位／join 已證實是主要容量或效能成本才試行。建立持久的 `(platform, native_id) → surrogate_id` 映射；不能每次刷新重新產生 identity。原碼與穩定 namespaced key 保留，更新所有 facts／bridges／dimensions 並驗證 Unicode、大小寫與不同平台同 ID 的不碰撞性。回復時保留兩套鍵映射與回填能力。

跨庫存取：FDW 不是必然反模式；目前已有遠端 scope 投影優化。先量測網路、source availability 與 freshness。必要時比較「按合格批次複製到本地 reporting mart」與邏輯複製的操作成本。

PostgreSQL 邏輯複製不能直接發布一般 view、materialized view 或 foreign table；若來源 Gold 是 view，原稿的「直接複製 Gold」不可照做。評估時還需包含 replica identity、DDL 演進、replication slot／WAL 成長、斷線重播、lag 與刪除語意。[PostgreSQL：邏輯複製限制](https://www.postgresql.org/docs/16/logical-replication-restrictions.html)

驗收：只有效益、運維責任與恢復路徑都明確才採用；不以「架構升級」作為獨立成功指標。回復時先確認舊 FDW／Gold 契約仍可讀，再切換 reader；不要提前刪除來源或複製槽所需狀態。

## 11. 共用發布、回復與營運條件

### 11.1 每次發布前

- 基準包含使用者既有 dirty 內容，另存本次精確差異；不得用歷史 HEAD 覆蓋所有未提交工作。
- 所需備份已試過還原，且儲存／鎖定／重啟窗口符合任務風險。
- 變更僅屬於本次約定層級；模型與 PBIR 需要改動時分開檢閱，PBIR 遵循現有核准圖。
- 同批次資料的列、鍵、欄位、NULL、時區、來源身份與語意差異已檢查；預期語意修正另列變更理由。
- 參數改動、mart 發布、ETL 寫入與 Desktop 刷新有明確順序，避免同時改變量測條件。
- 不自動 commit、publish、初始化 Git，或啟動新的大量採集。

### 11.2 回復觸發與方法

任何缺欄、來源鍵遺失、重複／孤兒鍵、未確認映射被當成確認、模型無法刷新、資料版本混用、來源證據損壞皆停止切換。效能明顯退步或資源超額則恢復上一個已驗證設定／reader，再保存診斷結果。

採新增物件、相容 view 與保留舊版本的方式實驗。資料／schema 回復用針對性的操作或後續 migration；設定回復使用原值與原作用域；模型／報表回復只還原本次改動。每次回復後重新查驗受影響的資料契約與可用性。

### 11.3 觀察與告警

至少保留最後成功 capture、ETL、mart 發布與 Desktop 刷新時間；各階段失敗／過期分開顯示。第一版可用本機結構化日誌與 Page 05，不必先引入新監控平台或外部訊息服務。

建議先觀察一個完整資料更新週期，再以三個連續成功週期作營運穩定驗收。新鮮度上限、跨平台更新不同步容忍度與事故處理責任在啟動排程前記錄；暫無需求數字時保持 `待確認`，不自行聲稱即時。

## 12. 實施時可重用的診斷命令

以下為實施階段命令，不代表本次已執行。從專案根目錄、使用既有 Python 環境執行；缺少依賴先回報，不藉診斷自動重建環境。只對既定本機資料庫使用，勿列印 `.env` 或完整帶密碼連線字串。

### 12.1 儲存庫與靜態契約

```powershell
git status --short
git rev-parse HEAD
python tools/sync_queries.py
python tools/validate_project.py
```

修改 ETL、validators 或核心資料契約時，再執行相關測試及專案既有必要檢查：

```powershell
python -m unittest discover -s tools/tests -v
```

純文件交付只檢查 UTF-8、連結、Markdown 結構與差異，不以完整資料庫／Desktop 測試冒充文件驗收。

### 12.2 資料庫只讀盤點

```powershell
python tools/check_migration_state.py --require-ready
python tools/report_category_coverage.py --format summary
```

需另外讀取 `pendingVersions` 與目標物件定義，不只看 exit code。以下 SQL 由已配置的本機 PostgreSQL 用戶端執行；`estimated_rows` 為估計值，不能當完整性證據：

```sql
BEGIN READ ONLY;
SET LOCAL statement_timeout = '60s';

SELECT current_database(), version();
SELECT version, applied_at
FROM bronze.schema_migrations ORDER BY version;

SELECT name, setting, unit, source, pending_restart
FROM pg_settings
WHERE name IN (
  'shared_buffers', 'work_mem', 'hash_mem_multiplier',
  'effective_cache_size', 'random_page_cost',
  'maintenance_work_mem', 'autovacuum_work_mem',
  'autovacuum_vacuum_scale_factor', 'default_toast_compression'
)
ORDER BY name;

SELECT n.nspname AS schema_name, c.relname AS table_name,
       c.reltuples::bigint AS estimated_rows,
       pg_table_size(c.oid) AS table_including_toast_bytes,
       pg_indexes_size(c.oid) AS indexes_bytes,
       CASE WHEN c.reltoastrelid = 0 THEN 0
            ELSE pg_total_relation_size(c.reltoastrelid)
       END AS toast_total_bytes,
       pg_total_relation_size(c.oid) AS total_bytes
FROM pg_class AS c
JOIN pg_namespace AS n ON n.oid = c.relnamespace
WHERE n.nspname IN ('bronze', 'silver', 'gold')
  AND c.relkind IN ('r', 'm')
ORDER BY total_bytes DESC;
COMMIT;
```

`table_including_toast_bytes` 已含 TOAST，不再與 `toast_total_bytes` 相加。分區父表需另展開 children，外部表需在所屬來源庫盤點。`pg_settings` 的值屬目前連線，要以實際報表角色／資料庫重查角色設定。

下列 EXPLAIN 會實際執行 SELECT 並消耗資源，在受控量測窗口一次選一個 active reader：

```sql
BEGIN READ ONLY;
SET LOCAL statement_timeout = '120s';
EXPLAIN (ANALYZE, BUFFERS, VERBOSE, FORMAT JSON)
SELECT "jobNo", "custNo", "areaKey", "jobName", "descSnippet",
       "jobAddress", "jobAddrNoDesc", "salaryLow", "salaryHigh",
       "appearDate", "jobLink", "snapshotDate", "snapshotDateTime",
       "sourcePlatform"
FROM gold.pbi_fact_jobs_report_v22;
COMMIT;
```

若超時記錄失敗並結束該 transaction，不無限提高 timeout。另以實際取完資料與 Desktop 刷新量測傳輸／模型成本。

### 12.3 Desktop 只讀驗證與發布驗收

需有唯一可辨識且完成載入的 `PBI_JobWant.pbip` Desktop instance：

```powershell
.\tools\desktop\desktop_model.ps1 -Operation Inventory
.\tools\desktop\desktop_model.ps1 -Operation Dax -QueryFile tools\probes\semantic-model-contract.dax
.\tools\desktop\desktop_model.ps1 -Operation Dax -QueryFile tools\probes\platform-scope.dax
.\tools\desktop\desktop_model.ps1 -Operation Dax -QueryFile tools\probes\area-category-intersection.dax
.\tools\desktop\desktop_model.ps1 -Operation Dax -QueryFile tools\probes\map-switching.dax
```

完整發布驗收另包含 Desktop「全部重新整理」、儲存、關閉、重新開啟與可見互動。開啟 PBIP、TMDL parser PASS 或 DAX 執行成功都不能單獨當成刷新與地圖完成。

## 13. 最終交付與完成定義

每個 OPT 任務交付一份紀錄：`狀態／範圍 → before／after → 正確性結果 → 效能與資源 → 失敗測試 → 回復驗證 → 限制／下一步`。狀態使用 `待量測`、`可實驗`、`驗收通過`、`未達效益` 或附原因的 `BLOCKED`，避免把「已寫 SQL」標成已完成。

第一輪完成需要：

1. 現況、migration／writer 相容與映射問題有可追溯結論；沒有靠移除 guard 或填造數據繞過問題。
2. 至少一個已量測瓶頸完成基準／候選比較；不值得採用的方案也留下數據與不採用理由。
3. 相容 Gold、Import、DAX 與受影響頁面的契約全部通過；資料正確性與效能結果分別報告。
4. 若新增平台維度或更動互動，需有完整使用情境驗收，且保存重開後仍成立。
5. 採集截斷／未知映射／無座標／過期狀態可見；不把局部來源宣稱為全台完整。
6. 所有發布變更可回復，操作文件與 active 程式一致；原始資料與使用者既有修改保留。

### 13.1 原提案項目追蹤

| 原提案 ID／主題 | 本方案落點 | 決策 |
| --- | --- | --- |
| OPT-DB-001／OPT-SYS-001 參數與 FDW | OPT-01、05 | 先量測，再小範圍調校 |
| OPT-DB-002／OPT-SYS-002 Gold 物化 | OPT-04 | 保留完整契約，補發布一致性與總成本 |
| OPT-DB-003／OPT-SYS-006 Bronze | OPT-11 | 壓縮、歸檔、刪除及磁碟回收分開 |
| OPT-DB-004／OPT-SYS-007 GIN | OPT-12 | 限資料庫實際文字搜尋工作負載 |
| OPT-DB-005／OPT-SYS-009 分區 | OPT-12 | 按日期條件、保留需求與規模觸發 |
| OPT-DB-006 代理鍵、FDW 邏輯複製 | OPT-13 | 第一輪不預設採用 |
| OPT-SYS-003 平台維度 | OPT-06 | 優先改善選項與粒度語意 |
| OPT-SYS-004 地圖／同步書籤 | OPT-08 | 先對齊實際 visual 與設計，保留保護 |
| OPT-SYS-005 雙向關聯、文字容量 | OPT-07 | 按消費者與篩選等價證據逐項處理 |
| OPT-SYS-008 切片、動態退避 | OPT-10 | 重用既有限速，補完整度與恢復帳本 |
| OPT-SYS-010 CI／BPA | OPT-09 | 分開結構、解析、live 驗收 |
| 兩份提案的映射告警 | OPT-03 | 正確性優先於覆蓋率 |
| 原提案缺少的 ETL 寫入與發布邊界 | OPT-02、04、11 | 先有相容／恢復條件，再部署優化 |

本方案的第一個實施工作是 OPT-01～03 的現況與正確性基準；實測結果決定後續要做多少，不以完成所有候選技術作為優化成功的條件。
