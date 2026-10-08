# TASK-004 Model Table Contract

## Current database-backed contract (2026-10-06)

The TASK-004 profile below is historical. The active model now imports all
nine tables from PostgreSQL Gold views. `FactJob` has one latest complete
occupational-category observation per `jobNo`; it has no keyword or area
predicate. `BridgeJobSkill` and `BridgeJobCategory` come from the selected
observation's Silver rows. `DimCompany`, `DimArea`, `DimSkill`,
`DimJobCategory`, and `DimDate` are built in Gold to match those keys.

`FactJobSnapshot` remains the complete-series history at
`querySeriesKey × snapshotDate × jobNo`, including retained legacy keyword
series. Current category facts are based on batches imported so far, not a
claim of all-Taiwan coverage. The existing complete category batches were
captured with the earlier two-area filter; nationwide category captures will
expand the same Gold views when they pass ETL validation. Power Query performs
no shaping or grain checks, and the DAX measures are unchanged.

See [current architecture](architecture.md) and
[database refresh status](optimization-status.md) for Gold view names and
Desktop acceptance status.

> Historical TASK-004 snapshot: row counts below describe the 2026-08-13
> profile. TASK-007 supersedes its current load inventory and persistence
> status; see [optimization status](optimization-status.md) for the verified
> 2026-10-05 Desktop state and current snapshot counts.

## Evidence boundary

The model-table design is based on the live 104 profile recorded on
2026-08-13 (Asia/Taipei): 55 rows across three confirmed API pages. The
profile found 55 unique `jobNo` values, 35 unique `custNo` values, two area
codes, 89 skill codes, 69 job-category codes, and 280 unique
`jobNo × skillCode` pairs. These counts are expected values for that refresh,
not a permanent API guarantee.

The model queries reference only `03_Staging`. They do not repeat API access or
the staging cleaning rules. Key failures are fail-closed: null keys,
duplicates, invalid snapshot dates, or conflicting dimension variants raise an
error instead of silently dropping or manufacturing rows.

## Tables

| Table | Purpose | Grain | Natural key | Model key | Source query | Expected rows |
|---|---|---|---|---|---|---:|
| `FactJob` | Current job listing for exploration and current KPIs | One current row per `jobNo` | `jobNo` | `jobNo` | `mdl_FactJob` ← `stg_Jobs` | 55 |
| `FactJobSnapshot` | The refresh's observed snapshot facts | `snapshotDate × jobNo` | `snapshotDate`, `jobNo` | composite natural key | `mdl_FactJobSnapshot` ← `stg_Jobs` | 55 |
| `DimCompany` | Observed company identity attributes | One row per `custNo` | `custNo` | `custNo` | `mdl_DimCompany` ← `stg_Companies` | 35 |
| `DimArea` | Observed area/address and coordinates | One row per observed location variant | `areaKey` (lowercase hex of the source key's UTF-8 bytes) | `areaKey` | `mdl_DimArea` ← `stg_Areas` | 2+ variants |
| `DimSkill` | Normalized observed skill codes/descriptions | One row per `skillCode` | `skillCode` | `skillCode` | `mdl_DimSkill` ← `stg_Skills` | 89 |
| `DimJobCategory` | Observed category codes | One row per `jobCatCode` | `jobCatCode` | `jobCatCode` | `mdl_DimJobCategory` ← `stg_JobCategories` | 69 |
| `BridgeJobSkill` | Job-to-skill bridge | One row per `jobNo × skillCode` | composite pair | composite natural key | `mdl_BridgeJobSkill` ← `stg_JobSkills` | 280 |
| `DimDate` | Contiguous dates covering observed appear/snapshot dates | One row per calendar date | `Date` | `Date` | Semantic-model calculated table from `FactJob[appearDate]` | 81 for the recorded profile |

No surrogate key is generated. The evidence supports the natural keys above;
creating opaque keys would hide rather than solve source-key quality issues.

## Column contracts

`FactJob` keeps the clean scalar fields required by exploration and preserves
raw nested and salary values (`*Raw`) for auditability. It also exposes
`jobLink` only when the observed `linkRaw` JSON record contains the API `job`
field. `salaryLow` and `salaryHigh` remain numeric projections while the raw
values are retained. Zero and `9999999` are not converted to null because
their business meaning and units remain **BLOCKED**.

`FactJobSnapshot` contains current snapshot facts and typed `snapshotDate` and
`snapshotDateTime`. It is intentionally not a history table. A Power Query
refresh does not accumulate prior days, so trend history and period-over-period
measures remain **BLOCKED** until an external persistence mechanism exists.

`DimJobCategory.jobCatDescription` is retained as the explicit value
`BLOCKED`; the API code-to-label mapping was not evidenced. `DimArea` carries
observed address, effective coordinates, and `jobLocationScope`. The scope is
`國內` when coordinates fall within the Taiwan/Penghu, Kinmen, Matsu, Dongsha,
or Taiping coordinate envelopes; it is `國外(台灣地區之外)` for other valid
coordinates and `未判定` when coordinates are missing. These coordinate
envelopes are a practical location rule, not exact administrative boundary
polygons. Missing locations are not inferred.
`jobAddrNo` is retained as an API code, but it is not used as the sole
dimension key because refresh validation observed multiple full location
variants for a code. Silver retains the original composite `area_key`. Gold
encodes its exact UTF-8 bytes as lowercase hexadecimal in both `FactJob` and
`DimArea`, so Power BI's string collation preserves compatibility-character
variants as distinct keys. The displayed address fields retain the original
text; the key encoding does not merge or select location variants.

## Validation rules and observed results

| Check | Rule | Recorded result |
|---|---|---:|
| `FactJob` key | `jobNo` non-null and unique | null 0, duplicate 0 |
| `FactJobSnapshot` grain | `snapshotDate × jobNo` non-null and unique | null 0, duplicate 0 |
| `DimCompany` key | `custNo` non-null and unique | 35 rows, duplicate 0 |
| `DimArea` identity | One observed row per byte-preserving encoded `areaKey` | variant-preserving; no collapse |
| `DimSkill` key | `skillCode` non-null and unique | 89 rows, duplicate 0 |
| `DimJobCategory` key | `jobCatCode` non-null and unique | 69 rows, duplicate 0 |
| `BridgeJobSkill` grain | `jobNo × skillCode` non-null and unique | 280 rows, duplicate 0 |
| Row reconciliation | Fact and snapshot rows match the source profile | 55 = 55 |
| Skill orphan keys | Every bridge skill exists in `DimSkill` | 0 |
| Skill job orphan keys | Every bridge job exists in `FactJob` | 0 |
| Company orphan keys | Every fact company exists in `DimCompany` | 0 |
| Area orphan keys | Every fact area exists in `DimArea` | 0 |
| Category orphan keys | Every observed category exists in `DimJobCategory` | 0 |

The model query expressions repeat these checks at refresh time so a future
schema or data-quality drift fails visibly.

## Proposed relationships for TASK-005

The following single-column, single-direction relationships are supported by
the recorded natural-key checks and are proposed for the next task:

```text
DimCompany[custNo]       1 ─── * FactJob[custNo]
DimArea[areaKey]         1 ─── * FactJob[areaKey]
DimJobCategory[jobCatCode] 1 ─ * FactJob[category key, pending]
FactJob[jobNo]            1 ─── * BridgeJobSkill[jobNo]
DimSkill[skillCode]      1 ─── * BridgeJobSkill[skillCode]
DimDate[Date]             1 ─── * FactJobSnapshot[snapshotDate]
```

The `DimJobCategory → FactJob` relationship is **BLOCKED** until a scalar
fact-side category key is exposed. `FactJob` currently preserves the nested
`jobCatRaw` JSON rather than pretending that a multi-valued category list is a
single foreign key. A later model revision may use a category bridge if that
need is confirmed. No relationship is created in TASK-004.

## Snapshot persistence status

`FactJobSnapshot` is a current-refresh table only. `DimDate` is a
semantic-model calculated table over the current `FactJob[appearDate]` range,
not a historical persistence mechanism. The project has no CSV,
database, lakehouse, dataflow, or other external append store. Therefore the
following remain explicitly unavailable:

- historical daily snapshots;
- reliable jobs/skills/company trends;
- previous-period and growth measures;
- emerging-skill measures.

The current table is still useful for a refresh timestamp, date coverage, and
future persistence hand-off, but it must not be described as historical data.

## Enable Load boundary

`00_Parameters`, `01_Functions`, `02_Source`, and `03_Staging` remain Disable
Load. Only the eight `04_Model` queries listed above are enabled for model
load. The pre-existing loaded `查詢` table is left untouched for this task and
is not part of the new star-schema contract.

## Query/table naming boundary

Power BI Desktop's Mashup document treats a named expression and a loaded
semantic table with the same identifier as duplicate members when authored
through the current Modeling MCP. Therefore the persisted Model queries use
the explicit `mdl_` prefix while the loaded semantic tables retain the public
star-schema names above. This is a naming boundary only; each `mdl_` query is
the sole M partition source for its corresponding table.
