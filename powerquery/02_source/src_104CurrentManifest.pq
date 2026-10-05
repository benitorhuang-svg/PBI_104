let
    Root = Text.TrimEnd(pSnapshotRoot, {"\", "/"}),
    DefaultCurrent = try Json.Document(File.Contents(Root & "\current.json")) otherwise null,
    ExpectedRequest = [baseUrl = pBaseUrl, keyword = pKeyword, area = pArea, jobsource = pJobSource, mode = pMode, order = pOrder, page = pPage, pagesize = pPageSize],
    MatchesExpected = (m as any) as logical =>
        Value.Is(m, type record) and
        Record.FieldOrDefault(m, "schemaVersion", null) = 1 and
        Value.Is(Record.FieldOrDefault(m, "request", null), type record) and
        List.AllTrue(List.Transform(Record.FieldNames(ExpectedRequest), each Record.FieldOrDefault(m[request], _, null) = Record.Field(ExpectedRequest, _))),
    SelectedManifest =
        if MatchesExpected(DefaultCurrent) then DefaultCurrent
        else
            let
                SeriesFolder = Root & "\series",
                Files = try Folder.Files(SeriesFolder) otherwise null,
                ManifestFiles = if Files = null then #table({}, {}) else Table.SelectRows(Files, each [Name] = "manifest.json"),
                Parsed = Table.AddColumn(ManifestFiles, "manifest", each try Json.Document([Content]) otherwise null, type nullable record),
                Matching = Table.SelectRows(Parsed, each MatchesExpected([manifest])),
                Sorted = Table.Sort(Matching, {{"Date modified", Order.Descending}})
            in
                if Table.RowCount(Sorted) > 0 then Sorted{0}[manifest]
                else error Error.Record("Snapshot parameters differ", "Capture a complete batch matching the Power Query parameters before refresh.", [keyword = pKeyword, area = pArea])
in
    SelectedManifest
