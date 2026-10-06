let
    Source =
        if pSourceMode = "Snapshot" then
            let
                Database = PostgreSQL.Database(pPostgresServer, pPostgresDatabase),
                GoldSnapshots = Database{[Schema = "gold", Item = "pbi_job_snapshots"]}[Data]
            in
                GoldSnapshots
        else if pSourceMode = "Live" then
            src_104Jobs
        else
            error Error.Record("Invalid source mode", "Use Snapshot or Live.", null)
in
    Source
