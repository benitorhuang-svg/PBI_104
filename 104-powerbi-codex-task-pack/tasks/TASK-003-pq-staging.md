# TASK-003 — Power Query Staging / Data Clean

## 前置條件

TASK-002 已完成並驗收。

資料來源只允許 `02_Source`。

## 目標

建立乾淨、可分析、可重用的 Staging Queries 與必要清洗 Functions。

## 非目標

不得：建立正式 relationships、DAX、PBIR、Dashboard、LLM 技能抽取、猜測未知欄位語意。

## 修改範圍

```text
powerquery/01_functions/
powerquery/03_staging/
docs/data-quality-report.md
```

不得修改 `04_model` 與 `powerbi/`。

## 需要建立

```text
stg_Jobs.pq
stg_Companies.pq
stg_Skills.pq
stg_JobSkills.pq
stg_Areas.pq
```

必要時建立：

```text
fxCleanSalary.pq
fxUnixDate.pq
fxParseSkills.pq
fxCleanArea.pq
fxNormalizeText.pq
```

## Function 原則

只有「重複、規則化、需集中維護」邏輯抽成 fx。

適合：Salary normalization、Date conversion、JSON/List parsing、Text/Area normalization。

不需為每個 Rename / Trim / SelectColumns / ChangeType 建 fx。

## 先 Profile 再 Clean

必須分析：

- row count
- duplicate `jobNo`
- duplicate `custNo`
- null rate
- `salaryLow / salaryHigh`
- `appearDate`
- `pcSkills`
- `tags`
- `labels`
- `jobCat`
- `languageRequirements`
- `jobAddrNoDesc`
- `remoteWorkType`

## stg_Jobs

至少保留：

```text
jobNo, custNo, jobName, description, descSnippet,
jobAddress, jobAddrNo, jobAddrNoDesc, lat, lon,
salaryLow, salaryHigh, appearDate, applyCnt,
jobCat, pcSkills, tags, labels, link,
snapshotDate, snapshotDateTime, sourceKeyword, sourceArea
```

## Salary

原始 `salaryLow / salaryHigh` 必須保留。

只有真實資料證據足夠才新增：

```text
salaryMid
salaryAvailable
```

不得自動假設 0 = null。

## appearDate

先確認格式，再轉日期。

不可因 Int64 就猜 Unix seconds / milliseconds。

## Skills

先分析 `pcSkills / tags / jobCat / labels` 真實結構。

只有可可靠拆成 `jobNo → Skill` 才建立 `stg_Skills / stg_JobSkills`。

第一版禁止使用 LLM 從 description 猜技能。

## Companies / Areas

- `custNo` 作 company natural key 候選，驗證一對一一致性。
- Area 使用 `jobAddrNo / jobAddrNoDesc / jobAddress / lat / lon`，不得自行填不存在座標。

## docs/data-quality-report.md

至少包含：

```text
Row Count
Duplicate jobNo
Duplicate custNo
Null Rates
Salary Patterns
appearDate Pattern
pcSkills Structure
tags Structure
jobCat Structure
Area Patterns
Unknown / Unresolved Fields
```

## 測試

- Null safe
- Duplicate detection
- Nested skills parsing 或明確 BLOCKED
- Salary 原始值可回溯
- 日期轉換有 sample verification

## 驗收標準

- [ ] 先 profile 再 clean。
- [ ] Source 未混入 business cleaning。
- [ ] Cleaning 規則有資料證據。
- [ ] Unknown fields 未猜測。
- [ ] `docs/data-quality-report.md` 完成。

## 回報格式

```text
FILES CHANGED
DATA PROFILE
CLEANING RULES
FUNCTIONS CREATED
TEST RESULTS
ASSUMPTIONS
UNRESOLVED FIELDS
RISKS / BLOCKERS
NEXT TASK
```
