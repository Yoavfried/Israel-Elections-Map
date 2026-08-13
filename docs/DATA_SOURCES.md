# Data Sources

Last updated: 2026-08-13

## Election Results

Official Knesset election results package:

https://data.gov.il/api/3/action/package_show?id=26f9fa06-fcd7-4173-8df5-65797b63e857

Current project scope starts at K17 / 2006 and runs through K25 / 2022.

- Locality totals are generated from normalized ballot rows and reviewed
  locality identities; official locality summaries are validation evidence.
- Party columns are election-specific ballot letters and are never treated as
  stable party IDs across elections.
- K16 / 2003 is outside the current product scope.
- K25 can also be checked against the official results site:
  https://votes25.bechirot.gov.il/

## Archived K17 Results Workbook

`data/raw/archive_knesset17_results_17.xls` preserves a second public copy of
the K17 results workbook. It was retrieved from an independent open repository
and is kept as source-preservation and reconciliation evidence, not as a new
vote source. The workbook has 8,426 rows and 39 columns. All 36 compared ballot,
turnout, and party-vote fields match the normalized K17 table on every row.
There is one metadata-only difference: Sansana ballot 10 uses locality code
1328 in this workbook and 3777 in the normalized official CSV. The workbook
also preserves 8,262 rows with address text.

This closes the K17 result-source check. The documented eligible-voter recovery
below remains reproducible, but K17 has no further special result-repair queue.
The retrieval URL, byte size, and SHA-256 fingerprint are committed in
`docs/ELECTION_SOURCE_ARCHIVES.csv`.

## K17 Eligible-Voter Recovery

The official K17 result resource omits ballot-level eligible-voter counts.
Archived official reports under `data/raw/` provide the missing counts,
locality subtotals, regional-committee totals, and the national denominator.
`data/manual/k17_eligible_voters.csv` restores the denominator for all 8,277
ordinary result rows.

The same K17 resource omits a separate invalid-vote column, so normalization
derives invalid votes as actual voters minus valid votes and verifies that every
row reconciles. This includes Ras Ali ballot 1, whose official final-report row
confirms the edge case of 196 voters, 196 invalid votes, and zero valid votes.

Final-report image extraction supplies 8,199 rows, 14 more are recovered from
otherwise unaligned final-report lines, and one omitted zero-voter row is
recorded explicitly as zero. The remaining 63 rows use the official planned
list under exact subtotal or national reconciliation. The ordinary-register
total is 5,011,053.

The separate 3,569-person Gush Katif register brings the official national
denominator to 5,014,622. It has no ballot-level geographic distribution. The
public envelope/non-geographic aggregate therefore stores it as a technical
denominator bucket alongside 518 eligible voters from three non-geographic K17
camp rows: 4,087 in that bucket plus 5,010,535 geographically represented
eligible voters equals 5,014,622. The frontend does not calculate envelope
turnout from this mixed bucket. Full recovery methods are in
`docs/K17_ELIGIBLE_VOTER_RECOVERY.md`.

## Party/List Registry

`data/manual/party_registry.csv` is keyed by `(election, source_column)` because
the same ballot letters can identify different lists in different elections.
It tracks all 309 K17-K25 source columns: 297 published lists and 12 confirmed
zero-filled columns for lists that did not run. Those 12 rows remain in the
registry as source-audit evidence but are excluded from map and national-result
payloads. Any future zero-vote registry row must receive an explicit exclusion
reason before the build will publish.

All published Hebrew and English display names are reviewed. The 297 English
labels are stored in `data/manual/party_display_names_en.csv` and applied to the
registry by election and ballot letter, independently of the reviewed
Wikipedia URLs. The generated-data checks enforce link-presence continuity
across elections when the reviewed Hebrew display name and identity are shared.
Explicit reviewed exceptions cover identical short labels used by different
slates, such as `כח להשפיע`, so a leader link is not copied onto an unrelated
election entry.
`web/app/config/party-overrides.json` separates reviewed names and colors from
the data table, supports stable default colors by ballot letter, and allows
election-specific exceptions. All 297 published K17-K25 lists now have
reviewed colors. The deterministic fallback remains available for future
unreviewed additions but is not used by the current published elections.

`data/manual/election_rules.csv` records the applicable threshold, chamber
size, official result URL, and threshold source for every K17-K25 election.
K17-K19 use 2%; K20-K25 use 3.25%. `data/manual/election_mandates.csv` records
the official final seats won by each represented list. The web compiler rejects
an election unless registry votes reconcile, mandates sum to 120, and every
seat-winning list crossed that election's threshold. Positive-vote lists below
the threshold remain in the national view with zero mandates.

## Historical Ballot Crosswalks And Geometry

The CBS GIS catalog supplies one direct ballot-to-statistical-area table for
every current-scope election:

- K17 -> 1995 areas
- K18 -> 2008 areas
- K19-K25 -> 2011 areas

It also supplies the corresponding geometry, transition tables, and one
stable-ballot workbook for each transition ending K19-K25.
`scripts/fetch_cbs_historical_geography.py` records exact source URLs, byte
lengths, and SHA-256 hashes in
`data/raw/cbs_historical_geography/manifest.json`.

The official [2008 GIS download page](https://www.cbs.gov.il/he/cbsNewBrand/Pages/%D7%A9%D7%9B%D7%91%D7%95%D7%AA-%D7%9E%D7%9E%D7%92-%D7%9E%D7%A2%D7%A8%D7%9B%D7%AA-%D7%9E%D7%99%D7%93%D7%A2-%D7%92%D7%90%D7%95%D7%92%D7%A8%D7%A4%D7%99%D7%AA-GIS-%D7%9E%D7%A4%D7%A7%D7%93-2008.aspx),
[transition-key page](https://www.cbs.gov.il/he/cbsNewBrand/Pages/%D7%9E%D7%99%D7%93%D7%A2-%D7%92%D7%90%D7%95%D7%92%D7%A8%D7%A4%D7%99-%D7%9E%D7%A4%D7%A7%D7%93-2008.aspx),
and [geographic-layer catalog](https://www.cbs.gov.il/he/Pages/geo-layers.aspx)
were checked for alternate geometry and crosswalk products. The CBS GIS
[`product_gis` catalog](https://www.cbs.gov.il/he/subjects/Documents/product_gis.pdf)
names a nationwide polling-district boundary layer,
`kalpi_artzi`, but classifies it as internal and unavailable for public sale or
download. No second public K17/K18 detailed crosswalk was found.

`historical_geography_build_summary.json` audits the downloaded geometry before
normalization. The 1995 archive contains 2,659 unique assignable IDs before two
official transition-key unions, the 2008 source contains 3,030, and the 2011
source contains 3,083 before 32 exact-ID supplements. Multipart pieces and
structural records without valid area IDs are counted separately. This audit
found no parser-level loss of a positive, fully identified statistical area.

The archived K20-K25 CEC polling-place workbooks were inspected separately.
Only K23 contains an AGS field. Its direct AGS evidence adds 74 assignments
after 6,775 of 6,776 comparable existing targets agree and the one conflict is
withheld. The stable-ballot workbooks produce 134 inferred candidates. The
election-specific polling-place safety audit withholds 38 K24 candidates after
showing that their decimal batches combine planned ballots from multiple areas:
ten in Daliyat al-Karmel and 28 in Umm al-Fahm. Ninety-six stable links publish.
All same-vintage and transition conflicts remain withheld.

A separate reviewed continuity pass compares official CEC polling-place
reports across elections with official same-vintage CBS crosswalk targets. It
accepts 54 additional high-confidence links where polling-register identity is
supported by exact ballot/place continuity or an independently reconcilable
crosswalk gap. The approved source fingerprints and notes are committed in
`data/manual/cross_election_stat_area_reviews.csv`. These links are explicitly
synthetic; polling-place coordinates and address geolocation are not used.

The final K25 register prompted a fresh review of Modi'in-Maccabim-Re'ut
ballots 83 and 94. In July both ballots were in polling-site group 25 at
Inbalim School; every mapped peer in that group targets statistical area 31.
The October register moved the same two ballot identities together to new site
109 at Nof Harim School, and its eligible counts exactly match the final result
rows. The new site has no independent direct area crosswalk, so these remain
high-confidence synthetic links rather than authoritative final-site matches.
Their target, area 31, is retained; the evidence labels and review notes now
state the planned-group and final-pair logic explicitly.

The same final-register audit independently confirms K25 Modi'in Illit ballot
47 at statistical area 9. The ballot remains at the same site, school, and
address in the July and October registers; every mapped peer at that site
targets area 9, and K24 directly maps ballot 47 to area 9. The general safety
audit now accepts this narrow single-area-site peer pattern. It does not relax
the rejection of final polling batches that span multiple candidate areas.

Two downloadable ArcGIS FeatureServer layers provide detailed display
footprints, 32 explicit exact-ID 2011 geometry supplements, and aggregate
evidence for K20/K21. Their service descriptions state both that the election
output is not official and that statistical areas in Arab localities were
merged. After classifying those dissolved locality totals correctly, the audit
accepts only nine exact K21 links and no K20 links. They never replace official
ballot or vote values.

The same two election layers were also checked for the four remaining tiny
West Bank display proxies: Rotem (3782), Maskiyot (3785), Avnat (3786), and
Mavo'ot Yeriho (3825). Neither layer contains any of those locality codes or
names. A separate public ArcGIS map package published by Peace Now contains a
single 2024 built-up polygon for each of the four:

- [Peace Now layers](https://www.arcgis.com/home/item.html?id=e3848dc0a04c44cc9ad9f7db228cd3a3)
- source layer `Settlements_and_outposts_14112024`
- retained source feature IDs and dates in
  `data/manual/west_bank_display_boundary_replacements.geojson`

Those four reviewed footprints are production display geometry only. They
replace the CBS point-like proxies but do not provide ballot-to-area evidence.
The selected polygons were checked against the current proxies, OpenStreetMap
residential footprints, the available K24 Kaplan polygons for Rotem and
Maskiyot, and the Civil Administration jurisdiction layer published through
[ArcGIS](https://services5.arcgis.com/jT9QGg5EVnLcQqRI/arcgis/rest/services/Tzav_Bdvar_Tchum_Shiput/FeatureServer).
The jurisdiction polygons are broader legal/administrative extents and are not
used as the displayed built-up boundaries. No candidate intersects another
current locality display feature.

### Kaplan Election-Map Payloads

The supplied Kaplan map applications were traced to five public data payloads:

| Election | Application/source payload | Observed grain |
|---|---|---|
| K22 | [September 2019 GeoJSON](https://elections.kaplanopensource.co.il/setl2013_results_2019b.geojson) | One polygon feature per locality |
| K23 | [2020 Geobuf](https://elections.kaplanopensource.co.il/2020/_6) | One polygon feature per locality |
| K24 | [2021 Geobuf](https://elections.kaplanopensource.co.il/2021/_7) | One polygon feature per locality |
| K25 | [2022 locality Geobuf](https://elections.kaplanopensource.co.il/2022/_7) | One polygon feature per locality |
| K25 | [2022 neighborhood Geobuf](https://elections.kaplanopensource.co.il/2022/ynet/_9) | 403 aggregate points across 15 localities |

`scripts/audit_kaplan_map_sources.py --fetch` downloads these files to the
ignored raw-data directory, records hashes in
`data/processed/manifest/kaplan_map_sources.*`, and writes the audit under
`data/processed/audits/kaplan_map_source_*`. The Geobuf properties are decoded
by `scripts/geobuf_properties.py` without executing publisher JavaScript.

The four locality layers expose no statistical-area identifier and have exactly
one feature per locality. The neighborhood layer exposes a neighborhood ID and
representative point, but no boundary, AGS identifier, or ballot crosswalk. It
therefore cannot prove a ballot-to-statistical-area assignment. These sources
are retained as reproducible locality-total cross-checks only; no vote values
are imported into production outputs. K24 polygons for Rotem and Maskiyot are
used only as secondary validation of the separate reviewed display footprints;
the Kaplan geometries themselves are not imported.

Display-only reuse is recorded separately from assignment evidence. The exact
Hebron footprint is reused for the two reviewed K17/K18 custom assignments, and
Ganei Modi'in uses a detailed footprint from K21. The ArcGIS tribal footprints
are not accepted as exclusive boundaries: they come from the derivative,
explicitly non-official election layers and materially overlap surrounding
areas. The map therefore uses one combined tribal marker in every election.
Exact tribe IDs and statistical-area assignments remain separate in the
downloadable ballot and aggregate tables. None of these display choices creates
or reallocates votes.

For K21-K25, official polling registers and final results support a nationwide
polling-group display policy. K21, K24, and K25 use direct pre-election
evidence. Consolidated final subdivisions in K21-K23 are accepted only when
locality, official site ID, and normalized site text remain continuous and at
least two direct-evidence elections agree on the exact multi-area set. Other
K22/K23 groups retain the stricter site-and-ballot-base continuity rule. The
final display layer produces 537 exact closed units and 1,732 representative
units over 4,731 polygon-election memberships, with no remaining broad
fallback. Exact units cover 1,336 polygon memberships and have no uncertainty
notice.
Bilingual notices remain on representative placements.
Disconnected geometry is disclosed rather than used to force larger groups.

K25 now uses the July 2022 polling-place workbook as the planned register and
the archived 27 October 2022 workbook as the final register. The later file has
11,707 rows, compared with 11,547 in July, and records final subdivisions and
site changes. Re-running the display audit changed K25 from 591 to 600 units:
192 exact and 399 representative units became 193 exact and 407 representative
units, while polygon memberships rose from 1,210 to 1,225. The final displayed
grouping changed in 14 K25 localities. It also removed four weak K22/K23
continuity displays covering two recurring relationships because the revised
K25 site topology no longer supplied the second direct reference required by
the approved rule. The final cross-layer ownership audit still reports zero
duplicate election/area claims.

Planned-only K25 sites are reconciled to unique final-result sites only through
overlapping candidate areas, polling-place identity, and eligible-voter balance.
These display rules leave downloadable ballot assignments, area aggregates,
and coverage figures unchanged.

The evidence audit and ownership policy are generated by
`scripts/audit_statistical_area_polling_group_evidence.py`,
`scripts/build_statistical_area_polling_group_policy.py`, and
`scripts/polling_group_flow.py`. Non-exact networks use
`scripts/polling_group_ownership.py` and `scripts/polling_group_partition.py`.
Planned eligible counts are used as edge proportions rather than assumed to
equal final eligible totals. K17-K19 have no compatible official polling-group
register. K20 has only a post-election register without an official site
identifier, so none of those elections is inferred into the policy.

The web map also uses a current locality, reviewed composite, or reviewed
component footprint when that result unit has no supported statistical-area
assignments at all. The corresponding total is labeled as a display-only
fallback and is not treated as historical assignment evidence. Its
election-by-election audit is published as
`historical_municipality_display_fallbacks.csv`.

`scripts/audit_election_source_geography_fields.py` publishes the complete
source-schema inventory. The recovered catalog contains no second in-scope
crosswalk or stability workbook for these elections.

Recurring crosswalk omissions are published in
`historical_crosswalk_locality_omission_recurrence.csv`. Sixteen localities are
absent from all nine public crosswalks. This is consistent with the CBS
[methodological note on address anchoring](https://www.cbs.gov.il/he/publications/doclib/2021/socio_eco17_1832/intro_h.pdf),
which documents substantially more limited residential-address anchoring in
Arab and Druze localities. It is evidence of a public-source limitation, not
proof that residents or historical polygons are absent.

For K17 and K18, reviewed polling-register scans and tables identify 153 rows
inside three historical composite municipalities and another 11 Ma'ale Iron
rows with their component locality. The exact ranges and page evidence are
committed in
`data/manual/historical_composite_ballot_components.csv`. These identities are
kept even when the historical source does not expose a component statistical
area. A polling-place address locates the station and may corroborate the
component locality; it does not establish the residential area of its voters.

See `docs/HISTORICAL_STATISTICAL_AREA_ASSIGNMENT.md` for the exact precedence,
vintage rules, supplement IDs, audit results, and current coverage.

## Current Locality Display Geometry

The 2022 FileGDB is canonical for current locality display geometry and for a
future election that publishes a direct 2022 crosswalk. K17-K25 statistical
results continue to use their historical targets.

Canonical raw source:

- `data/raw/ezorim_statistiim_2022.gdb`
- layer `statistical_areas_2022`
- 3,857 source polygon features
- 1,387 dissolved locality/display features
- 1,242 dissolved features with one statistical-area component
- 145 dissolved localities with multiple components

The dissolved layer retains 58 unlabeled land polygons as neutral context so
they do not appear as water. Kinneret remains unfilled. The previous partial
`data/raw/statistical-areas-2022.geojson` export is no longer a project source.

Relevant source fields:

| Field | Meaning |
|---|---|
| `SEMEL_YISHUV` | Locality code |
| `SHEM_YISHUV` | Hebrew locality name |
| `SHEM_YISHUV_ENGLISH` | English locality name |
| `STAT_2022` | Area code within locality |
| `YISHUV_STAT_2022` | Combined locality/area code |
| `ROVA` | Quarter code where present |
| `TAT_ROVA` | Sub-quarter code where present |
| `COD_TIFKUD` | Function/type code |

`data/manual/composite_localities.csv` defines four election-time composite
municipalities. `data/manual/joined_locality_composites.csv` defines
source-backed host/result unions for elections where a small register was
published under a nearby host result. Ganei Modi'in is joined to Modi'in Illit
in K17-K20, matching its historical municipal status before its 2016
[independence](https://www.cbs.gov.il/he/mediarelease/DocLib/2016/304/01_16_304b.pdf);
the separate statistical-area display proxy is hidden in K19 and K20 without
deleting its canonical geometry.

`scripts/audit_joined_locality_continuity.py` checks recurring joined-locality
relationships against the extracted official K18/K19 registers and the full
official K20-K25 polling-place workbooks. It accepts explicit attachment fields,
unique exact eligible-voter reconciliation, or strictly bounded continuity;
address geolocation is never used. Its 175-row evidence table records 38 active
automatic approvals and 137 covered, contradicted, or insufficient cases.

## Locality Classification Evidence

The official CBS 2022 locality workbook and definitions support the current
no-standalone-result audit:

- https://www.cbs.gov.il/he/publications/Pages/2019/%D7%99%D7%99%D7%A9%D7%95%D7%91%D7%99%D7%9D-%D7%91%D7%99%D7%A9%D7%A8%D7%90%D7%9C.aspx
- https://www.cbs.gov.il/he/publications/DocLib/2019/ishuvim/bycode2022.xlsx
- https://www.cbs.gov.il/he/publications/DocLib/2019/ishuvim/intro.pdf

The partial-presence audit also uses the 2005, 2008, 2012, 2014, 2018,
2019, and 2020 annual locality workbooks from that CBS collection. Each
election is compared with the closest pre-election register; the resulting
227-row classification is published in
`docs/LOCALITY_PARTIAL_GAP_AUDIT.csv`.

Reviewed form and population values are stored in
`data/manual/locality_result_presence_reviews.csv`. These 2022 classifications
do not by themselves prove a separate voter register in an older election.
Election-specific joins require independent result evidence.

Section 70 of the Knesset election law permits joining an area with fewer than
100 eligible voters to a nearby area:

https://www.gov.il/apps/elections/elections-knesset-17/heb/law/ElectionLaw.html

The resulting secret-ballot aggregate cannot be split into component party
totals. Where the source establishes the host, locality mode may display the
host and attached polygons as one election-specific union.

## 2022 Census Attributes

The 2022 census package is available at:

https://data.gov.il/api/3/action/package_show?id=2022

Resource `9a9e085f-3bc8-41df-b15f-be0daaf99e30` includes `LocalityCode`,
`StatArea`, `StatAreaCmb`, and census measures. No geometry resource was found
in the inspected package.

## Reuse And Provenance

Keep the most complete official/raw source for each vintage. Canonical inputs
are the CBS 1995 archive, 2008 FileGDB, 2011 FileGDB, and 2022 FileGDB. ArcGIS
layers are derivative supplement/display sources with explicit provenance.

Project-authored public data and reviewed data tables use the MIT Data License
defined in `LICENSE-DATA`. The website, pipeline implementation, presentation,
and project documentation are protected separately under `LICENSE-WEBSITE`.
CBS and other official source material remain subject to their source terms;
see `THIRD_PARTY_NOTICES.md`.
