# 文件內容審核（2026-10-09）

## 審核範圍與證據

本次檢查現行文件的內容日期、操作指示、資料模型數量、跨文件說法、schema 閘門和本機 Markdown 連結。參照的專案證據包括：

- 磁碟上的 `PBI_JobWant.SemanticModel/definition/tables/*.tmdl`：10 張模型表，10 張都有 M partition。
- `PBI_JobWant.Report/definition/pages/pages.json`：PBIR 定義 5 個頁面；`docs/report-design/` 有 pages 01–04 的核准規格，沒有 page 05 規格。
- [jobwant_104 catalog snapshot](../schema/databases/jobwant_104/catalog-20261009T114619Z.json)：擷取時間 2026-10-09 11:46 UTC，schema 登記到 migration 20，缺少 6 個模型要求的 Gold views。
- [jobwant_yes123 catalog snapshot](../schema/databases/jobwant_yes123/catalog-20261009T114619Z.json)：同一時間點的唯讀結構快照，schema 登記到 migration 19。

本次是文件與已保存 catalog 的靜態審核；沒有執行 API 擷取、資料庫 migration、資料寫入、單元測試或 Power BI Desktop 刷新。catalog 是有時間戳的快照，不宣稱為審核當下的 live 查詢。Report-design 圖片只核對檔案索引，未做視覺 QA；歷史 archive 未修改。

## 已修正

1. `docs/README.md` 原先寫 104 資料庫改名尚待執行，與現有 `jobwant_104` catalog 不符；已改為完成，並將資料庫用途與 yes123 中央 Gold 導入狀態分開敘述。
2. 架構與模型文件曾混用 9 表與 10 表說法。磁碟模型現有 10 張 M-partition 表；2026-10-06 的 9 表 Desktop 驗收保留為歷史快照，沒有冒充新版驗收。
3. 操作文件曾指示 `sync_lake_to_postgres.py --write`、`--direct-postgres` 和排程 launcher，而這些寫入路徑會套用版本 19 schema script 到版本 20 的報表資料庫。文件現明確阻擋這些操作，直到 migration runner 與 Gold view set 對齊。
4. yes123 盤點曾把 2026-10-09 初始查核時「尚無 adapter」寫在現況段落；已標成初始基準，並連到後續 adapter/schema 文件。授權與分類映射仍維持 `BLOCKED`。
5. Report-design 規格補上 pages 01–04 已存在的 `FactJob[sourcePlatform]` slicer，並註明該 slicer 只反映 Gold 實際提供的值。文件也指出 PBIR 目前另有 page 05，但尚無核准參考規格。
6. API、資料品質、擷取、刷新和模型驗收文件加上日期快照說明，避免把歷史數字當成即時狀態。

## 尚未解除的狀態

- `jobwant_104` 缺少 6 個目前模型要求的 Gold views：`pbi_bridge_job_skill`、`pbi_dim_area`、`pbi_dim_company`、`pbi_dim_date`、`pbi_dim_job_category`、`pbi_dim_skill`。10 表模型尚無 Desktop 刷新驗收；資料庫契約提案尚未套用。
- yes123 的批量保存/分析/展示授權，以及 `WcodeList`、`JcodeList` 和候選目錄的映射仍待證據。
- page 05 的正式設計參考與規格尚未建立。
- 104 API 欄位證據最後觀察於 2026-08-13；擷取規模與頁數限制證據最後記錄於 2026-10-06。新一輪擷取前應重新檢查。

## 靜態檢查

- 24 份現行 Markdown 文件包含 57 個本機 Markdown 連結，未發現失效路徑。
- `docs/schema/` 下 4 個 JSON 都可解析；registry 列出的 6 個 adapter/schema/evidence 路徑都存在。
- `git diff --check` 未報 whitespace error；Git 顯示的 LF/CRLF 訊息是工作樹換行正規化提示。
