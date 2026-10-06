(input as table, keys as list, grain as text) as table =>
let
    Invalid = Table.SelectRows(input, (row) => List.AnyTrue(List.Transform(keys, (key) =>
        let Value = Record.FieldOrDefault(row, key, null)
        in Value = null or (Value.Is(Value, type text) and Text.Trim(Value) = "")))),
    Counts = Table.Group(input, keys, {{"rowCount", each Table.RowCount(_), Int64.Type}}),
    Duplicates = Table.SelectRows(Counts, each [rowCount] > 1),
    Output = if Table.RowCount(Invalid) > 0 then
        error Error.Record("Model key is null", grain & " has missing keys.", [Rows = Table.RowCount(Invalid)])
        else if Table.RowCount(Duplicates) > 0 then
            error Error.Record("Model grain conflict", grain & " is not unique.", [Duplicates = Duplicates])
        else input
in
    Output
