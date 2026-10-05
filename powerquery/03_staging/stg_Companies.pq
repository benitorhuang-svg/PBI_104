let
    Source =
        Table.SelectColumns(
            stg_Jobs,
            {"custNo", "custName", "coIndustry", "coIndustryDesc"},
            MissingField.UseNull
        ),
    Normalized =
        Table.TransformColumns(
            Source,
            {
                {"custNo", fxNormalizeText, type nullable text},
                {"custName", fxNormalizeText, type nullable text},
                {"coIndustryDesc", fxNormalizeText, type nullable text},
                {"coIndustry", each fxStrictNumber(_, true), Int64.Type}
            },
            null,
            MissingField.Ignore
        ),
    ValidRows = Table.SelectRows(Normalized, each [custNo] <> null and [custNo] <> ""),
    Grouped =
        Table.Group(
            ValidRows,
            {"custNo"},
            {
                {"custName", each List.First(List.RemoveNulls([custName]), null), type nullable text},
                {"coIndustry", each List.First(List.RemoveNulls([coIndustry]), null), Int64.Type},
                {"coIndustryDesc", each List.First(List.RemoveNulls([coIndustryDesc]), null), type nullable text},
                {
                    "companyVariantCount",
                    each Table.RowCount(Table.Distinct(Table.SelectColumns(_, {"custName", "coIndustry", "coIndustryDesc"}))),
                    Int64.Type
                }
            }
        ),
    Conflicts = Table.SelectRows(Grouped, each [companyVariantCount] > 1),
    Validated =
        if Table.RowCount(Conflicts) > 0 then
            error Error.Record("Company identity conflict", "custNo maps to multiple name or industry values.", [Conflicts = Conflicts])
        else
            Table.RemoveColumns(Grouped, {"companyVariantCount"})
in
    Validated
