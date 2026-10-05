let
    Daily = Table.Group(src_104HistoryJobs, {"snapshotDate"}, {{"jobs", each fxStageJobs(_), type table}}),
    Output = if Table.RowCount(Daily) = 0 then fxStageJobs(src_104HistoryJobs) else Table.Combine(Daily[jobs])
in
    Output
