# TASK-012 — Repair job and category report filters

## Goal

Keep report filters useful after `FactJob` moved from keyword captures to
official occupational-category observations.

## Scope

- Replace every report slicer bound to `FactJob.sourceKeyword`, which is blank
  for current `FactJob` rows.
- Use `DimJobCategory.jobCatDescription` for official category labels and
  `FactJob.jobName` for job-title selection.
- Allow category and skill bridge selections to filter `FactJob` rows.
- Preserve existing visual IDs, positions, page layouts, and approved design
  references. Do not build new report pages.

## Acceptance

- No report slicer references `FactJob.sourceKeyword`.
- Pages 01 and 03 use the official category label; Page 02 uses job title and
  category; Page 04 uses job title and category.
- `DimJobCategory` labels are nonblank and selected categories filter current
  jobs through `BridgeJobCategory`.
- Desktop refreshes all nine model tables, saves, closes, and reopens the PBIP.
- Report filters and model relationship changes pass project validation.

## Exclusions

This task does not capture additional nationwide data or claim nationwide
coverage. It does not change report measures or visual layout.
