# TASK-005 — Power BI Semantic Model

## 前置條件

- TASK-004 完成。
- 建議 Power BI 已另存為 `.pbip`。
- 修改前已有 Git baseline commit。
- 若 Power BI Modeling MCP 已配置，優先使用 MCP inventory / authoring / validation。

## 目標

建立：

- Relationships
- Measures
- Formatting
- Display folders
- 必要 Hierarchies
- 基礎模型品質檢查

## 非目標

不得：建立 Report Pages、修改 Dashboard Layout、在 PBIR 偽造 measures、未驗證 key 就建 relationship。

## 執行順序

1. Inventory 現有 model。
2. 列 tables / columns / keys。
3. 驗證 TASK-004 relationships。
4. 先提出 proposed changes。
5. 再修改。
6. DAX validation。
7. Best-practice review。

## Relationship 候選

```text
DimCompany 1 → * FactJob
DimArea 1 → * FactJob
DimJobCategory 1 → * FactJob
FactJob 1 → * BridgeJobSkill
DimSkill 1 → * BridgeJobSkill
DimDate 1 → * FactJobSnapshot
```

預設避免 bidirectional relationship。

## 第一版候選 Measures

建立前必須確認商業定義、所需欄位及 Grain；清單不是預先核准的 DAX 規格。未確認者標記 `BLOCKED`。

核心：

```text
[Active Jobs]
[Company Count]
[New Jobs]
[Median Salary]
[Average Salary]
[Job Applications]
[Jobs with Salary]
[Salary Coverage %]
```

只有 Snapshot 歷史真正可用才建立：

```text
[Jobs Previous Period]
[Job Growth]
[Job Growth %]
```

只有 Skill bridge 可用才建立：

```text
[Skill Job Count]
[Skill Share %]
```

## Measure 標準

- 清楚名稱
- Description
- Format string
- Display folder
- DAX validation
- 不依賴不存在欄位

建議 folders：`Jobs / Companies / Salary / Applications / Trends / Skills`。

## DAX 原則

- Null safe
- Divide-by-zero safe
- Explicit measures 優先
- 不濫用 calculated columns
- Time intelligence 必須確認 DimDate relationship 與 snapshot grain

## 驗收標準

- [ ] Inventory 完成。
- [ ] Relationships 有資料證據。
- [ ] DAX 全部可 validate。
- [ ] Measures 有 formatting / descriptions。
- [ ] 無不必要 bidirectional relationships。
- [ ] Report 尚未修改。

## 回報格式

```text
MODEL INVENTORY
RELATIONSHIPS CREATED / CHANGED
MEASURES CREATED
DAX VALIDATION
BEST PRACTICE FINDINGS
KNOWN LIMITATIONS
BLOCKERS
NEXT TASK
```
