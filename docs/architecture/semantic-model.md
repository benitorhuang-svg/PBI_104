# TASK-005 Semantic Model Validation

## Current Desktop acceptance (2026-10-10)

The optimized nine-table model completed a Golden L1 category refresh, was
saved, closed, and reopened. All nine partitions reported `Ready`; the model
contains 21 expressions and seven relationships. A DAX equivalence probe
returned zero mismatches for skill/category filters and a 100-job sample.
Migrations 044–046 expanded the active category bridge to 433,972
cross-platform relationship rows covering 195,332 jobs; only confirmed
crosswalk rows receive a canonical Golden L1 and unresolved yes123 rows remain
`待對照／BLOCKED`. Migration 039 reduced the skill bridge to its exact
225,299-row key set. Migration 040 reduced the active FactJob Import payload
to 14 source columns while retaining the canonical v22 view.
See the [current database status](../operations/local-database.md)
before future database writes or contract changes.

## Desktop acceptance snapshot (2026-10-06; historical)

The nine imported tables use PostgreSQL Gold views, including database-provided
`DimDate`. Power BI Desktop refreshed, saved, closed, and reopened the project
after the change. The reopened model had nine Ready partitions, 21 expressions,
and eight relationships. Current row counts, report-filter checks, and the
28.33-second local refresh measurement are recorded in
[TASK-011 and TASK-012 status](../operations/optimization-status.md).

`BridgeJobSkill[jobNo]` and `BridgeJobCategory[jobNo]` filter `FactJob` in both
directions so skill and category slicers can select current jobs. Their code
columns filter `DimSkill` and `DimJobCategory` respectively. `FactJob` also
relates to company, area, and date dimensions; `FactJobSnapshot` relates to
`DimDate`. There is no direct category-to-FactJob relationship because a job
can have multiple categories.

> Historical TASK-005 validation follows. Its counts and refresh results
> describe the 2026-08-13 model and are not current model evidence.

## Inventory (2026-10-06 snapshot)

The saved live model contains the pre-existing `查詢` table plus the eight
TASK-004 model tables, two existing local date tables, and the semantic-model
calculated `DimDate` table. The legacy `查詢` table and its two date
relationships were not removed. No RLS roles, perspectives, or calculation
groups were added.

The new loaded tables and refresh states are:

| Table | Grain/key | Rows | Partition |
|---|---|---:|---|
| `FactJob` | one row per `jobNo` | 55 | Ready |
| `FactJobSnapshot` | `snapshotDate × jobNo` | 55 | Ready |
| `DimCompany` | one row per `custNo` | 35 | Ready |
| `DimArea` | one row per observed `areaKey` | 40 | Ready |
| `DimSkill` | one row per `skillCode` | 89 | Ready |
| `DimJobCategory` | one row per `jobCatCode` | 69 | Ready |
| `BridgeJobSkill` | one row per `jobNo × skillCode` | 280 | Ready |
| `DimDate` | one row per date | 81 | Ready |

`DimDate` is a calculated table:

```DAX
SELECTCOLUMNS(
    CALENDAR(MIN(FactJob[appearDate]), MAX(FactJob[appearDate])),
    "Date", [Date],
    "Year", YEAR([Date]),
    "MonthNo", MONTH([Date]),
    "Month", FORMAT([Date], "yyyy-MM"),
    "QuarterNo", QUARTER([Date]),
    "Quarter", "Q" & FORMAT(QUARTER([Date]), "0"),
    "Day", DAY([Date])
)
```

For the recorded refresh its range is `2026-05-25` through `2026-08-13`.
It is a current-refresh date range, not historical persistence.

## Historical TASK-005 relationships (2026-08-13)

All new relationships are active, single-column, many-to-one, and use
one-direction filtering from the fact/bridge side to the dimension side:

```text
FactJob[custNo]            * ─── 1 DimCompany[custNo]
FactJob[areaKey]           * ─── 1 DimArea[areaKey]
BridgeJobSkill[jobNo]      * ─── 1 FactJob[jobNo]
BridgeJobSkill[skillCode]  * ─── 1 DimSkill[skillCode]
FactJobSnapshot[snapshotDate] * ─ 1 DimDate[Date]
FactJob[appearDate]        * ─── 1 DimDate[Date]
```

The candidate `DimJobCategory → FactJob` relationship was not created. The
source category is a multi-valued JSON array (`jobCatRaw`), and no scalar
fact-side category key is evidenced. A category bridge is the safe future
option; a guessed scalar key would create incorrect filtering.

## Measures created

Measures live on `FactJob` and include descriptions, display folders, and
format strings:

| Measure | Definition boundary | Folder |
|---|---|---|
| `Active Jobs` | distinct current `jobNo` | Jobs |
| `Company Count` | distinct current `custNo` | Companies |
| `Jobs with Salary` | both numeric bounds present; no sentinel reinterpretation | Salary |
| `Salary Coverage %` | raw-bound coverage / current jobs | Salary |
| `Job Applications` | sum of API `applyCnt`; business semantics unresolved | Applications |
| `Skill Job Count` | distinct bridge jobs under filter context | Skills |
| `Skill Share %` | selected skill jobs / all current jobs | Skills |

The candidate `Median Salary`, `Average Salary`, and `New Jobs` measures are
not created because salary units/sentinel meanings and a business time window
are not confirmed. Previous-period/growth measures are blocked by the lack of
external snapshot persistence. The `Skill` measures are descriptive
associations and do not claim causality.

## Validation

The following DAX query executed successfully against the live model:

```DAX
EVALUATE
ROW(
    "Active Jobs", [Active Jobs],
    "Company Count", [Company Count],
    "Jobs with Salary", [Jobs with Salary],
    "Salary Coverage %", [Salary Coverage %],
    "Job Applications", [Job Applications],
    "Skill Job Count", [Skill Job Count],
    "Skill Share %", [Skill Share %]
)
```

Recorded result: `55`, `35`, `55`, `1.0`, `564`, `48`, and `0.872727...`
respectively. The values are for the live refresh and may drift with the API.

Key reconciliation checks were also executed: FactJob and FactJobSnapshot
each contain 55 distinct jobs; company, area, skill, and category dimension
keys are unique; the bridge contains 280 distinct pairs. No model relationship
was created for an unverified key.

## Known limitations

- The legacy `查詢` table remains loaded and retains its prior wide schema.
- `DimArea` uses an observation-level key that Gold encodes from the exact
  UTF-8 bytes of the source composite. This preserves compatibility-character
  variants under Power BI's string collation; `jobAddrNo` alone had multiple
  full location variants.
- No historical append store exists, so trend/emerging-skill measures remain
  blocked.
- Salary values remain raw numeric projections; zero and `9999999` are not
  reclassified.
- No report pages, PBIR visuals, RLS, or navigation were changed in TASK-005.
