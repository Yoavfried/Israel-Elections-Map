# Public Election Data

The repository includes a versioned, ready-to-download data release under
[`public-data/v2`](v2/). You do not need to run the pipeline to use these files.

The release contains all 109,455 normalized K17-K26 ballot-result rows, separate
polygon aggregates, full-resolution geography packages, election and party
metadata, row-level assignment provenance, checksums, and a machine-readable
validation report. The ballot-table contract is schema version 2.

The current data release is **v2.2**. It adds 4,081 validated, explicitly
synthetic K26 ballot-to-area links and archives both official polling registers.
Votes are unchanged, as are all K17-K25 ballot values and assignments. The v2.1
[25-list Wikipedia review](v2/metadata/party-wikipedia-reviews/k26.csv?raw=1)
is retained.

K26 is the complete-count snapshot from 30 October 2026, before certification.
Locality totals are complete. Statistical-area links include independently
known single-area localities, reviewed custom buckets, and high-confidence
register-based inference. The pre-balance CBS workbook is not used as a final
assignment without additional evidence. Mixed groups can be shown together on
the website without inventing one area per ballot. See the methodology for the
exact scope. The previous [v1 snapshot](v1/) is preserved.

Read the [public data methodology](METHODOLOGY.md) for the exact assignment
precedence, synthetic-link counts, unresolved-row policy, validation rules, and
step-by-step audit procedure.

Public releases use a two-level `major.minor` policy: minor releases correct
values or documentation without changing the contract, while a new election,
column change, or other major contract change starts the next major release.
See the [data and website versioning policy](../docs/VERSIONING.md).

## Download One Election

Each ballot CSV contains every source result row for that election, one column
per registered ballot letter, and both statistical-area and locality join IDs.

| Election | Rows | Statistical vintage | Ballot rows | Statistical aggregates | Locality aggregates | Statistical polygons |
|---|---:|---:|---|---|---|---|
| K26 (2026) | 12,926 | 2022 | [CSV](v2/ballots/k26.csv?raw=1) | [CSV](v2/aggregates/statistical-areas/k26.csv?raw=1) | [CSV](v2/aggregates/localities/k26.csv?raw=1) | [ZIP](v2/geographies/statistical_areas_2022.zip?raw=1) |
| K17 (2006) | 8,426 | 1995 | [CSV](v2/ballots/k17.csv?raw=1) | [CSV](v2/aggregates/statistical-areas/k17.csv?raw=1) | [CSV](v2/aggregates/localities/k17.csv?raw=1) | [ZIP](v2/geographies/statistical_areas_1995.zip?raw=1) |
| K18 (2009) | 9,264 | 2008 | [CSV](v2/ballots/k18.csv?raw=1) | [CSV](v2/aggregates/statistical-areas/k18.csv?raw=1) | [CSV](v2/aggregates/localities/k18.csv?raw=1) | [ZIP](v2/geographies/statistical_areas_2008.zip?raw=1) |
| K19 (2013) | 10,109 | 2011 | [CSV](v2/ballots/k19.csv?raw=1) | [CSV](v2/aggregates/statistical-areas/k19.csv?raw=1) | [CSV](v2/aggregates/localities/k19.csv?raw=1) | [ZIP](v2/geographies/statistical_areas_2011.zip?raw=1) |
| K20 (2015) | 10,414 | 2011 | [CSV](v2/ballots/k20.csv?raw=1) | [CSV](v2/aggregates/statistical-areas/k20.csv?raw=1) | [CSV](v2/aggregates/localities/k20.csv?raw=1) | [ZIP](v2/geographies/statistical_areas_2011.zip?raw=1) |
| K21 (April 2019) | 10,765 | 2011 | [CSV](v2/ballots/k21.csv?raw=1) | [CSV](v2/aggregates/statistical-areas/k21.csv?raw=1) | [CSV](v2/aggregates/localities/k21.csv?raw=1) | [ZIP](v2/geographies/statistical_areas_2011.zip?raw=1) |
| K22 (September 2019) | 10,901 | 2011 | [CSV](v2/ballots/k22.csv?raw=1) | [CSV](v2/aggregates/statistical-areas/k22.csv?raw=1) | [CSV](v2/aggregates/localities/k22.csv?raw=1) | [ZIP](v2/geographies/statistical_areas_2011.zip?raw=1) |
| K23 (2020) | 11,179 | 2011 | [CSV](v2/ballots/k23.csv?raw=1) | [CSV](v2/aggregates/statistical-areas/k23.csv?raw=1) | [CSV](v2/aggregates/localities/k23.csv?raw=1) | [ZIP](v2/geographies/statistical_areas_2011.zip?raw=1) |
| K24 (2021) | 12,926 | 2011 | [CSV](v2/ballots/k24.csv?raw=1) | [CSV](v2/aggregates/statistical-areas/k24.csv?raw=1) | [CSV](v2/aggregates/localities/k24.csv?raw=1) | [ZIP](v2/geographies/statistical_areas_2011.zip?raw=1) |
| K25 (2022) | 12,545 | 2011 | [CSV](v2/ballots/k25.csv?raw=1) | [CSV](v2/aggregates/statistical-areas/k25.csv?raw=1) | [CSV](v2/aggregates/localities/k25.csv?raw=1) | [ZIP](v2/geographies/statistical_areas_2011.zip?raw=1) |

Other election-specific downloads are organized under
[`aggregates/custom-geographies`](v2/aggregates/custom-geographies/),
[`aggregates/envelopes`](v2/aggregates/envelopes/), and
[`aggregates/unresolved`](v2/aggregates/unresolved/).

## Geography Packages

Each ZIP contains full-resolution GeoJSON and a CSV with the same feature
metadata. Every feature exposes `properties.geography_id`.

| Package | Features | Archive | Metadata only |
|---|---:|---|---|
| 1995 statistical areas | 2,661 | [ZIP](v2/geographies/statistical_areas_1995.zip?raw=1) | [CSV](v2/geographies/statistical_areas_1995.csv?raw=1) |
| 2008 statistical areas | 3,030 | [ZIP](v2/geographies/statistical_areas_2008.zip?raw=1) | [CSV](v2/geographies/statistical_areas_2008.csv?raw=1) |
| 2011 statistical areas | 3,115 | [ZIP](v2/geographies/statistical_areas_2011.zip?raw=1) | [CSV](v2/geographies/statistical_areas_2011.csv?raw=1) |
| 2022 statistical areas | 3,863 | [ZIP](v2/geographies/statistical_areas_2022.zip?raw=1) | [CSV](v2/geographies/statistical_areas_2022.csv?raw=1) |
| 2022 locality footprints | 1,393 | [ZIP](v2/geographies/localities_2022.zip?raw=1) | [CSV](v2/geographies/localities_2022.csv?raw=1) |
| Historical/reviewed locality composites | 104 | [ZIP](v2/geographies/composite_localities.zip?raw=1) | [CSV](v2/geographies/composite_localities.csv?raw=1) |
| Reviewed custom geographies | 2 | [ZIP](v2/geographies/custom_geographies.zip?raw=1) | [CSV](v2/geographies/custom_geographies.csv?raw=1) |

Use [`metadata/geographies.csv`](v2/metadata/geographies.csv?raw=1) as the
combined lookup from any `geography_id` to its geometry archive.

## Join Rules

- Statistical ballot assignment: `ballots/*.csv.stat_area_id` equals
  `GeoJSON.properties.geography_id` in the election's statistical package.
- Locality ballot assignment: `ballots/*.csv.locality_geography_id` equals
  `metadata/geographies.csv.geography_id`; `geometry_archive` identifies the
  package containing the feature.
- Polygon aggregates: every geographic aggregate CSV has a standard
  `geography_id` column that equals `GeoJSON.properties.geography_id`.
- Blank statistical IDs are intentional unresolved source gaps. Envelope rows
  are national non-geographic results and do not join to a polygon.

See the [data dictionary](DATA_DICTIONARY.md) for column-level definitions and
short pandas/QGIS examples.

## Assignment Provenance

Every ballot row exposes:

- `assignment_evidence_class`;
- `assignment_confidence`;
- `assignment_is_synthetic_link`;
- the specific `final_assignment_method` and `final_assignment_source`.

The release contains 164 inferred ballot-to-area links representing 52,804
actual voters: 96 from official CBS stable-ballot evidence, nine from reviewed
exact ArcGIS residuals, five reviewed cross-election corrections, and 54
approved high-confidence polling-register continuity links. The ballot
identity, electorate, turnout, valid/invalid totals, and party votes remain
unchanged official source values. Only the area link is synthetic.

The separate 74 K23 AGS assignments are direct official evidence and are not
marked synthetic. Users who require no inferred links can filter
`assignment_is_synthetic_link=false` and reaggregate the ballot rows.

The complete evidence tables, accepted and rejected decisions, conflicts,
source-schema inventory, unresolved-row classification, and polygon coverage
audit are under
[`metadata/assignment-provenance`](v2/metadata/assignment-provenance/).

## Metadata And Integrity

- [`metadata/elections.csv`](v2/metadata/elections.csv?raw=1) lists election
  years, active statistical vintages, and principal paths.
- [`metadata/parties.csv`](v2/metadata/parties.csv?raw=1) maps each
  election/ballot-letter combination to its reviewed list name and article
  metadata.
- [`metadata/coverage.csv`](v2/metadata/coverage.csv?raw=1) reports mapped and
  pending coverage by election.
- [`metadata/assignment-provenance`](v2/metadata/assignment-provenance/)
  contains 38 source, decision, conflict, gap, and polygon-audit artifacts.
- [`manifest.csv`](v2/manifest.csv?raw=1) and
  [`manifest.json`](v2/manifest.json?raw=1) contain file sizes, row counts, and
  SHA-256 checksums.
- [`validation.json`](v2/validation.json?raw=1) records the release checks.

CSVs are UTF-8 with a byte-order mark for reliable Hebrew display in spreadsheet
software. The release is generated by `scripts/build_public_data_release.py` and
must not be edited by hand.

## Data Versus Map Presentation

This release publishes election facts, reviewed party/list metadata, assignment
provenance, and canonical analytical geometry. It deliberately excludes map
colors, concise UI label overrides, web-only polygon unions and fallback
boundaries, masks, marker placement, layout, map modes, and interaction
configuration. Those are presentation choices owned by the map application.

The map groups the K19-K26 tribal statistical-area results into one combined
tribal marker because the available derivative footprints overlap surrounding
areas and cannot be treated as exclusive geography. The release tables do not
collapse those records: exact tribe statistical-area identifiers, results, and
assignment provenance remain available for analysis.

When an election/locality or reviewed historical-composite component has no
supported ballot-to-area assignment, the map can show its aggregate on a
display-only reviewed boundary with an info notice. The K17/K18 component
shapes retain the election-era composite's outer footprint. This does not
assign any ballot or change coverage. The historical map substitutions and their
represented totals are disclosed in
[`historical_municipality_display_fallbacks.csv`](v2/metadata/assignment-provenance/historical_municipality_display_fallbacks.csv?raw=1).

K26 retains 52 whole-locality display fallbacks after the register-based update.
Its source policy is recorded in
[`k26_source_audit.json`](v2/metadata/assignment-provenance/k26_source_audit.json?raw=1)
and its underlying assignment counts in [`coverage.csv`](v2/metadata/coverage.csv?raw=1).
Its Sha'ar Shomron display reuses the reviewed Etz Efrayim/Sha'are Tikva union;
the source 2022 feature remains unchanged in the downloadable geometry package.

The project-authored portions of this release, including its original
selection, arrangement, normalization, annotations, and assignment metadata,
are available under the [MIT Data License](LICENSE). Official and third-party
source data retain their source terms; see
[Third-Party Data Notices](../THIRD_PARTY_NOTICES.md). The website and other
project materials are not included in this data license.

For commercial deployment, also review the explicitly published third-party
terms collected in the [commercial-use audit](../docs/COMMERCIAL_USE_AUDIT.md).
