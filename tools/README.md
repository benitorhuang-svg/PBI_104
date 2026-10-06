# Local validation tools

Run these commands from the repository root in Windows PowerShell:

```powershell
python -m unittest discover -s tools/tests -v
python tools/sync_queries.py
python tools/validate_project.py
.\tools\desktop_model.ps1 -Operation Parse
```

`Parse` checks checked-in TMDL with the Power BI Desktop assemblies installed on this machine. `Inventory` and `Dax` require exactly one open Power BI Desktop model. `Inventory` reports loaded tables and partition states; `Dax -QueryFile <path>` executes a read-only DAX query against that model. Keep maintained DAX checks under `tools/probes/`. The Desktop helper no longer creates temporary model tables.

`ImportQueries` copies M expressions from disk into the open model and calls `SaveChanges`; use it only when deliberately updating that Desktop session. It does not create tables, relationships, measures, or report visuals. After an intended model update, refresh in Desktop, verify the changed layer and load states, save, close, and reopen the PBIP.

## Acquisition and local data

`tools/capture_category_matrix.py` reads 104's official `JobCat.json` taxonomy and inspects or captures official `jobcat` codes at depth 0 (top-level), 1 (subcategory), or 2 (occupation). The occupation collector defaults to the verified maximum `--pagesize 30`; pagesize=31 returns HTTP 400. For local files, use `--capture`; pages are written as UTF-8 JSON under `data/104/categories/<jobcat>/batches/<batch-id>/`. For direct database capture, use `--capture --direct-postgres`; pages are kept in memory until the category passes pagination checks, then that category is committed atomically to PostgreSQL Bronze and eligible Silver tables. Direct mode stores page checksums and API/client metadata in `bronze.capture_pages`, and stores the requested jobcat in `bronze.capture_batches.source_jobcat`. The official taxonomy snapshot and run summary remain local; raw job pages do not. `--category-workers` (default 2) captures independent categories concurrently; `--workers` (default 2) controls pages per category, with their product capped at 4 simultaneous requests. `--delay` (default 0.8 seconds) sets a shared minimum interval across workers; HTTP 429 doubles it, and successful requests gradually reduce it. Responses are reordered and validated before persistence. Transient HTTP/network failures use exponential backoff with jitter (five attempts total including the initial request, 30-second delay cap); access-denied responses stop all workers, and exhausted retries pause the run for later `--resume`. Collection is capped at 150 pages per category. A page-capped category is retained as Bronze-only. `--resume` skips matching same-day batches in the selected store. Category batches never replace the keyword-based `data/104/current.json` pointer. Use repeatable `--code` options to limit a run. The official taxonomy is saved as a checksum-verified reference snapshot. `tools/capture104.py` and `tools/capture_matrix.py` remain available for explicit legacy keyword queries. All API calls keep the established `cloudscraper` and Windows system-proxy path. Never commit `data/`, credentials, cookies, proxy secrets, or unsanitized responses. Keep the reviewed sanitized fixture under `samples/raw/`.

The Python tests use saved fixtures and synthetic transport responses; they do not prove current live API availability. Desktop refresh reads PostgreSQL Gold only; it does not refresh the 104 API or prove Power BI Service gateway access. Record those boundaries with each refresh report.

`tools/build_stage_probe.py` regenerates `tools/probes/staging.pq` from archived pre-database M sources and the reviewed fixture. It is a legacy diagnostic, not a gate for the active database-reader queries. The current Desktop SDK path could not execute this temporary M table probe reliably; it does not validate the current PostgreSQL ETL contract.

## Local PostgreSQL archive

`tools/sync_lake_to_postgres.py` verifies immutable keyword batches under `data/104/series/` and occupation batches under `data/104/categories/<jobcat>/batches/`, while continuing to read legacy category batches from `series/`. It also imports the latest saved official category taxonomy. It defaults to dry-run; pass `--write` to apply `tools/sql/init_postgres_schema.sql` and commit each batch atomically. A page-capped capture, a reported-total mismatch, or a batch blocked by conflicting duplicate jobs is retained in Bronze with an explicit status and excluded from Gold; only complete batches that also pass Silver normalization enter the analytical tables. PostgreSQL runs locally through `docker compose`; copy `.env.example` to ignored `.env` and set a private password first. Bronze retains raw pages and category catalogs; Silver records requested category filters, actual job category codes, and official category names. Gold selects the latest complete batch per query series/date and exposes all nine `gold.pbi_*` model views. FactJob uses complete occupational-category observations without a keyword or area filter. See [docs/local-database.md](../docs/local-database.md) for start, import, refresh, and coverage boundaries.
