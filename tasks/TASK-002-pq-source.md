# TASK-002 — Power Query Source Layer

## 前置條件

TASK-001 已完成。

## 背景

目前已驗證成功流程：

```text
Python.Execute
→ pandas
→ cloudscraper
→ urllib.request.getproxies()
→ Windows system proxy
→ GET 104 API
→ response.json()
→ DataFrame
```

API：

```text
https://www.104.com.tw/jobs/search/api/jobs
```

## 目標

建立可維護、可診斷、可參數化的 Source Layer。

## 非目標

不得做：薪資商業清洗、Skill model、Model Tables、DAX、PBIR、Dashboard。

## 修改範圍

```text
powerquery/00_parameters/
powerquery/01_functions/
powerquery/02_source/
docs/api-schema.md
samples/
```

不得修改：

```text
powerquery/03_staging/
powerquery/04_model/
powerbi/
```

## 需要建立

### Parameters

```text
pBaseUrl.pq
pKeyword.pq
pArea.pq
pMode.pq
pOrder.pq
pPage.pq
pPageSize.pq
```

預設：

```text
pBaseUrl = "https://www.104.com.tw/jobs/search/api/jobs"
pKeyword = "powerbi"
pArea = "6001008007,6001008006"
pMode = "s"
pOrder = "15"
pPage = 1
pPageSize = 20
```

### Functions（候選，不強制建立）

```text
fx104GetPage.pq
fx104GetAllPages.pq
```

只有在 `fx104GetPage` 確實被兩處以上重用時才建立；若單一 Source query 足以表達目前 page 1 擷取，保留空的 `01_Functions` 並記錄原因。`fx104GetAllPages` 必須等真實 pagination metadata 證據成立後才可建立。

### Source Queries

```text
src_104Jobs.pq
src_104Metadata.pq
```

## API 連線要求

保留已成功機制：

- `cloudscraper.create_scraper`
- `urllib.request.getproxies()`
- 僅注入 HTTP / HTTPS proxy
- timeout
- `raise_for_status()`
- JSON response

禁止硬編碼 Cookie、Cloudflare token、session、proxy credential。

## fx104GetPage（符合重用條件時）

輸入：

```text
keyword
area
page
pagesize
```

輸出：單頁 Raw Jobs + metadata。

要求：

- nested `dict/list` 不得用 Python `str()` 不可逆轉字串。
- 必須保留 `jobNo`、`custNo`、原始 salary / skill / tag / category 欄位。
- 複合值若需暫存，使用合法 JSON serialization。
- 加入：`snapshotDate`、`snapshotDateTime`、`sourceKeyword`、`sourceArea`、`sourcePage`、`sourcePageSize`。
- 欄位缺少時不可讓整體 refresh crash。
- API error 必須可診斷。

## fx104GetAllPages

必須先從真實 metadata 判定 pagination。

**不得猜測** `totalPage`、總筆數或停止條件。

若無法可靠確認：

- 完成 `fx104GetPage`。
- `fx104GetAllPages` 標記 `BLOCKED`。
- 不使用無限迴圈。

## src_104Metadata

至少輸出：

```text
httpStatus
requestUrl
snapshotDate
snapshotDateTime
keyword
area
requestedPage
requestedPageSize
returnedJobs
topLevelKeys
dataKeys
```

若真實 API 有則保留：

```text
totalCount
totalPage
page
pageSize
total
count
```

## docs/api-schema.md

只能根據真實 response 記錄：

- top-level keys
- data keys
- jobs list path
- pagination fields
- nullable fields
- nested fields
- unknown fields
- sample values
- confirmed / unconfirmed semantics

## 測試

- TC-001：正常查詢 page 1，HTTP 200，`jobNo` / `custNo` 存在。
- TC-002：無結果 keyword，回空 table，不製造假的職缺 Error row。
- TC-003：可選欄位缺少時 refresh 不 crash。
- TC-004：nested list/dict 未被破壞。
- TC-005：HTTP failure 可診斷。

## 驗收標準

- [ ] Page 1 可成功抓取。
- [ ] Row count 正確。
- [ ] 無 Cookie。
- [ ] Metadata 可讀。
- [ ] Source 無 business logic。
- [ ] Nested data 可逆/可解析。
- [ ] `docs/api-schema.md` 完成。
- [ ] Pagination 未確認則明確 BLOCKED。

## 回報格式

```text
FILES CHANGED
IMPLEMENTATION
API METADATA
TEST RESULTS
SCHEMA FINDINGS
PAGINATION STATUS
RISKS / BLOCKERS
NEXT TASK
```
