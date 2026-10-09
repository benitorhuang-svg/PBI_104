# Page 04 design brief — Job Explorer

## Page purpose

讓使用者依職稱、官方職類、地區、產業、技能與薪資篩選目前職缺，查看清單欄位與可追溯的原始 104 link。

## Canvas and grid

- 1280 × 720，Fit to page；原生頁籤導覽、上方 filter row、單一 matched-jobs KPI row。
- 中段左 46% job list、右 52% selected-row/trace panel；移除與其他頁重複的排行榜與公司/覆蓋率摘要。

## Filters

- `FactJob[sourcePlatform]`（平台；只代表目前 Gold 實際載入的來源）、`FactJob[jobName]`（職稱）、`DimJobCategory[jobCatDescription]`（官方職類）、`DimArea[jobAddrNoDesc]`、`DimCompany[coIndustryDesc]`、`DimSkill[skillDescription]`。
- Salary 以 `salaryLow`/`salaryHigh` numeric filters；不建立 experience filter，因模型未提供可靠 experience group。

## KPI card

- `Active Jobs`（Matched Jobs）。公司數與薪資覆蓋率摘要分別保留在總覽與薪資頁，避免在探索器重複呈現。

## Main visuals

- Job list table：`DimCompany[custName]`、`FactJob[jobName]`、`DimArea[jobAddrNoDesc]`、`FactJob[salaryLow]`、`FactJob[salaryHigh]`、`FactJob[appearDate]`、`FactJob[jobLink]`。
- Preview/trace table：同一組 selected-job fields 加上 `description`、`descSnippet`、`pcSkillsRaw`；使用者可透過 table selection cross-filter。

## External links and safety

`jobLink` 直接使用 API 提供值；不得自行拼接 URL。若欄位未被 Power BI 識別成 Web URL，仍顯示原值並在限制中說明，不製造連結。

## Style, interactions, accessibility

白底卡片、gold selected state、blue link accent、teal area chart；table selection 要 cross-filter preview/KPI。長描述只截斷顯示，保留原始欄位可追溯性；不顯示未取得個資。

## Unsupported elements

Experience filter、employment type、logo、前期變化、假設性的 selected-row rich preview 均不建立，除非模型與證據補齊。
