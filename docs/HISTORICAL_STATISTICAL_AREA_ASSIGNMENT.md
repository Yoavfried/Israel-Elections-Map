# Historical Statistical-Area Assignment

Last updated: 2026-08-02

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

The nine CBS crosswalks provide 83,230 final row assignments. K17 tenths
encoding and later decimal subdivisions are normalized explicitly:

- in K17, `10` means ballot 1, while values such as `61` and `62` are
  subdivisions of ballot 6;
- in later elections, subdivisions such as `1.1` and `1.2` inherit a direct
  base-ballot target when the official crosswalk maps ballot 1;
- the crosswalk's combined area ID is authoritative even when it crosses the
  result row's locality boundary;
- `Stat08_Unite` and `Stat11_Ref` are demographic reference fields, not
  instructions to merge election areas.

The K17 result CSV omits locality codes, so the normalizer recovers each code
from the official scanned polling register. It requires the recovered locality
name and ballot number to match all 8,277 ordinary result rows before accepting
the code. Historical matching then prefers that election-time identity over a
modern merger alias; this prevents identical ballot numbers in Kfar Azar,
Ramat Efal, Neve Efal, Ramat Pinkas, and Ma'ale Shomron from being matched into
their successor municipalities.

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

The assignment audit produces 134 candidates representing 35,129 actual voters.
The election-specific site-safety audit rejects 38 K24 candidates because the
official pre/post polling-place registers prove their final batches combine
planned ballots from multiple areas: ten in Daliyat al-Karmel and 28 in Umm
al-Fahm. The published row-level result is 96 links representing 27,761 actual
voters:

| Election | Rows | Actual voters |
|---|---:|---:|
| K19 | 2 | 537 |
| K20 | 43 | 16,676 |
| K22 | 1 | 344 |
| K24 | 49 | 9,714 |
| K25 | 1 | 490 |

One same-vintage conflict and 105 conflicts crossing a statistical-area
vintage transition are withheld. Stable-ballot links are high-confidence
inferences, not direct election-specific crosswalk rows. The safety audit covers
every candidate and fails publication when an unsafe mixed batch lacks an
explicit rejection. Forty-seven non-K24 integer candidates have no decimal
batch signal but cannot receive the same pre/post structural test because no
distinct register pair is available for those elections.

### Reviewed Cross-Election Polling-Register Continuity

The CEC polling-register reports can identify an exact recurring polling place
across elections. Fifty-four rows were approved only where that register continuity,
combined with direct CBS targets elsewhere in the same historical vintage,
supports one unique area. The reviewed table validates the exact source row,
electorate, turnout, target vintage, target locality, and target geometry before
the link is applied.

| Election | Rows | Eligible voters | Actual voters |
|---|---:|---:|---:|
| K18 | 1 | 613 | 459 |
| K19 | 6 | 4,325 | 1,838 |
| K20 | 25 | 16,449 | 10,149 |
| K21 | 2 | 1,277 | 461 |
| K22 | 3 | 2,097 | 1,052 |
| K23 | 3 | 2,130 | 1,206 |
| K24 | 3 | 1,832 | 545 |
| K25 | 11 | 7,105 | 3,710 |
| **Total** | **54** | **35,828** | **19,420** |

Forty-three approvals preserve the same ballot number and exact polling place,
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
| K22 locality polygons | 1,173 | 1,173 | 1 of 1 | 1,165 of 1,172 comparable | No |
| K23 locality polygons | 1,172 | 1,172 | 1 of 1 | 1,154 of 1,172 comparable | No |
| K24 locality polygons | 1,214 | 1,214 | 10 of 10 | 1,203 of 1,214 comparable | No |
| K25 locality polygons | 1,215 | 1,215 | 5 of 5 | 1,213 of 1,215 comparable | No |
| K25 neighborhood points | 403 | 15 | 1 of 5 | 14 of 15 comparable | No |

After the reviewed continuity approvals, the source-specific target scope
excludes entirely unmatched municipalities and contains 51 remaining rows
representing 14,190 actual voters:

| Election | Ballot-base 990 rows | 990 actual voters | Other rows | Other actual voters |
|---|---:|---:|---:|---:|
| K22 | 1 | 422 | 0 | 0 |
| K23 | 1 | 234 | 0 | 0 |
| K24 | 31 | 8,664 | 4 | 749 |
| K25 | 9 | 2,730 | 5 | 1,391 |
| **Total** | **42** | **12,050** | **9** | **2,140** |

Each locality payload supplies only the same whole-locality total already known
from the official ballot rows, so it provides no smaller target total for an
exact partition. The K25 neighborhood payload supplies aggregate representative
points but no neighborhood boundaries, statistical-area IDs, or contributing
ballot keys. It reaches only Haifa in the remaining target scope, where the
pending records are two ballot-base 990 rows; a point cannot prove their area.

The audit therefore ran zero partition searches, emitted zero assignment
candidates, and changed no published data. Small source-snapshot differences in
turnout or valid/invalid classification remain in the reconciliation output and
are not copied into the normalized election results. The 54 continuity
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

Nine reviewed component totals are displayed on election-era geometry without
turning the component identity into an area ID. The two K17 shapes are the
complete unions of their component's 1995 areas. The seven K18 shapes partition
the complete 2008 Carmel City, Shaghur, and Baqa-Jatt footprints using the
current component-locality boundaries as cut lines. Historical edge pieces not
covered by a current component boundary go to the component sharing the longest
boundary with that piece; distance and locality code are deterministic
tie-breakers. The build rejects a partition if its union differs from the
historical footprint or if two component shapes overlap by more than one square
metre. This is display geometry only and does not resolve any ballot to an area.

### Single-Area And Custom Rules

A locality fallback is allowed only when the active historical geography has
exactly one canonical area. This assigns 3,801 rows. Reviewed exclusions in
`data/manual/historical_single_stat_fallback_exclusions.csv` prevent this rule
from assigning a combined election municipality to only one obsolete component
of its historical geography. K17 Modi'in-Maccabim-Re'ut is the current reviewed
case. K17/K18 retain 92 reviewed custom-geography rows because their active
historical geometry cannot distinguish the later 2011 areas: 90 tribal rows use
one combined Negev marker, while the two Hebron rows use the audited detailed
Hebron footprint copied from the exact 2011 area geometry.

### Whole-Locality And Component Display Fallback

The web map uses a separate display rule when an election/locality, or a
reviewed component of a historical composite municipality, has zero supported
ballot-to-area assignments. Whole-locality cases use their reviewed fallback
boundary. The nine K17/K18 component cases use the election-era component
geometry described above. Every multi-area case uses the same standard notice:
`No ballot-to-statistical-area assignments are available for this locality in
this election. The whole-locality result is shown as one area.` It never writes
a `stat_area_id`, changes a ballot row, or increases statistical-area coverage.

| Election | Display records | Represented ballot rows | Actual voters |
|---|---:|---:|---:|
| K17 | 52 | 395 | 160,909 |
| K18 | 36 | 505 | 188,962 |
| K19 | 33 | 556 | 211,739 |
| K20 | 33 | 563 | 258,064 |
| K21 | 32 | 596 | 224,699 |
| K22 | 32 | 607 | 264,572 |
| K23 | 32 | 615 | 295,712 |
| K24 | 32 | 833 | 202,743 |
| K25 | 32 | 792 | 255,412 |
| **Total** | **314** | **5,462** | **2,062,812** |

The generated audit records every substituted display boundary and the totals
shown. These records remain separate from the downloadable statistical-area
aggregates. Of the 314 records, 305 cover a whole result locality and nine cover
a reviewed historical-composite component. Available polling-register evidence
does not publish an internal statistical-area split for these records, so the
polling-group network method cannot subdivide them. The component geometry
metadata separately records the source historical footprint, current-boundary
seed, assigned historical edge area, and coverage validation.

### Polling-Group Exact and Representative Placement

Official polling registers sometimes place several statistical areas in one
polling group. The final results then identify the contributing ballot rows but
do not provide a vote split among those areas. Treating the final host area as
the exclusive result would therefore leave populated polygons empty and assign
all votes to an arbitrary host.

The map first builds a bipartite graph between final polling groups and their
candidate polygons:

1. A polling group's value is the exact sum of its final ballot rows.
2. Exact election-specific ballot-to-area matches are removed before sites are
   linked. A ballot base or normalized site label may link planned and final
   sites only when that link is unique on both sides.
3. The remaining candidate polygons come only from official same-election
   evidence or the documented two-reference continuity rule.
4. A combined unit is exact only when all votes from its polygons and only
   votes from those polygons are included. Exact units may contain several
   polygons and several polling groups.
5. For exactly balanced eligible-voter networks, a transport-flow solver
   calculates the minimum and maximum possible flow on every area-to-group
   edge. Edges whose maximum is zero are removed; each remaining closed graph
   component is an exact display unit.
6. A structurally closed one-unit graph may remain exact as a whole even when
   planned and final eligibility counts differ. The count difference is kept as
   evidence and never used to manufacture or move votes.
7. Exact closed units have no uncertainty notice.

Only the remaining networks use representative placement. Every candidate
polygon and every final polling group is used once, but one displayed unit may
now contain multiple polling groups. The solver starts from the most detailed
one-group ownership and merges the most strongly coupled units only as needed.
A robust unit must have at least 50% precision and 50% recall under all three
weighting models: raw planned eligibility, final actual voters distributed by
the planned proportions, and final eligible voters distributed by those same
proportions. These weights select a display partition; they never alter final
votes. Disconnected geometry is retained and disclosed rather than used as a
reason to merge otherwise distinct polling groups.

A planned site with no identifiable final ballot rows is reconciled to a
surviving final-result site only when all four tests agree: same election and
locality, overlapping candidate areas, matching normalized polling-place text,
and a unique eligible-voter surplus match within 2% or 50 voters. Twelve K25
sites in seven components pass this strict consolidation test. Five are in Tel
Aviv, including the planned Tel Nordau site that recovers area 335. Unmatched
planned-only sites remain omitted.

When no mutually-majority partition exists without collapsing a larger
network, the original detailed ownership is retained with uncertainty notices.
This avoids replacing useful local detail with a city-wide aggregate merely to
make a low-confidence partition look exact. The new multi-group units also
remove the old need for broad fallback aggregates when there are more polling
groups than polygons.

No vote is divided, estimated, or moved between statistical areas. Exact units
state a set-level truth, not an invented split inside the combined geometry.
Representative units remain map placement and retain their bilingual
uncertainty notices. Existing directly assigned result rows inside a network
are retained exactly once with the unit owning their polygon.
Planned-to-final eligible-voter differences never change final vote totals.

One reviewed K23 Tel Aviv exception combines statistical areas 347 and 612 as
a disconnected representative display set. K23 ballots 390.1-390.9 are
recorded under area 347 while the area-612 ballot bases disappear; the same
polling place and near-identical group totals recur under area 612 in K21,
K22, and K25. The displayed set therefore includes all 13 K23 result rows now
attached to areas 347/612, totaling 5,245 actual voters, without asserting a
split between the two polygons. The uncertainty notice remains, and the
underlying row-level assignments are not changed.

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
register plus final results. A consolidated final ballot base in K21-K23 is
treated as a whole polling-site group only when the locality and official site
ID remain stable, at least one normalized site label matches, and at least two
direct-evidence elections agree on the exact same multi-area set. This prevents
decimal subdivisions from blindly inheriting one obsolete base-ballot area.
Other K22/K23 continuity units retain the stricter site-and-ballot-base rule and
use the intersection of matching reference sets. K17-K19 have no compatible
polling-group register. The K20 file is post-election only and has no official
site ID, so it cannot satisfy either continuity rule.

| Election | Evidence | All display units | Exact closed units | Representative units | Owned polygon memberships | Representative components | Broad fallbacks |
|---|---|---:|---:|---:|---:|---:|---:|
| K21 | Direct registers + two-reference site continuity | 226 | 134 | 92 | 497 | 47 | 0 |
| K22 | Two-reference site continuity | 433 | 4 | 429 | 877 | 282 | 0 |
| K23 | Two-reference site continuity | 428 | 2 | 426 | 871 | 278 | 0 |
| K24 | Direct official registers | 586 | 204 | 382 | 1,267 | 111 | 0 |
| K25 | Direct official register + final results | 591 | 192 | 399 | 1,210 | 126 | 0 |
| **Total** |  | **2,264** | **536** | **1,728** | **4,722** | **844** | **0** |

Compared with the direct statistical-area result tables, the approved policy
recovers 824 election-specific polygon placements that would otherwise be
blank: 76 in K21, 121 in K22, 118 in K23, 240 in K24, and 269 in K25. It does not
color a remaining blank polygon without qualifying polling-group evidence.

The 536 exact units cover 1,333 polygon-election memberships. None carries an
uncertainty notice.
The flow audit tested ten exactly balanced closed networks; no impossible-edge
removal divided a real network into more than one smaller closed component.
The full reproducible edge bounds are published in
`statistical_area_polling_group_exact_groups.csv`.

The 844 representative components produce 1,728 displayed units. Of those,
1,714 are connected and 14 require disclosed disconnected placement.
Strict site consolidation reconciles 12 planned-only K25 sites; remaining
planned groups without identifiable final results are omitted.

Jerusalem area 1024 illustrates the rule:

| Election | Final polling group | Representative polygons |
|---|---|---|
| K21 | Ballots 228.1-228.4 | Areas 1022 and 1024; shared area 864 may contribute votes |
| K22 | Ballots 228.1-228.4 | Areas 1022, 1023, and 1024; shared area 864 is represented by another group |
| K23 | Ballots 228.1-228.4 | Areas 1022, 1023, and 1024; shared area 864 is represented by another group |
| K24 | Ballots 228.1-228.4 | Areas 864, 1022, 1023, and 1024; some votes may be represented by adjacent units |
| K25 | Ballots 36.1-36.4 | Areas 864, 1022, 1023, and 1024; some votes may be represented by adjacent units |

K19 and K20 area 1024 remain separate because no comparable consolidation is
established for those elections.

The reproducible chain is:

- `scripts/audit_statistical_area_polling_group_evidence.py`
- `scripts/build_statistical_area_polling_group_policy.py`
- `scripts/polling_group_flow.py`
- `scripts/polling_group_ownership.py`
- `scripts/polling_group_partition.py`
- `scripts/build_statistical_area_result_aggregates.py`
- `scripts/build_statistical_area_polling_group_displays.py`

The generated policy, audit, fallback, geometry, result, and metadata files live
under `data/processed/audits`, `data/processed/geographies`, and
`data/processed/public`. The web compiler validates that no ballot or polygon is
owned twice and that every displayed total reconciles to its source rows.

### Contributor-capacity review

The rendered-set capacity audit is a review tool, not an assignment rule. It
compares actual voters with final eligible voters assigned to every possible
contributor polygon. Pre-election area weights may explain a polling network,
but they cannot cap a later final register. When election capacity is not
informative, the audit uses a deliberately lenient threshold of 125% of the
complete total-population proxy.

The first run produced 22 review cases. All were reviewed individually:

- 13 were planned-to-final register changes whose final ballots remained
  entirely inside the documented contributor set; no geometry changed;
- seven were demographic-proxy mismatches with direct or repeated election
  evidence and no supported neighboring contributor; no geometry changed;
- K22 Tel Aviv areas 313-315 were replaced by one exact closed display. The
  same Beit Magid site covers all three areas in K21 and K23, while its K22
  result was consolidated into ballot 139. The union has 14,024 eligible
  voters and 8,723 actual voters;
- K25 Safed areas 3-5 were replaced by one exact closed display. Missing
  planned ballot 25 and the excess in final ballot 9 differ by seven eligible
  voters, and the complete three-area network balances within two. The union
  has 5,827 eligible voters and 3,366 actual voters.

Exact closed unions carry no uncertainty notice. The remaining eight current
signals are demographic-only checks and all have a recorded closed review;
they are retained as inspectable evidence, not open map defects. Decisions live
in `data/manual/display_contributor_capacity_reviews.csv`; reproducible context
is generated by `scripts/review_display_contributor_capacity_flags.py`.

## Published Provenance Classes

| Evidence class | Rows | Synthetic link |
|---|---:|---|
| `official_direct_crosswalk` | 83,230 | No |
| `official_direct_ags` | 74 | No |
| `deterministic_single_area_locality` | 3,801 | No |
| `official_stability_inferred_link` | 96 | Yes |
| `reviewed_exact_aggregate_inferred_link` | 9 | Yes |
| `reviewed_cross_election_inferred_link` | 5 | Yes |
| `reviewed_polling_register_continuity_inferred_link` | 54 | Yes |
| `reviewed_custom_geography` | 92 | No |
| `non_geographic` | 3,585 | No |
| `unresolved` | 5,583 | No |
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
| K17 | 1995 | 7,865 | 409 | 161,195 | 94.65% |
| K18 | 2008 | 8,741 | 518 | 189,252 | 94.14% |
| K19 | 2011 | 9,317 | 558 | 212,413 | 94.13% |
| K20 | 2011 | 9,546 | 566 | 258,880 | 93.56% |
| K21 | 2011 | 9,856 | 596 | 224,699 | 94.52% |
| K22 | 2011 | 9,923 | 608 | 264,994 | 93.66% |
| K23 | 2011 | 10,007 | 616 | 295,946 | 93.09% |
| K24 | 2011 | 11,213 | 906 | 219,524 | 94.53% |
| K25 | 2011 | 10,893 | 806 | 259,533 | 94.01% |

The 5,583 pending rows are fully classified:

- 5,336 belong to entire localities omitted from an official crosswalk;
- 53 use an election locality identity absent from the active historical
  vintage;
- 31 are K17 component-locality rows where the component has multiple 1995
  areas but no component crosswalk;
- 84 are K18 component-locality rows nested in composite 2008 geometry;
- 70 are central ballot 990 rows intentionally retained at locality level;
- 9 are specific ordinary ballots omitted from an otherwise present locality.

Thirty-eight of the 5,336 rows in crosswalk-omitted localities are reviewed K24
mixed-site batches: ten in Daliyat al-Karmel and 28 in Umm al-Fahm. Their
row-level area IDs remain blank, but their complete results are recovered
without estimation in exact areas-1-3-4-5 and areas-13-14-15-21-34 displays.

These labels describe different failures. An "entire locality omitted" row has
usable historical geometry, but the public election crosswalk contains no
ballot keys for that locality. Sixteen such localities recur in all nine
elections, accounting for 3,409 rows; this pattern is consistent with the
CBS-documented address-anchoring limitation in many Arab and Druze localities.

"Identity absent" does not mean that the source file dropped a polygon. It
means the election result uses a locality code or identity that did not exist
as an independent area in that vintage. This covers 52 K17 rows across 34
source identities and one K18 Tzur Yitzhak row. The 34 K17 source identities
resolve to 33 effective fallback polygons because source code 989 is reviewed
as Kamane locality 1331. The transition tables provide no
1995/2008 predecessor link for them. The K17 identities later appear as one
2008 area except Kacir and Sansana, which first appear in 2011; K18 Tzur
Yitzhak also first appears in 2011. Using those later boundaries as historical
areas would be an explicitly labeled proxy, not a recovered official
assignment, so the pipeline does not do it silently.

Every specific omission was checked against normalized crosswalk keys, K23 AGS,
stable-ballot components, official polling registers, and applicable ArcGIS
evidence. Four Nazareth ballot-80 rows in K20-K23 are now approved synthetic
links to area 32: the number and exact polling place are unchanged, and both
official K18 and K19 crosswalks assign that ballot to area 32.

The nine rows still lacking a single-area ID have two exact set-level treatments.
Eight K24/K25 Ar'ara ballot-14 subdivisions replace complete planned polling-
site totals spanning areas 1 and 3. The final totals differ from the three
planned ballots by only one eligible voter in each election, and cross-election
area totals confine the missing planned ballot to that same area set. The map
therefore shows all and only the combined areas-1-and-3 results on one dissolved
display, while the downloadable subdivision rows remain blank rather than
inventing an internal split. K25 Daliyat al-Karmel ballot 23 is the new third
ballot at the unchanged polling site serving areas 3 and 5. Including it keeps
the combined electorate continuous from K24 to K25; excluding it creates an
unsupported drop. The map therefore publishes the complete areas-3-and-5 result
once while retaining a blank row-level area ID. All thirteen review outcomes are recorded in
`data/manual/omitted_ordinary_ballot_reviews.csv`.

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

K17 locality 978, Ka'abiyye-Tabbash-Hajajre, is one exact historical-locality
union. Its complete election result equals the result carried by
`stat1995:978001`, while the separate historical Hajajre polygon
`stat1995:977001` has no independent K17 result. Statistical mode therefore
shows the same complete locality result across the union of both polygons. No
uncertainty notice is needed because the displayed area contains all and only
the locality result.

Ganei Modi'in uses its detailed footprint and its own ballot result from K21.
Its standalone proxy is hidden in K19/K20, when it was still part of Modi'in
Illit. From K21, the stale and resultless `stat2011:37970001` Modi'in Illit area
1 polygon is hidden instead; it is almost entirely the same footprint. This
election-specific swap removes the duplicate geometry without reallocating any
votes. Hebron's exact 2011 footprint is reused as the K17/K18 custom display
polygon without changing its reviewed custom assignment ID.

All 33 effective K17 fallback polygons now have reviewed visual treatment. Abu
Ghosh and Kiryat Yearim use the same later/current locality display boundaries
used by later elections, and the obsolete 1995 Kiryat Yearim institution
feature is suppressed. Twenty-one other fallback footprints remain unchanged
while their exact current display shape is subtracted from every intersecting
1995 display host:

| K17 fallback | Current code | 1995 display host or hosts cut around it |
|---|---:|---|
| Ahuzat Barak | 1330 | `stat1995:407001` Dovrat |
| Nof Ayalon | 1333 | `stat1995:856001` Sha'alvim |
| Matan | 1315 | `stat1995:718001` Yarhiv |
| Kanaf | 4028 | `stat1995:4008001` Ma'ale Gamla; `stat1995:4702001` Ramot |
| Ras al-Ein | 1334 | `stat1995:1163001` Moran; `stat1995:1201001` Kamon |
| Hussniyya | 1332 | `stat1995:1180001` Tzvia; `stat1995:1202001` Mikhmannim |
| Kamane | 1331 | `stat1995:1201001` Kamon; `stat1995:1202001` Mikhmannim |
| Khawaled | 1321 | `stat1995:254001` Kfar HaMakkabi |
| Basma | 1326 | `stat1995:639001` Barta'a; `stat1995:643001` Mu'awiya; `stat1995:657001` Ein as-Sahla; `stat1995:1247001` Iron; `stat1995:1128001` Mei Ami; `stat1995:637001` Ar'ara |
| Dmeide | 1317 | `stat1995:1178001` Moreshet; `stat1995:8900001` Tamra |
| Caesarea | 1167 | `stat1995:327001` Sdot Yam; `stat1995:1020002`, `stat1995:1020003`, `stat1995:1020005` Or Akiva areas 2, 3, and 5 |
| Midreshet Ben Gurion | 1140 | `stat1995:885001` Sde Boker |
| Neve Avot | 926 | `stat1995:7800005`, `stat1995:7800006` Pardes Hanna-Karkur areas 5 and 6 |
| Umm Batin | 1358 | `stat1995:666001` Omer |
| Qasr al-Sir | 1347 | `stat1995:2200001`, `stat1995:2200012` Dimona areas 1 and 12 |
| Ivim | 338 | `stat1995:1031004` Sderot area 4 |
| Bat Hefer | 1319 | `stat1995:758001` Yad Hanna |
| Bat Hadar | 1323 | `stat1995:7100033` Ashkelon area 33 |
| Kfar Galim | 427 | `stat1995:434001` HaHotrim |
| Kfar HaOranim | 3796 | `stat1995:1310001` Lapid |
| Mikve Israel | 22 | `stat1995:6600135` Holon area 135 |

The other 11 fallbacks have no material overlap with any visible 1995 polygon
and are explicitly approved unchanged: Suwaed (Hamriyya), Ras Ali, Nitzana
(Educational Community), Shani, Avshalom, Neve Ziv, Shimshit, Drijat, Eshel
HaNasi, Sansana, and Revava.

Basma is published as one K17 result. Its historical Barta'a, Mu'awiya, and Ein
as-Sahla component polygons carry zero K17 rows and zero voters, so they are
hidden from the K17 display and search index beneath the reviewed Basma
fallback. All three source features remain in canonical 1995 geography.

The reviewed policy records the measured share of each fallback footprint that
intersected each original host and the build rejects any drift or residual
overlap above one square metre. Explicit no-overlap approvals fail the same
build if a future geometry change creates material overlap. Matan was 99.770%
covered by Yarhiv; its small remainder was already outside every visible 1995
polygon. These operations are display-only boundary substitutions, cutouts,
and approvals recorded in `historical_locality_boundary_overrides.csv`. They do
not assign a statistical area to any fallback row, alter vote totals, or change
canonical 1995 geometry in the downloadable package.

Additional approved current-boundary cutouts remove historical display overlap
without changing any result assignment. For K17 they cover Maghar, Kfar Qasem,
Sakhnin, Arraba, and Tamra. For K18 they cover Tzur Yitzhak, Maghar, Kfar
Qasem, Sakhnin, Arraba, Tamra, Fureidis, and Iksal. The K18 Kfar Bara case uses
reverse priority: its official 2008 polygon remains intact and is subtracted
from the current-boundary Kfar Qasem fallback. Election-vintage fallback
geometry is generated in
`historical_locality_fallback_display_geometries.geojson`; canonical source
geometry and ballot assignments remain unchanged.

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
- `data/processed/audits/statistical_display_component_ownership.csv`
- `data/processed/audits/statistical_display_component_ownership_summary.json`
- `data/processed/audits/display_contributor_capacity_*`
- `data/processed/audits/reviewed_locality_statistical_display_audit.csv`
- `data/processed/audits/reviewed_locality_statistical_display_audit_summary.json`
- `data/processed/audits/reviewed_locality_statistical_displays.csv`
- `data/processed/audits/joined_locality_continuity_evidence.csv`
- `data/processed/audits/joined_locality_continuity_evidence_summary.json`
- `data/processed/geographies/historical_geography_build_summary.json`
- `data/processed/geographies/statistical_area_result_aggregates.*`
- `data/processed/geographies/statistical_area_polling_group_displays.*`
- `data/processed/public/statistical_area_polling_group_displays.csv`
- `data/processed/assignments/ballot_geography_assignments.csv`
- `data/processed/assignments/unresolved_statistical_area_assignment_rows.csv`
- `data/manual/cross_election_stat_area_reviews.csv`
- `data/manual/display_contributor_capacity_reviews.csv`

Assignment provenance used by the release is committed under
`public-data/v1/metadata/assignment-provenance/`. The Kaplan audit remains a
reproducible working-source audit because it produces no assignment candidate.
The release builder validates row uniqueness, party totals, geography joins,
synthetic-link counts, and reviewed decision fingerprints before publishing.
