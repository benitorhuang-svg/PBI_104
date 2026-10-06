(input as table, key as text, reference as table, referenceKey as text, relationship as text) as table =>
let
    Lookup = List.Buffer(List.Distinct(Table.Column(reference, referenceKey))),
    Orphans = Table.SelectRows(input, each
        let Value = Record.FieldOrDefault(_, key, null)
        in Value = null or not List.Contains(Lookup, Value)),
    Output = if Table.RowCount(Orphans) > 0 then
        error Error.Record("Model relationship orphan", relationship & " contains keys absent from its dimension.", [Rows = Table.RowCount(Orphans)])
        else input
in
    Output
