let
    Pairs = List.Combine(List.Transform(Table.ToRecords(stg_Jobs), (job) =>
        List.Transform(fxParseJsonList(job[jobCatRaw], "jobCat"), (category) =>
            let Code = fxStrictNumber(category, true)
            in if Code = null then error Error.Record("Category key", "A category entry requires an integer code.", [jobNo = job[jobNo]]) else
                [jobNo = job[jobNo], jobCatCode = Code, jobCatDescription = "BLOCKED"]))),
    Output = Table.FromRecords(Pairs, type table [jobNo = text, jobCatCode = Int64.Type, jobCatDescription = text]),
    Counts = Table.Group(Output, {"jobNo", "jobCatCode"}, {{"rows", each Table.RowCount(_), Int64.Type}}),
    Validated = if Table.RowCount(Table.SelectRows(Counts, each [rows] > 1)) > 0 then
        error Error.Record("Duplicate category pair", "jobNo × jobCatCode must be unique within a job.", null) else Output
in
    Validated
