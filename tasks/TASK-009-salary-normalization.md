# TASK-009 — 薪資觀察與保守標準化

## 目標

在不覆寫 104 原始薪資欄位的前提下，從職缺描述擷取有明確證據的薪資金額與期間，另存可稽核的薪資觀察。區分 API 原始數字、文字描述證據與標準化結果，讓不明單位、期間及疑似特殊值可被辨認，不被誤當成月薪或真實上限。

## 範圍

- 新增確定性、無外部模型依賴的繁體中文薪資片語擷取器，保留原描述片語及其 Unicode 字元起訖位置。
- 支援明確月薪、時薪、年薪、日薪、週薪期間；數字、千分位、萬／千與常見中文數字；上下限區間、單值最低值、最高值、面議與未公開文字。
- 薪資觀察按 `series × snapshot date × batch × job × source kind × mention index` 保存，分開記錄 `API_FIELDS` 與 `DESCRIPTION`，保留 parser 版本、證據、狀態、品質旗標與信心值。
- `salaryLow`／`salaryHigh` 原始欄位照舊保留。API 欄位薪資單位與期間未經證實，標為 `API_UNIT_UNMAPPED`；`0` 與 `9999999` 僅標為 `SENTINEL_CANDIDATE`，不填入標準化上下限。依使用者規則，幣別預設 TWD 並以 `PLATFORM_DEFAULT` 標示；描述中的明確幣別優先。
- 描述文字只有明確期間才設定 `pay_period`；單一薪資數字一律作為下限，最高值留空；明確區間填入上下限。`jobType`、`period` 不映射成薪資期間。
- PostgreSQL schema migration 5 建立 Silver observation 表與 Gold 最新完整批次檢視。重新執行匯入時補處理已匯入的完整批次，確保現有資料可回填且不需重新呼叫 API。
- 更新資料品質與資料庫文件，交代解析涵蓋和未解析界線。

## 不在範圍

- 不修改 PBIR、Power Query、Semantic Model、薪資視覺或 measures。
- 不把年薪換算月薪、不估算獎金，也不把談薪敘述併入固定薪資；薪資組成除明示底薪或變動報酬外維持未知。
- 不猜 104 API 薪資代碼／單位或 `period` 的意義；幣別依使用者指定預設 TWD，明確外幣文字優先。
- 不呼叫 API、不更動原始捕獲檔、批次 manifest 或分類查詢流程。

## 驗收

- 單元測試涵蓋「月薪四萬以上」、`150/hr`、`35000~42000`、明確年薪範圍、無期間的「四萬以上」、面議／未公開、API 常態值與疑似哨兵值。
- 升級既有 schema 可重複執行； observation 寫入具批次來源且冪等。
- 重新匯入既有 lake 時可補上完整批次的 API 與描述觀察；原始薪資欄位及 Bronze payload 不變。
- 單元測試、專案驗證器、遷移後 PostgreSQL 查詢與回填筆數核對通過。
- 不執行 Power BI Desktop 刷新，該項標記為 `UNVERIFIED`，因為本 TASK 未變更該層。

## 執行結果（2026-10-06）

- 新增 `silver.job_salary_observations` 與 `gold.latest_job_salary_observations`；既有 PostgreSQL 從 schema version 4 升級至 5。
- 25 個既有批次成功補建觀察，未呼叫 104。最終 3,168 筆 API 觀察分成 1,845 筆 `API_UNIT_UNMAPPED` 與 1,323 筆 `SENTINEL_CANDIDATE`；幣別皆為預設 TWD、單位不明的 API 金額仍不正規化。
- 再次執行 `sync_lake_to_postgres.py --write` 後觀察筆數不變；API 金額仍為空，幣別採 TWD 預設；所有描述證據起訖長度核對通過。
- 使用者確認預設新台幣及 min/max 規則後，parser 升為 1.1.2 並重跑既有 25 批次；單一金額改存最低值，`150/hr` 解析為時薪下限，明確範圍保留上下限。
- 回填更新 parser 衍生欄位並清除新版規則不再產生的舊片語；Bronze 原始內容未變。最終有 1,314 筆描述觀察，其中 212 筆 `PARSED`、1,024 筆 `NEEDS_REVIEW`、74 筆 `NEGOTIABLE`、4 筆 `NOT_DISCLOSED`。
- Python 單元測試 40 項通過；`tools/validate_project.py` 通過。Power BI Desktop 刷新為 `UNVERIFIED`。
- 未修改 PBIR、Semantic Model、Power Query、原始捕獲檔或批次 manifest；未 commit。
