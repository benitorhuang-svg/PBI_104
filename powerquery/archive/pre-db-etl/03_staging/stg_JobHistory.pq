let
    Source = src_104HistoryJobs,
    SnapshotColumns = Table.SelectColumns(Source, {
        "series_key", "snapshot_date", "snapshot_datetime", "job_no", "cust_no",
        "salary_low", "salary_high", "appear_date", "source_keyword", "source_area"
    }, MissingField.Error),
    SnapshotRenamed = Table.RenameColumns(SnapshotColumns, {
        {"series_key", "querySeriesKey"}, {"snapshot_date", "snapshotDate"},
        {"snapshot_datetime", "snapshotDateTime"}, {"job_no", "jobNo"},
        {"cust_no", "custNo"}, {"salary_low", "salaryLow"},
        {"salary_high", "salaryHigh"}, {"appear_date", "appearDate"},
        {"source_keyword", "sourceKeyword"}, {"source_area", "sourceArea"}
    }, MissingField.Error),
    SnapshotTyped = Table.TransformColumnTypes(SnapshotRenamed, {
        {"querySeriesKey", type text}, {"snapshotDate", type date},
        {"snapshotDateTime", type datetime}, {"jobNo", type text}, {"custNo", type text},
        {"salaryLow", type nullable number}, {"salaryHigh", type nullable number},
        {"appearDate", type nullable date}, {"sourceKeyword", type nullable text},
        {"sourceArea", type nullable text}
    }, "en-US"),
    SnapshotChecked = if Table.IsEmpty(SnapshotTyped) then
        error Error.Record("Empty database history", "Sync verified batches to PostgreSQL before refreshing Snapshot mode.", null)
        else SnapshotTyped,
    LiveDaily = Table.Group(Source, {"querySeriesKey", "snapshotDate"},
        {{"jobs", each fxStageJobs(_), type table}}),
    LiveOutput = if Table.RowCount(LiveDaily) = 0 then fxStageJobs(Source)
        else Table.Combine(LiveDaily[jobs]),
    Output = if pSourceMode = "Snapshot" then SnapshotChecked else LiveOutput
in
    Output
