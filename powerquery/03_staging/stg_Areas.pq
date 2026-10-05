let
    Locations = Table.SelectColumns(stg_Jobs, {"jobAddrNo", "jobAddrNoDesc", "jobAddress", "lat", "lon"}),
    WithKey = Table.AddColumn(Locations, "areaKey", each fxAreaKey(_), type text),
    Output = Table.Distinct(WithKey)
in
    Output
