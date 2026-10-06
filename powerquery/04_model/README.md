# 04_Model query source

The nine `.pq` files are one-to-one pass-throughs to PostgreSQL Source queries:
`FactJob`, `FactJobSnapshot`, `DimCompany`, `DimArea`, `DimSkill`,
`DimJobCategory`, `BridgeJobSkill`, `BridgeJobCategory`, and `DimDate`.

Power BI Desktop persists their expressions with the `mdl_` prefix because the
Mashup authoring surface treats a named expression and loaded table with the
same identifier as duplicate members. The loaded semantic tables retain their
public star-schema names.

Every model expression returns a Gold view without M transformations. Only
these nine queries are Enable Load; parameters, functions, and source readers
remain Disable Load.
