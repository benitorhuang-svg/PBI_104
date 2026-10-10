# Page 04 design brief — Job Explorer

## Page purpose

讓使用者依職稱、官方職類、地區、產業、技能與薪資篩選目前職缺，查看清單欄位與可追溯的原始 104 link。

## Canvas and grid

- 1280 × 720，Fit to page；原生頁籤導覽、上方 filter row、單一 matched-jobs KPI。
- 左側上方呈現座標地圖、下方呈現精簡職缺清單；右側為所選職缺內容與來源欄位。
- 移除與其他頁重複的公司數、薪資覆蓋率及排行榜摘要。

## Filters

- `FactJob[sourcePlatform]`（平台；只代表目前 Gold 實際載入的來源）、`FactJob[jobName]`（職稱）、`DimJobCategory[jobCatDescription]`（官方職類）、`DimArea[jobAddrNoDesc]`、`DimCompany[coIndustryDesc]`、`DimSkill[skillDescription]`。
- Salary 以 `salaryLow`/`salaryHigh` numeric filters；不建立 experience filter，因模型未提供可靠 experience group。

## KPI card

- `Active Jobs`（Matched Jobs）。公司數與薪資覆蓋率摘要分別保留在總覽與薪資頁，避免在探索器重複呈現。

## Main visuals

- Map：`DimArea[areaKey]` 定位類別、`DimArea[lat]` / `[lon]` 作座標、`FactJob[Active Jobs]` 作泡泡大小；點選地區篩選清單。
- Job list table：`FactJob[jobName]`、`DimCompany[custName]`、`DimArea[jobAddrNoDesc]`；選取職缺後 cross-filter 右側內容。
- Selected-job panel：職缺概要（公司、職稱、地區、技能）、薪資原值／刊登日／`jobLink`，以及獨立的寬幅 `descSnippet` 區塊。
- `FactJob` 目前只有 `descSnippet`，沒有 `description` 或 `pcSkillsRaw`；摘要不得標示成完整職務說明。完整原文由來源職缺連結開啟。

## External links and safety

`jobLink` 直接使用 API 提供值；不得自行拼接 URL。若欄位未被 Power BI 識別成 Web URL，仍顯示原值並在限制中說明，不製造連結。

## Style, interactions, accessibility

淺灰畫布與白底卡片；gold selected state、blue link accent。地圖選區後更新職缺清單；清單選取後更新右側內容與 matched-jobs KPI。完整原文連結保留可追溯性；不顯示未取得個資。

## Unsupported elements

Experience filter、employment type、logo、前期變化、完整 description 與 `pcSkillsRaw` 欄位均不建立，除非模型資料契約補齊；不得以 `descSnippet` 冒充全文。
