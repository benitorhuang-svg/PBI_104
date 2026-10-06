(viewName as text) as table =>
let
    Database = PostgreSQL.Database(pPostgresServer, pPostgresDatabase),
    GoldView = Database{[Schema = "gold", Item = viewName]}[Data]
in
    GoldView
