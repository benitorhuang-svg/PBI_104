(value as any, fieldName as text) as list =>
let
    Parsed = if value = null then {} else if Value.Is(value, type list) then value else
        if Value.Is(value, type text) then Json.Document(value) else
        error Error.Record("Nested shape", "Expected a JSON list.", [Field = fieldName]),
    Validated = if Value.Is(Parsed, type list) then Parsed else
        error Error.Record("Nested shape", "Expected a JSON list; records and scalar values are invalid.", [Field = fieldName])
in
    Validated
