# Page 05 design brief — 下載戰情室

## Page purpose

按來源平台監看原生職類擷取狀態、批次品質、分頁完整度及各職類回傳筆數。平台切換只比較來源自己的擷取狀態，不把不同平台的分類碼視為同一套分類。

## Data source and grain

- `FactAcquisitionCategory`：每個 `sourcePlatform` 與來源原生職類一列。
- 104 rows come from the persisted distributed category queue and retain its queue states.
- yes123 rows come from `silver.category_crosswalk` plus persisted `bronze.capture_batches` for `YES123_WORK_MODE` (`2_`) only. The 402 `YES123_JOB_MODE` batches and their batch-linked rows were deleted from the yes123 source database; migration 025 remains prepared with the WORK_MODE scope, L2 parent-code projection, and L1/L3 depth values. It has not been applied to the reporting database.
- yes123 state is derived from the latest recorded capture date: `DONE` means a `COMPLETE` batch with `paginationStatus=PASS`; `STALE` means its newest batch predates the latest capture date; `NOT_CAPTURED` means no category batch is recorded. The yes123 runner does not persist a live queue or failed-attempt ledger, so the page must not label these rows as live pending or failed work.
- The result chart groups `resultStatus` (`結果狀態`) to compare captured, captured-with-warning, and skipped categories by platform. The table separately retains `captureStatus` as `批次品質` for page-total and Silver normalization warnings, plus `佇列狀態` for queue state.
- `職缺筆數` is the sum of per-category returned rows, not a distinct cross-category job count.

## Filters and interactions

- `FactAcquisitionCategory[職缺平台]` filters all visuals on this page.
- The Page 05 filter is independent from the `FactJob[sourcePlatform]` slicers on Pages 01–04 because the two facts have different grains and different persisted status sources.
- The lower detail table retains complete source-native codes. The upper matrix groups both platforms by their source L2 key; yes123 displays the `2_` family prefix, and no cross-platform category mapping is inferred.
- The upper source-category matrix shows yes123 L1 root rows and aggregates 104 detail categories by their L2 parent code. Its summary measures keep the parent-row count for yes123 and sum 104 child categories.
- Selecting an upper L2 row filters the lower detail table through the shared L2 key. The upper matrix has no L1-only visual filter, so that filter cannot suppress the L3 rows in the lower table.
- The lower detail table filters `職類階層顯示用 = 2` (L3) and uses `職類代碼` / `職類名稱`.
- For the requested report hierarchy, yes123 uses the matching Work Mode code ending in `_0000` as its L1 display row; L3 rows keep their complete native codes. The published catalog has no separate root code, so this is a report display convention, not a claim of an official cross-platform mapping.

## Layout and labels

- Keep the supplied 1280 × 720 operational dashboard layout, compact horizontal tile platform slicer without a title above the completion gauge, download-result chart, category summary matrix, and full-width detail table.
- Label the status chart `下載結果分布 / CAPTURE RESULT` and the category matrix `來源職類 / SOURCE CATEGORY`.
- The detail table includes platform, native category code/name, status, batch count, returned job rows, batch quality, and pagination status.
- Data-pane fields keep their existing Chinese names. Visual headings and filter names identify the L1 and L3 fields in Chinese.
- Subtitle states that categories remain platform-native and are not crosswalked.
