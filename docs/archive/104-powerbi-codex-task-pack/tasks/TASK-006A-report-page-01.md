# TASK-006A — Report Page 01：職缺市場總覽

## 前置條件

- TASK-005 完成。
- PBIP / PBIR 已有 Git baseline。
- 參考圖：`report-design/page-01-market-overview.png`

## 共通 Report 原則

- 現代 Power BI 商業 Dashboard。
- **不要手繪風格。**
- 圖片是視覺基準，不要求 pixel-perfect。
- 優先 Power BI native visuals。
- 配色：Power BI Yellow/Gold 主 accent；Blue、Teal、Purple 輔助；白 / 淺灰背景。
- KPI Cards 尺寸、間距、字級一致。
- Slicers 放上方。
- 不建立不存在的 measure。
- 每批 PBIR 修改後 validate。
- Desktop Bridge 可用時：Reload → Screenshot → Compare → Iterate。

## Page Purpose

一眼掌握：Active Jobs、Companies、New Jobs、Median Salary、Jobs Trend、Top Job Categories、Jobs by Region、Top Skills。

## Layout

- Header：Page title / branding / last refresh。
- Slicer row：Keyword / Area / Date。
- KPI row：Active Jobs / Companies / New Jobs / Median Salary。
- Main：Jobs Trend line chart。
- Bottom：Top Job Categories / Jobs by Region / Top Skills。

## 必須先做 Design Brief

先讀圖片，建立：`report-design/page-01-spec.md`。

至少包含：

```text
Page purpose
Canvas
Grid
Header
Slicers
KPI cards
Visuals
Visual hierarchy
Typography
Color roles
Spacing
Borders
Icons
Required measures
Interactions
Accessibility
Unsupported elements
```

Design Brief 完成後才修改 PBIR。

## 驗收標準

- [ ] Page 01 建立。
- [ ] 主要資訊架構符合參考圖。
- [ ] 無手繪風格。
- [ ] 配色符合 Power BI 視覺語言。
- [ ] PBIR validate。
- [ ] Screenshot review（若工具可用）。
- [ ] 尚未建立 Page 02。

## 回報格式

```text
FILES CHANGED
PAGE CREATED
VISUALS
MEASURES USED
VALIDATION RESULT
SCREENSHOT REVIEW
DIFFERENCES FROM REFERENCE
KNOWN LIMITATIONS
NEXT TASK
```
