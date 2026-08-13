(
    baseUrl as text,
    keyword as text,
    area as text,
    jobsource as text,
    mode as text,
    order as text,
    startPage as number,
    pagesize as number
) as record =>
let
    StartPage = Int64.From(startPage),
    FirstPage =
        fx104GetPage(
            baseUrl,
            keyword,
            area,
            jobsource,
            mode,
            order,
            StartPage,
            pagesize
        ),
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
                fx104GetPage(
                    baseUrl,
                    keyword,
                    area,
                    jobsource,
                    mode,
                    order,
                    currentPage,
                    pagesize
                )
        ),
    PageRecords = {FirstPage} & RemainingPages,
    Jobs = Table.Combine(List.Transform(PageRecords, each _[Jobs])),
    Metadata = Table.Combine(List.Transform(PageRecords, each _[Metadata])),
    RawResponses = Table.Combine(List.Transform(PageRecords, each _[RawResponse]))
in
    [
        Jobs = Jobs,
        Metadata = Metadata,
        RawResponses = RawResponses
    ]
