# Page 03 design brief — 技能需求分析

## Page purpose

以 `DimSkill` 與唯一的 `BridgeJobSkill` 關聯，呈現目前 refresh 的技能需求量與 job coverage；清楚區分 association 與因果。

## Canvas and grid

- 1280 × 720，Fit to page；左側導覽與 Page 01 一致。
- 上方四個 slicer；KPI row；上半部 Top Skills/Skill Coverage；下半部可驗證表格與 limitation/insight card。

## Slicers

- `DimJobCategory[jobCatDescription]`、`DimCompany[coIndustryDesc]`、`DimArea[jobAddrNoDesc]`、`DimDate[Date]`。

## KPI cards

- `Skill Job Count` 在 skill filter context 下代表 distinct jobs。
- `Skill Share %` 代表目前 jobs 中與 selected skill 關聯的比例。
- 技能總數可由 `DimSkill[skillDescription]` 的 distinct aggregation 顯示；不另造 measure。

## Visuals

- Top Skills：skill description × `Skill Job Count`，Top N/排序由 visual 設定。
- Skill Coverage：skill description × `Skill Share %`。
- Skill/job trace table：`BridgeJobSkill[jobNo]`、`DimSkill[skillDescription]`，供追溯與去重檢查。
- Insight card：只寫目前驗證的 row/coverage facts。

## Unsupported elements

- Skill Combination 需要 pair-level measure，目前沒有可靠的 pair grain visual；標記 BLOCKED。
- Skill Trend / Emerging Skills 需要多個 snapshot，目前僅一個 snapshot；明確顯示 `BLOCKED: insufficient historical snapshots`。

## Style, interactions, accessibility

Gold 用於 demand bars，teal 用於 coverage，purple 僅作 secondary accent；slicers/cross-filter 保持一致，標題不隱藏資料限制。
