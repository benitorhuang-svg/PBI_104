# 04_Model query source

The nine active `.pq` files are one-to-one pass-throughs to PostgreSQL Source queries:
`FactJob`, `FactAcquisitionCategory`, `DimCompany`, `DimArea`, `DimSkill`,
`DimJobCategory`, `BridgeJobSkill`, `BridgeJobCategory`, and `DimDate`.

Power BI Desktop persists their expressions with the `mdl_` prefix because the
Mashup authoring surface treats a named expression and loaded table with the
same identifier as duplicate members. The loaded semantic tables retain their
public star-schema names.

Every model expression returns a Gold view without M transformations. Only
these nine queries are Enable Load; parameters, functions, and source readers
remain Disable Load.

`FactJobSnapshot` and `FactSalaryObservation` remain in PostgreSQL Gold, but
their Power Query readers are paused in the semantic model as of 2026-10-10.
Their v21 readers are preserved in `powerquery/archive/paused-facts-v21/`.
Re-enable them only after the Gold grain, complete-batch filter, and relationship
contracts have been validated for each source platform.
