# PBI_104 專案稽核與優化建議

> 技術稽核基準：2026-10-06（Asia/Taipei）；目錄導覽依 2026-10-09 的整理結果更新。
> 2026-10-09 後續整理將歷史任務包、checkpoint、退役 TMDL 與舊架構圖歸檔，並依容器、桌面工具、啟動器與探針用途分組操作腳本；未移動 active PBIP/PBIR/TMDL、ETL 資料邏輯或本機資料。
> 歷史驗收數字依原日期引用，不視為本次即時狀態。

## 1. 專案基本資訊

- 入口：PBI_104.pbip。主要技術為 Power BI Desktop、PBIR、TMDL、Power Query M、Python 3.13、PostgreSQL 16。
- 資料路徑：104 API → Python 擷取與驗證 → PostgreSQL Bronze/Silver/Gold → Power Query Import → Semantic Model/DAX → PBIR 報表。
- 套件管理：Python pip；tools/requirements-dev.txt 已固定目前 Python 3.13 環境解析出的直接與傳遞依賴版本。沒有獨立的應用程式 build 命令。
- 開啟：Start-Process .\PBI_104.pbip。
- 已配置的離線測試：python -m unittest discover -s tools/tests -v；本次後續修補後 59 項通過。靜態檢查：python tools/validate_project.py；輸出 `PASS`、58 JSON、57 PBIR schemas、73 report field references、21 queries，Windows Desktop TMDL parser PASS。
- 目錄整理階段未執行單元測試、PBIP 刷新、DAX 或 API 請求；後續修補只做了唯讀 PostgreSQL coverage 查詢，沒有執行資料庫 schema 重套或 Power BI 全模型刷新。
- 磁碟定義 inventory：9 張模型表、52 個資料欄、9 個 measures、8 個關聯；4 頁報表、50 個 visual JSON。這些是檔案盤點，不代表本次驗證了實際載入資料或互動結果。
- Git：整理開始時 HEAD 為 806e437（main），162a193 是 origin/main 且為 HEAD 祖先。工作樹另有使用者未提交的文件與擷取工具修改；本次保留這些內容，沒有 stage、commit 或改動 Git 設定。

## 2. 專案目錄結構

- `PBI_104.pbip`：Power BI 專案入口；PBIR 與 TMDL 定義分別留在 `PBI_104.Report/`、`PBI_104.SemanticModel/`。
- `powerquery/`：active M 查詢依 `00_parameters/`、`01_functions/`、`02_source/`、`03_staging/`、`04_model/` 分組；舊查詢留在 `archive/pre-db-etl/`。
- `tools/acquisition/`：104 用戶端、分頁、不可變批次、PostgreSQL 擷取／載入、薪資與地理編碼模組。
- `tools/desktop/`、`tools/launchers/`、`tools/probes/`：分別保存 Desktop 操作、本機啟動入口與診斷探針。
- `tools/sql/`、`tools/tests/`、`tools/tests/fixtures/`：資料庫 schema、離線測試與審查過的最小 API fixture。
- `containers/Dockerfile.etl` 與根目錄 `docker-compose.yml`：ETL worker image 與本機服務編排。
- `docs/README.md`：現行文件索引；`docs/archive/` 保存舊任務包、退役模型、checkpoint、舊架構圖與歷史證據。
- `docs/assets/generated-inspiration/` 保存生成式探索圖；正式報表參考仍在 `report-design/`。
- `.env`、`.venv/`、`data/`、`.optimization/`、`.pbi/` 與 `cache.abf` 是本機設定、執行資料或快取；本次未讀取秘密值。Desktop 截圖輸出至使用者 TEMP 目錄。

## 3. 核心功能推測

- 擷取工具依官方職業類別代碼檢查或保存職缺，也保留既有 keyword capture 工作流程；使用 cloudscraper 與 Windows 系統 proxy。
- Bronze 保存原始頁面、checksum、請求與批次資訊；Silver 負責正規化；Gold 提供九個 Power BI 模型 views。擷取失敗、頁數封頂或品質檢查未通過的批次不應成為完整分析資料。
- FactJob 由完整職類觀測按 jobNo 選最新資料；FactJobSnapshot 保留批次快照。技能與職類透過 bridge 關聯篩選職缺。
- 四頁報表涵蓋市場總覽、薪資、技能與職缺探索。薪資原始數值、API applyCnt 與歷史快照不應自動解讀成已確認的商業語意。
- 專案文件明確指出尚無全台完整資料。報表中的目前職缺數是已載入資料範圍，不代表 104 全站或全台母體。

## 4. 架構分析

### 資料取得與資料庫

主要職責分層已移到 Python/PostgreSQL。檔案批次由 tools/sync_lake_to_postgres.py 驗證後匯入；TASK-014 另定義直接寫入 PostgreSQL Bronze 的 category capture。離線案例現已覆蓋 batch 狀態、query-series resume 與交易 wrapper rollback；實際 PostgreSQL migration 重跑、DB resume 和 rollback 仍需在隔離測試資料庫驗收。TASK-014 仍未標示完成。

### Power Query 與模型

目前 active M 僅連接並讀取 gold.pbi_* views。Parameters、Functions、Source 不載入模型；只有九個 Model pass-through tables 載入。03_staging 空著是目前設計，不是遺漏的 active path。模型含九張表、八個關聯與 measures；技能及職類 bridge 的雙向篩選用於 slicer 到 FactJob 的傳遞。既有 Desktop 驗收曾檢查 category/skill 篩選，但本次沒有重跑。

### 報表與驗證

PBIR 是四頁、50 個視覺檔；報表與 semantic model 是分開的修改層。CI workflow 在 Ubuntu 執行 Python 單元測試與 validate_project.py。該驗證器只有在 Windows 才呼叫 Power BI Desktop TMDL parser；Linux 會回報 desktopTmdlParser=UNAVAILABLE，但整體 JSON result 仍可為 PASS。CI 的 PASS 因此不能單獨證明 TMDL parser 已執行。

## 5. 目前風險

| 優先 | 風險 | 證據與影響 |
|---|---|---|
| P1 | 職缺覆蓋不完整 | docs/category-acquisition-probe.md 記錄不限地區 619 個職業代碼約需 42,466 個頁面請求；152 類回報超過 3,000 筆，達 API 150 頁上限。既有擷取還觀察到 total 不一致、重複 jobNo 與 HTTP 429。未完成完整性對帳前不得標示全台完整。 |
| P1 | 歷史刷新數字不可直接當作目前覆蓋 | docs/optimization-status.md 的 3,448 與 TASK-015 的 18,469 來自不同驗收快照。tools/report_category_coverage.py 現可唯讀產生各職類最新批次、查詢 area 範圍與 schema 版本；比較報表或刷新數字時需保存同一生成時間與批次狀態。 |
| P1 | 直接 PostgreSQL 擷取仍需隔離資料庫驗收 | 已新增離線案例檢查批次狀態、query-series resume 與交易 wrapper rollback；這些不會替代實際 PostgreSQL migration 重跑、same-day DB resume、原子 rollback 驗收。下一輪擷取前應在隔離測試資料庫完成這些案例。 |
| P2 | CI 的 TMDL 驗證範圍不同於 Desktop | Ubuntu workflow 只驗證 JSON/PBIR/query 結構；現在輸出 `STRUCTURE_PASS_DESKTOP_TMDL_UNAVAILABLE`。Windows 本機驗證器只有在 Desktop parser PASS 時才回報整體 PASS。 |
| P2 | 端到端刷新改善未證實 | TASK-013 記錄 Gold views 的 shared hit blocks 減少 26.5%、單輪 SQL 時間總和減少 7.3%；Power BI XMLA refresh 樣本在重開模型後波動較大，文件未宣稱可重複的完整刷新改善。SQL 計畫時間不等於 connector、模型處理或報表互動時間。 |
| P2 | 驗證環境仍有外部執行差異 | CI 與鎖版依賴固定 Python 3.13；PBIR schema 仍依賴官方外部 schema，Linux 不執行 Desktop parser。離線測試不等同即時 API、資料庫 migration 或 Desktop 刷新驗收。 |

本次未檢查秘密值，也未執行完整安全掃描。資料範圍、薪資語意、Service gateway 與報表使用者體驗均不因靜態檢查而得到額外保證。

## 6. 優化建議

### 先做

1. 先對齊唯一一份近期資料狀態：記錄資料庫 schema migration、最新成功 batch、職類／地區範圍、完整性狀態、九表筆數及 Desktop 刷新時間。若文件數字來自不同批次，明確標為歷史值；無法核實就標示 BLOCKED。
2. 在執行大規模資料擷取前完成 TASK-014 的資料庫整合驗收：驗證 migration 可重跑、每個 category transaction 原子性、resume 不覆蓋舊 batch、失敗不進 Gold，以及 raw page metadata 可追溯。
3. 把全台擷取拆成可核對的覆蓋工作。先從低頁數職類做小批 pilot，保存每類別的 API total、實際頁數、重複／衝突數、429 與 Bronze/Silver 狀態；達 150 頁或 metadata 不符一律明確標記未完整，不合成缺失資料。

### 中期

- TASK-014 驗收後再評估 619 類別擷取的總請求量、共享 rate limiter 與 resume 行為；用小批次結果調整併發，不依單一 page-size 實驗推論全量效能。
- 在資料筆數與 batch 範圍一致後，重新做多輪 Desktop 全模型 refresh 基準，分開記錄 PostgreSQL plan、資料傳輸、模型處理和 Desktop 總耗時；只有可重複改善才調 SQL 或載入路徑。
- CI 已將結構驗證與 Windows-only TMDL parser 狀態分開輸出，requirements-dev.txt 已鎖定目前 Python 3.13 環境解析出的直接與傳遞依賴版本。
- 維持現有九表與 Gold 契約；先用欄位／visual 依賴 inventory 證明模型欄位未使用，才考慮縮減載入欄位。

### 長期

- 若產品需要趨勢，先定義 snapshot 的查詢系列、每日成功條件、重跑與去重規則，再建立可解釋的趨勢 measures。
- Service 排程、gateway、資料庫供應與憑證管理需在目標環境另外驗收；本機 Desktop refresh 不能替代部署驗證。

## 7. 下一步任務建議

以下恰為五個建議工作單元；本次沒有新增 TASK 檔或開始實作。

### OPT-001：統一近期資料與驗收狀態

狀態：coverage ledger 指令已建立並連接唯讀 DB 查詢；最終擷取摘要仍須等目前 run 結束後更新。

- 目標：讓 README、optimization-status、architecture 與 TASK 索引指向同一份有日期的資料狀態。
- 範圍：只更新 docs/ 與 README；從一個明確 batch／Desktop 驗收取得筆數，不改資料庫、M、TMDL 或 PBIR。
- 驗收：標明 schema migration、batch 日期與覆蓋範圍；3,448 與 18,469 等舊數字均標示其批次／歷史語境；無法確認的範圍標為 BLOCKED。
- 驗證命令：rg -n "3,448|18,469|migration|全台|nationwide" README.md docs docs/archive/tasks。

### OPT-002：TASK-014 PostgreSQL capture 整合驗收

狀態：離線批次、resume 與交易 wrapper 案例已補；隔離 PostgreSQL migration／rollback 驗收仍未執行。

- 目標：證明直接擷取的 category transaction、migration 與 resume 邊界安全。
- 範圍：tools/acquisition/postgres_capture.py、postgres_writer.py、category_runner.py、migration 10 與對應 tests；不做 619 類全量擷取、不改 Power BI。
- 驗收：測試 migration 重跑、完整 batch、page-capped Bronze-only、Silver normalization block、transaction rollback、same-day resume 和舊 batch 保留。
- 驗證命令：python -m unittest discover -s tools/tests -v；本機 PostgreSQL 測試後查詢 bronze.schema_migrations 最高版本與 category batch 狀態。

### OPT-003：建立可核對的職類覆蓋 ledger 與小批 pilot

狀態：唯讀 ledger 已建立；目前擷取仍在進行，尚無最終覆蓋結果。

- 目標：量化哪些官方職類已完整、封頂、失敗或尚未擷取。
- 範圍：category batch 摘要與只讀 coverage report；先用低頁數職類驗證流程，不開始全台 42,466 頁請求。
- 驗收：逐類列出 requested code、API total、實收 rows/pages、pagination 與 normalization 狀態；上限或不一致的批次不列為完整，不改 keyword current pointer。
- 驗證命令：python tools/capture_category_matrix.py --capture --direct-postgres --resume --code <已選定的低頁數職類>；對照 bronze.capture_batches 的 source_jobcat、snapshot_date、capture_status 與 row_count。

### OPT-004：以固定資料集重測完整刷新時間

狀態：待目前擷取終止、Gold 筆數穩定後再測；本次沒有新增刷新時間樣本。

- 目標：判斷 TASK-013 SQL 精簡是否縮短實際 Power BI Import refresh。
- 範圍：只做基準測量與 docs 紀錄；在一致的資料集、Desktop 狀態與刷新方式下測至少五輪，不改 schema、DAX 或視覺。
- 驗收：保存每輪九表筆數、總時間、中位數、範圍與資料庫計畫時間；將 connector/模型處理與 SQL 時間分開，不用不同資料量的樣本比較。
- 驗證命令：Start-Process .\PBI_104.pbip；.\tools\desktop\desktop_model.ps1 -Operation Inventory；人工執行五輪 full refresh 並將原始時間寫入 docs。

### OPT-005：明確呈現 CI 與 Desktop parser 的驗證邊界

狀態：完成；結構 PASS 與 Desktop parser UNAVAILABLE/PASS 已分開輸出。

- 目標：CI 結果不讓 Linux 的結構 PASS 被理解為 Desktop TMDL parser PASS。
- 範圍：.github/workflows/validate.yml、tools/validate_project.py 與 tools/README.md 的狀態輸出／說明；不更動模型語意或報表。
- 驗收：Ubuntu log 明確顯示 Desktop parser 為 UNAVAILABLE；Windows 本機 Parse gate 單獨報告 PASS／FAIL；兩種結果不混為單一 parser claim。
- 驗證命令：python tools/validate_project.py；Windows PowerShell 執行 .\tools\desktop\desktop_model.ps1 -Operation Parse。
