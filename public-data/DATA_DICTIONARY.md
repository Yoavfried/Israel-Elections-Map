# Public Data Dictionary

This dictionary describes ballot-table schema version 2 under
[`public-data/v1`](v1/).

## Ballot Tables

Files: `v1/ballots/k17.csv` through `v1/ballots/k25.csv`.

The grain is one official election-result source row, sometimes a ballot
subdivision. `source_row_uid` is the unique repository key. A displayed ballot
number is not globally unique.

### Source And Vote Columns

| Column | Meaning |
|---|---|
| `source_row_uid` | Stable row key, unique across all elections. |
| `election`, `election_number` | Election key and Knesset number. |
| `source_row_id`, `source_order` | Source-system identity and source order. |
| `source_locality_code`, `source_locality_name` | Locality printed by the election source. |
| `source_kalpi` | Ballot/subdivision identifier printed by the source. |
| `eligible_voters` | Registered voters where the source provides a supported denominator. |
| `actual_voters` | Ballots cast. |
| `valid_votes`, `invalid_votes` | Valid and invalid ballots. |
| `is_envelope` | Whether the row is an official envelope result. |

Columns between `is_envelope` and `geography_assignment_status` are the
election-specific party vote columns. Join their source-column names to
[`metadata/parties.csv`](v1/metadata/parties.csv?raw=1) on
`(election, source_column)`. They sum exactly to `valid_votes` on every row.

### Statistical-Mode Assignment

| Column | Meaning |
|---|---|
| `geography_assignment_status` | Final statistical-mode handling status. |
| `geography_type` | Statistical area, custom geography, envelope/special type, or unresolved handling. |
| `geography_id` | Final statistical-mode target when one exists. |
| `stat_area_id` | Stable historical area ID; blank unless an actual area was assigned. |
| `stat_area_vintage` | 1995, 2008, or 2011 for K17-K25. |
| `stat_area_yishuv_stat` | Historical combined locality-area code. |
| `stat_area_number` | Area number within the historical locality. |
| `is_mapped` | Whether statistical mode has a supported map target. |
| `final_assignment_method` | Specific machine-readable assignment rule. |
| `final_assignment_source` | Source files and reviewed tables supporting the link. |
| `assignment_evidence_class` | General evidence category described below. |
| `assignment_confidence` | `authoritative`, `high`, `moderate`, `not_applicable`, or `unresolved`. |
| `assignment_is_synthetic_link` | True only when the ballot-to-area link is inferred. It never means vote data were synthesized. |
| `unresolved_reason` | Why no defensible statistical-area polygon was assigned. |

For an ordinary area, join `stat_area_id` to `properties.geography_id` in the
package named by `stat_area_vintage`. `geography_id` can instead identify a
reviewed custom geography, so use that generic field to reproduce the exact map
handling.

### Evidence Classes

| Evidence class | Rows | Meaning |
|---|---:|---|
| `official_direct_crosswalk` | 83,230 | Direct election-specific CBS crosswalk, including supported base subdivisions. |
| `official_direct_ags` | 74 | Direct AGS from the official K23 CEC report. |
| `deterministic_single_area_locality` | 3,801 | The active historical locality has exactly one canonical area; reviewed combined-municipality exclusions prevent assignment to only one obsolete component. |
| `official_stability_inferred_link` | 96 | Official CBS stable-ballot evidence has a unanimous same-vintage target after election-specific mixed-site rejections. |
| `reviewed_exact_aggregate_inferred_link` | 9 | Reviewed unique exact K21 ArcGIS residual partition. |
| `reviewed_cross_election_inferred_link` | 5 | Reviewed correction supported by independent same-vintage evidence. |
| `reviewed_polling_register_continuity_inferred_link` | 54 | Approved high-confidence link from exact cross-election polling-register continuity and direct same-vintage targets. |
| `reviewed_custom_geography` | 92 | Supported custom geography where historical geometry cannot represent the target; the tribal bucket is a marker and Hebron uses a detailed polygon. K19-K25 ballots retain their exact tribe/statistical-area IDs in this package even though the web map combines those results into the same marker. |
| `non_geographic` | 3,585 | Envelope or other reviewed non-geographic row. |
| `unresolved` | 5,583 | No defensible row-level historical area under the current evidence. Reviewed exact set-level displays may still recover the complete result without splitting it. |

The four inferred evidence paths total 164 rows and 52,804 actual voters. Filter
`assignment_is_synthetic_link=false` when an analysis requires only direct or
deterministic links.

### Method-Specific Notes

- `official_cbs_ballot_crosswalk*` methods are direct crosswalk assignments.
- `official_cec_k23_ags` is direct official AGS.
- `reviewed_composite_component_evidence` identifies a K17/K18 component
  locality from a polling-register source. It supports an area link only when
  that component has one area in the active historical vintage.
- `cbs_stable_ballot_*` methods are high-confidence inferred links. Conflicting
  stability components are withheld.
- `arcgis_residual_partition_tier_a` covers three exact Ar'ara-BaNegev rows.
- `arcgis_residual_partition_tier_c` covers six exact Jerusalem rows with
  unrelated source-snapshot deltas documented in the review record.
- `reviewed_historical_stat_area_override` covers five corrected K19 targets.
- `reviewed_cross_election_stat_area_assignment` covers 54 approved
  high-confidence polling-register continuity links. The reviewed table records
  source-row identity, target, evidence subtype, and source documents.
- `single_historical_stat_locality` is deterministic only when the active
  historical locality has one area.

No published method accepts a vote-count tolerance. ArcGIS election values are
audit evidence only and never replace the official ballot values.

### Locality Assignment

| Column | Meaning |
|---|---|
| `locality_assignment_status` | Independent locality-mode handling status. |
| `locality_geography_type` | Locality, composite, custom geography, envelope, or special handling. |
| `locality_geography_id` | Feature ID used by locality mode. |
| `locality_id`, `locality_code`, `locality_name` | Canonical 2022 locality identity where applicable. |
| `locality_result_code`, `locality_result_name` | Published result identity retained for aggregation and display. |
| `is_locality_mapped` | Whether locality mode has a supported target. |
| `custom_geography_id` | Reviewed custom grouping when applicable. |
| `is_geographic` | Whether the source row is an ordinary geographic result. |

Join `locality_geography_id` to
[`metadata/geographies.csv`](v1/metadata/geographies.csv?raw=1). Its
`geometry_archive` identifies the required locality, composite, or custom ZIP.

## Aggregate Tables

Each election has separate tables under `v1/aggregates/`:

| Directory | Grain |
|---|---|
| `statistical-areas` | One row per mapped historical statistical area. |
| `localities` | One row per published or reviewed locality result. |
| `custom-geographies` | Reviewed custom results, including applicable map mode. |
| `envelopes` | One national non-geographic envelope aggregate. |
| `unresolved` | Source rows without a statistical-area polygon, including non-geographic handling. |

Geographic aggregate tables expose `geography_id` and `geography_type` as their
first join columns. Vote totals and party columns are additive. Never split a
published aggregate among component polygons without independent evidence.

The web map's whole-locality or reviewed-component fallback is not a
statistical aggregate or ballot assignment. Rows remain in
`aggregates/unresolved`; the separate
`metadata/assignment-provenance/historical_municipality_display_fallbacks.csv`
audit identifies the 314 display-only substitutions.

The K17 envelope/non-geographic row stores 4,087 eligible voters as a technical
national-denominator bucket: 518 from three source camp rows plus the separate
3,569-person Gush Katif register. It is not a geographic split and must not be
used to calculate envelope turnout.

## Geography Packages

Every published GeoJSON feature has:

| Property | Meaning |
|---|---|
| `geography_id` | Stable join key used by ballot and aggregate CSVs. |
| `geography_type` | Statistical area, locality, composite locality, or custom geography. |

The CSV beside each ZIP contains the same non-geometry properties.
`metadata/geographies.csv` adds `geography_package` and `geometry_archive` so a
consumer can locate the correct archive from a join ID alone.

K25 uses 2011 because its official crosswalk targets 2011. The 2022 package is
provided for a future direct-crosswalk election and independent analysis, not
as a fabricated K25 conversion.

## Assignment Audit Package

[`v1/metadata/assignment-provenance`](v1/metadata/assignment-provenance/)
contains 30 inspectable artifacts:

- official normalized crosswalk and final assignment summary;
- source-field inventory;
- K23 AGS candidates, conflicts, validation, coverage, and summary;
- stable-ballot candidates, conflicts, transition audit, site-safety audit,
  reviewed mixed-batch rejections, and summaries;
- ArcGIS candidates, locality classifications, reviews, and summary;
- historical overrides;
- approved cross-election polling-register continuity reviews;
- unresolved row/locality classifications;
- display-only whole-locality and reviewed-component fallback records;
- per-election polygon coverage and cross-election persistence.

Population values in the polygon audit are demographic proxies. They are not
election-specific eligible-voter counts.

## Minimal Examples

Pandas:

```python
import geopandas as gpd
import pandas as pd
import zipfile

results = pd.read_csv("public-data/v1/aggregates/statistical-areas/k20.csv")
with zipfile.ZipFile("public-data/v1/geographies/statistical_areas_2011.zip") as z:
    z.extract("statistical_areas_2011.geojson", "tmp")

areas = gpd.read_file("tmp/statistical_areas_2011.geojson")
joined = areas.merge(results, on="geography_id", how="left", validate="one_to_one")
```

QGIS:

1. Extract the election's matching geography ZIP and open its GeoJSON.
2. Add the aggregate CSV as a delimited-text layer without geometry.
3. Join CSV `geography_id` to GeoJSON `geography_id`.

## Nulls And Validation

- Blank statistical IDs mean the evidence does not support a polygon; they are
  not zero-vote areas.
- Envelope and reviewed non-geographic rows remain counted but have no polygon.
- Statistical and locality coverage differ because they answer different
  geographic questions.
- `validation.json` verifies row counts, actual-voter reconciliation to valid
  plus invalid votes, party reconciliation, all nonblank geography joins,
  per-election evidence-class counts, and inferred-link totals.
- `manifest.csv` and `manifest.json` provide file sizes, row counts, and SHA-256
  checksums.

CSVs use UTF-8 with a byte-order mark for reliable Hebrew display in spreadsheet
software. Generated release files must not be edited manually.
