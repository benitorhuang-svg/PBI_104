# TASK-006B — Report Page 02：薪資市場分析

## 前置條件

- TASK-006A 完成並驗收。
- 參考圖：`report-design/page-02-salary.png`

## Report 原則

沿用 TASK-006A：現代 Power BI 樣式、非手繪、native visuals 優先、Power BI Yellow + Blue/Teal/Purple、每批 PBIR validate。

## Page Purpose

分析：Median Salary、P25、P75、Salary Range、Salary by Role、Salary by Experience、Skill Premium。

## 資料限制

若模型尚未可靠支援 P25/P75、Experience groups、Skill Premium：

- 不用假數值補齊。
- 該 visual 標記 `BLOCKED`。
- 其餘可驗證 visuals 可先建立。

## Skill Premium

若建立：

- 必須定義計算方式。
- 僅描述關聯/差異，不宣稱因果。
- 排除缺薪資資料。
- 記錄樣本限制。

## Layout

- Slicers：Job Role / Area / Experience / Date。
- KPI：Median / P25 / P75 / Salary Range。
- Main：Salary by Role / Salary by Experience。
- Bottom：Skill × Salary comparison / premium。

## 驗收標準

- [ ] 無虛構 salary data。
- [ ] Missing salary 處理一致。
- [ ] Layout 符合參考圖。
- [ ] PBIR validate。
- [ ] Screenshot review（若工具可用）。
- [ ] 尚未建立 Page 03。

## 回報格式

```text
FILES CHANGED
PAGE CREATED
SALARY DEFINITIONS
VISUALS
MEASURES USED
VALIDATION RESULT
BLOCKED VISUALS
SCREENSHOT REVIEW
NEXT TASK
```
