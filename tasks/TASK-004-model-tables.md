# TASK-004 — Power BI Model Tables

## 前置條件

TASK-002、TASK-003 已完成。

Model Tables 只允許引用 `03_Staging`。

## 目標

建立可供 Semantic Model 載入的 Star / Bridge Schema。

## 非目標

不得：重新做複雜 cleaning、建立 DAX、修改 PBIR、建立假的商業 key。

## 修改範圍

```text
powerquery/04_model/
docs/data-model.md
```

## 候選資料表

```text
FactJob
FactJobSnapshot
DimCompany
DimArea
DimSkill
DimJobCategory
DimDate
BridgeJobSkill
```

此清單是候選設計，不是預先核准的 Schema。只有 Grain、Keys 與使用需求都有真實證據的表才可建立；其餘標記 `BLOCKED`。

## FactJob

建議 grain：`1 jobNo = 1 筆目前職缺`。

必須驗證 `jobNo` uniqueness。

## FactJobSnapshot

建議 grain：`SnapshotDate × jobNo`。

用途：職缺趨勢、技能需求趨勢、公司招聘趨勢。

**關鍵限制：Power Query refresh 本身不會自動累積前一天歷史。**

若目前無外部 persistence（CSV / DB / Lakehouse / Dataflow 等），必須明確標記 snapshot history 尚未成立，不得假裝單次 PBIX refresh 能產生歷史。

## Dimensions / Bridge

- `DimCompany`：`custNo` natural key 候選，驗證 unique。
- `DimArea`：使用已標準化 area。
- `DimSkill`：normalized skill unique。
- `BridgeJobSkill` grain：`jobNo × SkillKey`，必須去重。
- `DimJobCategory`：只有 `jobCat` 可可靠正規化才建立。
- `DimDate`：覆蓋模型所需日期範圍。

## Enable Load

OFF：

```text
00_Parameters
01_Functions
02_Source
03_Staging
```

ON：

```text
04_Model
```

## docs/data-model.md

每張表記錄：

```text
Purpose
Grain
Natural Key
Model Key
Source Query
Expected Row Count
Uniqueness Rule
Proposed Relationships
Cardinality
Filter Direction
Known Limitations
```

並提供文字 ERD。

## Relationship 候選

```text
DimCompany 1 ─ * FactJob
DimArea 1 ─ * FactJob
DimJobCategory 1 ─ * FactJob
FactJob 1 ─ * BridgeJobSkill
DimSkill 1 ─ * BridgeJobSkill
DimDate 1 ─ * FactJobSnapshot
```

必須依真實 key 驗證，不得照抄即建立。

## 測試

- FactJob `jobNo` uniqueness
- DimCompany `custNo` uniqueness
- DimSkill unique
- BridgeJobSkill pair unique
- orphan key count
- null key count
- row count reconciliation

## 驗收標準

- [ ] Grain 明確。
- [ ] Keys 經資料驗證。
- [ ] Model query 無重複 cleaning。
- [ ] Load 設定正確。
- [ ] Snapshot persistence 限制已處理/記錄。
- [ ] `docs/data-model.md` 完成。

## 回報格式

```text
MODEL TABLES
GRAIN
KEYS
ROW COUNTS
UNIQUENESS TESTS
ORPHAN TESTS
PROPOSED RELATIONSHIPS
SNAPSHOT PERSISTENCE STATUS
BLOCKERS
NEXT TASK
```
