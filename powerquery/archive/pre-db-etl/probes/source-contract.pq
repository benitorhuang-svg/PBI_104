let
    Source = src_104Result,
    Rows = Table.RowCount(Source[Jobs]),
    Pages = Table.RowCount(Source[Metadata]),
    Total = Source[Metadata]{0}[total],
    Bad = [Jobs = #table({"jobNo"}, {{"probe"}}), Metadata = #table({"currentPage", "lastPage", "total", "count"}, {{2, 2, 1, 1}}), RawResponse = #table({}, {})],
    WrongPage = try fx104ValidatePage(Bad, 1),
    Empty = [Jobs = #table({"jobNo"}, {}), Metadata = #table({"currentPage", "lastPage", "total", "count"}, {{1, 0, 0, 0}}), RawResponse = #table({}, {})],
    EmptyRows = Table.RowCount(fx104ValidatePage(Empty, 1)[Jobs]),
    Passed = if Rows <> Total or not WrongPage[HasError] or EmptyRows <> 0 then error "Source contract probe failed" else true,
    Result = [passed = Passed, rows = Rows, pages = Pages, total = Total, wrongPageRejected = WrongPage[HasError], emptyRows = EmptyRows, sourceMode = pSourceMode]
in
    #table(type table [Result = text], {{Text.FromBinary(Json.FromValue(Result), TextEncoding.Utf8)}})
