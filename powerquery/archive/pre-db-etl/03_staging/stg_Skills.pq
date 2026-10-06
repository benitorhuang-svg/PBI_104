let
    Source = stg_JobSkills,
    DescriptionCounts =
        Table.Group(
            Source,
            {"skillCode"},
            {
                {"skillDescription", each List.First(List.RemoveNulls([skillDescription]), null), type nullable text},
                {"descriptionCount", each List.Count(List.Distinct(List.RemoveNulls([skillDescription]))), Int64.Type}
            }
        ),
    Conflicts = Table.SelectRows(DescriptionCounts, each [descriptionCount] > 1),
    Validated =
        if Table.RowCount(Conflicts) > 0 then
            error Error.Record("Conflicting skill description", "A skillCode has more than one non-null description.", [Conflicts = Conflicts])
        else
            Table.SelectColumns(DescriptionCounts, {"skillCode", "skillDescription"})
in
    Validated
