let
    Source = stg_JobCategories,
    InvalidKeys = Table.SelectRows(Source, each [jobNo] = null or [jobNo] = "" or [jobCatCode] = null),
    PairCounts = Table.Group(Source, {"jobNo", "jobCatCode"}, {{"rowCount", each Table.RowCount(_), Int64.Type}}),
    DuplicatePairs = Table.SelectRows(PairCounts, each [rowCount] > 1),
    Validated =
        if Table.RowCount(InvalidKeys) > 0 then
            error Error.Record("BridgeJobCategory null key", "jobNo and jobCatCode must be present for every bridge row.", [Rows = InvalidKeys])
        else if Table.RowCount(DuplicatePairs) > 0 then
            error Error.Record("BridgeJobCategory duplicate pair", "Bridge grain requires jobNo × jobCatCode uniqueness.", [Duplicates = DuplicatePairs])
        else
            Source,
    Output = Table.SelectColumns(Validated, {"jobNo", "jobCatCode", "jobCatDescription"}, MissingField.UseNull)
in
    Output
