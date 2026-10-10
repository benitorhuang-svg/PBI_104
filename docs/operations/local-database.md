# Local PostgreSQL and ETL

The local PostgreSQL databases store immutable source captures in Bronze and normalized records in Silver. Import does not call a source API. The 104 category batches retain their `jobcat` filter and snapshot date; yes123 uses a separate adapter and source-code contract. See the [schema registry](../schema/README.md) and [database schema contract](../schema/contracts/database-schema-contract-v1.md) for the current multi-platform state and Gold view requirements.

## Multi-platform schema status

Catalog inspection on 2026-10-09 found `jobwant_104` at migration 23 and `jobwant_yes123` at migration 19. Migration 24 adds a unified platform acquisition monitor to `gold.pbi_acquisition_categories`: the 104 queue rows remain intact, and yes123 native categories join their persisted capture batches through read-only FDW tables. The 11-table model includes `FactAcquisitionCategory` with a platform key. yes123 has no persisted live queue or failure-attempt ledger, so its statuses distinguish current captures, stale batches, and categories with no capture batch; they do not claim live pending/failed queue states. Migration 22 corrected the yes123 salary currency FDW column to `CHAR(3)`; migration 23 reads yes123 FactJob scope from its existing Gold view in one FDW projection, avoiding per-job remote lookups.

The separate `jobwant_yes123` source database has been cleaned of all `JOB_MODE` (`3_`) capture batches and batch-linked rows; its 574 `WORK_MODE` categories and 39,392 shared current jobs remain. The migration-24 reporting view now reads only those 574 categories through FDW. Migration 025 is prepared as an additional view-level filter but has not been applied because the reporting database write path remains blocked below.

Database writes remain blocked: `tools/sync_lake_to_postgres.py --write` applies `tools/sql/init_postgres_schema.sql` (version 19), which can replace the version 21–24 federated Gold views. Do not run `--write`, `--direct-postgres`, or a scheduled direct-capture launcher against the reporting database until the migration runner is reconciled. Migration 020 has unsafe FDW lifecycle handling; do not replay it. Track remediation under the [database schema contract](../schema/contracts/database-schema-contract-v1.md).

## Start and import

Run these commands from the project root in PowerShell. Docker Desktop must be running.

```powershell
Copy-Item .env.example .env
# Replace PBI104_POSTGRES_PASSWORD in .env with a private random value.
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r tools/requirements-dev.txt
docker compose up -d --build --wait
.\.venv\Scripts\python.exe tools/sync_lake_to_postgres.py
```

The sync command shown is a dry run and does not contact PostgreSQL. **Database writes are currently blocked:** `jobwant_104` is at migration 23, while `tools/sync_lake_to_postgres.py --write` reapplies the checked-in version-19 schema script. That script can replace the federated Gold views. Do not run `--write`, `--direct-postgres`, or a scheduled direct-capture launcher against the reporting database until the migration runner and Gold views are reconciled. File-backed captures may be retained for later import; use the [schema remediation contract](../schema/contracts/database-schema-contract-v1.md) as the gate.

The checked-in schema file records migrations through version 19. The local
reporting database also has local migrations 20–23, which are not part of the
checked-in schema runner. A version number alone does not prove that required
views exist; inspect the actual catalog before refresh or ETL writes. Schema
changes must preserve immutable Bronze payloads.

The Compose port is bound to `127.0.0.1:5433`; the named volume `pbi104_pgdata` holds the data across container restarts. The reporting database is now named `jobwant_104`; the local catalog contains `jobwant_104` and `jobwant_yes123`, not `pbi_104`. `.env` is ignored by Git. Keep the volume when stopping the service; `docker compose down -v` removes the local database.

## Rename the reporting database (completed)

The local catalog confirms that `jobwant_104` exists and `pbi_104` does not. The one-off rename operation is complete; do not rerun it. It renamed the database in place and updated `PBI104_POSTGRES_DB` without dropping or recreating the database volume.

Run `python tools/report_category_coverage.py` for the current official leaf-category coverage ledger. The report opens a read-only PostgreSQL transaction and summarizes the latest committed batch per category, including its area query filter; it does not include uncommitted categories from an active capture run. Use `--format summary` for compact status counts, or `--format csv --output data/104/category-coverage.csv` to save UTF-8 rows for Excel.

The Compose file also builds the geocoder backend from the sibling `WGS84_TWD97` checkout and mounts that project's SQLite data read-only. Keep both project folders beside each other. The endpoint defaults to `127.0.0.1:3301`; `PBI104_GEOCODER_PORT` can change the host port without moving or copying the address database.

## Data layers

- `bronze.capture_batches` records the request, explicit `source_jobcat`, manifest, manifest hash, snapshot date/time, raw row count, and validation status. `bronze.capture_pages` keeps each page's source checksum, response metadata, and HTTP/client metadata; `bronze.raw_job_rows` keeps each original job row keyed by batch, source page, and row index, including duplicate listings. `bronze.job_category_catalogs` and `bronze.job_category_catalog_rows` preserve the exact source manifest plus a normalized hierarchy. Page-capped batches, API-total mismatches, and Silver normalization conflicts remain queryable in Bronze and are excluded from Gold.
- `silver.job_snapshots` is keyed by search series, snapshot date, batch, and job number. Other Silver tables hold the latest observed job attributes and company, area, skill, and category dimensions. Duplicate `jobNo` rows are collapsed only when all staged fields match after excluding volatile `pddScore`, `interactionRecord`, and source-page metadata; conflicting variants stop that batch.
- Search-filter provenance and returned job location are separate: `source_area` records a query filter (null for nationwide category capture), while `silver.area_dimension` stores the returned `jobAddrNo`, `jobAddrNoDesc`, `jobAddress`, `lat`, and `lon`. The Bronze payload retains the source values. Silver normalization keeps the address when coordinates are incomplete, out of range, or `(0,0)`, clears unusable coordinates, and records the reason in `quality_issues`.
- `silver.job_snapshots.source_jobcat` identifies the official category filter used for a query; `silver.job_category_snapshots.job_cat_code` remains the occupation returned on each listing. `silver.category_dimension` maps those returned codes to the official hierarchy and retains the source catalogue hash.
- `gold.latest_job_snapshots`, `gold.latest_job_skills`, and `gold.latest_job_categories` select the latest complete batch for each query series and date. `gold.pbi_job_snapshots` projects the snapshot fact contract and keeps the Taiwan-local snapshot timestamp. `gold.capture_history.search_jobcat` reports the category filter. `gold.latest_observed_jobs` exposes the most recently observed attributes; it does not claim that an old listing remains active.
- `gold.pbi_fact_jobs_v21` exposes the latest eligible 104 and yes123 jobs with platform identity. The yes123 branch reads `jobwant_yes123.gold.pbi_fact_job_scope` through one foreign projection; this avoids an FDW lookup per job. The 11 model-facing Gold views are specified in the [database schema contract](../schema/contracts/database-schema-contract-v1.md).
- `silver.job_salary_observations` stores a separate observation for the API salary fields and each salary-bearing description clause, keyed by query series, snapshot, batch, job, source kind, and mention index. Repeated jobs across category series remain traceable instead of being merged without provenance. `gold.pbi_fact_salary_observations_v21` exposes both platform sources at this observation grain, including history for jobs no longer in FactJob; it retains raw currency and pay-period fields and is related to DimDate only.
- `silver.address_geocodes` stores WGS84_TWD97 lookup results separately from 104 coordinates, keyed by the observed `area_key`. Taiwan normalization standardizes `台` to `臺`, address-number Chinese numerals to Arabic numerals, and leading zeroes in numbered parts while preserving road-name numerals. A variant can fill missing API coordinates as `ADDRESS_STANDARDIZED` only when its street/house key matches and any explicit village or neighborhood values do not conflict. Other variants, street fallbacks, POI aliases, and misses remain review-only. Canonical input, normalization version, and a Google Maps search URL for complete unresolved addresses are retained for audit; Google coordinates are not stored in this archive.
- `gold.pbi_fact_job_scope_v21` selects each platform's latest eligible job observation. The yes123 source Gold scope is already deduplicated in `jobwant_yes123`; migration 23 reads that view instead of joining foreign tables row by row. Ten `gold.pbi_*_v21` model projections cover FactJob, snapshot history, salary observations, dimensions, bridges, and the date dimension. Migration 24 extends `gold.pbi_acquisition_categories` with yes123 native category capture rows alongside the 104 queue. Platform category codes remain source-specific; no taxonomy mapping is implied. The 104 category and skill bridges use the selected batch for each FactJob row; yes123 skill associations are not yet available.
- The `areaKey` columns in `gold.pbi_fact_jobs` and `gold.pbi_dim_area` are lowercase hexadecimal encodings of the exact UTF-8 bytes in Silver's `area_key`. This keeps distinct compatibility characters separate under Power BI's string collation while the address and coordinate columns retain readable values.
- Power Query reads only the `gold.pbi_*` model views. It no longer reads `data/104`, calls the 104 API, expands JSON, merges tables, or performs staging/model key checks. `DimDate` is also provided by `gold.pbi_dim_date`; DAX remains the presentation-measure layer.
- The 104 FactJob branch requires a captured `source_jobcat`, no keyword filter, and a complete category observation; the current 104 category batches were captured with a former two-area filter, so that source is not nationwide-complete. The yes123 branch uses its own Gold scope and source-code contract. Neither platform's category codes are treated as a cross-platform taxonomy without a confirmed mapping. Page-capped and API-total-mismatch batches remain outside eligible Gold scope.

Salary values are never normalized from the API `salaryLow`/`salaryHigh` until their amount unit and pay period have evidence. API observations keep the original values and use `API_UNIT_UNMAPPED`; `0` or `9999999` is only a `SENTINEL_CANDIDATE`, with normalized amounts left null. Currency defaults to TWD under the user-approved project rule and is marked `PLATFORM_DEFAULT`; explicit currency text takes precedence. Description extraction records the exact text clause and offsets into the cleaned Silver description. `月薪四萬以上` yields `amount_min=40000`, `amount_max=NULL`, and monthly period. A bare `四萬以上` keeps an unknown period and review status. `150/hr` yields a 150 hourly minimum with no maximum; `35000~42000` yields lower and upper amounts, while its period remains unknown and needs review unless the description says otherwise. A single amount always populates the minimum only. Annual pay is not divided by 12, and variable pay is not folded into base pay.

Parser statuses distinguish `PARSED`, `NEEDS_REVIEW`, `NEGOTIABLE`, `NOT_DISCLOSED`, `API_UNIT_UNMAPPED`, and `SENTINEL_CANDIDATE`; `quality_flags` records defaulted TWD, missing period evidence, and possible source sentinels. After the migration runner is reconciled with local schema version 23 and the write path is explicitly re-approved, `sync_lake_to_postgres.py --write` can backfill parser-derived observations for already imported complete batches without fetching the API again. The batch/job/source identity remains stable, while `parser_version` identifies the normalization rules; Bronze source payloads remain unchanged. This paragraph describes a future capability, not an instruction to run it now.

The initial keyword lake contained 738 raw rows and 691 normalized batch-job
rows across seven batches and three query series. Those historical counts
describe that saved capture set, not the current database or a live refresh.

Example checks with the default local database settings:

```powershell
docker compose exec -T postgres psql -U pbi_admin -d jobwant_104 -c "select count(*) from bronze.capture_batches;"
docker compose exec -T postgres psql -U pbi_admin -d jobwant_104 -c "select count(*) from bronze.raw_job_rows;"
docker compose exec -T postgres psql -U pbi_admin -d jobwant_104 -c "select count(*) from gold.latest_job_snapshots;"
```

## Ongoing collection

Run `python tools/capture_category_matrix.py` to inspect page-one totals by top-level occupation category across all areas. Use `--depth 1` or `--depth 2` to inspect subcategories or occupations when a top-level result exceeds the API page limit. The occupation collector defaults to the verified maximum `--pagesize 30`; pagesize=31 returns HTTP 400. For file-backed capture, use `--capture`; page files are UTF-8 without BOM, two-space JSON under `data/104/categories/<jobcat>/batches/<batch-id>/`. Direct PostgreSQL capture is blocked for the current reporting database: the capture sink applies `tools/sql/init_postgres_schema.sql` (schema version 19) before writing to the migration-23 database. Keep captures file-backed. The documented per-category transaction behavior applies only after the migration runner is reconciled. For file-backed runs, `--resume` skips same-day batches matching the query series, including saved pagination warnings and regardless of page size; omit `--resume` to recapture intentionally. Use repeatable `--code <10-digit-code>` options to limit a run. `--category-workers` (default 2) controls simultaneous categories and `--workers` (default 2) controls page workers per category; their product is capped at 4 active page requests. `--delay` (default 0.8 seconds) is a shared minimum interval across all API requests; HTTP 429 increases it by a factor of 1.5 up to 8 seconds; each 20 successful requests reduce it by 10% toward the configured minimum. Waiting workers recheck the shared schedule before sending. Pages are reordered and validated before persistence. Transient HTTP/network failures retry until success or operator interruption, using shared exponential backoff with jitter capped at five minutes; there is no fixed retry-count limit. Ordinary HTTP 403 responses retry with shared exponential backoff and no fixed attempt limit. Explicit 401/407/418 and detected challenge or non-JSON responses stop workers for review. The collector has no `area` filter by default; pass `--area <codes>` only for an explicitly regional capture. Each category is capped at 150 pages. If the API reports more, the file-backed batch is retained locally with an incomplete status and excluded from later Silver/Gold import. Category batches do not replace the current keyword pointer. Keep file-backed captures local until the migration runner and reporting Gold views are reconciled; the import `--write` path is currently blocked. Both paths preserve the existing `cloudscraper` and Windows system-proxy mechanism.

The live category size checks and API pagination limitations are recorded in [docs/data-reference/category-acquisition-probe.md](../data-reference/category-acquisition-probe.md). Category result totals are not globally unique job counts.

## Read-only browser viewer

Run `.\tools\launchers\view_acquisition_data.ps1` from Windows PowerShell to start the local viewer and print its URL and process ID, and open the page in the default browser. If the browser does not open, use `http://127.0.0.1:8765/`. It shows the latest distributed capture run, category queue states, each category's latest committed Bronze batch, and searchable raw job rows with their source JSON. The page refreshes every 10 seconds. The service binds only to `127.0.0.1`, accepts read requests only, and sets each PostgreSQL connection to read-only. Stop it with `Stop-Process -Id <PID>` using the printed process ID.

A category's pages are committed atomically after capture validation, so its in-flight responses do not appear in this viewer. The queue status can update before the job rows become visible. This page reads PostgreSQL Bronze directly and does not change ETL or Power Query.

## Scheduled distributed capture

The scheduled launcher writes directly to PostgreSQL and is currently blocked by the schema mismatch. Do not start it until database-write remediation is complete. Its configuration is documented below for the later approved run. The launcher defaults to `PBI104_CAPTURE_RUNTIME=host` on
Windows: the coordinator and worker processes use the verified Windows Python
client and connect to the shared PostgreSQL service on `127.0.0.1:5433`. The
coordinator fetches and saves the official occupation catalogue, then queues
one deterministic daily run. If fetching the catalogue fails, it can use the
last checksum-verified local snapshot; without one it stops before queuing.
Workers claim one category at a time with renewable leases. Each complete
category is committed atomically to Bronze and eligible Silver tables. Run and
batch dates use Asia/Taipei. Restarting on the same day resumes unfinished work
and skips categories already captured for that query.

Host and Compose worker modes use three workers by default, one page worker per
category, and `pagesize=30`. PostgreSQL coordinates request start times across
workers: the minimum interval defaults to 0.8 seconds, grows by 1.5 after HTTP
429 up to 8 seconds, and drops by 10% after each 20 successful requests.
Transient failures and ordinary 403 responses use shared exponential backoff
without a fixed retry limit. A response marked `cf-mitigated: challenge` blocks
the run for operator review instead of being retried as an ordinary 403. Set
`PBI104_CAPTURE_WORKERS` and `PBI104_CAPTURE_DELAY_SECONDS` in the ignored
`.env` to adjust the defaults; the launcher permits one to four workers.

Container mode is opt-in with `PBI104_CAPTURE_RUNTIME=container`. In this
checkout the same API request succeeds on Windows and receives a Cloudflare
challenge from Linux containers. The container and Windows host also use
different outbound IPs; sending container TLS through a host CONNECT tunnel
still received the challenge, so changing only the proxy route does not resolve
it. Cloudflare does not expose the exact fingerprint rule. Use container mode
only when its API route has been verified. Compose services accept runtime-only
`PBI104_HTTP_PROXY`, `PBI104_HTTPS_PROXY`, and `PBI104_ALL_PROXY` values from
`.env`; never put proxy credentials in the image or Git.

Check run progress from the project root with:

`python -m tools.acquisition.platforms.jobwant_104.distributed.coordinator --status`

Windows-host worker logs are under
`data/104/category-runs/host-worker-*`; container worker output is available
with `docker compose --profile acquisition logs -f etl-worker`. Windows Task
Scheduler should run the batch under the same Windows account that owns the
local `.env` and PostgreSQL service.

## Address geocoding backfill

The PBI_104 Compose stack starts the WGS84_TWD97 read-only backend alongside PostgreSQL. It mounts the local SQLite database read-only at `http://127.0.0.1:3301` and returns an explicit `matchLevel` for each result.

The `jobwant_104` catalog is already at schema version 23, so schema version 7 is in its migration history. Do not rerun `sync_lake_to_postgres.py --write` just to apply version 7; that command currently replays the version-19 schema script. After database-write remediation, preview the missing-address lookup:

```powershell
.\.venv\Scripts\python.exe tools/geocode_missing_addresses.py --geocoder-url http://127.0.0.1:3301
```

The preview contacts only the local geocoder and does not write PostgreSQL. Persist results with the geocoder's `--write` only after confirming the current table contract and intended data change. Requests are deduplicated by Taiwan-standardized address and limited to 2,000 addresses per API call. Use `--refresh` to retry already stored geocode rows. A failed request or malformed response aborts before any results are written. The original API values and Bronze payload remain unchanged. A complete local miss gets a Google Maps search link for manual review, but this project does not call or persist Google coordinates: the current Geocoding API terms generally permit coordinate caching for up to 30 days and prohibit using its content with non-Google maps. The current two misses are a masked `xxx路xxx號` placeholder and `公司指定派遣的辦公室`, so neither is a mappable address.

`gold.pbi_dim_area` applies the effective coordinate rule in SQL: retain valid 104 coordinates, otherwise use only exact-text or Taiwan-standardized geocode matches. Power Query performs no merge. In Power BI Desktop, open Data source settings for `127.0.0.1:5433`, clear any blank/anonymous permission, and reconnect with Database/Basic authentication using username `pbi_admin` and the password from the ignored local `.env`. Accept the unencrypted-connection prompt for this loopback-only PostgreSQL endpoint. Credentials are stored by Power BI and are never embedded in M or committed files. If the Compose PostgreSQL port changes, update `pPostgresServer` in Power Query to match.
