# TASK-015 — Preserve area-key identity in Power BI

## Goal

Keep byte-distinct area identities distinct when Power BI imports the Gold
dimension and fact views.

## Scope

- Preserve the original composite `area_key` in Silver.
- Expose lowercase UTF-8 hexadecimal keys from both `gold.pbi_fact_jobs` and
  `gold.pbi_dim_area`.
- Keep displayed address, description, and coordinate values unchanged.
- Record schema migration 11 and document the model-key representation.
- Leave PBIR visuals and relationship direction unchanged.

## Acceptance

- Gold FactJob and DimArea produce the same key for each Silver `area_key`.
- Distinct UTF-8 byte strings remain distinct after Power BI text comparison.
- The reported normal/compatibility ideograph pair has distinct Gold keys.
- Power BI refresh loads DimArea without duplicate-key errors and preserves
  fact-to-dimension matches.

## Verification (2026-10-06)

- PostgreSQL schema migration 11 applied.
- Gold returned 12,368 DimArea rows and 12,368 distinct keys; all 18,469
  FactJob rows had non-null area keys and every distinct fact key matched DimArea.
- A full Power BI Desktop model refresh completed successfully.
- Post-refresh DAX counts were 12,368/12,368 for DimArea,
  239/239 for DimSkill, and 563/563 for DimJobCategory. Area, skill, and
  category bridge orphan counts were zero.
- The reported duplicate is the same visible address containing U+8DEF and
  U+F937 in separate source keys; their UTF-8 hexadecimal keys remain distinct.
