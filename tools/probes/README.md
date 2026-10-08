# Diagnostic probes

These files are explicit diagnostic inputs. They are not run by the normal project validator.

| File | Purpose | Boundary |
| --- | --- | --- |
| `semantic-model-contract.dax` | Compare key skill/category measures with bridge-based counts; check intersections, populated job skills, and date relationships. | Run against an open Power BI Desktop model with `tools/desktop/desktop_model.ps1 -Operation Dax -QueryFile <path>`. |
| `filter-propagation-smoke.dax` | Small read-only query for the skill-filter path into active jobs. | Smoke check only; it does not replace the broader semantic contract query. |
| `build_stage_probe.py` | Rebuild the retired pre-database M edge-case probe from archived M functions and the reviewed fixture. | Writes `.optimization/probes/staging.pq`; native Power Query execution did not complete in the earlier attempt, and this is not an active-model gate. |

The old `src_104Result` source-contract query is kept with its retired dependencies at `powerquery/archive/pre-db-etl/probes/source-contract.pq`. The active model reads PostgreSQL Gold views and does not use these legacy probes.
