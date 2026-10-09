# Diagnostic probes

These files are explicit diagnostic inputs. They are not run by the normal project validator.

| File | Purpose | Boundary |
| --- | --- | --- |
| `semantic-model-contract.dax` | Compare key skill/category measures with bridge-based counts; check intersections, populated job skills, and date relationships. | Run against an open Power BI Desktop model with `tools/desktop/desktop_model.ps1 -Operation Dax -QueryFile <path>`. |
| `filter-propagation-smoke.dax` | Small read-only query for the skill-filter path into active jobs. | Smoke check only; it does not replace the broader semantic contract query. |
| `probe_yes123_acquisition.py` | Limited live probe of yes123 request, pagination, parsing, salary, and address fields. | Makes live requests and saves its result to `tools/tests/fixtures/yes123-sample-probe.json` by default; it does not establish bulk-use rights or field mappings. |

The old `src_104Result` source-contract query is kept with its retired dependencies at `powerquery/archive/pre-db-etl/probes/source-contract.pq`. Its former staging-probe generator was removed because it exercised only the retired pre-database M path; neither is an active-model gate. The active model reads PostgreSQL Gold views.
