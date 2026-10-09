# 104 來源 Schema 記錄

## 識別與狀態

- 平台 slug：`104`
- Adapter：`tools/acquisition/platforms/jobwant_104/`
- Schema 狀態：`OBSERVED_LIMITED`
- 最近記錄的 live evidence：2026-08-13（Asia/Taipei）
- 完整欄位證據：[docs/data-reference/api-schema.md](../../../data-reference/api-schema.md)
- 最小 sanitized fixture：`tools/tests/fixtures/api-response-page-1.fixture.json`

## 觀察範圍

證據來自 104 搜尋 API 的一個指定 keyword/area 查詢及前三頁、共 55 列；代表該次回應，不保證所有平台查詢、登入狀態或未來版本都相同。來源欄位名稱、JSON 路徑與巢狀 shape 以證據文件為準；不可把單次都有出現的欄位當成 API 永久必填。

已觀察到職缺原生識別欄位 `jobNo`，公司識別欄位 `custNo`；兩者在該批資料有值，但全站唯一性尚不能只靠這份查詢證明。已觀察到的 nested paths 包含 `pcSkills`、`jobCat`、`link`、`tags` 和 `languageRequirements`；其中部分值存在多種型別或未確認的商業語意，必須照 evidence file 的限制處理。

## 對應規則

- 來源原始 payload 及擷取頁面 metadata 存於 Bronze；欄位解析、正規化和品質處理由 adapter/ETL 執行，不由 Power Query 展開。
- 來源識別保留為文字；Gold 以平台限定鍵暴露職缺，不能將 `jobNo` 的單次觀察等同於跨平台全域唯一。
- 薪資單位、部分代碼語意及 nested 欄位的完整 optionality 仍依 [API evidence](../../../data-reference/api-schema.md) 標記為待確認。

## 更新方式

新的 API shape 需附查詢條件、時間、fixture/hash 和欄位差異；建立下一個版本記錄，不覆寫本次 2026-08-13 的有限範圍證據。
