let
    Source = stg_Jobs,
    InvalidKeyRows =
        Table.SelectRows(
            Source,
            each [jobNo] = null or [jobNo] = "" or [snapshotDate] = null or [snapshotDate] = ""
        ),
    WithSnapshotDate =
        Table.AddColumn(
            Source,
            "snapshotDateValue",
            each try Date.FromText(Text.Start(Text.From([snapshotDate]), 10)) otherwise null,
            type nullable date
        ),
    InvalidDateRows = Table.SelectRows(WithSnapshotDate, each [snapshotDateValue] = null),
    PairCounts =
        Table.Group(
            WithSnapshotDate,
            {"snapshotDateValue", "jobNo"},
            {{"rowCount", each Table.RowCount(_), Int64.Type}}
        ),
    DuplicatePairs = Table.SelectRows(PairCounts, each [rowCount] > 1),
    Validated =
        if Table.RowCount(InvalidKeyRows) > 0 then
            error Error.Record("FactJobSnapshot null key", "snapshotDate and jobNo must be present.", [Rows = InvalidKeyRows])
        else if Table.RowCount(InvalidDateRows) > 0 then
            error Error.Record("FactJobSnapshot invalid date", "snapshotDate must be an ISO date or datetime.", [Rows = InvalidDateRows])
        else if Table.RowCount(DuplicatePairs) > 0 then
            error Error.Record("FactJobSnapshot duplicate grain", "FactJobSnapshot grain requires snapshotDate × jobNo uniqueness.", [Duplicates = DuplicatePairs])
        else
            WithSnapshotDate,
    Selected =
        Table.SelectColumns(
            Validated,
            {
                "snapshotDateValue", "snapshotDateTime", "jobNo", "custNo", "jobAddrNo",
                "appearDate", "salaryLow", "salaryHigh", "applyCnt", "remoteWorkType",
                "sourceKeyword", "sourceArea", "sourcePage", "sourcePageSize"
            },
            MissingField.UseNull
        ),
    Renamed = Table.RenameColumns(Selected, {{"snapshotDateValue", "snapshotDate"}}, MissingField.Ignore),
    Typed =
        Table.TransformColumns(
            Renamed,
            {
                {"snapshotDateTime", each try DateTimeZone.RemoveZone(DateTimeZone.FromText(Text.From(_))) otherwise null, type nullable datetime}
            },
            null,
            MissingField.Ignore
        )
in
    Typed
