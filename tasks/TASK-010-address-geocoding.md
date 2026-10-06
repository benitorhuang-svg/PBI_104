# TASK-010 — Address geocoding enrichment

## Goal

Use the local WGS84_TWD97 geocoder to enrich missing job coordinates in the
PBI_104 PostgreSQL archive while preserving 104 source values and making
approximate matches explicit.

## Scope

- Add a backward-compatible `matchLevel` to the geocoder API: exact normalized
  address text, address variant, street fallback, or POI alias.
- Add an additive PostgreSQL migration for area geocode results keyed by the
  existing `area_key`; never alter the immutable Bronze payload or original
  `silver.area_dimension` coordinates.
- Add an idempotent Python backfill command. It deduplicates normalized input
  addresses, sends batches of at most 2,000, validates every response, and
  writes only when `--write` is supplied.
- Expose source and derived coordinates separately in `gold.latest_observed_jobs`;
  exact text and address variants proven equivalent by Taiwan address
  standardization may populate effective coordinates. Other approximate matches
  remain review-only.
- Normalize Taiwan address forms before lookup: official `臺` place names,
  Arabic numerals for address-number components, and unpadded neighborhood
  numbers. Preserve road-name numerals and reject conflicting village or
  neighborhood values when comparing variants.
- Save a Google Maps search link only for a complete, plausible Taiwan address
  that the local geocoder cannot resolve. Do not import Google Maps coordinates
  into the persistent job archive.
- Add a PostgreSQL source query and merge effective coordinates into the existing
  `DimArea.lat` / `DimArea.lon`, with observed API coordinates taking precedence.
- Let the PBI_104 Compose stack orchestrate the read-only WGS84_TWD97 service
  from the sibling project directory without copying its SQLite data into PBI_104.
- Document local service and database setup, result quality, and limitations.

## Out of scope

- No PBIR/report visual or 104 acquisition changes. The existing DimArea table
  keeps its column contract and only its coordinate values gain exact matches.
- No edits to Bronze captures or `silver.area_dimension` source coordinates.
- No geocoding through a public third-party service.
- No automatic use of street, address-variant, or POI-alias results as effective
  coordinates.

## Acceptance

- Geocoder match classification is covered by unit tests and remains additive to
  existing response fields.
- Address variants are marked `ADDRESS_STANDARDIZED` only when the normalized
  street/house key matches and any village/neighborhood values do not conflict.
- Schema migration is repeatable and adds `silver.address_geocodes` plus Gold
  output columns without changing the original area key or coordinates.
- Backfill defaults to no database writes, deduplicates inputs, validates
  WGS84 ranges and response shape, and is idempotent when written.
- Tests cover exact/variant/approximate/not-found results and invalid API output.
- Run WGS84_TWD97 lint, PBI Python tests, project validator, local SQL migration,
  and Power BI Desktop refresh when the local connector credentials are available.

## Execution results (2026-10-06)

- PBI_104 Compose now runs PostgreSQL and the WGS84_TWD97 backend together. The
  backend bind-mounts the sibling project read-only; its container health check
  passes.
- PostgreSQL schema version 6 is applied. Three missing-coordinate area rows
  were queried and stored: one `ADDRESS_VARIANT`, two `NOT_FOUND`. All three
  original API coordinate pairs remain null; no geocoder point qualified as an
  effective coordinate. The default backfill preview is now idempotent and
  reports zero pending rows.
- WGS84_TWD97 lint, TypeScript type checks, and all three match-quality tests
  pass. The six new PBI geocoding tests and 35 acquisition, loader, and salary
  tests pass. `tools/validate_project.py` passes with 45 synchronized M
  expressions and the Desktop TMDL parser.
- Full test discovery has one environment error: the existing category test
  cannot import `pandas` from `.venv`; an attempted local package download
  stalled before installation. No dependency manifest was changed.
- Power BI Desktop refresh is `UNVERIFIED`. The project reopened with 45
  expressions, but model partitions remain `NoData`; the refresh did not reach
  PostgreSQL. No PBIP data refresh was saved. Inspect Desktop credentials and
  source privacy settings before relying on the enriched `DimArea` in a report.

## Follow-up (2026-10-06)

- Taiwan-standardized addresses now convert `台` to `臺`, normalize Chinese
  numerals only in address-number fields, remove leading zeroes from numbered
  address parts, and retain the complete canonical address beside the source
  input. Optional village/neighborhood details are ignored only when one side
  omits them; explicit conflicting values prevent promotion.
- PostgreSQL schema version 7 adds the canonical address, standardization
  version, and Google Maps search-link fields. One local doorplate match is now
  `ADDRESS_STANDARDIZED`; its effective coordinate comes from the local
  WGS84_TWD97 reference database. Two remaining rows (`xxx路xxx號` and
  `公司指定派遣的辦公室`) are incomplete/non-address text, so no Maps query or
  coordinate was manufactured for them.
- The official Taichung employment listing uses the canonical address
  `臺中市西屯區工業區六路7號` for the corresponding work site. Google Maps
  is kept as a manual search link for future valid local misses; its API
  coordinates are not archived because the current service terms limit normal
  coordinate caching to 30 days and restrict use with non-Google maps.
- The Power Query history loader now excludes manifests whose
  `paginationStatus` is not `PASS`, matching the existing Bronze-only policy for
  page-capped and API-total-mismatch captures. The configured snapshot folder
  contains 13 such batches.
- Python geocoding tests, PostgreSQL migration/import, and project validation
  pass. Desktop refresh remains `UNVERIFIED`: Docker Engine is inaccessible in
  this execution environment and PostgreSQL is not listening on port 5433. The
  ignored local `.env` contains the configured database password; it remains
  local and is not embedded in the model.
- The writable workspace is limited to PBI_104; no files in the sibling
  `WGS84_TWD97` project were changed. Read-only inspection confirms its API
  already normalizes NFKC, `台`/`臺`, punctuation, and Chinese numerals in address
  number fields for matching. Its response still returns the stored address
  and match level rather than a canonicalized address; the PBI backfill keeps
  its stricter coordinate-promotion check.

## Desktop refresh follow-up (2026-10-06)

- Power BI Desktop now connects to PostgreSQL and refreshed all nine model
  tables, including Gold-backed `DimArea`, in 28.33 seconds. The PBIP was
  saved, closed, and reopened; the reopened model showed nine Ready partitions.
- This resolves the earlier `UNVERIFIED` Desktop refresh status. The model
  refresh confirms the query connection and load path; it does not change the
  geocoder's recorded match classifications or imply nationwide coverage.
