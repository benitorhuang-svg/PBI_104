# Semantic Model 繁中顯示契約 v1

本契約記錄 Power BI 資料窗格使用的繁體中文表格、欄位與量值名稱。完整的舊名稱、新名稱、資料型別、隱藏狀態與來源欄位對照位於 [semantic-model-display-names-v1.json](semantic-model-display-names-v1.json)。

| 原 TMDL 檔案 | 資料窗格名稱 |
|---|---|
| `FactJob.tmdl` | 目前職缺 |
| `FactJobSnapshot.tmdl` | 職缺快照 |
| `FactSalaryObservation.tmdl` | 薪資觀測 |
| `FactAcquisitionCategory.tmdl` | 職類擷取進度 |
| `DimCompany.tmdl` | `dim_公司` |
| `DimArea.tmdl` | `dim_地區` |
| `DimDate.tmdl` | `dim_日期` |
| `DimJobCategory.tmdl` | `dim_職類` |
| `DimSkill.tmdl` | `dim_技能` |
| `BridgeJobCategory.tmdl` | 職缺職類對照 |
| `BridgeJobSkill.tmdl` | 職缺技能對照 |

截至 2026-10-11，模型有 9 張表、86 個欄位與 37 個量值。`FactJobSnapshot` 和 `FactSalaryObservation` 的名稱仍保留在 v1 對照歷史中，但兩表目前不在語意模型，也不載入 Power BI；資料庫 Gold views 仍保留。五張維度表以 `dim_` 前綴標示；TMDL 物件名稱直接採用繁中名稱，`zh-TW` 翻譯標題與它們一致。欄位的 `sourceColumn`、Power Query 查詢名稱、Gold view、資料粒度與來源資料保持原值；名稱對照可由 JSON 的 `previousName`、`name` 與 `sourceColumn` 欄位追溯。`dim_職類[GoldenL1]` 以 104 官方 18 個根類別作 canonical baseline，跨平台來源只有在 crosswalk `CONFIRMED` 時才歸入；未確認資料維持 `待對照／BLOCKED`。

這是 Power BI 語意模型名稱契約。PostgreSQL Bronze/Silver/Gold 結構仍依 [資料庫契約 v1](database-schema-contract-v1.md) 管理。本契約升版時，同步更新 TMDL 名稱、關聯端點、DAX 引用、PBIR 欄位引用、模型圖與 DAX 探針。
