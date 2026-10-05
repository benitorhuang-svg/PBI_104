# 04_Model query source

These seven `.pq` files are the complete M source for the persisted model
queries. In Power BI Desktop they are named with the `mdl_` prefix
(`mdl_FactJob`, `mdl_FactJobSnapshot`, `mdl_DimCompany`, `mdl_DimArea`,
`mdl_DimSkill`, `mdl_DimJobCategory`, `mdl_BridgeJobSkill`) because the current
Mashup authoring surface treats a named expression and a loaded table with
the same identifier as duplicate members. The loaded semantic tables retain
the unprefixed star-schema names.

`DimDate` is intentionally not an M query. It is a semantic-model calculated
table over the loaded `FactJob[appearDate]` range; this keeps the date
dimension in the Semantic Model layer and avoids a second staging/API access.

Only these seven `mdl_` queries are Enable Load. Parameters, Functions,
Source, and Staging remain Disable Load.
