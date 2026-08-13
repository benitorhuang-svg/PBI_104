# TASK-006C — Report Page 03：技能需求分析

## 前置條件

- TASK-006B 完成。
- `DimSkill + BridgeJobSkill` 可用，否則技能 visual 必須 BLOCKED。
- 參考圖：`report-design/page-03-skills.png`

## Report 原則

沿用 TASK-006A。

## Page Purpose

分析：Top Skills、Skill Trend、Skill Combination、Emerging Skills、Insight。

## 資料原則

- 技能只使用可靠正規化資料。
- 禁止 LLM 猜測後直接當 Ground Truth。
- 沒有 snapshot history 不得建立假的 Skill Trend / Emerging Skills。

## Layout

- Slicers：Keyword / Industry / Area / Date。
- Upper：Top Skills / Skill Trend。
- Lower：Skill Combination / Emerging Skills / Insight。

## Skill Combination

必須確認：

- BridgeJobSkill grain 正確。
- 同一 job-skill 不重複。
- 技能組合不重複計數。

## Emerging Skills

只有歷史 snapshot 足夠才建立；否則：

```text
BLOCKED: insufficient historical snapshots
```

## Insight

只可根據可驗證 measures / trends 生成，不得寫資料未支持的結論。

## 驗收標準

- [ ] Skills 可追溯。
- [ ] Skill count 不重複。
- [ ] Trend 只在 snapshot 可用時建立。
- [ ] PBIR validate。
- [ ] Screenshot review（若工具可用）。
- [ ] 尚未建立 Page 04。

## 回報格式

```text
FILES CHANGED
PAGE CREATED
SKILL DATA SOURCE
VISUALS
MEASURES USED
TREND AVAILABILITY
VALIDATION RESULT
SCREENSHOT REVIEW
KNOWN LIMITATIONS
NEXT TASK
```
