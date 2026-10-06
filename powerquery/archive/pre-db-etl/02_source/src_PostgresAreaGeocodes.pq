let
    Database = PostgreSQL.Database(pPostgresServer, pPostgresDatabase),
    AreaGeocodes = Database{[Schema = "gold", Item = "area_geocodes"]}[Data],
    Selected = Table.SelectColumns(AreaGeocodes, {"area_key", "latitude_effective", "longitude_effective"}),
    Typed = Table.TransformColumnTypes(Selected, {{"area_key", type text}, {"latitude_effective", type nullable number}, {"longitude_effective", type nullable number}})
in
    Typed
