# 歷史封存

此處保存已停止維護的任務文件、舊模型材料與歷史證據，以便追溯專案沿革。封存內容不代表目前的架構、資料狀態或操作方式；請以 [`docs/README.md`](../README.md)、根目錄 `AGENTS.md` 與現行文件為準。

## 內容

- `104-powerbi-codex-task-pack/`：早期專案初始化、Power Query、模型與報表頁任務包。
- `tasks/`：舊版 TASK-001 至 TASK-015 任務文件與索引。
- `checkpoints/`：TASK-007 前的歷史檢查點備份。
- `legacy-model/`：退役的 Power Query/TMDL 匯出及自動日期表。
- `operating-notes/`：舊 Power Query 執行計畫、驗證紀錄與報表任務狀態。
- `evidence/`：Power BI 關閉／重開失敗的歷史截圖。
- `architecture/`：2026-08-13 的舊架構圖；圖中仍把 Power Query/Staging 畫成資料清理層，現行架構請看 [`../architecture.md`](../architecture.md)。
- `samples/README.md`：舊測試樣本說明。舊原始 API 回應未複製到封存；測試只使用 `tools/tests/fixtures/` 的審查版 fixture。

封存檔案保留原始內容，沒有改寫其中的歷史數字或任務敘述。

`104-powerbi-codex-task-pack/` 是早期任務包的原始展開副本，包含一份不完整的任務子集；`tasks/` 則是專案完整的 TASK-001 至 TASK-015 歷史序列。部分同名任務檔案內容完全相同，仍保留在兩處以維持任務包來源脈絡。`legacy-model/legacy-query.tmdl` 與 `legacy-model/tables/查詢.tmdl` 也是內容相同、原始名稱不同的舊模型匯出。這些副本都不是現行操作來源。

`SHA256SUMS` 記錄本封存目錄內每個檔案的 SHA-256（不含清單本身）。只有在刻意新增、移除或修改封存內容時才更新清單；可用來確認歷史文件與證據仍維持原始位元內容。
