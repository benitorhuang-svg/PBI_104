let
    Source = stg_Areas,
    ValidKeys = Table.SelectRows(Source, each [areaKey] <> null and [areaKey] <> ""),
    Selected =
        Table.SelectColumns(
            ValidKeys,
            {"areaKey", "jobAddrNo", "jobAddrNoDesc", "jobAddress", "lat", "lon"},
            MissingField.UseNull
        ),
    Output = Table.Distinct(Selected, {"areaKey"})
in
    Output
