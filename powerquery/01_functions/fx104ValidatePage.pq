(pageResult as record, requestedPage as number, optional expectedLastPage as nullable number, optional expectedTotal as nullable number) as record =>
let
    Metadata = Table.Buffer(pageResult[Metadata]),
    Jobs = Table.Buffer(pageResult[Jobs]),
    Required = {"currentPage", "lastPage", "total", "count"},
    ValidMetadata =
        if Table.RowCount(Metadata) <> 1 or not Table.HasColumns(Metadata, Required) then
            error Error.Record("Pagination metadata missing", "Each page requires one complete pagination record.", [Page = requestedPage])
        else Metadata{0},
    ReadInteger = (field as text) as number =>
        let PaginationValue = Record.Field(ValidMetadata, field)
        in if not Value.Is(PaginationValue, type number) then
            error Error.Record("Invalid pagination integer", field & " must be numeric.", [Page = requestedPage])
        else if PaginationValue < 0 or Number.RoundDown(PaginationValue) <> PaginationValue then
            error Error.Record("Invalid pagination integer", field & " must be a non-negative integer.", [Page = requestedPage])
        else PaginationValue,
    CurrentPage = ReadInteger("currentPage"),
    LastPage = ReadInteger("lastPage"),
    Total = ReadInteger("total"),
    Count = ReadInteger("count"),
    RowCount = Table.RowCount(Jobs),
    Validated =
        if CurrentPage <> requestedPage then
            error Error.Record("Pagination page mismatch", "The returned page does not match the request.", [RequestedPage = requestedPage, CurrentPage = CurrentPage])
        else if Count <> RowCount then
            error Error.Record("Pagination count mismatch", "Pagination count does not match the returned rows.", [Page = requestedPage, Count = Count, Rows = RowCount])
        else if (Total = 0 and (LastPage <> 0 or Count <> 0)) or (Total > 0 and (LastPage < requestedPage or Count = 0)) then
            error Error.Record("Inconsistent pagination", "The page is inconsistent with total/lastPage.", [Page = requestedPage])
        else if expectedLastPage <> null and LastPage <> expectedLastPage then
            error Error.Record("Pagination changed", "lastPage changed during acquisition; retry the complete batch.", [Page = requestedPage])
        else if expectedTotal <> null and Total <> expectedTotal then
            error Error.Record("Pagination changed", "total changed during acquisition; retry the complete batch.", [Page = requestedPage])
        else [Jobs = Jobs, Metadata = Metadata, RawResponse = pageResult[RawResponse]]
in
    Validated
