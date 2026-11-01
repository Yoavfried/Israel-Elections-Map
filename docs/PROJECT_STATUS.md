# Project Status

Last updated: 2026-11-01

This is the repository's only project completion tracker. Methodology, audit
evidence, and generated coverage tables remain in subject-specific documents,
but open/complete workstream declarations belong here.

## Workstreams

| Workstream | Status | Current boundary |
|---|---|---|
| K26 / 2026 addition | Initial complete-count snapshot implemented; area audit remains open | All 12,926 source rows reconcile exactly to 5,690,685 valid votes. National results, 120 provisional mandates, locality results, and double envelopes are included. K26 uses 2022 geography. Only 1,783 single-area ballots plus 71 established custom-bucket rows receive supported geographic assignments; 10,157 rows remain municipality-only and are displayed through 145 disclosed whole-locality fallback units. Pre-balance crosswalk candidates are archived, not accepted. Final-register balancing, certification refresh, and new K26 party color/name/article review remain open; completed K17-K25 reviews are unchanged. No K26 coalition is invented before one is formed. |
| K17-K25 election normalization | Complete | 96,529 source rows are normalized and reconcile to the official election totals. |
| Locality-mode aggregation | Complete | Every geographic-scope result row is mapped. Twelve unsupported partial-presence cells across eight localities remain neutral under a closed policy; their effect is immaterial and no further matching work is planned. |
| Historical statistical-area mode | Complete under the current evidence policy | Election-specific CBS crosswalks and matching 1995/2008/2011 geometry are active. Fifty-four high-confidence row-level continuity links are approved and labeled synthetic. The final K21-K25 display layer publishes 537 exact closed units and 1,732 disclosed representative units across 4,731 polygon-election memberships. Entirely unassigned localities use a display-only fallback. Visual refinement of all nine K17/K18 historical-composite components, all 33 effective K17 historical-identity fallback polygons, and the additional reviewed K17/K18 locality overlaps is complete. All 119 reviewed tiny West Bank proxies now have detailed display footprints; the final four use reviewed Peace Now polygons and do not alter assignments. A separate automated joined-locality display audit evaluates 175 election-specific continuity leads: 38 strict approvals are active and 137 are covered, contradicted, or unresolved; these never change ballot-level area assignments. A polling-register safety audit rejects 38 false K24 row-level stable-ballot candidates: ten in Daliyat al-Karmel and 28 in Umm al-Fahm. Their complete final results publish only through reviewed exact closed area sets. All nine specific ordinary crosswalk omissions are likewise resolved at exact set level, including K25 Daliyat ballot 23; no internal area split is invented. Remaining source limitations have settled display and publication rules and are not an active repair queue. |
| Party/list names | Complete | All 297 published K17-K25 lists have reviewed Hebrew and English display names; the English review is independent of Wikipedia-link selection. |
| Party colors | Complete | All 297 published K17-K25 lists have reviewed colors. Stable-letter defaults, election-specific exceptions, and audited identity carryovers remain explicit in the map configuration. |
| Wikipedia links | Complete | Hebrew and English article links, repeated-party continuity, same-label/different-identity exceptions, and intentional blanks are reviewed for every published K17-K25 list. |
| UX and accessibility | Complete for the current desktop and portrait-mobile scope | Bilingual desktop and portrait-mobile behavior is active, including document-level direction, properly shaped Hebrew/Arabic vector labels, a top-bar accessibility control, compact mobile navigation and selectors, a persistent map viewport, keyboard-aware search, closable result sheets, and short-screen scrolling that keeps the selected geography title visible. Landscape-phone support is outside the agreed scope. |
| National results | Implemented | A primary top-bar view publishes every positive-vote list in each K17-K26 election with official national votes, election-specific threshold, mandates, current color, and separate Hebrew/English Wikipedia controls. K26 is explicitly marked pending certification. The 14 documented zero-filled nonrunner columns remain auditable in the registry but are excluded from every election view. |
| Product features | Complete for the current scope | Election-aware bilingual geography and numbered-address search, national results, both party-analysis modes, coalition results, and persisted neutral/vector backgrounds are implemented on desktop and portrait mobile. Single-party mode includes an area/vote-circle toggle: color represents vote share and circle area represents absolute votes. The color cap remains the positive-share 95th percentile; circle size uses one party-independent scale capped at the 99th percentile of each area's leading-party vote total, a smaller maximum radius, and a visible positive-vote tint floor. Coalition mode uses reviewed election-specific first-coalition lists, the outgoing transitional coalition for K21/K22, and explicit K21-K23 joint-list caveats. Satellite and 3D-building modes have been removed and are not planned. |
| Public data distribution | Implemented | `public-data/v2` is data release v2.0 with schema version 2 and 124 manifest-listed files plus release manifests and validation, direct geography joins, checksums, and row-level assignment provenance. The preceding v1 snapshot is preserved. Data releases use the independent two-level `major.minor` policy in `docs/VERSIONING.md`. |
| Public repository hardening | Implemented | Split licensing keeps the downloadable data, canonical geography, methodology, and non-presentation evidence tables under MIT while reserving rights in the website, colors, web-only polygon transformations, modes, and other product presentation. The app links directly to this repository for downloads, sources, methodology, and legal notices, and publishes a bilingual privacy notice for current network and browser-storage behavior. Rebuilding the private-input pipeline from a fresh clone, hosted CI, continuous performance monitoring, and duplicate in-app Sources/Legal pages are not public-data deliverables. |
| Production website launch | Implemented | The locally compiled deployment is live at `https://yoavfried.com/isr-electionmap`. Cloudflare Workers Static Assets hosts the application and a selective Worker handles SEO routes; the owned-domain subpath proxies to that origin. No paid database or object storage is required. |
| SEO and discoverability | Implemented; submission pending | Worker-rendered overview, feature overview, party-comparison, coalition, election-specific single-party, 2026 results, historical-election, locality, and statistical-area pages are available in Hebrew, English, French, Spanish, Russian, Simplified Chinese, Arabic, German, Ukrainian, and Polish. Every language has equivalent descriptions, initial HTML, complete Open Graph/social metadata, canonical and reciprocal hreflang links, WebApplication/WebPage/Dataset structured data as appropriate, exact map deep links including party selections, real 404s, and split sitemaps. Deliberately, arbitrary party-pair combinations do not create indexable pages. Google Search Console verification/submission, the canonical host's root `robots.txt` sitemap declaration, and post-indexing performance review remain operational launch tasks. |
| AdSense advertising | Planned | Use manual responsive units on content-rich pages and the national-results view. Keep mobile maps, result sheets, controls, search, and selectors ad-free. Hosting and crawlable content prerequisites are complete; implementation still requires an issued AdSense publisher/slot ID, the advertising update to the privacy notice, and a Google-certified consent flow. |

## Public Data Release

The committed `public-data/v2` release (data version v2.0) can be used without the private working
data. It includes:

- ten ballot-row CSVs covering all 109,455 normalized rows;
- statistical-area, locality, custom-geography, envelope, and unresolved tables;
- full-resolution 1995, 2008, 2011, and 2022 statistical-area packages;
- current locality, reviewed composite-locality, and custom-geography packages;
- direct `geography_id` joins, party/election metadata, checksums, and validation;
- 38 machine-readable provenance and audit artifacts under
  `metadata/assignment-provenance/`.

The v2 manifest lists 124 files, including the unmodified K26 source snapshot.
The preceding `public-data/v1` release is preserved. K26 is a complete-count,
pre-certification snapshot dated 2026-10-30; it is not described as certified.

`public-data/METHODOLOGY.md` now states the exact assignment precedence,
synthetic-link counts, unresolved-row policy, validation rules, and audit path
under the MIT data licence.

The release marks 164 ballot-to-area links as synthetic links, representing
52,804 actual voters. The ballot rows and votes themselves are never synthetic:

| Evidence | Rows | Actual voters |
|---|---:|---:|
| Official CBS stable-ballot inference | 96 | 27,761 |
| Reviewed exact ArcGIS residual inference | 9 | 3,599 |
| Reviewed cross-election correction | 5 | 2,024 |
| Reviewed polling-register continuity | 54 | 19,420 |
| **Total** | **164** | **52,804** |

The separate 74 K23 AGS assignments, representing 29,685 actual voters, are
direct official evidence and are therefore not marked synthetic. Users can
exclude every inferred link with `assignment_is_synthetic_link=false`.

Map colors and other presentation choices remain in `web/app/`; they are not
part of the reusable election tables.

## Statistical-Area Coverage

Statistical mode uses the historical vintage named by the official crosswalk:
1995 for K17, 2008 for K18, 2011 for K19-K25, and 2022 for K26. K25 is not converted to 2022
areas because its official crosswalk still targets 2011.

Across K17-K25, 5,583 rows representing 2,086,436 actual voters remain
without a defensible statistical-area target. Supported statistical-mode voter
coverage is 94.00% for those elections. K26 currently has 14.44% supported
statistical/custom coverage; its remaining geographic votes are visible as
disclosed municipality totals, not claimed area assignments. Locality coverage
is 100% in every election.

| Election | Vintage | Statistical-area rows | Custom rows | Pending rows | Pending actual voters | Supported voter share |
|---|---:|---:|---:|---:|---:|---:|
| K17 | 1995 | 7,821 | 44 | 409 | 161,195 | 94.65% |
| K18 | 2008 | 8,693 | 48 | 518 | 189,252 | 94.14% |
| K19 | 2011 | 9,317 | 0 | 558 | 212,413 | 94.13% |
| K20 | 2011 | 9,546 | 0 | 566 | 258,880 | 93.56% |
| K21 | 2011 | 9,856 | 0 | 596 | 224,699 | 94.52% |
| K22 | 2011 | 9,923 | 0 | 608 | 264,994 | 93.66% |
| K23 | 2011 | 10,007 | 0 | 616 | 295,946 | 93.09% |
| K24 | 2011 | 11,213 | 0 | 906 | 219,524 | 94.53% |
| K25 | 2011 | 10,893 | 0 | 806 | 259,533 | 94.01% |

The unresolved rows are classified rather than silently estimated:

| Current explanation | Rows |
|---|---:|
| Entire locality omitted from the official crosswalk | 5,336 |
| Election locality identity absent from the active historical vintage | 53 |
| K17 component locality has multiple areas but no component crosswalk | 31 |
| K18 component locality is nested in the published composite geometry | 84 |
| Central ballot 990, intentionally locality-only | 70 |
| Specific ordinary ballot omitted from the official crosswalk | 9 |
| **Total** | **5,583** |

These numbers are source limitations, not one undifferentiated repair queue:

| Item | Plain meaning | Current treatment | What could change it |
|---|---|---|---|
| 12 partial-presence locality/election cells | A current 2022 locality polygon exists, but no standalone result or reviewed host was found for that election. | **Closed:** leave the polygon neutral. | No further work is planned unless an explicit host source appears. |
| 53 historical locality-identity rows | The election identity exists in the results but not as an independent locality in the active historical vintage. Every result already has fallback display geometry. The 34 K17 source identities resolve to 33 effective fallback polygons because source code 989 is reviewed as כמאנה (1331). | Keep the rows unassigned. Visual review is complete for all 33 effective K17 fallbacks: one current-boundary replacement, 21 exact cutout fallbacks, and 11 fallbacks approved unchanged after zero-overlap validation. This is presentation repair, not another identity investigation. | A row-level area ID would still require direct historical evidence. |
| 9 omitted ordinary ballots | The final ballot result exists, but its key is absent from the official CBS area crosswalk. Eight K24/K25 Ar'ara rows are final subdivisions of complete polling-site totals spanning areas 1 and 3. K25 Daliyat ballot 23 is a new third ballot at the unchanged polling site serving areas 3 and 5. | **Resolved at set level:** keep all nine row-level area IDs blank. Publish each complete area set once through its reviewed exact display. | A direct row-level crosswalk could restore an internal split, but no result is missing from the map. |
| 38 rejected K24 stable-ballot row candidates | Stable ballot numbers suggested one area per final row, but the official K24 pre/post registers prove that 10 Daliyat rows and 28 Umm al-Fahm rows are final polling-site batches mixing several planned areas. | **Resolved at set level:** keep the 38 row-level IDs blank. Publish Daliyat areas 1, 3, 4, and 5 together and the closed Umm al-Fahm areas 13, 14, 15, 21, and 34 network together; unaffected areas remain separate. | A direct K24 row-level crosswalk could restore the internal splits. |
| 70 ballot-990 rows | These are explicitly central/unallocated locality ballots, not ordinary area ballots. | **Final methodology:** keep them locality-only and out of area totals. | No work is planned without explicit election-specific area evidence. |
| 31 K17 composite rows | The component locality is known, but it has several 1995 areas and no component ballot-to-area crosswalk. | Keep area IDs blank; show each component total on its complete 1995 footprint with the standard unsplit-locality notice. | A component-level K17 crosswalk or equivalent register evidence. |
| 84 K18 composite rows | The component locality is known, but the 2008 source publishes it inside composite geometry without separate component area IDs. | Keep area IDs blank; show seven component totals in a non-overlapping partition of the three complete 2008 composite footprints with the same notice. | A more detailed official 2008 geometry/crosswalk source. |
| Entirely unassigned localities | The locality result is known, but no ballot in that locality has a supported area ID for that election. | **Final methodology:** show a labeled whole-locality fallback and keep public row assignments blank. | A detailed official crosswalk or independently reconcilable ballot-register source. |

The K17 Maghar station-number discrepancy is closed: the published vote count
is treated as complete and no missing-vote row is synthesized. The neutral
partial-presence cells, ballot 990, composite rows, and entirely unassigned
localities are documented end states rather than a general repair queue.
Polling-place addresses alone never justify an area assignment.

Statistical mode makes the dominant missing-municipality case visible without
pretending it is area-level data. For 314 election/locality or reviewed
component cases where no ballot has a supported statistical-area assignment,
the map shows the corresponding total on a display-only reviewed boundary with
the standard unsplit-locality notice. The nine K17/K18 component records retain
their election-era outer footprints and do not overlap their siblings. These
displays represent 5,462 unresolved ballot rows and 2,062,812 actual voters.
They do not write area IDs, alter the downloadable ballot assignments, or
increase the 94.00% row-level coverage figure.

Reviewed display geometry now also removes every material historical-host
overlap for the K17 Maghar, Kfar Qasem, Sakhnin, Arraba, and Tamra fallbacks and
the K18 Tzur Yitzhak, Maghar, Kfar Qasem, Sakhnin, Arraba, Tamra, Fureidis, and
Iksal fallbacks. K18 Kfar Bara has the opposite priority: its official 2008
polygon remains intact and is cut out of the Kfar Qasem fallback. These are
presentation-only geometry operations with measured overlap and one-square-
metre residual-overlap checks.

A second display-only rule covers 4,731 polygon-election memberships across
K21-K25. It publishes 2,269 polling-group units: 537 exact closed units and
1,732 representative units. The exact units cover 1,336 polygon memberships;
none carries an uncertainty notice. Direct official pre-election evidence supports K21,
K24, and K25. Consolidated final subdivisions in K21-K23 require continuous
locality/site identity and at least two direct-evidence elections agreeing on
the exact multi-area set; remaining K22/K23 groups retain the stricter
site-and-ballot-base rule. Representative units may contain multiple polling
groups and must pass majority precision and recall under three weighting models
or retain the most detailed placement with a notice. Geometry disconnection is
disclosed rather than used to merge groups. K25 uses the July planned register
and archived 27 October final register directly; the old July-only count of 12
reconciled planned sites is superseded. No broad network fallback remains.
Fifteen representative units require disclosed disconnected placement.
The cross-layer ownership audit combines result aggregates, generated polling
displays, and reviewed polling displays; it currently reports zero duplicate
election/statistical-area claims.
Public ballot assignments, per-area tables, and coverage remain unchanged. No
vote is divided or estimated.

The source audit found exactly one public CBS direct crosswalk for each K17-K25
election and one stable-ballot workbook for each transition ending K19-K25. The
CBS product catalog also identifies a polling-district boundary layer named
`kalpi_artzi`, but classifies it as internal and unavailable for public sale or
download. Of the archived K20-K25 CEC polling-place reports, only K23 contains
AGS. No second public in-scope crosswalk was found.

The recurring omissions are not random missing shapefile polygons. Sixteen
localities are omitted from all nine published crosswalks, accounting for
3,409 pending rows, and another 16 recur in seven or eight elections. This is
consistent with the CBS-documented limitation on address anchoring and
statistical-area treatment in many Arab and Druze localities. The complete
recurrence table is published in
`historical_crosswalk_locality_omission_recurrence.csv`.

Reviewed K17/K18 polling-register evidence now identifies the component
locality for 164 rows: 153 historical composite-municipality rows and 11
Ma'ale Iron rows. It resolves 49 K17 rows directly to one historical area.
Thirty-one K17 rows remain in component localities
with multiple 1995 areas, and all 84 K18 rows remain nested inside composite
2008 geometry that does not publish separate component area IDs. These rows are
preserved as component-level evidence even when a statistical-area assignment
is not possible. For presentation, two K17 component totals now use their full
1995 footprints and seven K18 component totals partition the complete 2008
Carmel City, Shaghur, and Baqa-Jatt footprints. All nine use the same notice as
other multi-area unsplit localities. This changes geometry presentation only.

The ArcGIS review is closed under the approved Tier A/B/C policy. Source
metadata states that statistical areas in Arab localities were merged, so 65
apparent locality partitions were rejected as locality totals rather than
detailed areas. One military/non-geographic case was also rejected. The only
structurally valid exact assignments are nine K21 rows: three Tier A rows in
Ar'ara-BaNegev and six Tier C rows in Jerusalem. K20 has no accepted ArcGIS
assignment. No 1-3 vote tolerance is used.

Official stable-ballot evidence produces 134 candidates. The site-safety audit
publishes 96 and rejects 38 K24 mixed-batch rows. One same-vintage contradiction
and 105 vintage-transition conflicts are retained in the audit and withheld.
The K23 AGS audit agrees with 6,775 of 6,776 comparable existing assignments,
withholds the one contradiction, and adds 74 direct assignments.

The supplied Kaplan K22-K25 map sources are now closed as assignment evidence.
Four payloads contain exactly one aggregate feature per locality. The additional
K25 payload contains 403 neighborhood aggregate points across 15 localities but
no boundaries, AGS IDs, or ballot crosswalk. After the continuity approvals, 51
remaining target rows in partially assigned municipalities represent 14,190
actual voters; the audit found zero defensible candidates and made no data
changes. The 54 continuity approvals use independent CEC polling-register and
CBS crosswalk evidence. Two moderate K19 Tel Sheva candidates and 15 mixed or
unallocated-register candidates remain withheld.

## Remaining Work

The map, data, production deployment, and ten-language SEO implementation are
complete. The remaining public-website work is operational:

1. add the subpath sitemap to the canonical host's root `robots.txt`, verify the
   domain in Google Search Console, submit the sitemap index, and inspect
   representative pages in every language after indexing begins;
2. monitor indexed coverage and real Core Web Vitals before changing the SEO
   route or asset strategy;
3. apply for and integrate AdSense using only the reviewed placements and
   consent behavior after Google supplies the publisher and slot IDs.

The exact plan and completion criteria are in `WEBSITE_LAUNCH_PLAN.md`.
Landscape-phone support, satellite imagery, and 3D buildings remain outside
scope.

The supplied Kaplan layers are exhausted locality/neighborhood aggregates.
Historical assignment limitations should be reopened only if the internal CBS
`kalpi_artzi` layer, another detailed official crosswalk, or independently
reconcilable ballot-register evidence becomes available.

Historical assignment gaps should only be reopened when a new official or
independently reconcilable source becomes available. Reusing a ballot number
across elections or approximate arithmetic is not sufficient evidence.

## Geometry Caveats

- Every assigned statistical-area ID resolves to a published geometry.
- Canonical feature counts are 2,661 for 1995, 3,030 for 2008, and 3,115 for
  2011. The 2011 layer includes 32 documented exact-ID ArcGIS supplements; the
  1995 layer includes two official transition-key unions, including the
  reverse-transition reconstruction of Modi'in Illit.
- The raw-source inventory distinguishes assignable geometry records from
  multipart pieces and structural/non-area records, and is published in
  `historical_geography_build_summary.json`.
- Detailed West Bank ArcGIS footprints are display derivatives except for those
  explicit exact-ID supplements. ArcGIS vote totals are never imported.
- K17/K18 preserve shared boundaries and clip replacement footprints against
  historical neighbors. Reviewed confirmation places the K17 Yehud area 8
  result on the non-conflicting historical component polygon between Or Yehuda
  area 4 and Yehud area 3. The map calls it Yehud; canonical transition
  provenance remains unchanged.
- The K17/K18 Hebron custom target uses the exact detailed 2011 Hebron
  footprint. Tribal results use one combined marker in every election because
  the derivative ArcGIS tribe footprints overlap surrounding areas and are not
  defensible as exclusive boundaries. K19-K25 exact tribe assignments remain
  separate in the downloadable data and are combined only in the web display.
- Marker assets are data-dependent at runtime: resultless West Bank proxies,
  Umm al-Fahm points, and facility points do not render. The 16 evacuated Gaza
  features remain in the canonical 1995 download but are hidden in K17.
- Population attributes attached to historical polygons are demographic
  proxies, not election-specific eligible-voter counts.
- The neutral grey land backdrop is visual context only. Detailed West Bank
  locality footprints are excluded from that backdrop so historical polygons
  do not render on top of current Ma'ale Adumim, Ariel, Beitar Illit, or
  Modi'in Illit shapes.

See `HISTORICAL_STATISTICAL_AREA_ASSIGNMENT.md` for the evidence hierarchy and
`public-data/v2/metadata/assignment-provenance/` for row-level audit artifacts.
