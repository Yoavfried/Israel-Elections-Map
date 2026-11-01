# Public Data Methodology

## K26 / 2026 Publication Policy

Release v2.0 adds the official complete-count snapshot dated 2026-10-30,
pending certification. Every original party vote, eligible-voter count, actual
voter, valid vote, and invalid vote is preserved. The raw ballot and locality
exports are archived under `v2/sources/k26/`; their totals reconcile exactly
for every locality and party. The two zero-vote list columns are retained in
the data, although the website omits them.

K26 uses 2022 statistical areas. No K25/2011 assignment is carried into the
new vintage. Independently identified single-area localities and the existing
reviewed non-geographic/custom rules are applied. Multi-area localities do not
receive an unverified internal split: their totals remain municipality-only
and the website displays the whole municipality with its standard disclosure.
This does not make the underlying statistical assignment complete.

The CBS K26 workbook was prepared before final balancing. The exported
`k26_crosswalk_candidates.csv` distinguishes exact, base-only, and missing keys;
**none of those candidates is accepted as an assignment**. A single-area
locality may independently be mapped to the same area, without relying on its
candidate key. The archived stable-ballot workbook likewise does not authorize
a transfer across statistical-area vintages. Final-register composition
validation is required before activating more detailed K26 assignments.

Six missing exact-ID 2022 areas/localities were supplemented from the official
CBS 2025 demographic publication (`STAT22` / `YISHUV_STAT22`). Existing
boundaries were not replaced. These new locality footprints are hidden in
earlier elections. K17-K25 ballot values and assignments remain unchanged;
the previous v1 data release remains available.

This document explains how the downloadable K17-K26 release was built, which
fields are official, which geographic links are inferred, and how to audit the
result. It describes the data release, not the website's visual presentation.

## What The Release Preserves

The release contains 109,455 normalized ballot-result rows. Vote counts,
eligible voters, actual voters, valid and invalid votes, locality identity,
ballot identity, and election identity come from the cited official result
sources. The project does not estimate party votes or divide one ballot's votes
between statistical areas.

The files under `v2/ballots/` are normalized row-level exports, not copies of
the original source workbooks or PDFs. Normalization standardizes encoding,
column names, identifiers, and numeric types; it also adds locality and
statistical-area join fields plus row-level provenance.

## Geographic Versions

Each election uses the statistical-area version targeted by its official
ballot crosswalk:

| Election | Statistical-area version |
|---|---:|
| K17 | 1995 |
| K18 | 2008 |
| K19-K25 | 2011 |
| K26 | 2022 |

K25 is not converted to 2022 areas. Its official crosswalk still targets 2011
areas, so a 2022 conversion would add unsupported precision. The 2022 package
is used for K26 and is also available for independent analysis.

## Assignment Procedure

Each ordinary ballot row receives at most one `stat_area_id`. The first
applicable rule in this order wins:

1. classify official envelope or reviewed non-geographic rows as non-polygon
   results;
2. apply a reviewed historical correction when independent evidence disproves
   a nominal direct target;
3. use the election-specific official CBS ballot-to-area crosswalk;
4. use direct K23 CEC AGS evidence;
5. use a reviewed exact ArcGIS residual only when the official aggregate can be
   reconciled uniquely;
6. propagate an official CBS stable-ballot link only when all same-version
   evidence agrees and the polling-site safety audit does not identify a mixed
   final batch;
7. use reviewed polling-register continuity only when election, locality,
   ballot/site identity, and the target area's evidence meet the documented
   high-confidence rule;
8. retain reviewed K17/K18 component-locality evidence for historical
   composites;
9. assign a historical locality fallback only when that locality has exactly
   one published statistical area;
10. use a reviewed custom geography only where no supported historical area
    exists;
11. otherwise leave `stat_area_id` blank and publish the unresolved reason.

Polling-place address geocoding is not part of this assignment procedure. A
polling station's physical address does not prove that all voters assigned to
that station live in the address's statistical area.

## Inferred Links

The release marks 164 ballot-to-area links as inferred. The vote rows remain
official; only their geographic link is synthetic.

| Evidence class | Rows | Actual voters |
|---|---:|---:|
| Official CBS stable-ballot inference | 96 | 27,761 |
| Reviewed exact ArcGIS residual inference | 9 | 3,599 |
| Reviewed cross-election correction | 5 | 2,024 |
| Reviewed polling-register continuity | 54 | 19,420 |
| **Total** | **164** | **52,804** |

The separate 74 K23 AGS links, representing 29,685 actual voters, are direct
official evidence and are not marked synthetic.

Every ballot CSV exposes:

- `assignment_evidence_class`;
- `assignment_confidence`;
- `assignment_is_synthetic_link`;
- `final_assignment_method`;
- `final_assignment_source`.

To analyze only direct assignments, filter
`assignment_is_synthetic_link=false` before aggregating.

## Explicit Unresolved Rows

The release leaves 5,583 rows without a statistical-area target rather than
guessing:

| Source limitation | Rows |
|---|---:|
| Entire locality omitted from the official crosswalk | 5,336 |
| Election locality identity absent from the active historical version | 53 |
| K17 component locality has multiple areas but no component crosswalk | 31 |
| K18 component locality is nested in published composite geometry | 84 |
| Central ballot 990, intentionally locality-only | 70 |
| Specific ordinary ballot omitted from the official crosswalk | 9 |
| **Total** | **5,583** |

These rows are available under `v2/aggregates/unresolved/` and retain their
locality result. They are not counted as statistical-area assignments.

Row-level unresolved does not always mean map-level missing. Thirty-eight K24
mixed-batch rows and nine specific omitted rows have reviewed exact set-level
displays. Their votes are shown once across the complete contributing polygon
set, while their ballot rows retain blank area IDs because no internal split is
supported.

## Aggregation And Joins

- `ballots/*.csv.stat_area_id` joins directly to
  `GeoJSON.properties.geography_id` in the election's statistical package.
- `ballots/*.csv.locality_geography_id` joins to the locality or reviewed
  composite package identified by `metadata/geographies.csv`.
- Statistical aggregates sum only rows assigned to that geography ID.
- Locality aggregates reconcile all geographic-scope rows, including rows that
  have no statistical-area assignment.
- Envelope results remain separate national non-geographic aggregates.

No aggregate is used to overwrite a ballot row. Aggregates are regenerated
from the normalized rows and checked back against official totals.

## Validation

The release build fails when any of these checks fail:

- a row's party votes do not sum to its valid-vote total;
- normalized locality and national totals do not reconcile to the official
  election totals;
- an assigned geography ID is absent from its published geometry package;
- duplicate row or geography IDs are present;
- an inferred link lacks its method, source, confidence, or synthetic flag;
- aggregate totals do not reconcile to their contributing rows;
- a manifest checksum or declared row count is wrong.

See `v2/validation.json`, `v2/manifest.csv`, and `v2/manifest.json` for the
machine-readable result of those checks.

## How To Audit A Link

1. Locate the ballot row in `v2/ballots/<election>.csv`.
2. Read its assignment method, source, confidence, and synthetic flag.
3. Inspect the matching evidence file under
   `v2/metadata/assignment-provenance/`.
4. Join `stat_area_id` to the election's full-resolution geography package.
5. Reaggregate the row set and compare it with the supplied aggregate and
   validation files.

The most useful evidence files are:

- `official_historical_ballot_crosswalk.csv`;
- `k23_cec_ags_validation.csv`;
- `stable_ballot_assignment_candidates.csv` and its conflict table;
- `arcgis_reconstruction_reviews.csv`;
- `cross_election_stat_area_reviews.csv`;
- `historical_assignment_gap_rows.csv`;
- `historical_polygon_coverage.csv`;
- `final_assignment_summary.csv`.

## Data Versus Website Presentation

The downloadable assignment remains row based. The website may combine or
substitute shapes to communicate uncertainty without changing those rows. In
particular, whole-locality fallbacks, representative polling-group unions,
tribal display markers, hidden empty proxies, basemap masks, circle placement,
party colors, and map modes are presentation behavior. They do not write a
`stat_area_id`, split votes, or increase assignment coverage.

Canonical downloadable geometry and its join metadata are part of the public
data release. Web-only transformed geometry and presentation-control tables
remain part of the protected website product, as specified in the repository's
root `LICENSE` notice.

The project-authored portions of this document and the public data release are
available under the MIT Data License. Official and third-party source material
retains its source terms.
