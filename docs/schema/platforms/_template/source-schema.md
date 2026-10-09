# `<platform>` 來源 Schema 記錄

## 識別與狀態

- 平台 slug：`<lowercase-id>`
- adapter 路徑：`tools/acquisition/platforms/<platform>/`
- schema 版本：`v1`
- schema 狀態：`UNOBSERVED` / `OBSERVED_LIMITED` / `CONFIRMED` / `BLOCKED`
- 最近觀察日期與時區：`YYYY-MM-DD` (`Asia/Taipei`)
- 證據檔案與 SHA-256：`<path>` / `<hash>`

## 來源範圍

- Host/endpoint/page:
- HTTP 方法及必要查詢條件:
- 查核範圍、頁數、筆數與擷取時間:
- 權利/使用限制狀態:

## 欄位契約

| 欄位/路徑 | 觀察到的型別 | Nullable/缺值狀態 | 正規化位置 | 證據與備註 |
|---|---|---|---|---|

## 鍵、分頁與批次

- 原生 ID 路徑和文字保留方式:
- JobWant 的 source key 規則:
- 分頁/終止規則及證據:
- 批次唯一鍵、hash 和完整性條件:

## 對應與待確認項目

| 項目 | 狀態 | 所需證據/負責層 |
|---|---|---|

未觀察或未確認的欄位、代碼意義、鍵唯一性、分頁語意和跨平台 mapping 一律標記 `BLOCKED`，不得補猜。
