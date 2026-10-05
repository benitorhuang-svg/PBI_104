# Power Query Source Files

此目錄保存可貼入 Power Query Advanced Editor 的完整 M expressions。檔案系統使用小寫目錄；Power BI Desktop 內請建立 `00_Parameters` 至 `04_Model` Query Groups。

## TASK-002 import order

1. 在 `00_Parameters` 建立 `pBaseUrl`、`pArea`、`pJobSource`、`pKeyword`、`pMode`、`pOrder`、`pPage`、`pPageSize`。
2. 在 `01_Functions` 建立 `fx104GetPage`、`fx104GetAllPages`。
3. 在 `02_Source` 建立 `src_104Result`、`src_104Jobs`、`src_104Metadata`。
4. 先單獨呼叫 `fx104GetPage` 驗證 page 1，再 refresh `src_104Jobs` 與 `src_104Metadata`。

所有 TASK-002 queries 都必須 Disable Load。`src_104Result` 是共享 record，避免在 M code 中複製擷取流程；`src_104Jobs` 與 `src_104Metadata` 只投影該 record，不加入清理或商業邏輯。

`fx104GetPage` 只有 `baseUrl` 必填；`keyword`、`area`、`jobsource`、`mode`、`order`、`page`、`pagesize` 均可省略。省略或傳入空白文字時，該參數不會加入 HTTP query string；若有提供 `page` 或 `pagesize`，其值必須是正整數。正式的 `src_104Result` 仍會明確傳入八個專案參數。

TASK-003R 已將 `00_Parameters` 至 `03_Staging` 共 20 個 expressions 與四個 Query Groups 持久化至 PBIP/TMDL，並在 Power BI Desktop 儲存、關閉、重開及 refresh 驗證。這 20 個 queries 全部維持 Disable Load；`04_Model` 尚未建立，既有 loaded query `查詢` 未被修改。
