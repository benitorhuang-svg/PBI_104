let
    Source = stg_Jobs,
    InvalidKeyRows =
        Table.SelectRows(
            Source,
            each [jobNo] = null or [jobNo] = ""
        ),
    DuplicateCounts =
        Table.Group(
            Source,
            {"jobNo"},
            {{"rowCount", each Table.RowCount(_), Int64.Type}}
        ),
    DuplicateKeys = Table.SelectRows(DuplicateCounts, each [rowCount] > 1),
    Validated =
        if Table.RowCount(InvalidKeyRows) > 0 then
            error Error.Record("FactJob null key", "jobNo must be present for every model row.", [Rows = InvalidKeyRows])
        else if Table.RowCount(DuplicateKeys) > 0 then
            error Error.Record("FactJob duplicate key", "FactJob grain requires one row per jobNo.", [Duplicates = DuplicateKeys])
        else
            Source,
    Selected =
        Table.SelectColumns(
            Validated,
            {
                "jobNo", "custNo", "custName", "coIndustry", "coIndustryDesc",
                "jobName", "description", "descSnippet", "jobAddress", "jobAddrNo",
                "jobAddrNoDesc", "lat", "lon", "salaryLowRaw", "salaryHighRaw",
                "salaryLow", "salaryHigh", "appearDateRaw", "appearDate", "applyCnt",
                "jobCatRaw", "pcSkillsRaw", "tagsRaw", "labelsRaw", "linkRaw",
                "remoteWorkType", "languageRequirementsRaw", "majorRaw", "acceptRoleRaw",
                "snapshotDate", "snapshotDateTime", "sourceKeyword", "sourceArea",
                "sourcePage", "sourcePageSize", "areaKey", "jobLink"
            },
            MissingField.UseNull
        )
in
    Selected
