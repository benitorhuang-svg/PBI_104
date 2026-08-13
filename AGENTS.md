# Repository Guidelines

## Project Structure

Open `PBI_104.pbip` as the entry point. `PBI_104.Report/` contains PBIR definitions; `PBI_104.SemanticModel/definition/` contains TMDL tables, relationships, and culture metadata. Planning belongs in `docs/`, work specifications in `tasks/`, future M scripts in `powerquery/`, sanitized fixtures in `samples/`, and approved references in `report-design/`. Treat `.pbi/` and `cache.abf` as local state.

## Architecture and Load Boundaries

Power Query must use these groups and one-way dependencies:

`00_Parameters` / `01_Functions` → `02_Source` → `03_Staging` → `04_Model`

- Source acquires raw API data and technical metadata only.
- Staging owns expansion, cleaning, typing, normalization, and data-quality handling.
- Create an `fx` only for repeated, stable rules with explicit inputs and outputs.
- Model queries expose clean, grain-defined tables for loading.
- Parameters, Functions, Source, and Staging default to Disable Load; only Model queries Enable Load.
- Semantic Model responsibilities—relationships, DAX, formats, hierarchies, and RLS—are outside Power Query. PBIR visuals are a separate report layer.

## Development and Validation

- `Start-Process .\PBI_104.pbip` opens the project in Power BI Desktop.
- `python -c "import pandas, cloudscraper; print('ok')"` checks current Python refresh dependencies.
- Refresh in Desktop, save, close, and reopen after each TASK. Validate only the layer changed, its row/column contract, error path, and Enable Load state.
- Read this file, `README_TASKS.md`, and the active TASK before editing. Inventory existing files and queries first; do not duplicate functionality or expand scope across TASKs.
- When a future TASK delivers Power Query code, provide the complete code for every required query; do not replace unchanged queries with references to older versions.

## Data, Style, and Safety Rules

Use UTF-8, two-space JSON indentation, existing TMDL tab nesting, four-space Python indentation, and descriptive M step names. Preserve generated IDs and lineage tags unless Power BI Desktop intentionally regenerates them. Never guess an unverified API field, nested shape, key, pagination rule, or business meaning; mark it `BLOCKED` and record required evidence. Preserve the proven `cloudscraper` plus Windows system-proxy mechanism until a tested replacement exists. Never hard-code cookies, Cloudflare tokens, credentials, or secrets, and never manufacture rows to hide an API failure.

Do not build report pages during a Power Query or model TASK. Before any PBIR edit, require a Git baseline and follow approved `report-design/*.png`; do not use a hand-drawn style. This directory currently has no Git metadata. Do not commit, publish, or initialize Git unless the user explicitly requests it.
