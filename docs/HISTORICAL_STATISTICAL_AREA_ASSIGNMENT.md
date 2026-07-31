# Historical Statistical-Area Assignment

Last updated: 2026-07-30

## Decision

Statistical-area results represent the areas assigned to each ballot register.
The project starts from official ballot-to-area evidence and leaves a row
unresolved when no source supports a unique area.

Assignment precedence is:

1. official envelope or reviewed non-geographic handling;
2. reviewed historical override where independent evidence disproves a direct
   crosswalk target;
3. official election-specific CBS ballot crosswalk;
4. direct K23 CEC AGS evidence;
5. reviewed exact ArcGIS residual reconstruction;
6. official CBS stable-ballot propagation when all same-vintage evidence agrees;
7. approved high-confidence cross-election polling-register continuity;
8. reviewed K17/K18 composite polling-register evidence identifying the
   component locality;
9. election-vintage locality fallback only when one area exists;
10. reviewed custom geography where no historical area is supported;
11. unresolved.

No assignment is accepted from a merely similar ballot number, an approximate
aggregate match, or a polling-place location alone.

## Election Vintages

| Election | Year | Area vintage | Official crosswalk |
|---|---:|---:|---|
| K17 | 2006 | 1995 | `Kalpi2006_stat1995.xls` |
| K18 | 2009 | 2008 | `kalpi2008_stat2008.xlsx` |
| K19 | 2013 | 2011 | `kalpi2013_stat2011.xlsx` |
| K20 | 2015 | 2011 | `kalpi2015_stat2011.xlsx` |
| K21 | Apr 2019 | 2011 | `kalpi_April2019_stat2011.xlsx` |
| K22 | Sep 2019 | 2011 | `kalpi_September2019_stat2011.xlsx` |
| K23 | 2020 | 2011 | `kalpi_March2020_stat2011.xlsx` |
| K24 | 2021 | 2011 | `kalpi_March2021_stat2011.xlsx` |
| K25 | 2022 | 2011 | `kalpi_November2022_stat2011.xlsx` |

K25 deliberately stays on 2011 areas. Its official crosswalk targets 2011, and
at least 3,543 directly assigned K25 rows point to 2011 areas that split across
multiple 2022 areas. A future election should use 2022 geometry only when an
official 2022 ballot crosswalk exists.

## Source Inventory

`scripts/fetch_cbs_historical_geography.py` enumerates the public CBS GIS
catalog, downloads the nine crosswalks, seven stable-ballot workbooks, three
historical geometry vintages, and transition tables, verifies signatures and
sizes, and writes a SHA-256 manifest.

`scripts/audit_election_source_geography_fields.py` audits the available source
schemas. The downloaded CBS catalog contains exactly one in-scope direct
crosswalk for each K17-K25 election and one stability workbook for each
transition ending K19-K25. No alternate in-scope ballot-geography workbook is
listed. Among the archived K20-K25 CEC polling-place reports, only K23 contains
an AGS field.

The CBS GIS product catalog identifies a nationwide polling-district boundary
layer named `kalpi_artzi`, but marks it as an internal product that is not
available for public sale or download. It therefore confirms that more direct
geometry exists inside CBS without supplying a reproducible public input for
this project.

The historical geometry builder also publishes a raw-source inventory rather
than treating every shapefile record as an area. The 1995 archive has 3,210 raw
records: 2,834 assignable geometry records representing 2,659 unique area IDs,
175 repeated multipart pieces, and 376 structural or non-area exclusions. The
2008 source has 3,030 assignable unique areas and 41 structural records. The
2011 source has 3,083 assignable official areas and 104 structural records,
before 32 audited exact-ID supplements are added. These counts rule out an
accidental parser-level loss of positive, identified statistical areas.

The machine-readable inventory is published as
`metadata/assignment-provenance/election_source_geography_field_audit.*`.

## Evidence Paths

### Official Direct Crosswalks

The nine CBS crosswalks provide 83,237 final row assignments. K17 tenths
encoding and later decimal subdivisions are normalized explicitly:

- in K17, `10` means ballot 1, while values such as `61` and `62` are
  subdivisions of ballot 6;
- in later elections, subdivisions such as `1.1` and `1.2` inherit a direct
  base-ballot target when the official crosswalk maps ballot 1;
- the crosswalk's combined area ID is authoritative even when it crosses the
  result row's locality boundary;
- `Stat08_Unite` and `Stat11_Ref` are demographic reference fields, not
  instructions to merge election areas.

Five K19 targets contradicted independent same-vintage evidence. Reviewed rows
in `data/manual/historical_stat_area_overrides.csv` replace those links using
adjacent-election and ArcGIS evidence. They are labeled synthetic corrections,
not silently presented as direct crosswalk rows.

### K23 Direct AGS

The official K23 CEC report supplies AGS for 6,849 ballot keys. Against 6,776
rows already assigned by the CBS crosswalk, 6,775 agree and one contradicts.
The contradiction is withheld. The remaining direct AGS evidence assigns 74
previously pending rows representing 29,685 actual voters.

These links use `assignment_evidence_class=official_direct_ags` and are not
synthetic. Full validation, conflicts, candidates, and hashes are published
under `metadata/assignment-provenance/k23_cec_ags_*`.

### Official Stable-Ballot Workbooks

The seven CBS transition workbooks identify ballot registers treated as stable
between elections. A pending row is propagated only when every assigned member
of its same-vintage stability component agrees on one area. Decimal
subdivisions are evaluated through the historical base ballot.

This adds 134 links representing 35,129 actual voters:

| Election | Rows | Actual voters |
|---|---:|---:|
| K19 | 2 | 537 |
| K20 | 43 | 16,676 |
| K22 | 1 | 344 |
| K24 | 87 | 17,082 |
| K25 | 1 | 490 |

One same-vintage conflict and 105 conflicts crossing a statistical-area
vintage transition are withheld. Stable-ballot links are high-confidence
inferences, not direct election-specific crosswalk rows.

### Reviewed Cross-Election Polling-Register Continuity

The CEC polling-register reports can identify an exact recurring polling place
across elections. Fifty rows were approved only where that register continuity,
combined with direct CBS targets elsewhere in the same historical vintage,
supports one unique area. The reviewed table validates the exact source row,
electorate, turnout, target vintage, target locality, and target geometry before
the link is applied.

| Election | Rows | Eligible voters | Actual voters |
|---|---:|---:|---:|
| K18 | 1 | 613 | 459 |
| K19 | 6 | 4,325 | 1,838 |
| K20 | 24 | 15,820 | 9,825 |
| K21 | 1 | 574 | 235 |
| K22 | 2 | 1,380 | 689 |
| K23 | 2 | 1,399 | 776 |
| K24 | 3 | 1,832 | 545 |
| K25 | 11 | 7,105 | 3,710 |
| **Total** | **50** | **33,048** | **18,077** |

Thirty-nine approvals preserve the same ballot number and exact polling place,
six use an exact place with an otherwise documented register change, three use
a renumbered exact place, one uses a prior exact ballot/place link, and one
reconstructs an isolated K18 crosswalk gap from the surrounding official
evidence. Addresses and geocoded coordinates are not used. The two moderate K19
Tel Sheva candidates and 15 mixed or unallocated-register candidates are
withheld.

### ArcGIS Residual Reconstruction

The 2015 and April 2019 FeatureServer layers can validate or reconstruct some
K20/K21 area totals, but their item descriptions explicitly state that
statistical areas in Arab localities were merged and that the election product
is not official. A locality-wide feature is therefore never treated as a
detailed statistical area.

The audit classifies every feature before arithmetic:

| Election | Detailed or single-area records | Dissolved locality aggregates |
|---|---:|---:|
| K20 | 2,826 | 35 |
| K21 | 2,655 | 34 |

Sixty-five reviewed locality decisions were rejected after this metadata check,
and one military/non-geographic candidate was rejected. K20 has no accepted
ArcGIS reconstruction. K21 has two accepted exact decisions:

| Tier | Locality | Rows | Actual voters | Basis |
|---|---|---:|---:|---|
| A | Ar'ara-BaNegev | 3 | 965 | Unique exact residual across ballot, eligible, actual, valid, invalid, and party totals. |
| C | Jerusalem | 6 | 2,634 | One isolated residual area matches exactly; unrelated zero-ballot source deltas remain documented. |

Tier B/C approval was permission to use defensible evidence, not permission to
accept a 1-3 vote discrepancy. No tolerance-based Tier B row is published.
ArcGIS party vectors and vote totals are never copied into election results.

### Kaplan K22-K25 Source Audit

The supplied Kaplan election maps were traced to their underlying payloads and
decoded locally. They are aggregate map layers, not hidden ballot crosswalks:

| Source | Features | Unique localities | Target localities present | Exact eligible + actual totals | AGS or ballot crosswalk |
|---|---:|---:|---:|---:|---|
| K22 locality polygons | 1,173 | 1,173 | 3 of 3 | 1,165 of 1,172 comparable | No |
| K23 locality polygons | 1,172 | 1,172 | 3 of 3 | 1,154 of 1,172 comparable | No |
| K24 locality polygons | 1,214 | 1,214 | 11 of 11 | 1,203 of 1,214 comparable | No |
| K25 locality polygons | 1,215 | 1,215 | 7 of 7 | 1,213 of 1,215 comparable | No |
| K25 neighborhood points | 403 | 15 | 1 of 7 | 14 of 15 comparable | No |

After the reviewed continuity approvals, the source-specific target scope
excludes entirely unmatched municipalities and contains 53 remaining rows
representing 14,983 actual voters:

| Election | Ballot-base 990 rows | 990 actual voters | Other rows | Other actual voters |
|---|---:|---:|---:|---:|
| K22 | 1 | 422 | 1 | 363 |
| K23 | 1 | 234 | 1 | 430 |
| K24 | 31 | 8,664 | 4 | 749 |
| K25 | 9 | 2,730 | 5 | 1,391 |
| **Total** | **42** | **12,050** | **11** | **2,933** |

Each locality payload supplies only the same whole-locality total already known
from the official ballot rows, so it provides no smaller target total for an
exact partition. The K25 neighborhood payload supplies aggregate representative
points but no neighborhood boundaries, statistical-area IDs, or contributing
ballot keys. It reaches only Haifa in the remaining target scope, where the
pending records are two ballot-base 990 rows; a point cannot prove their area.

The audit therefore ran zero partition searches, emitted zero assignment
candidates, and changed no published data. Small source-snapshot differences in
turnout or valid/invalid classification remain in the reconciliation output and
are not copied into the normalized election results. The 50 continuity
approvals come from independent CEC polling-register and CBS crosswalk evidence,
not from the Kaplan payloads.

### Composite Polling-Register Evidence

The K17 scan and K18 official polling-place table identify which component
locality supplied 153 ballot rows published under Carmel City, Shaghur, and
Baqa-Jatt. The K17 scan identifies another 11 Ma'ale Iron rows as Zalafa,
Musmus, Musheirifa, or Salem, for 164 reviewed rows in total. The reviewed
ranges and page-level evidence are preserved in
`data/manual/historical_composite_ballot_components.csv`.

Component identity is not treated as a statistical-area number. It enables a
deterministic assignment only when that component has exactly one area in the
active vintage. Of the 80 K17 component-evidence rows, 49 have such a target
and 31 remain unresolved in Daliyat al-Karmel or Baqa al-Gharbiyye, which have
multiple 1995 areas. All 84 K18 rows remain unresolved because the 2008 source
stores those component identities inside composite-municipality geometry and
does not publish separate component area IDs. The component evidence remains
available for a future finer source even where no area link is published now.

### Single-Area And Custom Rules

A locality fallback is allowed only when the active historical geography has
exactly one canonical area. This assigns 3,845 rows. K17/K18 retain 92 reviewed
custom-geography rows because their active historical geometry cannot
distinguish the later 2011 areas: 90 tribal rows use one combined Negev marker,
while the two Hebron rows use the audited detailed Hebron footprint copied from
the exact 2011 area geometry.

### Whole-Locality Display Fallback

The web map uses a separate display rule when an election/locality has zero
supported ballot-to-area assignments. It shows the locality aggregate on a
current locality or reviewed historical-composite boundary and adds an info
notice stating that no area-level assignment exists. It never writes a
`stat_area_id`, changes a ballot row, or increases statistical-area coverage.

| Election | Display records | Represented ballot rows | Actual voters |
|---|---:|---:|---:|
| K17 | 50 | 313 | 126,182 |
| K18 | 32 | 505 | 188,962 |
| K19 | 33 | 556 | 211,739 |
| K20 | 33 | 563 | 258,064 |
| K21 | 32 | 596 | 224,699 |
| K22 | 32 | 607 | 264,572 |
| K23 | 32 | 615 | 295,712 |
| K24 | 32 | 833 | 202,743 |
| K25 | 32 | 792 | 255,412 |
| **Total** | **308** | **5,380** | **2,028,085** |

The generated audit records every substituted display boundary and the totals
shown. These records remain separate from the downloadable statistical-area
aggregates. None of the 308 election/locality fallback cases overlaps a site in
the currently available official polling-register evidence, so the
polling-group network method cannot subdivide any of them.

### Polling-Group Exact and Representative Placement

Official polling registers sometimes place several statistical areas in one
polling group. The final results then identify the contributing ballot rows but
do not provide a vote split among those areas. Treating the final host area as
the exclusive result would therefore leave populated polygons empty and assign
all votes to an arbitrary host.

The map first looks for a closed pairing between a set of polygons and a set of
final polling groups:

1. A polling group's value is the exact sum of its final ballot rows.
2. Its candidate polygons are only the areas explicitly linked to that group by
   official pre-election evidence.
3. A combined unit is exact only when all votes from its polygons and only
   votes from those polygons are included. Exact units may contain several
   polygons and several polling groups.
4. For exactly balanced eligible-voter networks, a transport-flow solver
   calculates the minimum and maximum possible flow on every area-to-group
   edge. Edges whose maximum is zero are removed; each remaining closed graph
   component is an exact display unit.
5. A closed official network with a small documented planned/final electorate
   difference remains exact as a whole, but is not split internally by flow.
6. Exact closed units have no uncertainty notice.

Only the remaining networks use representative placement. Within each such
network, every candidate polygon is assigned once, every final polling group
receives at least one polygon, and a group may receive only one of its own
candidate polygons. The solver first requires connected ownership and
maximizes the weakest represented share of planned electorate, then total
represented electorate, then applies a stable deterministic tie-break.
If no connected solution exists, a disconnected representative placement is
accepted only after the solver proves that no connected all-groups-covered
solution exists. Its notice discloses the disconnected geometry.
If unique ownership is impossible because there are fewer polygons than
groups or several groups have the same sole candidate, one broad network
aggregate is displayed with an uncertainty notice instead.

No vote is divided, estimated, or moved between statistical areas. Exact units
state a set-level truth, not an invented split inside the combined geometry.
Representative units remain map placement and retain their bilingual
uncertainty notices. Existing directly assigned result rows inside a network
are retained exactly once with the unit owning their polygon.
Planned-to-final eligible-voter differences never change final vote totals.

Representative notices now distinguish two directions of uncertainty. A
possible inflow lists candidate areas whose voters may contribute to the result
shown on the selected unit. A possible outflow lists the other displayed areas
whose polling groups may contain voters from the selected unit. Units affected
in both directions list both sets. When the evidence proves uncertainty but
does not support either directional list, the notice remains generic. The
generated metadata records `ambiguity_type`, both area-ID sets, and both
human-readable area-number sets.

Direct same-election evidence is available for K21 and K24 from official
pre- and post-election registers, and for K25 from the official pre-election
register plus final results. K22 and K23 use continuity only when the locality,
official site ID, normalized site text, and final ballot base match in at least
two direct-evidence elections. Their candidate polygons are the intersection of
the matching reference sets. K17-K19 have no compatible polling-group register.
The K20 file is post-election only and has no official site ID, so it cannot
satisfy either the direct or continuity rule.

| Election | Evidence | All display units | Exact closed units | Representative units | Owned polygon memberships | Representative components | Broad fallbacks |
|---|---|---:|---:|---:|---:|---:|---:|
| K21 | Direct official registers | 167 | 8 | 159 | 352 | 123 | 0 |
| K22 | Two-reference continuity | 344 | 0 | 344 | 656 | 235 | 0 |
| K23 | Two-reference continuity | 352 | 0 | 352 | 676 | 239 | 0 |
| K24 | Direct official registers | 670 | 152 | 518 | 1,215 | 153 | 6 |
| K25 | Direct official register + final results | 684 | 95 | 589 | 1,176 | 217 | 3 |
| **Total** |  | **2,217** | **255** | **1,962** | **4,075** | **967** | **9** |

Compared with the direct statistical-area result tables, the approved policy
recovers 697 election-specific polygon placements that would otherwise be
blank: 52 in K21, 76 in K22, 81 in K23, 228 in K24, and 260 in K25. It does not
color a remaining blank polygon without qualifying polling-group evidence.

The 255 exact units cover 677 polygon-election memberships and 397 final
polling groups. Ninety-four exact units combine more than one polling group.
The flow audit tested ten exactly balanced closed networks; no impossible-edge
removal divided a real network into more than one smaller closed component.
The full reproducible edge bounds are published in
`statistical_area_polling_group_exact_groups.csv`.

Of the 967 representative components, 950 have connected ownership and 17
require disclosed disconnected placement. All nine broad fallback networks are
connected. The bounded ownership search completed without reaching its search
limit. Thirty-one planned groups in 24 direct-evidence components have no
identifiable final result row; those groups are omitted, and polygons that only
they could own remain ordinary or neutral rather than being absorbed into
another result.

Jerusalem area 1024 illustrates the rule:

| Election | Final polling group | Representative polygons |
|---|---|---|
| K21 | Ballots 228.1-228.4 | Areas 1022 and 1024; shared area 864 is represented by another group |
| K22 | Ballots 228.1-228.4 | Areas 864, 1022, and 1024, using two-reference continuity |
| K23 | Ballots 228.1-228.4 | Areas 864, 1022, and 1024, using two-reference continuity |
| K24 | Ballots 228.1-228.4 | Areas 1022, 1023, and 1024; shared area 864 is represented by another group |
| K25 | Ballots 36.1-36.4 | Areas 1022, 1023, and 1024; shared area 864 is represented by another group |

K19 and K20 area 1024 remain separate because no comparable consolidation is
established for those elections.

The reproducible chain is:

- `scripts/audit_statistical_area_polling_group_evidence.py`
- `scripts/build_statistical_area_polling_group_policy.py`
- `scripts/polling_group_flow.py`
- `scripts/polling_group_ownership.py`
- `scripts/build_statistical_area_result_aggregates.py`
- `scripts/build_statistical_area_polling_group_displays.py`

The generated policy, audit, fallback, geometry, result, and metadata files live
under `data/processed/audits`, `data/processed/geographies`, and
`data/processed/public`. The web compiler validates that no ballot or polygon is
owned twice and that every displayed total reconciles to its source rows.

## Published Provenance Classes

| Evidence class | Rows | Synthetic link |
|---|---:|---|
| `official_direct_crosswalk` | 83,237 | No |
| `official_direct_ags` | 74 | No |
| `deterministic_single_area_locality` | 3,845 | No |
| `official_stability_inferred_link` | 134 | Yes |
| `reviewed_exact_aggregate_inferred_link` | 9 | Yes |
| `reviewed_cross_election_inferred_link` | 5 | Yes |
| `reviewed_polling_register_continuity_inferred_link` | 50 | Yes |
| `reviewed_custom_geography` | 92 | No |
| `non_geographic` | 3,585 | No |
| `unresolved` | 5,498 | No |
| **Total** | **96,529** | |

Every public ballot row carries `assignment_evidence_class`,
`assignment_confidence`, and `assignment_is_synthetic_link`, together with the
more specific method and source fields.

## Current Coverage

Coverage is the share of actual voters in geographic scope with a supported
statistical-mode target. Reviewed K17/K18 custom geographies count as supported
map targets; envelopes and other non-geographic rows are outside the
denominator.

| Election | Vintage | Supported rows | Pending rows | Pending actual voters | Supported voter share |
|---|---:|---:|---:|---:|---:|
| K17 | 1995 | 7,916 | 358 | 136,480 | 95.47% |
| K18 | 2008 | 8,741 | 518 | 189,252 | 94.14% |
| K19 | 2011 | 9,317 | 558 | 212,413 | 94.13% |
| K20 | 2011 | 9,545 | 567 | 259,204 | 93.55% |
| K21 | 2011 | 9,855 | 597 | 224,925 | 94.51% |
| K22 | 2011 | 9,922 | 609 | 265,357 | 93.65% |
| K23 | 2011 | 10,006 | 617 | 296,376 | 93.08% |
| K24 | 2011 | 11,251 | 868 | 212,156 | 94.71% |
| K25 | 2011 | 10,893 | 806 | 259,533 | 94.01% |

The 5,498 pending rows are fully classified:

- 5,245 belong to entire localities omitted from an official crosswalk;
- 55 use an election locality identity absent from the active historical
  vintage;
- 31 are K17 component-locality rows where the component has multiple 1995
  areas but no component crosswalk;
- 84 are K18 component-locality rows nested in composite 2008 geometry;
- 70 are central ballot 990 rows intentionally retained at locality level;
- 13 are specific ordinary ballots omitted from an otherwise present locality.

These labels describe different failures. An "entire locality omitted" row has
usable historical geometry, but the public election crosswalk contains no
ballot keys for that locality. Sixteen such localities recur in all nine
elections, accounting for 3,409 rows; this pattern is consistent with the
CBS-documented address-anchoring limitation in many Arab and Druze localities.

"Identity absent" does not mean that the source file dropped a polygon. It
means the election result uses a locality code or identity that did not exist
as an independent area in that vintage. This covers 54 K17 rows across 34
identities and one K18 Tzur Yitzhak row. The transition tables provide no
1995/2008 predecessor link for them. The K17 identities later appear as one
2008 area except Kacir and Sansana, which first appear in 2011; K18 Tzur
Yitzhak also first appears in 2011. Using those later boundaries as historical
areas would be an explicitly labeled proxy, not a recovered official
assignment, so the pipeline does not do it silently.

Every specific omission was checked against normalized crosswalk keys, K23 AGS,
stable-ballot components, and applicable ArcGIS evidence. The remaining gaps
are irreducible with the currently recovered sources. They are published, not
estimated, in `historical_assignment_gap_rows.csv`.

## Geometry Provenance

`scripts/build_historical_geographies.py` builds canonical assignment geometry
and separate display geometry.

| Vintage | Canonical features | Use |
|---:|---:|---|
| 1995 | 2,661 | K17 |
| 2008 | 3,030 | K18 |
| 2011 | 3,115 | K19-K25 |
| 2022 | 3,857 | Future direct-crosswalk election and independent analysis |

Canonical geometry is official CBS geometry except for 34 documented targets:

- `stat1995:9400008` is an official 1995-to-2008 transition-key union;
- `stat1995:3797001` is reconstructed as the union of all eight 2008
  Modi'in Illit targets named by the official 1995-to-2008 transition key;
- 32 2011 targets absent from the downloaded CBS FileGDB use exact-ID geometry
  from the audited ArcGIS layers.

Detailed West Bank ArcGIS footprints otherwise remain display derivatives.
Replacement footprints are clipped against historical neighbors. The tribal
footprints are a deliberate exception to polygon reuse: although their exact
2011 IDs are useful assignment keys, the derivative geometries materially
overlap surrounding official areas and cannot be interpreted as exclusive
boundaries. All K17-K25 tribal results therefore render through one combined
marker. For K19-K25 this is only a web presentation aggregate; exact tribe IDs,
ballot assignments, and statistical-area totals remain separate in the public
data package. `data/manual/statistical_area_display_groups.csv` records every
component, and the web build rejects the group unless all voter totals and every
party column equal the source components exactly.

Statistical areas remain separate whenever the source supports separate
complete results. Polling-place continuity or planned-versus-final ballot
changes alone do not justify broad or transitive grouping. A merge is displayed
only for one of the reviewed multi-area units described above, where the
collective result is defensible but an internal split is not. All other empty
polygons remain neutral.

Ganei Modi'in uses its detailed footprint from K21, while its standalone proxy
is hidden in K19/K20. Hebron's exact 2011 footprint is reused as the K17/K18
custom display polygon without changing its reviewed custom assignment ID.

Marker assets can retain source proxies, but the web map displays a marker only
when the selected election has a result for that exact ID. This suppresses the
resultless K17/K18 West Bank proxies, the two Umm al-Fahm points, the Yavne-area
facility point, and other source artifacts. Reviewed confirmation places the
K17 `stat1995:9400008` result on the non-conflicting `stat1995:1062001`
component polygon between Or Yehuda area 4 and Yehud area 3. The duplicate
source feature is hidden, and the election-specific map name is `Yehud`; the
official transition assignment ID and source name remain intact in published
canonical data. Rotem and Maskiyot remain markers only in elections where they
have standalone results and no accepted detailed boundary. Election votes
never come from geometry files.

The 16 evacuated Gaza localities present in the canonical 1995 source package
are hidden in K17 by `statistical_area_display_overrides.csv`. They remain in
the downloadable canonical package so that the source vintage is not silently
rewritten.

The polygon audit reports zero assigned IDs without geometry and zero
unassigned detailed K20/K21 ArcGIS polygons carrying an official electorate
after dissolved locality totals and special rows are classified correctly.
Population fields attached to historical geometry are demographic proxies, not
election-specific eligible-voter counts.

For the 2011 vintage, 2,405 polygons receive an assignment in every supported
election, 358 are intermittent, 75 are never assigned but have a positive
population proxy, and 277 are never assigned without one. Those last two
categories are audit leads, not proof that a separate ballot result should
exist.

## Reproducible Outputs

Working audit outputs include:

- `data/processed/audits/election_source_geography_field_audit.*`
- `data/processed/audits/k23_cec_ags_*`
- `data/processed/audits/stable_ballot_*`
- `data/processed/audits/arcgis_assignment_reconstruction_*`
- `data/processed/audits/kaplan_map_source_*`
- `data/processed/audits/historical_assignment_gap_*`
- `data/processed/audits/historical_municipality_display_fallbacks.csv`
- `data/processed/audits/historical_crosswalk_locality_omission_recurrence.csv`
- `data/processed/audits/historical_polygon_*`
- `data/processed/audits/statistical_area_polling_group_*`
- `data/processed/geographies/historical_geography_build_summary.json`
- `data/processed/geographies/statistical_area_result_aggregates.*`
- `data/processed/geographies/statistical_area_polling_group_displays.*`
- `data/processed/public/statistical_area_polling_group_displays.csv`
- `data/processed/assignments/ballot_geography_assignments.csv`
- `data/processed/assignments/unresolved_statistical_area_assignment_rows.csv`
- `data/manual/cross_election_stat_area_reviews.csv`

Assignment provenance used by the release is committed under
`public-data/v1/metadata/assignment-provenance/`. The Kaplan audit remains a
reproducible working-source audit because it produces no assignment candidate.
The release builder validates row uniqueness, party totals, geography joins,
synthetic-link counts, and reviewed decision fingerprints before publishing.
