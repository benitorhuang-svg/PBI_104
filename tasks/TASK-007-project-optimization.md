# TASK-007 — 專案全面優化

## 授權與既有證據

使用者於 2026-10-05 要求「全部優化」，涵蓋 PROJECT_AUDIT.md 的可驗證建議。
沿用 TASK-002 至 TASK-006D 的分層與設計原則。既有 Git baseline 為 162a193；
修改前另保存含未提交成果的 ZIP checkpoint，不自行 commit 或 publish。

## 執行順序與範圍

1. Source：逐頁契約、完整批次、可重跑擷取與固定批次／歷史保存。
2. Staging：嚴格 nested parsing、型別品質記錄、共享地點 key／連結規則。
3. Model queries：投影與 grain／orphan checks，職類 bridge、歷史快照讀取。
4. Semantic Model：技能／分類篩選、日期覆蓋、明確 measures、非加總 metadata；
   檢查依賴後保留可恢復舊查詢原始碼並退役重複 loaded 路徑。
5. Report：依核准參考圖更新既有頁，修正命名、職缺粒度、排序與篩選一致性。
6. 文件／工具：完整 query 匯出、runtime 記錄、可重跑唯讀 gates、環境版本與部署指引。

每個階段完成獨立測試後再進入下一階段，不在 PQ／Model 工作期間修改 PBIR。
完整 M 原始碼保存在 powerquery/；TMDL 同步只維護持久化表達式。

## 契約

- 多技能／職類選取使用 OR；與地區／公司／日期等其他篩選使用交集。
- 所有 snapshot batches 保留完整擷取時間與查詢參數；同一日同一查詢使用最新
  成功完整批次，跨日保留歷史。不將不同 keyword／area 混成同一歷史系列。
- 0／9999999 薪資保持原值；薪資單位、揭露語意與職類名称映射繼續 BLOCKED。
- 正常空結果是零列；malformed JSON、錯誤形狀、無效必要鍵必須明確失敗。
- 保留 cloudscraper＋Windows system proxy，不加入 cookies／tokens／credentials。
- 不以 fixture／歷史結果冒充 live API；部署到 Service 與外部排程不在本機修改中宣稱完成。

## 驗收

- 正常、零結果、錯頁、部分失敗、型別漂移與 orphan cases 有具體 gates。
- 所有 M 匯出與 TMDL 一致，JSON Schema／TMDL 可解析，程式檔 <= 300 行。
- 技能／分類 OR、多篩選交集、比例分母、日期 coverage 與 jobNo 選取通過。
- 持久化失敗不能更新 current pointer；失敗保留上一個成功批次。
- Desktop refresh／save／close／reopen 後的 row counts、Enable Load 與互動另行記錄。
- 未能執行的 runtime gate 明確為 UNVERIFIED／BLOCKED，不宣稱全部測試通過。

## 驗證入口

將建立 tools/validate_project.py、tools/tests/ 與 Desktop DAX／M probes。
正常開啟命令：`Start-Process .\PBI_104.pbip`。
