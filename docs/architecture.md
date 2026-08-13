# 104 Power BI Job Intelligence 架構

## 目的與本次邊界

本文件定義 Power Query、資料載入與 Semantic Model 的責任邊界。目前只建立架構與工作拆分，不修改查詢、模型或 Dashboard。`00_Parameters` 至 `04_Model` 是 Power Query 內的 Query Groups，不是檔案系統目錄。

## 現況盤點

- `PBI_104.pbip` 連結 `PBI_104.Report/` 與 `PBI_104.SemanticModel/`。
- 報表目前只有一個 1280×720 空白頁。
- Semantic Model 目前載入單一 `查詢` 表，另有 Power BI 自動日期表與兩條日期關聯。
- `查詢.tmdl` 目前將參數、Python API 呼叫、JSON 展開、清理、型別轉換及模型輸出放在同一個查詢內。
- 已驗證的連線方式是 Python、`cloudscraper`、Windows 系統 Proxy；目前沒有獨立測試或 Git metadata。

## 目標分層

| Query Group | 責任 | Enable Load |
|---|---|---|
| `00_Parameters` | API URL 與已確認的 `area`、`keyword`、`mode`、`order`、`page`、`pagesize` | 否 |
| `01_Functions` | 僅放兩處以上會重複使用且規則穩定的轉換或呼叫 | 否 |
| `02_Source` | 取得原始回應與技術性請求中繼資料，不做商業清理 | 否 |
| `03_Staging` | 展開、清理、型別化、錯誤與空值處理、加入稽核欄位 | 否 |
| `04_Model` | 只輸出供模型使用、粒度明確的乾淨資料表 | 是 |

依賴只能單向往下：Parameters／Functions → Source → Staging → Model。不得讓 Source 參照 Staging 或 Model。若沒有可證明的重複規則，`01_Functions` 可以保持空白，不為抽象而抽象。

Semantic Model 位於上述流程之外，負責關聯、DAX measures、格式、階層與 RLS。Power Query 的 `04_Model` 只定義資料形狀，不定義報表視覺或 DAX 商業語意。Report 是再下一層，僅負責 PBIR pages、visuals、slicers、互動與版面；本次不實作。

## API 與 Schema 契約

固定端點為 `https://www.104.com.tw/jobs/search/api/jobs`。目前基準參數為 `area=6001008007,6001008006`、`keyword=powerbi`、`mode=s`、`order=15`、`page=1`、`pagesize=20`。

已確認的頂層欄位只有：

```text
appearDate, applyCnt, coIndustry, coIndustryDesc, custName, custNo,
description, descSnippet, mrtDist, jobAddress, jobAddrNo, jobAddrNoDesc,
jobName, jobNameSnippet, jobNo, jobRo, jobType, lat, lon, link, major,
mrt, mrtDesc, optionEdu, period, remoteWorkType, s10, salaryHigh,
salaryLow, tags, s9, s5, d3, hrBehaviorPR, jobCat, labels,
languageRequirements, acceptRole, employeeCount, pcSkills, pddScore,
custLogo, jobSwitch, isSave, interactionRecord, isApplied, applyDate,
userApplyCount
```

`link`、`tags`、`pcSkills`、`jobCat`、`interactionRecord` 等欄位的內部結構，以及分頁 metadata、唯一鍵與跨頁重複規則，尚未形成穩定契約。現有模型中的 `link.job`、`tags.*` 等展開結果只能視為一次觀察，不得直接推定為永久 Schema。每次 Schema 擴充都必須保留真實回應證據並獨立驗證。

## 擷取、清理與安全規則

- 保留已證實有效的 `cloudscraper` 與 Windows Proxy 注入方式，替代方案必須先通過同參數測試。
- 不硬編碼 Cookie、Token、帳密或個人 Proxy 設定；HTTP 失敗必須明確回報，不以假資料補成功。
- Source 保留原始欄位與請求事實；欄位改名、型別轉換、展開與商業規則集中在 Staging。
- Staging 必須能處理合法空結果；是否去重、薪資解讀與日期語意須先有規則與證據。
- 只有 `04_Model` 查詢允許載入 Data Model。`.pbi/`、`cache.abf` 與原始職缺匯出不得納入版本控制。
- 未經明確要求不建立 Dashboard，也不自行 commit。
- 未來若交付可貼入 Power Query 的版本，該版本所需的每個 query 都必須提供完整程式碼，不以「沿用上一版」省略。

## 驗證與變更流程

依 `TASK-001` 至 `TASK-005`、再依 `TASK-006A` 至 `TASK-006D` 順序執行。這是六個主階段，其中 Report 階段拆成四個可獨立驗證的頁面文件。每個 TASK 都要先檢查既有查詢、只修改允許範圍、完成對應驗證，並記錄輸入、結果與未解問題後才可進入下一項。未通過的 TASK 不得由後續 TASK 隱性補救。

## 尚待決策

1. API 分頁節點、總筆數與 rate limit 的實際契約。
2. 複合欄位的穩定結構、缺欄與型別漂移策略。
3. 職缺資料粒度、候選唯一鍵與跨快照歷史保存方式。
4. `salaryLow`／`salaryHigh` 與薪資型態欄位的商業解讀。
5. Power BI Service refresh 是否需要 gateway，以及 Python／`cloudscraper` 的部署限制。
6. 是否停用 Auto Date/Time 並建立正式日期維度；需待 Model 粒度確認。
