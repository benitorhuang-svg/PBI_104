let
    Source = stg_Companies,
    InvalidKeys = Table.SelectRows(Source, each [custNo] = null or [custNo] = ""),
    Counts = Table.Group(Source, {"custNo"}, {{"rowCount", each Table.RowCount(_), Int64.Type}}),
    DuplicateKeys = Table.SelectRows(Counts, each [rowCount] > 1),
    Validated =
        if Table.RowCount(InvalidKeys) > 0 then
            error Error.Record("DimCompany null key", "custNo must be present for every company row.", [Rows = InvalidKeys])
        else if Table.RowCount(DuplicateKeys) > 0 then
            error Error.Record("DimCompany duplicate key", "stg_Companies must provide one row per custNo.", [Duplicates = DuplicateKeys])
        else
            Source,
    Output =
        Table.SelectColumns(
            Validated,
            {"custNo", "custName", "coIndustry", "coIndustryDesc"},
            MissingField.UseNull
        )
in
    Output
