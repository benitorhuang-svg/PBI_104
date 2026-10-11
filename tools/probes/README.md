# Diagnostic probes

These files are explicit diagnostic inputs. They are not run by the normal project validator.

| File | Purpose | Boundary |
| --- | --- | --- |
| `semantic-model-contract.dax` | Compare key skill/category measures with bridge-based counts; check intersections, populated job skills, and the active FactJob date relationship. | Run against an open Power BI Desktop model with `tools/desktop/desktop_model.ps1 -Operation Dax -QueryFile <path>`. Snapshot and salary fact checks remain paused with those model tables. |
| `filter-propagation-smoke.dax` | Small read-only query for the skill-filter path into active jobs. | Smoke check only; it does not replace the broader semantic contract query. |
| `map-switching.dax` | Compare map point/gate counts across domestic, overseas, and unknown scopes and verify FactJob uniqueness. | Read-only DAX proxy; it does not replace a timed Desktop interaction benchmark. |
| `map-tooltip-company.dax` | Check that map tooltip company/address measures evaluate against location groups without a query error. | Read-only DAX probe; aggregated locations may intentionally return `多家公司／請選取`. |
| `map-tooltip-point.dax` | Check the screenshot coordinate's address and company tooltip behavior. | Read-only point probe; it confirms ambiguous same-coordinate rows are not reduced to an arbitrary company. |
| `map-tooltip-company-point-names.dax` | List the source company names at the screenshot coordinate for investigation. | Read-only evidence probe; it is not a replacement for the filtered tooltip measure. |
| `area-category-intersection.dax` | Check county/category intersection counts and whether either dimension list contracts under the other filter. | Read-only DAX probe for filter-direction diagnosis; it does not change model relationships. |
| `area-hierarchy-anomalies.dax` | Find township labels that still contain a county/city suffix or other malformed location text. | Read-only DAX regression probe for the county/township cleanup; an empty result is expected. |
| `platform-scope.dax` | Verify scope job counts and coordinate-gated map groups separately for 104 and yes123. | Read-only DAX regression probe for explicit-label location classification; it does not add coordinates. |
| `probe_yes123_acquisition.py` | Limited live probe of yes123 request, pagination, parsing, salary, and address fields. | Makes live requests and saves its result to `tools/tests/fixtures/yes123-sample-probe.json` by default; it does not establish bulk-use rights or field mappings. |

The old `src_104Result` source-contract query is kept with its retired dependencies at `powerquery/archive/pre-db-etl/probes/source-contract.pq`. Its former staging-probe generator was removed because it exercised only the retired pre-database M path; neither is an active-model gate. The active model reads PostgreSQL Gold views.
