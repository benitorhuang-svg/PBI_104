# TASK-003R Power Query Runtime Validation

This document is the point-in-time TASK-003R gate record. TASK-004 and
TASK-005 subsequently added the persisted `04_Model` queries, loaded tables,
relationships, and measures documented in `docs/data-model.md` and
`docs/semantic-model.md`.

## 1. Decision

**TASK-003R RESULT: PASS.**

On 2026-08-13 (Asia/Taipei), the complete `00_Parameters` through
`03_Staging` Power Query pipeline was persisted in the PBIP project, authorized
through the Power BI Desktop script-execution dialog, refreshed in two
independent Desktop sessions, saved, closed, reopened, and re-inventoried.

TASK-004 was not started by this validation task.

## 2. Runtime environment

- OS/runtime: Windows
- Power BI Desktop: `2.156.951.0`
- Power BI Modeling MCP: `0.5.0.0`
- Project: `PBI_104`
- Python dependency check: `pandas` and `cloudscraper` imported successfully
- Python acquisition path: `Python.Execute + pandas + cloudscraper + Windows system proxy`
- Authorization: approved through Desktop's visible **指令碼執行 / 執行**
  dialog; no skip-confirmation option was used
- Legacy loaded table `查詢`: untouched

## 3. Persisted Power Query inventory

The final saved and reopened project contains 20 named expressions in exactly
four query groups:

| Group | Count | Expressions |
|---|---:|---|
| `00_Parameters` | 8 | `pArea`, `pBaseUrl`, `pJobSource`, `pKeyword`, `pMode`, `pOrder`, `pPage`, `pPageSize` |
| `01_Functions` | 3 | `fx104GetPage`, `fx104GetAllPages`, `fxNormalizeText` |
| `02_Source` | 3 | `src_104Result`, `src_104Jobs`, `src_104Metadata` |
| `03_Staging` | 6 | `stg_Jobs`, `stg_JobSkills`, `stg_Skills`, `stg_JobCategories`, `stg_Companies`, `stg_Areas` |

Power Query Editor showed `查詢 [21]`: the 20 expressions above plus the
pre-existing loaded `查詢` table. The four groups and all 20 expressions were
also re-read after a full close/reopen. A live expression-to-file comparison
reported 20 retrieved expressions and zero mismatches against the corresponding
`powerquery/**/*.pq` files.

All `00`–`03` expressions remain non-loaded named expressions. No Model table
was created from them. Temporary validation tables were deleted before the
final save.

## 4. Function input contract

Per the confirmed requirement, `fx104GetPage` now requires only `baseUrl`.
The following inputs are optional and omitted from the HTTP query string when
null or blank:

- `keyword`
- `area`
- `jobsource`
- `mode`
- `order`
- `page`
- `pagesize`

When supplied, `page` and `pagesize` must be positive integers. The normal
`src_104Result` path still supplies all eight project parameters explicitly.

A Power Query type probe returned:

```text
RequiredParameterCount = 1
ParameterNames = baseUrl,keyword,area,jobsource,mode,order,page,pagesize
```

A Power BI runtime call with only `pBaseUrl` returned HTTP 200, 32 rows on
page 1, and this exact request URL with no query string:

```text
https://www.104.com.tw/jobs/search/api/jobs
```

The live unfiltered total changed during the session, as expected for a live
job API; that probe verifies optional-parameter behavior, not a stable business
count.

## 5. Refresh Test 1

**Result: PASS.**

The first complete refresh ran after the visible Desktop authorization. The
full project-parameter route returned:

| Metric | Result |
|---|---:|
| HTTP statuses | `200` |
| Requested pages | `1,2,3` |
| Live API total | 55 |
| `src_104Jobs` rows | 55 |
| `src_104Metadata` rows | 3 |
| Raw response rows | 3 |
| `stg_Jobs` rows | 55 |
| `stg_JobSkills` rows | 280 |
| `stg_Skills` rows | 89 |
| `stg_JobCategories` rows | 142 |
| `stg_Companies` rows | 35 |
| `stg_Areas` rows | 40 |

A direct metadata probe confirmed page row counts `20 + 20 + 15 = 55`, with
`currentPage = 1,2,3`, `lastPage = 3`, and `total = 55` on every page.

A separate salary trace probe joined all 55 source jobs to all 55 staged jobs
by `jobNo` and returned zero `salaryLow` mismatches and zero
`salaryHigh` mismatches.

## 6. Refresh Test 2

**Result: PASS.**

The second complete refresh ran in a newly opened Power BI Desktop / Analysis
Services session. It did not require cookies, tokens, secrets, or another
skip-confirmation mechanism.

It independently returned the same validated snapshot counts:

| Metric | Result |
|---|---:|
| HTTP statuses | `200` |
| Requested pages | `1,2,3` |
| Live API total / source rows / returned rows | `55 / 55 / 55` |
| Metadata / raw-response rows | `3 / 3` |
| Jobs / job-skills / skills | `55 / 280 / 89` |
| Job categories / companies / areas | `142 / 35 / 40` |

## 7. Key, type, date, and salary checks

Both the complete pipeline and targeted probes established:

| Check | Result |
|---|---:|
| Null/blank `jobNo` | 0 |
| Duplicate `jobNo` | 0 |
| Duplicate `jobNo × skillCode` | 0 |
| Duplicate `skillCode` | 0 |
| Duplicate `jobNo × jobCatCode` | 0 |
| Duplicate `custNo` in `stg_Companies` | 0 |
| `jobNo` / `custNo` kind | `text / text` |
| `appearDateRaw` / `appearDate` kind | `text / date` |
| Non-null raw dates that failed parsing | 0 |
| Salary raw-value mismatches | 0 |
| Rows containing salary value `0` | 32 |
| Rows containing salary value `9999999` | 8 |
| `salaryMid`, `salaryBand`, `salaryAvailable` | absent |
| `fxNormalizeText` null/trim test | PASS |

The observed `0` and `9999999` salary values remain raw source values. No
business meaning was assigned to either value.

## 8. Final model inventory

After every temporary probe was removed, the saved and reopened model contained:

| Object | Final result |
|---|---:|
| Query groups | 4 |
| Named expressions | 20 |
| Tables | 4 |
| Columns | 135 |
| Partitions | 4, all Ready |
| Relationships | 2, unchanged |
| Measures | 0, unchanged |
| Temporary `TASK003R_*` objects | 0 |

The legacy `查詢` table, its 114 columns, the two auto-date relationships,
Semantic Model business logic, and PBIR report content were not changed.

## 9. Disk and Git evidence

The persisted Power Query metadata is stored in:

- `PBI_104.SemanticModel/definition/expressions.tmdl` — 20 expressions
- `PBI_104.SemanticModel/definition/queryGroups.tmdl` — 4 groups
- `PBI_104.SemanticModel/definition/model.tmdl` — query order/pro-tooling metadata

The protected PBIP/Report/Semantic Model inventory changed only in those three
expected places. No report file, relationship file, table definition, or PBIR
page changed.

```text
Before: 19 files, aggregate SHA-256
F5B930C97B96C541F93229D66A037CDA1181EF79E062652C7B37B7F569CD2A27

After: 21 files, aggregate SHA-256
D6DD20A02F7654C166B5D6C28C48F41DF9723AB347E05D62025C3094AAD42060
```

`git diff --check` passed. The checkout remains `main` at `162a193`; no
commit was created. Existing TASK-003 deliverables remain untracked, and the
runtime integration files are intentionally left for review.

## 10. Known limitations

- The 104 endpoint is an undocumented live API; counts and schema can drift.
- Query groups and non-load state were validated in Desktop and through the
  semantic-model metadata surface, but this task did not create `04_Model`
  load queries.
- The legacy `查詢` query still has its prior wide-table design and historical
  type choices; replacing it is outside TASK-003R.
- No report, DAX measure, hierarchy, RLS role, or business relationship was
  added.

## 11. Next task

The runtime gate that previously blocked progression is resolved. The next
permitted task is `TASK-004 — Power BI Model Tables`, beginning with its own
inventory and grain/key evidence review.
