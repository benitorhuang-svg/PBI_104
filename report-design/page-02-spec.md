# Page 02 design brief — 薪資市場分析

## Page purpose

呈現目前 refresh 的 raw salary bounds 覆蓋情況，並按職缺分類與地區提供可驗證的薪資分布視角。

## Canvas and grid

- 1280 × 720，Fit to page；沿用左側導覽、16 px 外距與卡片式 grid。
- 上方四個 slicer；其下 KPI row；中段 salary-bound distribution；下方兩個 breakdown 與一個 limitation/detail card。

## Header and slicers

- 標題「薪資市場分析 / Salary Intelligence」。
- `FactJob[jobName]` 不作搜尋輸入；使用有直接資料關聯的 `FactJob[jobCatRaw]`（raw category）、`DimArea[jobAddrNoDesc]`、`FactJob[sourceKeyword]`、`DimDate[Date]`。`DimJobCategory` 目前沒有可驗證的 FactJob key，不拿來假裝篩選關聯。

## KPI cards

- `Salary Coverage %` 與 `Jobs with Salary` 可驗證，作為主要 KPI。
- Median、P25、P75、Salary Range 目前沒有已定義且單位確認的 measures；以明確 BLOCKED 說明取代假卡片。

## Visuals

- Salary bounds：`salaryLow`、`salaryHigh` 的 raw numeric aggregation，標題必須寫明 bounds/units unresolved。
- Salary by job category：job category × average raw lower/upper bound（僅描述資料，不宣稱市場中位數）。
- Salary by area：area × average raw lower/upper bound。
- Limitations/info card：說明缺少 percentile、experience group 與單位證據。

## Visual language

主 accent 使用 purple（salary coverage）與 gold（raw lower bound），blue/teal 作對照；白色卡片、細灰邊框、8 px spacing。

## Interactions and accessibility

Slicers 與圖表 cross-filter；所有圖表標題標明「raw」或「reported bounds」。不得用顏色暗示因果或薪資優勢。

## Unsupported elements

`Median Salary`、`P25`、`P75`、Experience breakdown、Skill Premium、薪資單位換算與前期變化均 BLOCKED，直到模型與證據補齊。
