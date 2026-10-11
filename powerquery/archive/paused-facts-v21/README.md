# Paused v21 fact readers

These four M files are the previous Power Query readers for
`FactJobSnapshot` and `FactSalaryObservation`. They are archived, not active
model queries. Their PostgreSQL Gold v21 views and Silver source data remain
untouched.

The imports were paused on 2026-10-10 because neither fact is used by report
visuals and the observed history is too shallow for reliable trends. The salary
view also needs a latest-complete-batch filter and cross-series de-duplication.
Before reactivation, publish and validate a versioned Gold contract with
source-specific batch completeness, key/grain checks, conflict metadata, and
model relationship tests.
