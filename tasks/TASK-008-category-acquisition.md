# TASK-008 — 104 官方職業類別擷取與資料庫對照

## 目標

資料擷取以 104 官方職業類別為查詢依據，不再要求使用者先猜關鍵字。使用官方
`JobCat.json` 作為職類代碼與名稱來源，呼叫 104 職缺搜尋 API 的 `jobcat` 篩選，
並將查詢類別、職缺回傳職類、擷取批次和分類名稱分開保存。

## 範圍

- 從 `https://static.104.com.tw/category-tool/json/JobCat.json` 取得原始分類樹，
  驗證唯一代碼、名稱、父子形狀，並以 SHA-256 manifest 保存不可變快照。
- 以官方職類代碼作為批次查詢單位；先查 page 1 確認筆數／頁數，再明確
  指定完整擷取。預設不傳 `area`；只有明確要求區域資料時才指定 area。
- 每個職類維持獨立 query series 和完整批次；同一批次所有頁驗證完成後才落盤。
  類別批次不可覆寫既有 keyword `current.json`。
- PostgreSQL 保存官方分類原始快照與攤平階層，更新職缺回傳 `jobCat` 對照名稱，
  並分欄保存查詢 `jobcat` 與實際職缺類別。
- 保留既有 keyword query key、捕獲檔案與資料；繼續使用 `cloudscraper` 及 Windows
  system proxy，不新增 cookie、token 或憑證。

## 明確不在範圍

- 不修改 PBIR、Semantic Model、報表或職缺商業分類解讀。
- 不把不同類別批次合併成一個無來源的結果集；跨類別同一職缺仍由 `jobNo` 識別。
- 不繞過已觀察到的 API 150 頁限制或合成缺失列；全區擷取依官方細職類拆分並記錄未覆蓋項目。
- 不移動、替換或重新發布目前 `current.json`。

## 驗收

- 可在沒有 `keyword` 的情況下以官方 `jobcat` 擷取，並保留 area、頁次、原始回應、
  manifest、HTTP 狀態、分頁完整性和類別來源。
- 類別樹內容、代碼唯一性與 checksum 通過；資料庫職類名稱來自同一官方快照，
  原始回傳的職缺職類代碼可正確 join。
- 既有 keyword series key 與 current pointer 位元內容維持不變；分類批次不得移動
  pointer。新 schema 可從現有 v2 資料庫升級，重跑 migration／import 不重複加資料。
- 先執行官方職類逐類 page-1 檢查；記錄總職缺量與總頁數。超出合理操作時間時，
  保留檢查結果並按明確類別分批執行，不宣稱尚未擷取的分類已完成。
- Python 測試、schema migration、既有 lake 匯入及 PostgreSQL 分類名稱／查詢來源
  驗證通過。未執行 Power BI Desktop 刷新時，標記該項為 UNVERIFIED。

## 執行結果（2026-10-05）

- 已完成官方 681 節點分類快照與 18 個第一層職類的 `jobcat` 擷取；完整逐類結果及
  API 分頁限制見 `docs/category-acquisition-probe.md`。
- 原始批次均已匯入 PostgreSQL；4 個分頁一致批次進 Silver。13 個有分頁不一致的批次
  和 1 個重複職缺欄位衝突批次保留在 Bronze，未發布為完整資料。
- 既有 keyword 批次與 `data/104/current.json` 未變；未修改 PBIR 或 Semantic Model。
- Power BI Desktop 刷新與視覺層驗證：UNVERIFIED，本 TASK 未修改該層。
- `python tools/sync_lake_to_postgres.py --write`、Python 單元測試、專案驗證器及
  Power Query 同步檢查通過。
- 後續依使用者要求移除職類查詢預設 `area` 篩選；預設不傳 `area`，可用 `--area`
  明確指定地區。不限地區三層 page-1 檢查發現大量分類碰到 150 頁限制；未宣稱或
  匯入未執行的全台批次，數據與估計頁數見 `docs/category-acquisition-probe.md`。
