# 文件索引與目錄規則

`docs/` 根層只放目前維護的架構、模型、資料品質、操作說明與有日期的驗收紀錄。舊任務包、舊模型檔與歷史證據集中在 [`archive/`](archive/README.md)，封存內容供追溯，不作為現行操作指引。

## 專案主要目錄

| 路徑 | 用途 |
| --- | --- |
| `PBI_104.pbip` | Power BI 專案入口。 |
| `PBI_104.Report/` | PBIR 報表頁面與視覺定義。 |
| `PBI_104.SemanticModel/` | TMDL 語意模型、關聯與文化設定。 |
| `powerquery/` | 目前由 PostgreSQL Gold views 供應資料的 M 查詢。 |
| `tools/` | Python 擷取、ETL、驗證及本機操作工具。 |
| `containers/` | PostgreSQL 與 ETL Compose 使用的容器建置定義。 |
| `report-design/` | 核准的報表設計參考圖與規格。 |
| `docs/` | 現行專案文件；生成式探索圖另放在 `assets/generated-inspiration/`。 |
| `data/104/` | 本機不可變 API 批次、分類目錄與執行摘要；供擷取及資料庫匯入流程使用。 |

## 現行文件

- 架構與模型：[`architecture.md`](architecture.md)、[`data-model.md`](data-model.md)、[`semantic-model.md`](semantic-model.md)。
- API 與資料品質：[`api-schema.md`](api-schema.md)、[`data-quality-report.md`](data-quality-report.md)、[`category-acquisition-probe.md`](category-acquisition-probe.md)。
- 本機資料庫、操作與刷新：[`local-database.md`](local-database.md)、[`optimization-status.md`](optimization-status.md)。
- 專案盤點：[`PROJECT_AUDIT.md`](PROJECT_AUDIT.md)。

## 素材與暫存資料

- `assets/generated-inspiration/` 僅放生成式設計探索圖；正式報表依專案根目錄 `report-design/` 的核准資料維護。
- Desktop 暫存截圖輸出至 `%TEMP%/PBI_104/desktop.png`，不存入專案。
- `.env`、`.venv/`、`data/`、`.optimization/`、`.pbi/` 與 `cache.abf` 是本機設定、執行資料或快取，依 `.gitignore` 管理。`data/104/` 不應清空：擷取工具、批次追溯與 Compose volume 都使用此路徑。
- `.optimization/deps/` 與 `.optimization/schema-cache/` 供本機驗證使用；一次性診斷腳本放在被忽略的 `.optimization/archive/`。
- 測試 API fixture 僅使用 `tools/tests/fixtures/` 內經審查的最小範例，不把原始擷取資料複製到文件目錄。
