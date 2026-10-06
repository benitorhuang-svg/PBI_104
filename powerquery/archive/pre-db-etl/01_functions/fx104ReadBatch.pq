(root as text, manifest as record) as record =>
let
    Root = Text.TrimEnd(root, {"\", "/"}),
    RelativePath = manifest[batchPath],
    PathParts = Text.Split(Text.Replace(RelativePath, "\", "/"), "/"),
    BatchPath =
        if Text.Contains(RelativePath, ":") or List.Contains(PathParts, "..") or List.Contains(PathParts, "") then
            error Error.Record("Invalid snapshot path", "Batch paths must remain below the configured root.", null)
        else Root & "\" & Text.Combine(PathParts, "\"),
    SeriesKey = Text.Lower(Text.From(manifest[seriesKey])),
    SafeSeriesKey = if Text.Length(SeriesKey) <> 20 or Text.Select(SeriesKey, {"0".."9", "a".."f"}) <> SeriesKey then
        error Error.Record("Invalid snapshot series", "seriesKey must be 20 lowercase hexadecimal characters.", null) else SeriesKey,
    ExpectedBatchPath = "series/" & SafeSeriesKey & "/batches/" & Text.From(manifest[batchId]),
    CheckedManifest = if RelativePath <> ExpectedBatchPath then
        error Error.Record("Manifest path mismatch", "batchPath must match the seriesKey and batchId.", null) else manifest,
    Request = CheckedManifest[request],
            SerializeComplex = (value as any) as any =>
        if Value.Is(value, type record) or Value.Is(value, type list) then Text.FromBinary(Json.FromValue(value), TextEncoding.Utf8) else value,
    ReadPage = (descriptor as record) as record =>
        let
            FileName = descriptor[file],
            SafeFileName = if Text.Contains(FileName, "/") or Text.Contains(FileName, "\") or Text.Contains(FileName, ":") or FileName = ".." then
                error Error.Record("Invalid snapshot page path", "Page names cannot contain path components.", null) else FileName,
            Stored = Json.Document(File.Contents(BatchPath & "\" & SafeFileName)),
            Response = Stored[response],
            Pagination = Response[metadata][pagination],
            RawRows = Response[data],
            SerializedRows = List.Transform(RawRows, (job as record) => Record.Combine({
                Record.TransformFields(job, List.Transform(Record.FieldNames(job), each {_, SerializeComplex})),
                [snapshotDate = manifest[snapshotDate], snapshotDateTime = manifest[snapshotDateTime],
                 sourceKeyword = Record.FieldOrDefault(Request, "keyword", null),
                 sourceJobcat = Record.FieldOrDefault(Request, "jobcat", null),
                 sourceArea = Record.FieldOrDefault(Request, "area", null), querySeriesKey = SafeSeriesKey,
                 sourcePage = descriptor[page], sourcePageSize = Request[pagesize]]
            })),
            Columns = List.Distinct(List.Combine({{"jobNo", "custNo", "pcSkills", "jobCat", "snapshotDate", "snapshotDateTime", "sourceKeyword", "sourceJobcat", "sourceArea", "querySeriesKey", "sourcePage", "sourcePageSize"}, List.Combine(List.Transform(SerializedRows, Record.FieldNames))})),
            Jobs = Table.FromRecords(SerializedRows, Columns, MissingField.UseNull),
            Metadata = Table.FromRecords({Record.Combine({Stored[technical], Pagination,
                [snapshotDate = manifest[snapshotDate], snapshotDateTime = manifest[snapshotDateTime]]})}),
            RawResponse = Table.FromRecords({[sourcePage = descriptor[page], snapshotDateTime = manifest[snapshotDateTime], rawResponseJson = Text.FromBinary(Json.FromValue(Response), TextEncoding.Utf8)]}),
            PageResult = fx104ValidatePage([Jobs = Jobs, Metadata = Metadata, RawResponse = RawResponse], descriptor[page]),
            Validated = if Table.RowCount(PageResult[Jobs]) <> descriptor[rows] or Stored[technical][httpStatus] <> 200 then
                error Error.Record("Snapshot page mismatch", "Stored rows/status do not match the completed acquisition.", [Page = descriptor[page]]) else PageResult
        in Validated,
    Pages = List.Buffer(List.Transform(manifest[pages], ReadPage)),
    FirstMetadata = Pages{0}[Metadata]{0},
    CheckedPages = List.Transform(Pages, each fx104ValidatePage(_, _[Metadata]{0}[currentPage], FirstMetadata[lastPage], FirstMetadata[total])),
    Jobs = Table.Combine(List.Transform(CheckedPages, each _[Jobs])),
    PageNumbers = List.Transform(manifest[pages], each _[page]),
    ExpectedPageNumbers = if FirstMetadata[lastPage] = 0 then {1} else {1 .. FirstMetadata[lastPage]},
    ValidatedJobs = if PageNumbers <> ExpectedPageNumbers or Table.RowCount(Jobs) <> manifest[rows] or Table.RowCount(Jobs) <> FirstMetadata[total] then
        error Error.Record("Incomplete snapshot batch", "Stored pages/rows do not match the completed manifest.", null) else Jobs
in
    [Jobs = ValidatedJobs, Metadata = Table.Combine(List.Transform(CheckedPages, each _[Metadata])), RawResponses = Table.Combine(List.Transform(CheckedPages, each _[RawResponse]))]
