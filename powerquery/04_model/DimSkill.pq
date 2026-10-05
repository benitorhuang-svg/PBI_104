let
    Source = stg_Skills,
    InvalidKeys = Table.SelectRows(Source, each [skillCode] = null or [skillCode] = ""),
    Counts = Table.Group(Source, {"skillCode"}, {{"rowCount", each Table.RowCount(_), Int64.Type}}),
    DuplicateKeys = Table.SelectRows(Counts, each [rowCount] > 1),
    Validated =
        if Table.RowCount(InvalidKeys) > 0 then
            error Error.Record("DimSkill null key", "skillCode must be present for every skill row.", [Rows = InvalidKeys])
        else if Table.RowCount(DuplicateKeys) > 0 then
            error Error.Record("DimSkill duplicate key", "stg_Skills must provide one row per skillCode.", [Duplicates = DuplicateKeys])
        else
            Source
in
    Validated
