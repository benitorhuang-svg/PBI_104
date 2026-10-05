let
    Rows = Table.ToRecords(stg_Jobs),
    Pairs = List.Combine(List.Transform(Rows, (job) => List.Transform(fxParseJsonList(job[pcSkillsRaw], "pcSkills"), (skill) =>
        if not Value.Is(skill, type record) then error Error.Record("Skill shape", "Each skill must be a record.", [jobNo = job[jobNo]]) else
        let Code = fxNormalizeText(Record.FieldOrDefault(skill, "code", null)),
            Description = fxNormalizeText(Record.FieldOrDefault(skill, "description", null))
        in if Code = null or Code = "" then error Error.Record("Skill key", "Each skill requires a code.", [jobNo = job[jobNo]]) else
            [jobNo = job[jobNo], skillCode = Code, skillDescription = Description]))),
    Output = Table.FromRecords(Pairs, type table [jobNo = text, skillCode = text, skillDescription = nullable text]),
    Counts = Table.Group(Output, {"jobNo", "skillCode"}, {{"rows", each Table.RowCount(_), Int64.Type}}),
    Validated = if Table.RowCount(Table.SelectRows(Counts, each [rows] > 1)) > 0 then
        error Error.Record("Duplicate skill pair", "jobNo × skillCode must be unique within a job.", null) else Output
in
    Validated
