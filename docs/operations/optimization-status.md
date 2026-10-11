# TASK-011 and TASK-012 status (2026-10-06)

> 歷史驗收紀錄，不是目前健康狀態。這裡的九表 Desktop 刷新與效能數字只對應 2026-10-06 的模型。2026-10-09 磁碟上的模型定義已有 10 張表，而 `jobwant_104` catalog 缺少 6 個模型 Gold views；新版模型尚無 Desktop 刷新驗收。現況請讀 [local database status](local-database.md) 與 [schema catalog](../schema/README.md)。

## Direct capture client optimization (2026-10-06)

Capture mode now skips the pandas job-table expansion and the full-response
JSON serialize/parse round trip, while retaining the response and the same
technical metadata for Bronze. The existing cloudscraper instance is reused
within a worker thread; the request, headers, and Windows system-proxy setup
remain sourced from the established client. Legacy Power Query calls still
produce their original DataFrame outputs.

This code change has not yet been measured end to end. At 21:42 Taipei time,
the pre-change active run had completed 118 of 619 categories and its Python
worker showed approximately 2.87 GiB working set; this is one live observation,
not a peak or a controlled baseline. Compare elapsed time and peak working set
on a later run with the same page/category workers, request delay, and query
scope after the current run is terminal. Do not infer an API speedup from the
local CPU/memory change; the shared request interval and source pagination
behavior remain the dominant external limits.

The counts and timings in this file are dated validation snapshots. For the
latest committed official-category batches, run
`python tools/report_category_coverage.py`; the active capture's local
`data/104/category-runs/` summary reports in-flight progress. The coverage
report is read-only and distinguishes all-area queries from filtered-area
queries.

## Current Page 04 runtime acceptance (2026-10-10)

Power BI Desktop was reopened from `PBI_JobWant.pbip`. After the background
refresh settled, all nine model partitions reported `Ready`; the model had 21
expressions and seven relationships. The Azure Map X/Y projections request
`Average` for longitude and latitude, matching the Desktop visual contract.
The v22 FactJob view returned 195,332 rows: 155,940 from 104 and 39,392 from
yes123. After migration 035, a read-only DAX scope check returned 104
`未判定` 54, `國內` 154,024, and `國外(台灣地區之外)` 1,862; yes123 returned
`未判定` 0, `國內` 39,317, and `國外(台灣地區之外)` 75. Migration 035 uses
only explicit source-provided county or overseas-region labels when coordinates
are absent; it does not create coordinates, and unrecognized values remain
`未判定`.

The map path was optimized at two boundaries:

- `gold.pbi_dim_area_v22` now selects one current job per `(platform,
  sourceAreaKey)` before address/geocode and county work. Migrations 031–040 are applied; the migration check reports versions 1–40, no
  pending versions, no missing migration files, and `READY`.
- `目前符合條件職缺數` uses `COUNTROWS` because the current FactJob contains
  195,332 rows and 195,332 distinct `jobNo` values. The map presence flag
  reuses that measure instead of repeating a `DISTINCTCOUNT` for every map
  group.

Read-only database checks show current v22 area representatives for both
platforms. 104 returns 73,631 domestic rows (73,058 with coordinates), 585
overseas rows (582 with coordinates), and 12 unresolved rows; yes123 returns
410 domestic rows (64 with coordinates), eight overseas rows, and no unresolved
rows. The platform-scope DAX probe returns yes123 `39,317` domestic jobs,
`75` overseas jobs, and `0` unresolved jobs. The map remains coordinate-gated;
the text classification changes the scope label only and does not add map
points.
Four interleaved warm DAX proxy runs (excluding the first cold run) had median
times of about `0.67s` with the old distinct-count expression and `0.61s` with
the row-count measure. This is a semantic-query proxy, not a measured mouse
click latency or a Service benchmark.

The first post-migration Desktop helper call timed out while saving even though
the background queries continued; after the active database queries drained,
the model inventory showed all nine partitions `Ready`. A later Desktop UI
refresh completed the visual queries without trace errors. Selecting `國內`
changed the KPI to 193,341 and rendered the map; selecting `yes123` with
`國內` kept both slicers active, changed the KPI to 39,317, and rendered the
Taiwan point set. This acceptance does not claim nationwide data coverage.
The observed v22 area query runtime was about 8.8 seconds; it is a database
view observation, not a repeatable end-to-end Desktop refresh benchmark.

Migration 038 applies a key-only payload to the active category bridge. The
legacy and new bridge key sets are exactly equal: 394,580 rows, zero old-only
rows, and zero new-only rows. The redundant `jobCatDescription` string remains
available in `dim_職類`; the hidden bridge now imports only `jobNo` and
`jobCatCode`. Its table refresh measured 23.57s and 34.18s in two consecutive
runs after the change, compared with 38.74s immediately before it and 56.26s
in the earlier table-level baseline.

The full-model Desktop refresh then measured 42.17s and 39.34s in two runs,
versus the prior 64.94s and 67.36s observations. This is now a repeatable
directional improvement, although Desktop timing still varies with cache and
model state. Migration 037 still supplies the isolated `dim_技能` gain from
19.72s to 3.06s. The category DAX contract, bridge intersection, row counts,
map gates, and platform scope counts remain unchanged.

Migration 039 applies the same relationship-key reduction to the active skill
bridge. The legacy and key-only bridge sets are exactly equal at 225,299 rows
and 59,988 jobs; `old_only` and `new_only` are both zero. All 225,299 legacy
bridge descriptions match `silver.skill_dimension`, so `職缺技能清單` now
resolves names from `dim_技能` with `TREATAS` and the bridge imports only
`jobNo` and `skillCode`. Two full refreshes after migration 039 measured
42.02s and 43.00s; this is a payload reduction without an isolated full-refresh
gain beyond normal Desktop variation.

Migration 040 publishes `gold.pbi_fact_jobs_report_v22`, a model-specific
projection of the unchanged canonical v22 FactJob view. It removes seven
unused legacy/lineage columns from the active Import path while retaining the
report fields, company/area/date relationships, and all source data in the
canonical view and Silver. The projection has 195,332 rows and its retained
payload has zero old-only/new-only differences. The active FactJob table now
has 14 source columns (15 Desktop columns including the automatic RowNumber)
instead of 21 source columns. FactJob table refreshes measured 20.21s and
16.70s; three subsequent full refreshes measured 42.33s, 56.26s, and 37.16s.
Because the range is still cache/connection sensitive, record this as a
validated model-payload reduction, not a certified end-to-end speedup.

All nine model tables now read PostgreSQL Gold views. Power Query handles
connection/navigation only; acquisition, ETL, dimensions, bridges,
deduplication, and the date calendar stay in Python/PostgreSQL. `DimDate` is
database supplied. `FactJob` selects the latest observed occupational-category
row per `jobNo` across all area values currently present in the database.

TASK-012 replaces report slicers that used the now-empty
`FactJob.sourceKeyword`: category slicers use `DimJobCategory.jobCatDescription`
and job-title slicers use `FactJob.jobName`. The category and skill bridge
relationships use bidirectional filtering to pass selections to `FactJob`.
Visual IDs, positions, and page layouts were preserved.

## Desktop refresh and acceptance (2026-10-06)

- Power BI Desktop refreshed all nine model tables in 28.33 seconds, saved the
  PBIP, closed it, and reopened it. The reopened model showed nine tables,
  nine Ready partitions, 21 expressions, and eight relationships. The earlier
  `Stored pages/rows do not match the completed manifest` error did not recur.
- Refreshed row counts: `FactJob` 3,448; `FactJobSnapshot` 3,860;
  `DimCompany` 1,567; `DimArea` 2,008; `BridgeJobSkill` 3,241;
  `DimSkill` 143; `BridgeJobCategory` 9,017; `DimJobCategory` 398;
  `DimDate` 218. `FactJob.jobNo` is unique and its `sourceKeyword` values are
  empty.
- Live DAX checks returned 216 jobs for category `經營管理主管`, 730 for skill
  `Excel`, and 81 for their intersection. This confirms the category/skill
  bridge selections filter current jobs.
- `python tools/sync_queries.py`: 21 queries, no mismatches, query order
  unchanged. `python tools/validate_project.py`: PASS; 58 JSON files, 57 PBIR
  schemas, 73 report field references, and Desktop TMDL parser PASS.
- The measured 28.33 seconds is a local Desktop model refresh, not a Service
  refresh benchmark. A PostgreSQL `EXPLAIN ANALYZE` FactJob count took 31.7 ms;
  that SQL count-plan timing is a separate measurement.

No repeatable full-refresh speedup has been established. A new five-run
benchmark requires a terminal category-capture status and unchanged row counts
for all nine Gold views across every run. Record each run's timestamp,
refresh method, nine view counts, duration, and error status before comparing
medians or ranges.

## Data coverage and remaining limits

The database still contains captures from only two areas
(`6001008007`, `6001008006`), so it is not a nationwide job inventory. No
large-scale recapture was started. An earlier inventory estimated about
42,466 page requests across occupation codes, with many categories hitting the
API's 150-page ceiling. Historical keyword batches remain available in
`FactJobSnapshot` with source metadata. No claim of nationwide completeness or
of a faster full refresh is made.

The former active `.pbi/unappliedChanges.json` and stale cache were backed up
outside the repository under
`C:\Users\benit\AppData\Local\PBI104_Task011_Recovery\20261006_112702` before
clearing the stale local Desktop state. The current PBIP was then refreshed,
saved, closed, and reopened successfully.

## TASK-011 and TASK-012 project verification (2026-10-06)

- PostgreSQL migration versions 1–9 are present. The nine `gold.pbi_*` views
  currently return:

  | Model table | Gold rows |
  | --- | ---: |
  | FactJob | 3,448 |
  | FactJobSnapshot | 3,860 |
  | DimCompany | 1,567 |
  | DimArea | 2,008 |
  | BridgeJobSkill | 3,241 |
  | DimSkill | 143 |
  | BridgeJobCategory | 9,017 |
  | DimJobCategory | 398 |
  | DimDate | 218 |

- SQL contract checks found zero duplicate FactJob keys, zero nonempty or
  `powerbi` `sourceKeyword` values in FactJob, and zero orphan relationships
  across FactJob, both bridges, their dimensions, and DimDate. The current 3,448
  FactJob rows still carry the old area pair `6001008007,6001008006`; the
  jobcat Gold selection has no area predicate, but nationwide category batches
  have not been captured yet.
- `python tools/sync_queries.py`: 21 queries, no M/TMDL mismatches, query order
  unchanged. `python tools/validate_project.py`: PASS; 58 JSON files, 57 PBIR
  schemas, 73 report field references, and Desktop TMDL parser PASS. The
  requested visualContainer schema 2.13 uses the validator's 2.12 compatibility
  fallback.
- A PostgreSQL `EXPLAIN ANALYZE` count of the FactJob view took 31.7 ms. This is
  a SQL count-plan measurement only; it does not measure Power BI row transfer,
  model processing, or full refresh time.
- Power BI Desktop refresh, save, close, and reopen acceptance is recorded
  above. The earlier manifest error did not recur in this workflow.

The remaining sections record the earlier TASK-007 refresh and validation
snapshot. Their row counts describe the pre-redesign model, not the current
category-based FactJob scope.

# TASK-007 optimization status

Updated 2026-10-05. The work was local to the existing PBIP checkout and was not committed or published. Its pre-work checkpoint was removed from the project workspace during the user-requested environment cleanup on 2026-10-09. Local captures and diagnostic artifacts remain outside the repository.

The local `data/104/current.json` pointer was not written during this work. Its final SHA-256 is `B4D8E2C69510B0DE48E84BA6EFC67117B7BD75E08ECB1F0539F11C89771C4E1F`.

## Implemented

- The query graph is organized as Parameters / Functions → Source → Staging → Model. Complete M expressions are exported under `powerquery/` and synchronized with TMDL by `tools/sync_queries.py`. Eight `04_Model` M queries load; the ninth semantic table is the DAX-calculated `DimDate`.
- Source refresh supports immutable local snapshot batches and an explicitly selected legacy live path. Batch/page contracts, checksums, pagination reconciliation, immutable history, and pointer advancement after successful validation are implemented. The known cloudscraper plus Windows system-proxy path is retained; secrets are not stored in the repository.
- Staging parses nested JSON, applies explicit types and quality handling, and shares area/key rules. Model queries enforce uniqueness and references, preserve query-series/date/job grain in `FactJobSnapshot`, and keep observed but unmapped job-category labels unresolved.
- The semantic model has skill and category bridges, date relationships, explicit measures, and measures that apply OR within a multi-select bridge while retaining intersections with other filters. Salary bounds keep their raw values and are not described as disclosed salary.
- Existing approved report pages were updated in place. The job explorer has aligned slicers, selection-aware KPIs, deterministic newest-first ordering, and job detail fields. No additional report page was introduced.
- Validation tooling checks TMDL/PBIR structure, report-field references, query synchronization, Python acquisition/storage behavior, and runtime DAX contracts. The Desktop helper's temporary-table probe was removed after its SDK path failed to complete cleanly; DAX evaluation is now read-only.

## Evidence from this checkout

- `python -m unittest discover -s tools/tests -v`: 11 tests passed.
- `python tools/sync_queries.py`: 42 queries, no M/TMDL mismatches, query order unchanged.
- `python tools/validate_project.py`: PASS; 58 JSON files, 57 PBIR schemas, 73 report field references, and Desktop TMDL parser PASS. The local validator uses visualContainer schema 2.12 as a compatibility fallback for the requested 2.13 schema.
- Power BI Desktop completed a full snapshot-mode refresh. The open model inventory contained nine tables, all nine partitions Ready, 42 expressions, and eight relationships. Snapshot rows total 323: python 249, powerbi 52, tableau 22. Each series currently has one snapshot date, 2026-10-04; this is a baseline, not a time series.
- After closing and reopening the PBIP, imported partitions initially showed `NoData`; a new snapshot refresh repopulated all nine tables, restored the same DAX results, and the project was saved again at 8:23 PM Asia/Taipei. The saved PBIP does not carry the in-memory imported rows into a fresh Desktop session; refresh after reopen is required for data-backed review.
- Runtime DAX returned 52 current jobs, 33 companies, 100% salary-bound coverage, skill selection 3/3, category selection 2/2, combined skill/category intersection 1/1, populated job skills, and zero orphan appear/snapshot dates. The DAX contract flags all passed. Salary coverage measures presence of bounds; sentinel values and business interpretation remain unresolved.
- Page04 single-row selection behavior was observed earlier in the same Desktop validation: the matched-jobs KPI filtered from 52 to 1 and the detail visual updated. The latest visible state after report edits showed all three KPIs and no visual error.

## Limits and next evidence

- The three query series have only one day each. Trend, emergence, and change-over-time claims require future complete daily batches; no live capture was run for this optimization.
- The legacy M edge-case probe is generated at the ignored local path `.optimization/probes/staging.pq`. Its earlier native Power Query execution did not complete, so malformed/edge fixture outcomes remain unverified; it is not a gate for the active database-reader queries. See `tools/probes/README.md`.
- Category-code descriptions, salary units/meaning (including the 9,999,999 upper bound), and unsupported experience/employment/logo details remain unresolved. Keep them labelled `BLOCKED` until verified against authoritative API evidence.
- This checkout does not prove Power BI Service refresh, gateway configuration, external scheduling, or deployment. Those require the target environment.

## Local recovery note

Power BI offered an auto-recovered `PBI_104 (已復原).pbix` dated 8:14 PM, older than the 8:23 PM saved PBIP. The recovery item was left unopened and retained for manual review; it was not used to overwrite the saved project.

## Repeatable checks

Run commands and their evidence boundaries from `tools/README.md`. For each future TASK, refresh in Desktop, validate only the changed layer and its Enable Load state, save, close, reopen, and record the observed result. Do not update the current pointer unless a complete new acquisition batch passes validation.


## TASK-013 PostgreSQL Gold view refresh optimization (2026-10-06)

The Gold SQL now carries selected snapshot fields out of the latest complete
category-job observation instead of joining silver.job_snapshots a second
time. The company dimension reuses those joined attributes, the area dimension
deduplicates keys before geocode joins, and date bounds use one aggregate pass.
The schema's existing area-key type change is guarded so the complete init
script can be rerun with dependent views present.

### Gold view plans

The table compares one full-view EXPLAIN (ANALYZE, BUFFERS) pass before and
after the rewrite. Every plan reported zero shared disk-read blocks. Times are
PostgreSQL execution times, not connector transfer or Desktop refresh times.

| Gold view | Rows | Shared hit blocks before | After | Change |
| --- | ---: | ---: | ---: | ---: |
| pbi_fact_jobs | 3,448 | 41,823 | 31,411 | -24.9% |
| pbi_fact_job_snapshots | 3,860 | 259 | 259 | 0.0% |
| pbi_dim_company | 1,567 | 39,917 | 19,041 | -52.3% |
| pbi_dim_area | 2,008 | 43,133 | 26,955 | -37.5% |
| pbi_bridge_job_skill | 3,241 | 40,616 | 30,204 | -25.6% |
| pbi_dim_skill | 143 | 46,578 | 36,166 | -22.3% |
| pbi_bridge_job_category | 9,017 | 66,728 | 56,316 | -15.6% |
| pbi_dim_job_category | 398 | 66,731 | 56,319 | -15.6% |
| pbi_dim_date | 218 | 29,477 | 19,065 | -35.3% |
| **Total** |  | **375,262** | **275,736** | **-26.5%** |

The serial sum of those nine single-run execution times was 439.6 ms before and
407.4 ms after (-7.3%). That timing sample is directional; shared hit blocks
show less repeated logical page access, while elapsed time is cache- and
scheduler-sensitive.

### Desktop refresh and model checks

The same XMLA Full refresh method measured 1,689 / 1,761 / 1,974 ms before the
SQL rewrite (median 1,761 ms), then 1,637 / 1,642 / 1,771 ms after it (median
1,642 ms). After reopening the final PBIP, runs were 10,339 / 3,399 / 3,778 ms
(median 3,778 ms). These ranges do not establish a repeatable full-model
refresh improvement. CreateNavigationProperties=false was slower and was
reverted. A native SQL connector trial stalled without issuing a database
query and was also reverted; the final M expression uses the default
PostgreSQL Gold schema/view navigator.

Final model inventory has nine Ready partitions, 21 expressions, and eight
relationships. DAX checks returned FactJob 3,448 (3,448 distinct job keys),
FactJobSnapshot 3,860, DimCompany 1,567, DimArea 2,008, BridgeJobSkill 3,241,
DimSkill 143, BridgeJobCategory 9,017, DimJobCategory 398, and DimDate 218.
The semantic probe's skill and category actual/expected counts matched (11 and
768), its intersection count matched (1), and both date orphan counts were
zero. EXCEPT ALL checks found no differences in FactJob, DimCompany, DimArea,
or DimDate before and after the SQL rewrite.

python tools/sync_queries.py, python tools/validate_project.py, and the Desktop
TMDL parser passed. Desktop was saved, closed, and reopened. No unit tests
were run, and no report visuals or DAX were changed.
