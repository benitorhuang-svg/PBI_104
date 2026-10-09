# Page 01 design brief — 職缺市場總覽

## Page purpose

讓使用者快速掌握目前 refresh 的職缺量、公司量、薪資資料覆蓋率，以及可追溯的日期、地區、產業與技能分布。

## Canvas and grid

- 1280 × 720，Fit to page。
- 左側導覽欄 176 px；主內容從 x=176 開始。
- 16 px 外距；上方 slicer row、KPI row、中段 trend、下方三個分析卡片。

## Header

- 中文主標「職缺市場總覽」，英文副標「Executive Overview」。
- 右上顯示資料來源/refresh 說明，不製造未取得的 timestamp。

## Slicers

- `FactJob[sourcePlatform]`：平台選擇；只代表目前 Gold 實際載入的來源。
- `DimJobCategory[jobCatDescription]`：依目前職缺的 104 官方職類篩選。
- `DimArea[jobAddrNoDesc]`：地區。
- `DimDate[Date]`：日期範圍。

## KPI cards

- `FactJob[Active Jobs]`：目前 refresh 中的 distinct jobNo。
- `FactJob[Company Count]`：目前 refresh 中的 distinct custNo。
- `FactJob[Jobs with Salary]`：具備兩個 numeric salary bounds 的 rows。
- `FactJob[Salary Coverage %]`：raw-bound coverage；不宣稱薪資已揭露或單位已確認。

## Visuals

- Jobs trend：`DimDate[Date]` × `Active Jobs`；目前只有一個 snapshot，視覺上保留 trend 位置但標題必須說明為 current refresh/date distribution。
- Top areas：`DimArea[jobAddrNoDesc]` × distinct job count。
- Top industries：`DimCompany[coIndustryDesc]` × `Active Jobs`。
- Top skills：`DimSkill[skillDescription]` × `Skill Job Count`。

## Visual hierarchy

Header → slicers → KPI cards → date/area/industry/skill visuals。分析卡片以白底、細邊框、低陰影區隔。

## Typography, color, spacing

- Segoe UI / system sans-serif；標題 24–28 px，卡片數字 28–36 px，圖表標籤 10–12 px。
- Power BI yellow/gold `#F2B705` 為主 accent；blue `#2F80ED`、teal `#2AA7A1`、purple `#7B61D1` 為輔；背景 `#F7F8FA`、卡片白色。
- 8 px 基準間距；卡片圓角視覺由 native container/陰影表達，不使用手繪元素。

## Borders and icons

使用 native visual container border/drop shadow；不引入未核准外部 logo。圖示若無穩定來源則省略。

## Required measures

僅使用既有七個 measures；本頁使用前四個與 `Skill Job Count`。

## Interactions and accessibility

- slicers 應篩選所有頁面視覺；圖表點選可 cross-filter 其他視覺。
- 視覺標題要包含資料語意；避免只用顏色傳遞狀態，維持足夠對比與鍵盤可達性。

## Unsupported elements

- 前期比較箭頭、真實 active-status、產業總市場量、長期趨勢均沒有可靠 snapshot/基準，不建立假數值。
- 目前 single snapshot 不宣稱時間趨勢；若圖表只呈現單點，標題需明示限制。
