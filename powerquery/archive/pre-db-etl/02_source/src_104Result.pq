let
    Source =
        if pSourceMode = "Snapshot" then fx104ReadBatch(pSnapshotRoot, src_104CurrentManifest)
        else if pSourceMode <> "Live" then error Error.Record("Invalid source mode", "Use Snapshot or Live.", null)
        else fx104GetAllPages(
            pBaseUrl,
            pKeyword,
            pArea,
            pJobSource,
            pMode,
            pOrder,
            pPage,
            pPageSize
        )
in
    Source
