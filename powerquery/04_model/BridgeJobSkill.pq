let
    Source = stg_JobSkills,
    InvalidKeys = Table.SelectRows(Source, each [jobNo] = null or [jobNo] = "" or [skillCode] = null or [skillCode] = ""),
    PairCounts = Table.Group(Source, {"jobNo", "skillCode"}, {{"rowCount", each Table.RowCount(_), Int64.Type}}),
    DuplicatePairs = Table.SelectRows(PairCounts, each [rowCount] > 1),
    Validated =
        if Table.RowCount(InvalidKeys) > 0 then
            error Error.Record("BridgeJobSkill null key", "jobNo and skillCode must be present for every bridge row.", [Rows = InvalidKeys])
        else if Table.RowCount(DuplicatePairs) > 0 then
            error Error.Record("BridgeJobSkill duplicate pair", "Bridge grain requires jobNo × skillCode uniqueness.", [Duplicates = DuplicatePairs])
        else
            Source,
    Output = Table.SelectColumns(Validated, {"jobNo", "skillCode", "skillDescription"}, MissingField.UseNull)
in
    Output
