let
    Root = Text.TrimEnd(pSnapshotRoot, {"\", "/"}),
    Current = src_104CurrentManifest,
    BatchFolder = Root & "\series\" & Current[seriesKey] & "\batches",
    Files = Folder.Files(BatchFolder),
    Manifests = Table.SelectRows(Files, each [Name] = "manifest.json"),
    Parsed = Table.AddColumn(Manifests, "manifest", each Json.Document([Content]), type record),
    SameSeries = Table.SelectRows(Parsed, each [manifest][seriesKey] = Current[seriesKey]),
    WithDate = Table.AddColumn(SameSeries, "snapshotDay", each [manifest][snapshotDate], type text),
    WithTime = Table.AddColumn(WithDate, "snapshotTime", each DateTimeZone.FromText([manifest][snapshotDateTime]), type datetimezone),
    WithBatchId = Table.AddColumn(WithTime, "batchId", each [manifest][batchId], type text),
    LatestDaily = Table.Group(WithBatchId, {"snapshotDay"}, {{"manifest", each Table.Sort(_, {{"snapshotTime", Order.Descending}, {"batchId", Order.Descending}}){0}[manifest], type record}}),
    Jobs = Table.Combine(List.Transform(LatestDaily[manifest], each fx104ReadBatch(pSnapshotRoot, _)[Jobs])),
    Output = if pSourceMode = "Live" then src_104Jobs else if pSourceMode = "Snapshot" then Jobs else error Error.Record("Invalid source mode", "Use Snapshot or Live.", null)
in
    Output
