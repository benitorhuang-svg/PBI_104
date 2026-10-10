# Power BI rendered layout gap review

Date: 2026-10-09  
Scope: visual comparison only; no PBIR or model changes.

## Capture conditions

Reviewed all five pages in the current `PBI_JobWant.pbip` Power BI Desktop session. Desktop was in authoring mode at 57% zoom with the Build/Data panes open and showed a banner that some tables were incomplete or had no data. Screenshots were kept under `%TEMP%\PBI_104\design-audit-stable\` and are not repository assets.

The banner and authoring viewport obscure part of each page header. This review therefore treats clipped headers as a capture limitation. Empty visuals and missing values are recorded separately from visual styling because the model warning may affect their data state.

## Page-by-page comparison

| Page | Rendered state | Gap from reference/spec | Target for the next design draft |
| --- | --- | --- | --- |
| 01 — 職缺市場總覽 | Four slicers and four KPI values render. The date chart is nearly flat for much of its range with a few large spikes; the industry donut has many small slices and crowded labels. | The approved PNG uses a clear left navigation rail, framed cards, a stronger header, and restrained gold/blue/teal/purple accents. The current page is mostly white space with unframed visuals and default blue chart styling. The chart also reads like a long trend although the spec limits interpretation to the current refresh/date distribution. | Keep the shared shell and KPI/chart hierarchy from the reference. Label the date visual as current-refresh distribution, use readable category limits, and do not imply unsupported historical change. |
| 02 — 薪資市場分析 | Coverage and salary-row KPIs, a limitation card, raw lower-bound chart, category/area visuals, and a detail visual render. The raw axis extends to about 10 million, compressing most values near zero. | Card framing and page hierarchy are weak. The outlier dominates the distribution, and the details visual competes with the main salary view. The reference includes median/range examples that the current spec correctly blocks. | Retain explicit raw-bound and unit limitations. Design a readable distribution that keeps extreme values visible and disclosed; do not copy unsupported median, percentile, or currency claims from the inspiration PNG. |
| 03 — 技能需求分析 | Three KPIs, Top Skills and coverage charts, a trace table, an insight card, and a historical-data limitation card render. | The two bar visuals have substantial unused space relative to their small visible bars; the trace table and limitation cards do not read as one hierarchy. The PNG includes combination/trend visuals that the current spec blocks for lack of grain/history evidence. | Give the ranked skills and coverage the visual priority, make the trace area secondary, and retain a compact, readable limitation treatment. Do not imply skill combinations or emerging trends. |
| 04 — 職缺搜尋器 | Seven filters, three KPI values, a job list table, and a second multi-row detail table render. | The page has no map despite the designed coordinates. The filters consume most of the top row, the three KPIs conflict with the current spec's single matched-job KPI, and the right-hand visual behaves like another table rather than selected-job content. The inspiration PNG's logos and decorative details are not supported requirements. | One integrated map-led explorer: map and concise results list select a job; a same-page detail pane shows its sourced content and original link. Keep only fields supported by the model and give the selected job clear visual focus. |
| 05 — 下載戰情室 | Completion gauge, result donut, category matrix, and full-width detail table render with data. | The current layout broadly follows `page-05-spec.md`, but there is no approved Page 05 PNG to lock the target visual language. Its title/header was partly obscured in the capture. | Create a dedicated reference using the current operational purpose and data semantics, then align its shell, card treatment, and labels with the other pages. |

## Cross-page causes of drift

- Pages 01–04 have inspiration PNGs, but those images include illustrative values or visual elements that the current specs prohibit. No revised target set yet shows the same visual quality using only supported measures and fields.
- The references show a left navigation rail. Current report navigation is in Power BI's bottom page tabs; Page 04's spec also calls for native tabs. The navigation choice is inconsistent and should be settled once for all pages.
- The current report needs a clean, same-scale capture with the incomplete-data banner and authoring panes out of the way before final visual acceptance. That capture should not be confused with a refresh or data-quality gate.

## Recommended order

1. Establish one coherent target design for each page, including the agreed map/list/detail composition on Page 04 and a new Page 05 reference.
2. Review the target drafts against supported fields and measures; keep unsupported sample metrics out of the formal designs.
3. Change PBIR layout and formatting page by page, preserving the existing dirty work and model layer.
4. Compare clean Desktop captures at the same canvas size and zoom; separately resolve any remaining incomplete-data or empty-result states.
