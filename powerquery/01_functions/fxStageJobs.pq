(input as table) as table =>
let
    Raw = Table.Buffer(input),
    IdentityColumns = List.RemoveItems(Table.ColumnNames(Raw), {"sourcePage"}),
    GroupedRaw = Table.Group(Raw, {"jobNo"}, {
        {"variants", each Table.RowCount(Table.Distinct(Table.SelectColumns(_, IdentityColumns))), Int64.Type},
        {"firstRow", each Table.First(_), type record}}),
    Conflicts = Table.SelectRows(GroupedRaw, each [variants] > 1),
    UniqueRaw = if Table.RowCount(Conflicts) > 0 then
        error Error.Record("Conflicting job duplicate", "A jobNo has different raw values within one batch.", [Jobs = Conflicts[jobNo]])
        else Table.FromRecords(GroupedRaw[firstRow], Table.ColumnNames(Raw), MissingField.UseNull),
    Selected = Table.SelectColumns(UniqueRaw, {
        "jobNo", "custNo", "custName", "coIndustry", "coIndustryDesc", "jobName", "description",
        "descSnippet", "jobAddress", "jobAddrNo", "jobAddrNoDesc", "lat", "lon", "salaryLow",
        "salaryHigh", "appearDate", "applyCnt", "jobCat", "pcSkills", "tags", "labels", "link",
        "remoteWorkType", "languageRequirements", "major", "acceptRole", "snapshotDate",
        "snapshotDateTime", "sourceKeyword", "sourceArea", "sourcePage", "sourcePageSize"}, MissingField.UseNull),
    RawNames = {"salaryLow", "salaryHigh", "appearDate", "jobCat", "pcSkills", "tags", "labels", "link", "languageRequirements", "major", "acceptRole"},
    Renamed = Table.RenameColumns(Selected, List.Transform(RawNames, each {_, _ & "Raw"})),
    TextNames = {"jobNo", "custNo", "custName", "jobName", "description", "descSnippet", "jobAddress", "jobAddrNoDesc", "coIndustryDesc", "sourceKeyword", "sourceArea"},
    NormalizedText = Table.TransformColumns(Renamed, List.Transform(TextNames, each {_, fxNormalizeText, type nullable text})),
    InvalidKeys = Table.SelectRows(NormalizedText, each [jobNo] = null or [jobNo] = "" or [custNo] = null or [custNo] = ""),
    RequiredKeys = if Table.RowCount(InvalidKeys) > 0 then
        error Error.Record("Required job key", "jobNo and custNo must be non-empty scalar identifiers.", [Rows = Table.RowCount(InvalidKeys)]) else NormalizedText,
    IntegerNames = {"coIndustry", "jobAddrNo", "applyCnt", "remoteWorkType", "sourcePage", "sourcePageSize"},
    WithQuality = Table.AddColumn(RequiredKeys, "qualityIssues", each
        let Current = _, Checks = List.Transform(IntegerNames & {"lat", "lon", "salaryLow", "salaryHigh"}, (name) =>
            let Value = Record.Field(Current, if List.Contains({"salaryLow", "salaryHigh"}, name) then name & "Raw" else name),
                Attempt = try fxStrictNumber(Value, List.Contains(IntegerNames, name))
            in if Attempt[HasError] then name & ":invalid-number" else null)
        in Text.Combine(List.RemoveNulls(Checks), ";"), type text),
    TypedNumbers = Table.TransformColumns(WithQuality,
        List.Transform(IntegerNames, each {_, (value) => try fxStrictNumber(value, true) otherwise null, Int64.Type}) &
        List.Transform({"lat", "lon"}, each {_, (value) => try fxStrictNumber(value) otherwise null, type nullable number})),
    WithSalaryLow = Table.AddColumn(TypedNumbers, "salaryLow", each try fxStrictNumber([salaryLowRaw]) otherwise null, type nullable number),
    WithSalaryHigh = Table.AddColumn(WithSalaryLow, "salaryHigh", each try fxStrictNumber([salaryHighRaw]) otherwise null, type nullable number),
    WithAppearDate = Table.AddColumn(WithSalaryHigh, "appearDate", each
        let Value = fxNormalizeText([appearDateRaw]), Parsed = try
            if Value <> null and Text.Length(Value) = 8 and Text.Select(Value, {"0".."9"}) = Value then
                #date(Number.FromText(Text.Start(Value, 4)), Number.FromText(Text.Range(Value, 4, 2)), Number.FromText(Text.End(Value, 2)))
            else null
        in if Parsed[HasError] then null else Parsed[Value], type nullable date),
    DateQuality = Table.AddColumn(WithAppearDate, "appearDateQuality", each
        if [appearDateRaw] = null then "missing" else if [appearDate] = null then "invalid" else "valid", type text),
    TypedSnapshot = Table.TransformColumns(DateQuality, {
        {"snapshotDate", each Date.FromText(Text.Start(Text.From(_, "en-US"), 10), [Format = "yyyy-MM-dd", Culture = "en-US"]), type date},
        {"snapshotDateTime", each DateTimeZone.RemoveZone(DateTimeZone.FromText(Text.From(_, "en-US"))), type datetime}}),
    RequiredTechnical = Table.SelectRows(TypedSnapshot, each [snapshotDate] = null or [snapshotDateTime] = null or [sourcePage] = null or [sourcePageSize] = null),
    Technical = if Table.RowCount(RequiredTechnical) > 0 then error Error.Record("Missing acquisition metadata", "Snapshot and page metadata are required.", null) else TypedSnapshot,
    WithArea = Table.AddColumn(Technical, "areaKey", each fxAreaKey(_), type text),
    WithLink = Table.AddColumn(WithArea, "jobLink", each
        let Value = [linkRaw], Parsed = if Value = null then null else if Value.Is(Value, type record) then Value else Json.Document(Value),
            Job = if Parsed = null then null else if Value.Is(Parsed, type record) then Record.FieldOrDefault(Parsed, "job", null) else
                error Error.Record("Link shape", "link must be a record.", null),
            Url = fxNormalizeText(Job)
        in if Url = null then null else if Text.StartsWith(Url, "https://www.104.com.tw/") then Url else
            error Error.Record("Unverified job URL", "Expected the observed 104 HTTPS URL; preserve the raw batch for review.", null), type nullable text)
in
    WithLink
