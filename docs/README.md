# 文件索引與目錄規則

`docs/` 根層只放目前維護的架構、模型、資料品質、操作說明與有日期的驗收紀錄。舊任務包、舊模型檔與歷史證據集中在 [`archive/`](archive/README.md)，封存內容供追溯，不作為現行操作指引。

本專案產品名稱為 **JobWant**。PBIP 入口、報表與語意模型目錄均使用 `PBI_JobWant` 名稱；104 仍是來源平台識別。本機資料庫已完成改名為 `jobwant_104`，yes123 來源資料庫為 `jobwant_yes123`。104 是既有報表來源；yes123 adapter 與 capture 已存在，但授權、代碼映射和中央 Gold 接入仍未解除阻擋。

## 專案主要目錄

| 路徑 | 用途 |
| --- | --- |
| `PBI_JobWant.pbip` | Power BI 專案入口。 |
| `PBI_JobWant.Report/` | PBIR 報表頁面與視覺定義。 |
| `PBI_JobWant.SemanticModel/` | TMDL 語意模型、關聯與文化設定。 |
| `powerquery/` | 目前由 PostgreSQL Gold views 供應資料的 M 查詢。 |
| `tools/` | Python 擷取、ETL、驗證及本機操作工具。 |
| `tools/acquisition/shared/` | 多平台共用、不得綁定來源 API 契約的工具。 |
| `tools/acquisition/platforms/<platform>/` | 各職缺來源獨立的客戶端、擷取與載入程式；分組細節見 [`tools/acquisition/README.md`](../tools/acquisition/README.md)。 |
| `tools/deployment/containers/` | PostgreSQL 與 ETL Compose 使用的容器建置定義。 |
| `docs/report-design/` | 核准的報表設計參考圖與規格。 |
| `docs/` | 現行專案文件；生成式探索圖另放在 `assets/generated-inspiration/`。 |
| `data/<platform>/` | 本機來源批次、目錄與執行摘要按平台隔離；現有 `data/104/` 是不可變來源證據，應保留。 |

## 現行文件

> 讀取原則：架構說明描述目標與目前程式邊界；TASK、刷新效能、API profile 和擷取規模文件是有日期的證據快照，不代表即時資料庫或 Desktop 狀態。執行寫入前先讀 `operations/local-database.md` 和 `schema/` 的最新差異。

- 架構與模型：[`architecture.md`](architecture/README.md)、[`data-model.md`](architecture/data-model.md)、[`semantic-model.md`](architecture/semantic-model.md)。
- Schema 蒐錄：[`schema/`](schema/README.md)（共用契約、平台來源 schema 與 PostgreSQL dated catalog 快照）。
- API、品質與擷取規模的日期快照：[`api-schema.md`](data-reference/api-schema.md)、[`data-quality-report.md`](data-reference/data-quality-report.md)、[`category-acquisition-probe.md`](data-reference/category-acquisition-probe.md)、[yes123 接入盤點](data-reference/yes123-category-acquisition-probe.md)。
- 本機資料庫操作與歷史刷新驗收：[`local-database.md`](operations/local-database.md)、[`optimization-status.md`](operations/optimization-status.md)。
- 專案靜態盤點與文件內容審核：[`PROJECT_AUDIT.md`](audits/PROJECT_AUDIT.md)、[`DOCS_CONTENT_REVIEW_2026-10-09.md`](audits/DOCS_CONTENT_REVIEW_2026-10-09.md)。

## 素材與暫存資料

- `assets/generated-inspiration/` 僅放生成式設計探索圖；正式報表依專案根目錄 `docs/report-design/` 的核准資料維護。
- Desktop 暫存截圖輸出至 `%TEMP%/PBI_104/desktop.png`，不存入專案。
- `.env`、`.venv/`、`data/`、`.optimization/`、`.pbi/` 與 `cache.abf` 是本機設定、執行資料或快取，依 `.gitignore` 管理。`data/104/` 不應清空：擷取工具、批次追溯與 Compose volume 都使用此路徑。
- `.optimization/deps/` 與 `.optimization/schema-cache/` 供本機驗證使用；一次性診斷腳本放在被忽略的 `.optimization/archive/`。
- 測試 API fixture 僅使用 `tools/tests/fixtures/` 內經審查的最小範例，不把原始擷取資料複製到文件目錄。
