# TASK-014 — Direct PostgreSQL category capture

## Goal

Allow verified 104 occupation-category captures to be written directly to the
existing PostgreSQL ETL without creating per-page job JSON files.

## Scope

- Keep page fetching on the existing bounded worker pool and exponential retry
  policy.
- Allow independent occupation categories to run concurrently while limiting
  `category_workers * page_workers` to four active API page requests, with a
  shared minimum request interval of 0.8 seconds by default. HTTP 429 responses
  increase the shared interval; successful requests gradually lower it.
- Default to the verified maximum `pagesize=30`; the boundary probe at 31 failed.
- Share retry backoff and fail-fast access-denial handling across category
  workers.
- Hold one category's pages outside a database transaction while fetching.
- Validate pagination and normalize the batch before opening its commit
  transaction.
- Commit each category atomically to Bronze, and to Silver only when pagination
  and normalization both pass. A page-capped or normalization-blocked capture
  remains Bronze-only.
- Record `source_jobcat` and `snapshot_date` on `bronze.capture_batches`.
- Preserve page checksum, row count, API response metadata, and client metadata
  in `bronze.capture_pages`; preserve each raw job payload in
  `bronze.raw_job_rows`.
- Let `--resume` skip matching same-day batches already in PostgreSQL.
- Keep file capture and lake import available for existing and explicit file
  workflows. The category catalogue snapshot and run summary remain local.

## Out of scope

- Power Query, Semantic Model, PBIR, Gold contracts, and business
  classification changes.
- Partial-page commits or promotion of incomplete categories.
- Changes to the established `cloudscraper` and Windows system-proxy path.

## Acceptance

- Schema migration 10 upgrades existing databases idempotently and backfills
  `source_jobcat` from the saved request JSON.
- Direct capture stores no per-page job JSON files; one category commits in one
  transaction after page validation.
- Matching same-day database batches are skipped on resume.
- Complete batches enter existing Silver/Gold paths. Pagination mismatches and
  normalization conflicts remain queryable in Bronze only.
- Existing lake batches remain importable, including their page-level metadata.
- The current direct capture can be resumed after interruption without
  replacing prior batch identities or keyword pointers.
