# Local validation tools

Run these commands from the repository root in Windows PowerShell:

```powershell
python -m unittest discover -s tools/tests -v
python tools/sync_queries.py
python tools/validate_project.py
.\tools\desktop\desktop_model.ps1 -Operation Parse
```

## Tool groups

- `acquisition/`: reusable acquisition, ETL, database, and browser-viewer modules.
- `desktop/`: Power BI Desktop model and UI helpers.
- `launchers/`: Windows entry points for capture, distributed workers, and the local data viewer.
- `probes/`: DAX contract queries and a legacy M probe generator; see [`probes/README.md`](probes/README.md).
- `sql/` and `tests/`: database schema and offline test suite.

## Entry point index

| Task | Entry point |
| --- | --- |
| Inspect or capture official occupation categories | `python tools/capture_category_matrix.py` |
| Capture legacy keyword queries | `python tools/capture104.py` or `python tools/capture_matrix.py` |
| Validate and import saved batches into PostgreSQL | `python tools/sync_lake_to_postgres.py` (`--write` applies changes) |
| Read category coverage from PostgreSQL | `python tools/report_category_coverage.py` |
| Geocode missing addresses | `python tools/geocode_missing_addresses.py` |
| Check M/TMDL synchronization | `python tools/sync_queries.py` |
| Validate project structure | `python tools/validate_project.py` |
| Run Desktop model operations | `tools/desktop/desktop_model.ps1`; see its operations below |

`Parse` checks checked-in TMDL with the Power BI Desktop assemblies installed on this machine. `Inventory` and `Dax` require exactly one open Power BI Desktop model. `Inventory` reports loaded tables and partition states; `Dax -QueryFile <path>` executes a read-only DAX query against that model. Keep maintained DAX checks under `tools/probes/`. The Desktop helper no longer creates temporary model tables.

The Linux CI validator reports `result=STRUCTURE_PASS_DESKTOP_TMDL_UNAVAILABLE`; this means JSON, PBIR references, query sync, and Python checks passed, while the Windows Power BI Desktop parser was not available. A local Windows run reports `result=PASS` only after the Desktop TMDL parser passes. The dependency file pins direct and transitive package versions for Python 3.13; update it only from a clean environment after an intentional dependency change.

`ImportQueries` copies M expressions from disk into the open model and calls `SaveChanges`; use it only when deliberately updating that Desktop session. It does not create tables, relationships, measures, or report visuals. After an intended model update, refresh in Desktop, verify the changed layer and load states, save, close, and reopen the PBIP.

## Acquisition and local data

Generate a current, read-only coverage ledger from PostgreSQL with `python tools/report_category_coverage.py`; use `--format summary` for compact counts, or `--format csv --output data/104/category-coverage.csv` to save UTF-8 rows for Excel. It reports the latest committed batch per official leaf category, area query filter, database schema version, pagination metadata ranges, and Bronze-only/complete/not-captured counts. A running acquisition appears only as categories commit; use its local `data/104/category-runs/` summary for live progress.

`tools/capture_category_matrix.py` reads 104's official `JobCat.json` taxonomy and inspects or captures official `jobcat` codes at depth 0 (top-level), 1 (subcategory), or 2 (occupation). The occupation collector defaults to the verified maximum `--pagesize 30`; pagesize=31 returns HTTP 400. For local files, use `--capture`; pages are written as UTF-8 JSON under `data/104/categories/<jobcat>/batches/<batch-id>/`. For direct database capture, use `--capture --direct-postgres`; pages are kept in memory until the category passes pagination checks, then that category is committed atomically to PostgreSQL Bronze and eligible Silver tables. Direct mode stores page checksums and API/client metadata in `bronze.capture_pages`, and stores the requested jobcat in `bronze.capture_batches.source_jobcat`. Its lightweight client path skips the unused pandas job-table materialization and reuses the existing `cloudscraper` session within each worker thread; the Windows system-proxy mechanism and raw response contract stay the same. Legacy Power Query calls retain their DataFrame outputs. Runtime and peak-memory improvement still need a controlled before/after capture benchmark. The official taxonomy snapshot and run summary remain local; raw job pages do not. `--category-workers` (default 2) captures independent categories concurrently; `--workers` (default 2) controls pages per category, with their product capped at 4 simultaneous requests. `--delay` (default 0.8 seconds) sets a shared minimum interval across workers; HTTP 429 increases it by a factor of 1.5 up to 8 seconds; each 20 successful requests reduce it by 10% toward the configured minimum. Waiting workers recheck the shared schedule before sending. Responses are reordered and validated before persistence. Transient HTTP/network failures retry until success or operator interruption with shared exponential backoff and jitter capped at five minutes; there is no fixed retry-count limit. Ordinary HTTP 403 responses retry with shared exponential backoff and no fixed attempt limit. Explicit 401/407/418 and detected challenge or non-JSON responses stop workers for review. Collection is capped at 150 pages per category. A page-capped category is retained as Bronze-only. `--resume` skips same-day batches matching the query series, including saved pagination warnings and regardless of page size; omit `--resume` to recapture intentionally. Category batches never replace the keyword-based `data/104/current.json` pointer. Use repeatable `--code` options to limit a run. The official taxonomy is saved as a checksum-verified reference snapshot. `tools/capture104.py` and `tools/capture_matrix.py` remain available for explicit legacy keyword queries. All API calls keep the established `cloudscraper` and Windows system-proxy path. Never commit `data/`, credentials, cookies, proxy secrets, or unsanitized responses. Keep the reviewed sanitized fixture under `tools/tests/fixtures/`.

For scheduled nationwide capture from the repository root in Windows PowerShell, run `.\tools\launchers\download_all_occupations_docker.bat`.
The launcher defaults to Windows-host workers while keeping PostgreSQL as the
shared queue, lease store, request gate, and Bronze database. This checkout's
Linux Docker client receives a Cloudflare challenge from the 104 API, while the
same client on Windows succeeds. Set `PBI104_CAPTURE_RUNTIME=container` only
when that container's API route has been verified. The Compose profile accepts
runtime-only `PBI104_HTTP_PROXY`, `PBI104_HTTPS_PROXY`, and `PBI104_ALL_PROXY`
values from the ignored `.env`; a CONNECT tunnel alone did not clear this
checkout's Cloudflare challenge. Never put proxy credentials in the image or
Git. Defaults remain three workers, one page worker per category, pagesize 30,
and a shared adaptive request interval with a 0.8-second minimum. Resume and
live status details are in
[`docs/local-database.md`](../docs/local-database.md#scheduled-containerized-capture).

Transient HTTP/network failures and ordinary HTTP 403 responses use exponential retries with no fixed attempt limit. Explicit HTTP 401/407/418 and detected challenge or non-JSON responses stop workers for operator review. The Python tests use the reviewed fixture under `tools/tests/fixtures/` and synthetic transport responses; they do not prove current live API availability. Desktop refresh reads PostgreSQL Gold only; it does not refresh the 104 API or prove Power BI Service gateway access. Record those boundaries with each refresh report.

The legacy M probe generator writes its reproducible output to ignored `.optimization/probes/staging.pq`; it does not add generated M output to the maintained tool tree. The probe is not a gate for active database-reader queries. See [`tools/probes/README.md`](probes/README.md) for its limits and the current DAX probes.

## Local PostgreSQL archive

`tools/sync_lake_to_postgres.py` verifies immutable keyword batches under `data/104/series/` and occupation batches under `data/104/categories/<jobcat>/batches/`, while continuing to read legacy category batches from `series/`. It also imports the latest saved official category taxonomy. It defaults to dry-run; pass `--write` to apply `tools/sql/init_postgres_schema.sql` and commit each batch atomically. A page-capped capture, a reported-total mismatch, or a batch blocked by conflicting duplicate jobs is retained in Bronze with an explicit status and excluded from Gold; only complete batches that also pass Silver normalization enter the analytical tables. PostgreSQL runs locally through `docker compose`; copy `.env.example` to ignored `.env` and set a private password first. Bronze retains raw pages and category catalogs; Silver records requested category filters, actual job category codes, and official category names. Gold selects the latest complete batch per query series/date and exposes all nine `gold.pbi_*` model views. FactJob uses complete occupational-category observations without a keyword or area filter. See [docs/local-database.md](../docs/local-database.md) for start, import, refresh, and coverage boundaries.

### Browse current category data

Run `.\tools\launchers\view_acquisition_data.ps1` in Windows PowerShell, the script opens the printed `http://127.0.0.1:8765/` URL in the default browser. The local read-only page shows capture progress, category states, latest committed batches, and searchable Bronze job rows with raw JSON. It refreshes every 10 seconds; in-flight category pages appear after the category commits. Stop the background viewer with `Stop-Process -Id <PID>` using the printed process ID.
