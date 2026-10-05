(value as any) as nullable text =>
let
    Result = if value = null then null else
        if Value.Is(value, type text) or Value.Is(value, type number) then
            Text.Trim(Text.Clean(Text.From(value, "en-US")))
        else error Error.Record("Text shape", "Expected a text or numeric scalar.", null)
in
    Result
