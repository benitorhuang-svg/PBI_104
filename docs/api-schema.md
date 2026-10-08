# 104 Job Search API Schema Evidence

## Evidence scope

This document records observations from live requests made on 2026-08-13 (Asia/Taipei). It is evidence for the tested query, not a guarantee that 104 will keep the same undocumented contract.

- Endpoint: `GET https://www.104.com.tw/jobs/search/api/jobs`
- Parameters: `area=6001008007,6001008006`, `jobsource=index_s`, `keyword=powerbi`, `mode=s`, `order=15`, `page=1`, `pagesize=20`
- Baseline result: HTTP 200 at `2026-08-13T15:07:33+08:00`
- Reviewed test fixture: `tools/tests/fixtures/api-response-page-1.fixture.json`
- Fixture SHA-256: `F0BE85529D50F254506882C6675B49B13CB8AB9782E540EC5EB33E822D6C19FC`
- The request had no Cookie header. The response did include `Set-Cookie`, but response headers and cookies are not stored in the fixture.
- `urllib.request.getproxies()` returned no HTTP/HTTPS proxy for this run. The Source implementation still preserves Windows proxy discovery and injection.

## Confirmed JSON paths

| Path | Observed type | Evidence |
|---|---|---|
| `$` | object | Keys: `data`, `metadata` |
| `$.data` | array | The jobs list; 20 objects on page 1 |
| `$.metadata` | object | Keys: `pagination`, `isPreciseHotJob`, `filterQuery`, `offJobs`, `personalBoost` |
| `$.metadata.pagination` | object | Keys: `count`, `currentPage`, `lastPage`, `total` |
| `$.metadata.filterQuery` | object | Echoes normalized request/filter values |
| `$.metadata.offJobs` | array | Empty in the captured response; semantics unconfirmed |

`$.data` is an array, so it has no object keys of its own. The union of keys observed on its 20 job-row objects is:

```text
acceptRole, appearDate, applyCnt, applyDate, coIndustry,
coIndustryDesc, custLogo, custName, custNo, d3, descSnippet,
description, employeeCount, hrBehaviorPR, interactionRecord, isApplied,
isSave, jobAddrNo, jobAddrNoDesc, jobAddress, jobCat, jobName,
jobNameSnippet, jobNo, jobRo, jobSwitch, jobType, labels,
languageRequirements, lat, link, lon, major, mrt, mrtDesc, mrtDist,
optionEdu, pcSkills, pddScore, period, remoteWorkType, s10, s5, s9,
salaryHigh, salaryLow, tags, userApplyCount
```

All 48 keys were present on every page-1 row. That observation does not make every field mandatory for future responses.

## Pagination and counts

The live response provides an explicit pagination contract under `$.metadata.pagination`:

| Requested page | `count` | `currentPage` | `lastPage` | `total` | Actual rows |
|---:|---:|---:|---:|---:|---:|
| 1 | 20 | 1 | 3 | 55 | 20 |
| 2 | 20 | 2 | 3 | 55 | 20 |
| 3 | 15 | 3 | 3 | 55 | 15 |

The three pages returned 55 rows in total, matching `total=55`. `fx104GetAllPages` therefore uses the finite range from requested `currentPage` through confirmed `lastPage`; it does not stop on an empty page. A separate no-result keyword test returned HTTP 200, `data=[]`, `count=0`, `currentPage=1`, `lastPage=0`, and `total=0`.

## Page-1 scalar and nullable evidence

Observed JSON types include:

- Strings: `appearDate`, `custNo`, `jobNo`, `mrt`, job/company text, URLs, and descriptions.
- Integers: `applyCnt`, `coIndustry`, `jobAddrNo`, `jobRo`, `jobType`, `period`, `remoteWorkType`, salary bounds, and several coded fields.
- Numbers: `lat`, `lon`, `hrBehaviorPR`, `pddScore`; `mrtDist` appeared as both integer and floating-point JSON numbers.
- Null on all 20 captured rows: `applyDate`, `isApplied`, `isSave`, `userApplyCount`.

No page-1 nulls were observed for `jobNo` or `custNo`. Empty arrays are values, not nulls. Date, code, salary, and boolean-like business meanings remain unconfirmed until Staging profiling.

## Nested-field evidence

| Field | Page-1 shape | Confirmed child shape |
|---|---|---|
| `pcSkills` | array on 20/20 rows | Items are objects with string `code` and string `description`; lengths 0–19 |
| `tags` | object on 17 rows; empty array on 3 rows | Object keys vary (`wf*`, `zone`, `remote`, `landmark`); values are objects with `desc` and `param`. `param` was usually a string, with integer values also observed |
| `jobCat` | array on 20/20 rows | Items are integers; lengths 1–3 |
| `link` | object on 20/20 rows | Keys: `job`, `cust`, `applyAnalyze` |
| `interactionRecord` | object on 20/20 rows | Keys: `lastProcessedResumeAtTime`, `lastCustReplyTimestamp`, `nowTimestamp` |
| `labels` | array on 20/20 rows | String items |
| `languageRequirements` | array on 20/20 rows | Empty or objects with `language` and `ability` |
| `major` | array on 20/20 rows | String items |
| `optionEdu`, `s9`, `acceptRole` | arrays on 20/20 rows | Integer items |

Across all 55 jobs, `pcSkills` was always an array and `jobCat` was always an array. `tags` was an object on 51 rows and an array on 4 rows, confirming that consumers must handle both JSON types. Source serializes every nested list/object with `json.dumps(..., ensure_ascii=False)` so the structure remains valid JSON rather than Python `str()` output.

## Metadata exposed by Source

`src_104Metadata` returns one row per requested page with HTTP status, request URL, snapshot timestamps, request parameters, returned row count, top-level/job/metadata keys, raw pagination/filter/metadata JSON, and the confirmed pagination scalars `count`, `currentPage`, `lastPage`, and `total`.

## Unknown or unresolved

- The business semantics of `appearDate`, salary codes/units, `jobType`, `s*`, `d3`, `hrBehaviorPR`, and `pddScore` are not established here.
- The meanings of `tags` keys, tag `param`, `jobCat` integers, `pcSkills.code`, `offJobs`, and `personalBoost` are unconfirmed.
- Field optionality across other keywords, areas, authentication states, and future API versions is unconfirmed.
- Rate limits, maximum supported `pagesize`, ordering stability, and pagination behavior while the dataset changes are unconfirmed.
- Page-1 `jobNo` uniqueness is evidence only, not a model key decision.
