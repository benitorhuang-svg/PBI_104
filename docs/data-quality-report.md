# TASK-003 Data Quality Report

## Evidence boundary

This report separates the checked page-1 fixture from the live 55-row profile. It records observed data, not an API contract for future keywords, areas, or response versions.

### Page-1 fixture

- Source: `samples/raw/api-response-page-1.sample.json`; SHA-256: `F0BE85529D50F254506882C6675B49B13CB8AB9782E540EC5EB33E822D6C19FC`.
- 20 rows; `jobNo` duplicate count 0.
- `custNo`: 15 distinct values, with 5 duplicate rows; company consistency conflicts 0.
- `pcSkills`: 107 pairs, 47 codes, duplicate pairs 0.
- `jobCat`: 52 pairs, 28 codes, duplicate pairs 0.

### Live profile

Profile timestamp: `2026-08-13T16:02:51+08:00` (Asia/Taipei). Pages returned 20, 20, and 15 rows; `total=55`. All 48 observed job keys were present on all 55 rows.

## Row count and keys

- `jobNo`: string; null 0; duplicate 0.
- `custNo`: string; 35 distinct companies; 10 repeated `custNo` values; conflicting `custName`/industry combinations 0.
- The source pagination was complete for the observed run: 55 rows returned and 55 reported.

## Null rates and target fields

In the live 55-row profile, `applyDate`, `isApplied`, `isSave`, and `userApplyCount` were null on all 55 rows. Every other TASK-003 target field below had null count 0 in this run. This is an observation, not a future non-null guarantee.

## appearDate

All 55 values were strings matching eight-digit `yyyyMMdd`; there were 12 distinct values, ranging from `20260525` through `20260813`. Staging parses this confirmed pattern to a nullable date while retaining `appearDateRaw`. Other date meanings remain unresolved.

## Salary

`salaryLow` and `salaryHigh` were integer-valued. There were 20 distinct low/high pairs. `(0,0)` occurred 32 times; zero low/high occurred 32 times; `low > high` occurred 0 times. The value `9999999` occurred. Salary units, code meaning, and whether zero or `9999999` represent “not disclosed” are **BLOCKED**. Staging retains raw salary fields and does not convert these sentinel-like values to null.

## pcSkills

`pcSkills` was an array on all 55 rows. It produced 280 rows and 280 distinct `jobNo × skillCode` pairs, with duplicate pair count 0; there were 89 distinct codes, 0 description conflicts, and 7 jobs with empty `pcSkills` arrays. The confirmed child shape is `{code: string, description: string}`. `stg_JobSkills` parses the JSON text safely, validates duplicate pairs fail-closed, and emits the candidate grain; `stg_Skills` is a staging projection only. No `DimSkill` is created here.

## jobCat

`jobCat` was an integer array on all 55 rows. It produced 142 rows and 142 distinct `jobNo × jobCatCode` pairs, with duplicate pair count 0; there were 69 distinct codes. No reliable code-to-description mapping was observed, so staging preserves the integer code, sets `jobCatDescription` to the explicit status `BLOCKED`, and validates duplicate pairs fail-closed.

## tags

`tags` was an object on 51 rows and an array on 4 rows. Observed `param` values were string 526, integer 12, and null 11. Because the shape is heterogeneous and key semantics are unconfirmed, tags remain profile-only and are not split into a formal staging/model table.

## Companies

`custNo` was used only as a staging natural-key candidate. The live profile had 35 values, 10 repeated values, and 0 conflicts across `custName`, `coIndustry`, and `coIndustryDesc`. `stg_Companies` groups by `custNo` and raises a validation error if a future source snapshot contains conflicting observed identity values. Industry business meaning remains unresolved.

## Areas

There were 2 observed `jobAddrNo` codes, 0 description conflicts, and 0 null coordinates in the live profile. `stg_Areas` carries observed code, description, address, latitude, and longitude only; it does not infer or fill coordinates.

## Other observed structures

- `labels`: array; observed length range 1–30.
- `languageRequirements`: array; observed length range 0–1, with 28 empty arrays.
- `remoteWorkType`: integer values 0:48, 2:6, 1:1. Business meaning is unresolved.

## Staging rules and unresolved fields

- Text values are null-safe, cleaned, and trimmed through `fxNormalizeText`.
- Integer-coded fields (`coIndustry`, `jobAddrNo`, `applyCnt`, `remoteWorkType`, `sourcePage`, `sourcePageSize`, and `jobCatCode`) use safe `Int64.From`; latitude/longitude and derived salary values remain numeric, with raw salary retained.
- Unknown meanings for salary sentinels/units, job-category names, tags, remote-work codes, and other coded API fields are not guessed.
- Nested JSON is parsed only where its observed shape is sufficiently stable (`pcSkills`, `jobCat`); tags are intentionally not parsed into a model.

## Integration and validation boundary

The `00_Parameters` through `03_Staging` expressions are persisted in the
PBIP under five query groups (the `04_Model` group is added by TASK-004). The
source, staging, and function expressions remain Disable Load; only the model
tables are loaded. Power BI Desktop refreshes were performed after import and
after a close/reopen cycle. The legacy `查詢` table, relationships, measures,
and PBIR were not changed by TASK-003. No commit was created.
