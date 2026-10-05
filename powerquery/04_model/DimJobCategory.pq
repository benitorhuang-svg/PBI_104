let
    Source = stg_JobCategories,
    InvalidKeys = Table.SelectRows(Source, each [jobCatCode] = null),
    Grouped =
        Table.Group(
            Table.SelectRows(Source, each [jobCatCode] <> null),
            {"jobCatCode"},
            {
                {"jobCatDescription", each List.First(List.RemoveNulls([jobCatDescription]), null), type nullable text},
                {
                    "descriptionCount",
                    each List.Count(List.Distinct(List.RemoveNulls([jobCatDescription]))),
                    Int64.Type
                }
            }
        ),
    Conflicts = Table.SelectRows(Grouped, each [descriptionCount] > 1),
    Validated =
        if Table.RowCount(InvalidKeys) > 0 then
            error Error.Record("DimJobCategory null key", "jobCatCode must be present for every category row.", [Rows = InvalidKeys])
        else if Table.RowCount(Conflicts) > 0 then
            error Error.Record("DimJobCategory description conflict", "A jobCatCode has multiple observed descriptions.", [Conflicts = Conflicts])
        else
            Table.RemoveColumns(Grouped, {"descriptionCount"})
in
    Validated
