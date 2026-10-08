# TASK-006D — Report Page 04：Job Explorer

## 前置條件

- TASK-006C 完成。
- 參考圖：`report-design/page-04-job-explorer.png`

## Report 原則

沿用 TASK-006A。

## Page Purpose

讓使用者：搜尋職缺、Filter 地區/薪資/經驗/技能/分類、查看清單、查看選取職缺細節、跳轉原始 104 職缺 URL。

## Layout

### Top Filters

```text
Search
Area
Salary
Experience
Skill
Job Category
```

### KPI

```text
Matched Jobs
Companies
Avg Salary
```

### Main Left：Job List

```text
Company
Job
Area
Salary
Experience
Skills
```

### Main Right：Job Preview

```text
Company
Job title
Area
Employment type（若可靠）
Salary
Description
Requirements
Skills
Original Job link
```

### Bottom

- Top Companies
- Top Areas

## 資料 / 安全原則

- External URL 優先直接使用 API `link`。
- 不自行猜 URL 規則。
- Description 過長可合理截斷。
- 不顯示未取得個資。
- Logo 若無法穩定呈現，可改文字/通用 icon。

## Interactions

至少：

- Select Job → Preview 更新。
- Slicers → Job list filter。
- Job selection → KPI/supporting visual 合理互動。
- URL → 原始職缺。

## 最終 Report Review

四頁完成後檢查：

- Page naming
- Theme consistency
- Slicer consistency
- KPI formatting
- Cross-filter behavior
- Accessibility
- Broken visuals
- Missing measures
- PBIR validation

## 驗收標準

- [ ] Job list 可 filter。
- [ ] Preview 與 selection 連動。
- [ ] 原始 link 正確。
- [ ] 無假資料。
- [ ] PBIR validate。
- [ ] Screenshot review（若工具可用）。
- [ ] 四頁 style / navigation 一致。

## 回報格式

```text
FILES CHANGED
PAGE CREATED
VISUALS
MEASURES USED
INTERACTIONS
EXTERNAL LINKS
VALIDATION RESULT
SCREENSHOT REVIEW
FULL REPORT REVIEW
KNOWN LIMITATIONS
PROJECT STATUS
```
