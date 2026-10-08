# TASK-003R Power Query Runtime Integration Plan

## Scope and gate

This is a plan for TASK-003R (Power Query Runtime Integration Validation), not
TASK-004. It covers importing and runtime-validating the already delivered
TASK-002/TASK-003 expressions in Power BI Desktop. It does not design model
tables, relationships, measures, report pages, PBIR, or business logic.

The current repository evidence does not establish a `task/003-staging`
checkpoint: the actual checkout is `main` at `162a193` and the TASK-003
deliverables are untracked. This mismatch is recorded, not corrected here.

## Before-state and repository evidence

The runtime task must capture a read-only Power BI inventory before any write:

- existing query expressions and query groups;
- table and partition names, table count, and column count;
- relationship count and definitions; and
- measure count and names.

The baseline must also record that the existing legacy wide table `查詢` is
left intact. No MCP write or Desktop save is authorized during this planning
phase.

Repository checks performed for this plan:

```text
checkout: main (origin/main)
HEAD:     162a193 chore: bootstrap Power BI project
status:   8 TASK-003 files untracked; no task/003-staging branch observed
```

The eight untracked files are `docs/data-quality-report.md`,
`powerquery/01_functions/fxNormalizeText.pq`, and the six files under
`powerquery/03_staging/`. The other TASK-003 source and parameter scripts are
present in the working tree but are not part of the current Git status output.

## Expression classification and target groups

Every expression imported by TASK-003R remains Disable Load. There are no
`E. Loaded table` expressions in the supplied `00`–`03` scope; only a future
`04_Model` query may be classified as E and Enable Load. The existing `查詢`
table is not reclassified or modified.

| File | Classification | Target group | Direct dependencies | Load target |
|---|---|---|---|---|
| `powerquery/00_parameters/pArea.pq` | A. Parameter | `00_Parameters` | none | Disable Load |
| `powerquery/00_parameters/pBaseUrl.pq` | A. Parameter | `00_Parameters` | none | Disable Load |
| `powerquery/00_parameters/pJobSource.pq` | A. Parameter | `00_Parameters` | none | Disable Load |
| `powerquery/00_parameters/pKeyword.pq` | A. Parameter | `00_Parameters` | none | Disable Load |
| `powerquery/00_parameters/pMode.pq` | A. Parameter | `00_Parameters` | none | Disable Load |
| `powerquery/00_parameters/pOrder.pq` | A. Parameter | `00_Parameters` | none | Disable Load |
| `powerquery/00_parameters/pPage.pq` | A. Parameter | `00_Parameters` | none | Disable Load |
| `powerquery/00_parameters/pPageSize.pq` | A. Parameter | `00_Parameters` | none | Disable Load |
| `powerquery/01_functions/fx104GetPage.pq` | B. Function / reusable expression | `01_Functions` | `Python.Execute`, parameter values at call time | Disable Load |
| `powerquery/01_functions/fx104GetAllPages.pq` | B. Function / reusable expression | `01_Functions` | `fx104GetPage` | Disable Load |
| `powerquery/01_functions/fxNormalizeText.pq` | B. Function / reusable expression | `01_Functions` | M text conversion functions | Disable Load |
| `powerquery/02_source/src_104Result.pq` | C. Source non-load | `02_Source` | `fx104GetAllPages`, `p*` parameters | Disable Load |
| `powerquery/02_source/src_104Jobs.pq` | C. Source non-load | `02_Source` | `src_104Result[Jobs]` | Disable Load |
| `powerquery/02_source/src_104Metadata.pq` | C. Source non-load | `02_Source` | `src_104Result[Metadata]` | Disable Load |
| `powerquery/03_staging/stg_Jobs.pq` | D. Staging non-load | `03_Staging` | `src_104Jobs`, `fxNormalizeText` | Disable Load |
| `powerquery/03_staging/stg_JobSkills.pq` | D. Staging non-load | `03_Staging` | `src_104Jobs`, `fxNormalizeText` | Disable Load |
| `powerquery/03_staging/stg_Skills.pq` | D. Staging non-load | `03_Staging` | `stg_JobSkills` | Disable Load |
| `powerquery/03_staging/stg_JobCategories.pq` | D. Staging non-load | `03_Staging` | `src_104Jobs`, `fxNormalizeText` | Disable Load |
| `powerquery/03_staging/stg_Companies.pq` | D. Staging non-load | `03_Staging` | `src_104Jobs`, `fxNormalizeText` | Disable Load |
| `powerquery/03_staging/stg_Areas.pq` | D. Staging non-load | `03_Staging` | `src_104Jobs`, `fxNormalizeText` | Disable Load |

## Dependency tree and import order

The permitted one-way dependency tree is:

```text
00_Parameters
  ├─ pBaseUrl, pKeyword, pArea, pJobSource, pMode, pOrder, pPage, pPageSize
  └──────────────────────────────────────────────────────────────┐
01_Functions                                                     │
  ├─ fx104GetPage (Python.Execute + cloudscraper)                 │
  ├─ fx104GetAllPages ──> fx104GetPage                            │
  └─ fxNormalizeText                                              │
                              ┌──────────────────────────────────┘
02_Source                     │
  └─ src_104Result ──> src_104Jobs / src_104Metadata
                              │
03_Staging                    │
  ├─ stg_Jobs                  │
  ├─ stg_JobSkills ──> stg_Skills
  ├─ stg_JobCategories         │
  ├─ stg_Companies             │
  └─ stg_Areas                 │
```

Import and placement order is:

1. Create or verify `00_Parameters`, then import all eight parameter
   expressions.
2. Import `fx104GetPage`, then `fx104GetAllPages`, then `fxNormalizeText` into
   `01_Functions`.
3. Import `src_104Result`, then `src_104Jobs` and `src_104Metadata` into
   `02_Source`.
4. Import `stg_Jobs`, `stg_JobSkills`, `stg_JobCategories`, `stg_Companies`,
   and `stg_Areas`; import `stg_Skills` after `stg_JobSkills`, all into
   `03_Staging`.
5. Confirm that no expression in these groups references `04_Model`, the
   Semantic Model, or Report metadata.

## Controlled-write boundary

After this plan is reviewed, a write-capable MCP may be used only if its mode
is explicitly verified as normal read/write and confirmation is retained on
the first modification. `--skipconfirmation` is forbidden. The allowed write
scope is limited to named expressions, parameters, query groups, and the
minimum query/partition integration needed to make these expressions
refreshable. Relationships, measures, hierarchies, RLS, perspectives,
calculation groups, PBIR, report metadata, and the legacy `查詢` table remain
outside scope.

If the MCP cannot represent Power Query expressions or Enable Load state
safely, stop and mark TASK-003R BLOCKED; do not use unrelated Semantic Model
writes as a workaround.

## Query-group and Disable Load validation

The final metadata target is exactly four groups:

| Group | Expressions | Final Enable Load target |
|---|---:|---|
| `00_Parameters` | 8 | all disabled |
| `01_Functions` | 3 | all disabled |
| `02_Source` | 3 | all disabled |
| `03_Staging` | 6 | all disabled |

The Desktop UI may visually collapse folders. A collapsed folder is not
evidence of metadata loss; after any UI operation, re-inventory expressions
and groups through the available metadata surface. No staging expression may
become a final Model table merely to facilitate testing.

## Layered runtime validation plan

Do not refresh all queries at once. Validate in this order, recording the
actual live counts because the API may change:

1. Parameters: values and declared types resolve.
2. `fx104GetPage`: one page; Python, `cloudscraper`, HTTP 200, JSON shape, and
   page metadata resolve.
3. `fx104GetAllPages`: finite pagination from `currentPage` to `lastPage`.
4. `src_104Result`: record contains Jobs, Metadata, and RawResponses.
5. `src_104Jobs`: row count equals `src_104Metadata[total]` for the live run.
6. `src_104Metadata`: pagination fields and technical audit fields exist.
7. `fxNormalizeText`: null-safe trim/clean/text behavior.
8. `stg_Jobs`: safe typing, `jobNo` non-null, raw salary fields retained,
   `appearDateRaw` text and `appearDate` date.
9. `stg_JobSkills`: no duplicate `(jobNo, skillCode)` pair.
10. `stg_Skills`: one row per unique `skillCode`; conflicting descriptions
    fail closed.
11. `stg_JobCategories`: candidate pair uniqueness and explicit
    `jobCatDescription = BLOCKED`.
12. `stg_Companies`: one row per `custNo`; conflicting identity values fail
    closed.
13. `stg_Areas`: observed code/description/address/lat/lon only; no inferred
    coordinates.

Reference counts from the TASK-003 live profile are expectations, not hard
assertions: total 55, `stg_Jobs` 55, skills 280 pairs/89 codes, categories 142
pairs, and companies 35. Validate the equality and uniqueness rules above
against each live refresh instead.

## Refresh tests

Run two independent Desktop refreshes after integration. Each test must record
timestamp, live API total, per-layer row counts, HTTP/API failures, Python
failures, M-expression failures, and schema drift. The second refresh must
start from a clean query evaluation and prove that session/cookie state is not
required. Preserve the existing `cloudscraper` plus Windows system-proxy
mechanism and never add secrets or synthetic rows.

Both tests must confirm:

- `jobNo` and `custNo` are text/string;
- `appearDateRaw` is text and `appearDate` is date;
- `salaryLowRaw` and `salaryHighRaw` retain source values;
- `0` and `9999999` are not assigned business meaning; and
- `salaryMid`, `salaryBand`, and `salaryAvailable` are absent.

## Temporary objects, rollback, and stop conditions

Temporary test objects: **none planned**. Validation uses the imported
expressions only, with all four groups Disable Load. If an isolated test
expression becomes necessary, it must be explicitly named, kept outside the
four production groups, disabled, documented, and removed before completion;
otherwise stop rather than widening scope.

Stop and mark BLOCKED when any of the following occurs:

- MCP cannot safely write/query Power Query metadata or its mode cannot be
  verified;
- a dependency requires `04_Model`, Semantic Model, or Report metadata;
- Python, `cloudscraper`, HTTP, JSON, pagination, or M evaluation fails;
- required schema/type/uniqueness checks fail without an evidence-backed fix;
- Power BI attempts to load a `00`–`03` query into the model;
- any relationship, measure, legacy table, PBIR, or report metadata changes;
- a UI group collapse cannot be reconciled by metadata inventory; or
- a refresh requires secrets, hard-coded cookies/tokens, guessed fields, or
  manufactured rows.

On a failed write or refresh, stop immediately, capture the error and
before/after inventory, and restore only the TASK-003R changes using the
Power BI/Desktop undo or a verified backup/export. Do not reset or overwrite
the repository, and do not commit. A successful run still requires a final
inventory showing unchanged table/column, relationship, and measure counts,
unchanged legacy `查詢`, and no PBIR/report changes before PASS.

## Completion evidence

The implementation phase must produce `docs/pq-runtime-validation.md` with
runtime environment, dependency tree, groups, imported expressions, both
refresh tests, live counts, key/type/salary checks, MCP before/after inventory,
Git diff, limitations, and a PASS/FAIL decision. TASK-003R must end without a
commit and without beginning TASK-004.
