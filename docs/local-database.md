# Local PostgreSQL archive

The local PostgreSQL database stores immutable 104 category captures directly in Bronze or imports previously saved files. It does not call the API during lake import. The original seven keyword batches remain intact; each category batch records its `jobcat` filter and snapshot date. The official occupational-category catalogue is saved and imported separately so each returned job category can be named from 104's own mapping.

## Start and import

Run these commands from the project root in PowerShell. Docker Desktop must be running.

```powershell
Copy-Item .env.example .env
# Replace PBI104_POSTGRES_PASSWORD in .env with a private random value.
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r tools/requirements-dev.txt
docker compose up -d --build --wait
.\.venv\Scripts\python.exe tools/sync_lake_to_postgres.py
.\.venv\Scripts\python.exe tools/sync_lake_to_postgres.py --write
```

The first sync command is a dry run. `--write` applies the checked-in schema and commits each complete batch in its own transaction. A batch already present with the same manifest SHA-256 is skipped; a conflicting identity fails. Re-running after an interruption therefore imports only the remaining batches. The loader verifies each manifest, page hash, pagination contract, and row count before connecting to PostgreSQL. Run `--write` after a new capture and before a Power BI Snapshot-mode refresh.

Schema migration 9 adds the PostgreSQL Gold views used by all nine Power BI
Import tables. Migration 10 adds and backfills the explicit query-category
field. Migration 12 adds the coordinate-derived job location scope to
`gold.pbi_dim_area`. Migration 13 adds the shared distributed capture queue and
request gate. The checked-in schema currently records version 13; the coverage
report shows the highest version installed in the local database.
Applying the checked-in schema is idempotent and does not rewrite immutable
Bronze payloads.

The Compose port is bound to `127.0.0.1:5433` so it does not collide with the other local PostgreSQL service on port 5432; the named volume `pbi104_pgdata` holds this database across container restarts. `.env` is ignored by Git. Keep the volume when stopping the service; `docker compose down -v` removes the local database.

Run `python tools/report_category_coverage.py` for the current official leaf-category coverage ledger. The report opens a read-only PostgreSQL transaction and summarizes the latest committed batch per category, including its area query filter; it does not include uncommitted categories from an active capture run. Use `--format summary` for compact status counts, or `--format csv --output data/104/category-coverage.csv` to save UTF-8 rows for Excel.

The Compose file also builds the geocoder backend from the sibling `WGS84_TWD97` checkout and mounts that project's SQLite data read-only. Keep both project folders beside each other. The endpoint defaults to `127.0.0.1:3301`; `PBI104_GEOCODER_PORT` can change the host port without moving or copying the address database.

## Data layers

- `bronze.capture_batches` records the request, explicit `source_jobcat`, manifest, manifest hash, snapshot date/time, raw row count, and validation status. `bronze.capture_pages` keeps each page's source checksum, response metadata, and HTTP/client metadata; `bronze.raw_job_rows` keeps each original job row keyed by batch, source page, and row index, including duplicate listings. `bronze.job_category_catalogs` and `bronze.job_category_catalog_rows` preserve the exact source manifest plus a normalized hierarchy. Page-capped batches, API-total mismatches, and Silver normalization conflicts remain queryable in Bronze and are excluded from Gold.
- `silver.job_snapshots` is keyed by search series, snapshot date, batch, and job number. Other Silver tables hold the latest observed job attributes and company, area, skill, and category dimensions. Duplicate `jobNo` rows are collapsed only when all staged fields match after excluding volatile `pddScore`, `interactionRecord`, and source-page metadata; conflicting variants stop that batch.
- Search-filter provenance and returned job location are separate: `source_area` records a query filter (null for nationwide category capture), while `silver.area_dimension` stores the returned `jobAddrNo`, `jobAddrNoDesc`, `jobAddress`, `lat`, and `lon`. The Bronze payload retains the source values. Silver normalization keeps the address when coordinates are incomplete, out of range, or `(0,0)`, clears unusable coordinates, and records the reason in `quality_issues`.
- `silver.job_snapshots.source_jobcat` identifies the official category filter used for a query; `silver.job_category_snapshots.job_cat_code` remains the occupation returned on each listing. `silver.category_dimension` maps those returned codes to the official hierarchy and retains the source catalogue hash.
- `gold.latest_job_snapshots`, `gold.latest_job_skills`, and `gold.latest_job_categories` select the latest complete batch for each query series and date. `gold.pbi_job_snapshots` projects the snapshot fact contract and keeps the Taiwan-local snapshot timestamp. `gold.capture_history.search_jobcat` reports the category filter. `gold.latest_observed_jobs` exposes the most recently observed attributes; it does not claim that an old listing remains active.
- `gold.pbi_fact_jobs` selects complete occupational-category observations, deduplicates to the latest selected observation per `jobNo`, and has no keyword or area predicate. The related `gold.pbi_dim_*`, `gold.pbi_bridge_*`, `gold.pbi_fact_job_snapshots`, and `gold.pbi_dim_date` views expose the nine Power BI Import table contracts.
- `silver.job_salary_observations` stores a separate observation for the API salary fields and each salary-bearing description clause, keyed by query series, snapshot, batch, job, source kind, and mention index. Repeated jobs across category series remain traceable instead of being merged without provenance. `gold.latest_job_salary_observations` limits the output to each series/date's latest complete batch.
- `silver.address_geocodes` stores WGS84_TWD97 lookup results separately from 104 coordinates, keyed by the observed `area_key`. Taiwan normalization standardizes `台` to `臺`, address-number Chinese numerals to Arabic numerals, and leading zeroes in numbered parts while preserving road-name numerals. A variant can fill missing API coordinates as `ADDRESS_STANDARDIZED` only when its street/house key matches and any explicit village or neighborhood values do not conflict. Other variants, street fallbacks, POI aliases, and misses remain review-only. Canonical input, normalization version, and a Google Maps search URL for complete unresolved addresses are retained for audit; Google coordinates are not stored in this archive.
- `gold.pbi_fact_job_scope` selects the latest complete category-sourced observation for each job across the areas represented in complete captures. It has no keyword or area filter. The nine `gold.pbi_*` model views project exact table contracts and include FactJob, snapshot history, dimensions, bridges, and the date dimension. Category and skill bridges use the same selected batch as their FactJob row.
- The `areaKey` columns in `gold.pbi_fact_jobs` and `gold.pbi_dim_area` are lowercase hexadecimal encodings of the exact UTF-8 bytes in Silver's `area_key`. This keeps distinct compatibility characters separate under Power BI's string collation while the address and coordinate columns retain readable values.
- Power Query reads only the `gold.pbi_*` model views. It no longer reads `data/104`, calls the 104 API, expands JSON, merges tables, or performs staging/model key checks. `DimDate` is also provided by `gold.pbi_dim_date`; DAX remains the presentation-measure layer.
- FactJob eligibility is based on a non-null captured `source_jobcat` and no keyword filter. It includes every area represented in complete category batches. Current complete category batches were captured with the former two-area filter, so the present model data is not nationwide-complete; new nationwide batches enter automatically after ETL. The loader verifies each local manifest/page contract before writing Silver, and only `COMPLETE` batches enter Gold. Page-capped and API-total-mismatch batches remain in Bronze.

Salary values are never normalized from the API `salaryLow`/`salaryHigh` until their amount unit and pay period have evidence. API observations keep the original values and use `API_UNIT_UNMAPPED`; `0` or `9999999` is only a `SENTINEL_CANDIDATE`, with normalized amounts left null. Currency defaults to TWD under the user-approved project rule and is marked `PLATFORM_DEFAULT`; explicit currency text takes precedence. Description extraction records the exact text clause and offsets into the cleaned Silver description. `月薪四萬以上` yields `amount_min=40000`, `amount_max=NULL`, and monthly period. A bare `四萬以上` keeps an unknown period and review status. `150/hr` yields a 150 hourly minimum with no maximum; `35000~42000` yields lower and upper amounts, while its period remains unknown and needs review unless the description says otherwise. A single amount always populates the minimum only. Annual pay is not divided by 12, and variable pay is not folded into base pay.

Parser statuses distinguish `PARSED`, `NEEDS_REVIEW`, `NEGOTIABLE`, `NOT_DISCLOSED`, `API_UNIT_UNMAPPED`, and `SENTINEL_CANDIDATE`; `quality_flags` records defaulted TWD, missing period evidence, and possible source sentinels. Re-running `python tools/sync_lake_to_postgres.py --write` can backfill or refresh parser-derived observations for already imported complete batches without fetching the API again. The batch/job/source identity remains stable, while `parser_version` identifies the current normalization rules; Bronze source payloads remain unchanged.

The initial keyword lake contained 738 raw rows and 691 normalized batch-job
rows across seven batches and three query series. Those historical counts
describe that saved capture set, not the current database or a live refresh.

Example checks with the default local database settings:

```powershell
docker compose exec -T postgres psql -U pbi_admin -d pbi_104 -c "select count(*) from bronze.capture_batches;"
docker compose exec -T postgres psql -U pbi_admin -d pbi_104 -c "select count(*) from bronze.raw_job_rows;"
docker compose exec -T postgres psql -U pbi_admin -d pbi_104 -c "select count(*) from gold.latest_job_snapshots;"
```

## Ongoing collection

Run `python tools/capture_category_matrix.py` to inspect page-one totals by top-level occupation category across all areas. Use `--depth 1` or `--depth 2` to inspect subcategories or occupations when a top-level result exceeds the API page limit. The occupation collector defaults to the verified maximum `--pagesize 30`; pagesize=31 returns HTTP 400. For file-backed capture, use `--capture`; page files are UTF-8 without BOM, two-space JSON under `data/104/categories/<jobcat>/batches/<batch-id>/`. To write job captures directly to PostgreSQL, use `python tools/capture_category_matrix.py --depth 2 --capture --direct-postgres --resume`. The direct mode keeps each fetched category in memory, validates every page, then commits that category's Bronze and eligible Silver rows in one transaction. It keeps the official taxonomy snapshot and run summary on disk, but does not write per-page job JSON files. In either mode, `--resume` skips same-day batches matching the query series, including saved pagination warnings and regardless of page size; omit `--resume` to recapture intentionally. Use repeatable `--code <10-digit-code>` options to limit a run. `--category-workers` (default 2) controls simultaneous categories and `--workers` (default 2) controls page workers per category; their product is capped at 4 active page requests. `--delay` (default 0.8 seconds) is a shared minimum interval across all API requests; HTTP 429 increases it by a factor of 1.5 up to 8 seconds; each 20 successful requests reduce it by 10% toward the configured minimum. Waiting workers recheck the shared schedule before sending. Pages are reordered and validated before persistence. Transient HTTP/network failures retry until success or operator interruption, using shared exponential backoff with jitter capped at five minutes; there is no fixed retry-count limit. Ordinary HTTP 403 responses retry with shared exponential backoff and no fixed attempt limit. Explicit 401/407/418 and detected challenge or non-JSON responses stop workers for review. The collector has no `area` filter by default; pass `--area <codes>` only for an explicitly regional capture. Each category is capped at 150 pages. If the API reports more, the received pages are preserved as an incomplete Bronze batch and excluded from Silver/Gold. Category batches do not replace the current keyword pointer. Import file-backed captures with `python tools/sync_lake_to_postgres.py --write`. Both paths preserve the existing `cloudscraper` and Windows system-proxy mechanism.

The live category size checks and API pagination limitations are recorded in [docs/category-acquisition-probe.md](category-acquisition-probe.md). Category result totals are not globally unique job counts.

## Read-only browser viewer

Run `.\tools\launchers\view_acquisition_data.ps1` from Windows PowerShell to start the local viewer and print its URL and process ID, and open the page in the default browser. If the browser does not open, use `http://127.0.0.1:8765/`. It shows the latest distributed capture run, category queue states, each category's latest committed Bronze batch, and searchable raw job rows with their source JSON. The page refreshes every 10 seconds. The service binds only to `127.0.0.1`, accepts read requests only, and sets each PostgreSQL connection to read-only. Stop it with `Stop-Process -Id <PID>` using the printed process ID.

A category's pages are committed atomically after capture validation, so its in-flight responses do not appear in this viewer. The queue status can update before the job rows become visible. This page reads PostgreSQL Bronze directly and does not change ETL or Power Query.

## Scheduled distributed capture

Run `.\tools\launchers\download_all_occupations_docker.bat` after PostgreSQL and Docker Desktop
are available. The launcher defaults to `PBI104_CAPTURE_RUNTIME=host` on
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

Check run progress with `python -m tools.acquisition.distributed_coordinator
--status` from the project root. Windows-host worker logs are under
`data/104/category-runs/host-worker-*`; container worker output is available
with `docker compose --profile acquisition logs -f etl-worker`. Windows Task
Scheduler should run the batch under the same Windows account that owns the
local `.env` and PostgreSQL service.

## Address geocoding backfill

The PBI_104 Compose stack starts the WGS84_TWD97 read-only backend alongside PostgreSQL. It mounts the local SQLite database read-only at `http://127.0.0.1:3301` and returns an explicit `matchLevel` for each result.

Apply schema version 7 with `python tools/sync_lake_to_postgres.py --write`, then preview the missing-address lookup:

```powershell
.\.venv\Scripts\python.exe tools/geocode_missing_addresses.py --geocoder-url http://127.0.0.1:3301
```

The preview contacts only the local geocoder and does not write PostgreSQL. Persist validated results with `--write`. Requests are deduplicated by Taiwan-standardized address and limited to 2,000 addresses per API call. Use `--refresh` to retry already stored geocode rows. A failed request or malformed response aborts before any results are written. The original API values and Bronze payload remain unchanged. A complete local miss gets a Google Maps search link for manual review, but this project does not call or persist Google coordinates: the current Geocoding API terms generally permit coordinate caching for up to 30 days and prohibit using its content with non-Google maps. The current two misses are a masked `xxx路xxx號` placeholder and `公司指定派遣的辦公室`, so neither is a mappable address.

`gold.pbi_dim_area` applies the effective coordinate rule in SQL: retain valid 104 coordinates, otherwise use only exact-text or Taiwan-standardized geocode matches. Power Query performs no merge. In Power BI Desktop, open Data source settings for `127.0.0.1:5433`, clear any blank/anonymous permission, and reconnect with Database/Basic authentication using username `pbi_admin` and the password from the ignored local `.env`. Accept the unencrypted-connection prompt for this loopback-only PostgreSQL endpoint. Credentials are stored by Power BI and are never embedded in M or committed files. If the Compose PostgreSQL port changes, update `pPostgresServer` in Power Query to match.
