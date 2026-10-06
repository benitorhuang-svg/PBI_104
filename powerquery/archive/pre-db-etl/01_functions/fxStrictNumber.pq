(value as any, optional requireInteger as nullable logical) as nullable number =>
let
    Parsed = if value = null then null else if Value.Is(value, type number) then value else
        if Value.Is(value, type text) then Number.FromText(value, "en-US") else
        error Error.Record("Numeric shape", "Expected number or numeric text.", null),
    Validated = if Parsed = null then null else
        if Number.IsNaN(Parsed) or Number.Abs(Parsed) = #infinity then
            error Error.Record("Non-finite number", "Numbers must be finite.", null)
        else if requireInteger = true and Number.RoundDown(Parsed) <> Parsed then
            error Error.Record("Fractional integer", "Integer fields cannot be rounded.", null)
        else Parsed
in
    Validated
