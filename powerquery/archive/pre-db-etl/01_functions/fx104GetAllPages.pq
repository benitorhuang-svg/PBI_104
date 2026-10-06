(
    baseUrl as text,
    keyword as nullable text,
    area as nullable text,
    jobsource as text,
    mode as text,
    order as text,
    startPage as number,
    pagesize as number,
    optional maxPages as nullable number,
    optional jobcat as nullable text
) as record =>
let
    StartPage =
        if startPage < 1 or Number.RoundDown(startPage) <> startPage then
            error Error.Record("Invalid start page", "startPage must be a positive integer.", null)
        else startPage,
    PageLimit = if maxPages = null then 1000 else maxPages,
    FirstPage =
        fx104ValidatePage(fx104GetPage(
            baseUrl,
            keyword,
            area,
            jobsource,
            mode,
            order,
            StartPage,
            pagesize,
            jobcat = jobcat
        ), StartPage),
    FirstMetadata = FirstPage[Metadata],
    CurrentPageValue =
        if Table.HasColumns(FirstMetadata, "currentPage") then
            try Int64.From(FirstMetadata{0}[currentPage]) otherwise null
        else
            null,
    LastPageValue =
        if Table.HasColumns(FirstMetadata, "lastPage") then
            try Int64.From(FirstMetadata{0}[lastPage]) otherwise null
        else
            null,
    ValidatedLastPage =
        if CurrentPageValue = null then
            error Error.Record(
                "Pagination metadata missing",
                "$.metadata.pagination.currentPage was not available.",
                [RequestedPage = StartPage]
            )
        else if CurrentPageValue <> StartPage then
            error Error.Record(
                "Pagination page mismatch",
                "The API currentPage did not match the requested page.",
                [RequestedPage = StartPage, CurrentPage = CurrentPageValue]
            )
        else if LastPageValue = null or LastPageValue < 0 then
            error Error.Record(
                "Pagination metadata missing",
                "$.metadata.pagination.lastPage was not a non-negative integer.",
                [RequestedPage = StartPage, LastPage = LastPageValue]
            )
        else if PageLimit < 1 or Number.RoundDown(PageLimit) <> PageLimit or LastPageValue - StartPage + 1 > PageLimit then
            error Error.Record("Acquisition page guard", "Invalid or exceeded maxPages; this is an operational guard, not an API limit.", [MaxPages = PageLimit])
        else
            LastPageValue,
    RemainingPageNumbers =
        if ValidatedLastPage > StartPage then
            {StartPage + 1 .. ValidatedLastPage}
        else
            {},
    RemainingPages =
        List.Transform(
            RemainingPageNumbers,
            (currentPage as number) =>
                fx104ValidatePage(fx104GetPage(
                    baseUrl,
                    keyword,
                    area,
                    jobsource,
                    mode,
                    order,
                    currentPage,
                    pagesize,
                    jobcat = jobcat
                ), currentPage, ValidatedLastPage, FirstMetadata{0}[total])
        ),
    PageRecords = List.Buffer({FirstPage} & RemainingPages),
    Jobs = Table.Combine(List.Transform(PageRecords, each _[Jobs])),
    Metadata = Table.Combine(List.Transform(PageRecords, each _[Metadata])),
    RawResponses = Table.Combine(List.Transform(PageRecords, each _[RawResponse])),
    ValidatedJobs =
        if StartPage = 1 and Table.RowCount(Jobs) <> FirstMetadata{0}[total] then
            error Error.Record("Incomplete acquisition", "Returned rows do not match the API total.", [Rows = Table.RowCount(Jobs), Total = FirstMetadata{0}[total]])
        else Jobs
in
    [
        Jobs = ValidatedJobs,
        Metadata = Metadata,
        RawResponses = RawResponses
    ]
