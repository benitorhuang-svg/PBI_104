# TASK-011 — PostgreSQL ETL decoupling

## Goal

Move every loaded model table behind PostgreSQL ETL/Gold views. Power Query must
only read those model-ready views; DAX remains responsible for measures used by
report visuals. FactJob uses 104 official occupational-category captures,
without a keyword or area restriction in its Gold selection.

## Scope

- Keep immutable captures and existing Bronze/Silver history. Only complete,
  Silver-valid category batches can feed the current FactJob scope.
- Deduplicate category observations in Gold to one latest row per `jobNo`.
  Build company/area/skill/category dimensions and bridges from that selected
  observation so model relationships have matching keys.
- Keep `FactJobSnapshot` as the history of complete source series, including
  legacy keyword series for provenance; preserve grain
  `querySeriesKey × snapshotDate × jobNo`.
- Publish one PostgreSQL `gold.pbi_*` view for each of the nine loaded model
  tables, including the date dimension.
- Replace active M acquisition/staging logic with PostgreSQL view navigation
  and one-to-one Model references. Preserve prior M exports in an archive.
- Keep existing Semantic Model relationships and presentation measures; do not
  change PBIR visuals in this task.
- Update refresh/runbook documentation and preserve current source files,
  manifests, report definitions, lineage tags, and credentials.

## Current data boundary

The database currently contains complete occupational-category batches, but
they were captured with the prior two-area filter. The unlimited-area census
estimated about 42,466 page requests across the occupation codes and found
many API categories capped at 150 pages. The Gold selection itself has no area
filter and will accept future complete nationwide category batches. Until
those batches are captured, do not describe current imported coverage as all
Taiwan jobs. Incomplete or capped batches remain Bronze-only.

## Acceptance

- All nine active `04_Model` queries are direct references to PostgreSQL
  `gold.pbi_*` views; no active M query enumerates files, calls the 104 API,
  transforms rows, merges tables, or checks business keys.
- PostgreSQL views expose the existing model column names and grain; category
  fact rows are unique by `jobNo`, and bridge rows reference those facts.
- Power Query M exports and TMDL expressions synchronize, with only model
  queries enabled for load. `DimDate` is read from Gold, not computed in DAX.
- `FactJob` is selected from occupational-category captures and does not filter
  by keyword or region. Historical keyword snapshots remain separate rows in
  `FactJobSnapshot` with their original source metadata.
- Desktop applies the saved query/model definitions, refreshes all nine
  partitions, saves, then reopens without pending query changes. Record actual
  row counts and refresh time; distinguish this from SQL view execution time.
