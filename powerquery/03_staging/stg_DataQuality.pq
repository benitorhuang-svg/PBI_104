let
    Jobs = Table.Buffer(stg_Jobs),
    NestedMissing = (field as text) as number => Table.RowCount(Table.SelectRows(Jobs, each Record.Field(_, field) = null)),
    Output = #table(type table [check = text, rows = Int64.Type], {
        {"raw_rows", Table.RowCount(src_104Jobs)},
        {"unique_jobs", Table.RowCount(Jobs)},
        {"identical_duplicates_collapsed", Table.RowCount(src_104Jobs) - Table.RowCount(Jobs)},
        {"invalid_numeric_rows", Table.RowCount(Table.SelectRows(Jobs, each [qualityIssues] <> ""))},
        {"invalid_appear_date", Table.RowCount(Table.SelectRows(Jobs, each [appearDateQuality] = "invalid"))},
        {"missing_appear_date", Table.RowCount(Table.SelectRows(Jobs, each [appearDateQuality] = "missing"))},
        {"missing_skills", NestedMissing("pcSkillsRaw")},
        {"missing_categories", NestedMissing("jobCatRaw")},
        {"missing_job_link", Table.RowCount(Table.SelectRows(Jobs, each [jobLink] = null))}})
in
    Output
