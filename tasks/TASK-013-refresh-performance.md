# TASK-013 — PostgreSQL Import refresh performance (completed 2026-10-06)

## Goal and scope

Reduce avoidable PostgreSQL view work while preserving the nine loaded model
tables and their row/column contracts. Measure database plans and repeated
full-model Desktop refreshes. Do not change PBIR, DAX, table grain, model
columns, database credentials, or acquisition coverage.

## Changes

- Removed the second read of `silver.job_snapshots` from the latest complete
  category-job scope; the `DISTINCT ON` result now carries the fields required
  by the fact view.
- Reused company attributes already present in that scope, deduplicated area
  keys before joining area/geocode details, and calculated date bounds in one
  aggregate pass.
- Made the existing area-key type migration conditional so the full schema
  script can be reapplied when dependent Gold views exist.
- Kept the default PostgreSQL schema/view navigator. The
  `CreateNavigationProperties=false` trial was slower. The native `Query`
  connector trial stalled without issuing a PostgreSQL query and was reverted.

## Evidence and limits

- `EXCEPT ALL` comparisons returned zero differences for `FactJob` (3,448
  rows), `DimCompany` (1,567), `DimArea` (2,008), and `DimDate` (218).
- Across the nine full-view plans, shared hit blocks fell from 375,262 to
  275,736 (-26.5%). The serial sum of one set of plans moved from 439.6 ms to
  407.4 ms (-7.3%); all plans reported zero shared disk-read blocks. These are
  PostgreSQL plan measurements, not Power BI refresh measurements.
- XMLA full-refresh samples before the SQL change were 1,689 / 1,761 / 1,974
  ms (median 1,761 ms). Samples immediately after were 1,637 / 1,642 / 1,771
  ms (median 1,642 ms). After reopening the final PBIP, samples were 10,339 /
  3,399 / 3,778 ms (median 3,778 ms). Variation is too large to establish a
  repeatable end-to-end refresh improvement; no such claim is made.
- Final Desktop inventory: all nine partitions Ready, 21 expressions, eight
  relationships. DAX validation retained the row counts, unique FactJob key,
  category/skill selection behavior, and zero orphan date keys.
- `python tools/sync_queries.py`, `python tools/validate_project.py`, and the
  Desktop TMDL parser passed. Desktop was saved, closed, and reopened.

## Result

Keep the SQL view simplifications because they preserve exact rows while
reducing logical PostgreSQL buffer visits. Keep the normal Gold-view
navigation query. Full Power BI refresh speed remains unproven; future timing
comparisons need controlled repeated runs under the same Desktop state.
