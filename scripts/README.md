# Scripts

Install Python dependencies from the repository root:

```bash
python -m pip install -r requirements.txt
```

## Source Preparation

Raw downloads are not committed. Prepare inputs using
`docs/DATA_SOURCES.md`:

```bash
python scripts/fetch_election_results.py
python scripts/fetch_cbs_historical_geography.py
```

`fetch_arcgis_feature_layer.py` downloads complete paged FeatureServer layers
for labeled geometry supplements, display footprints, and aggregate audits.
Those layers never replace official vote rows.

The optional Kaplan source audit downloads the data payloads behind the supplied
K22-K25 map applications, decodes their properties locally, and checks their
grain and locality totals:

```bash
python scripts/audit_kaplan_map_sources.py --fetch
```

It writes a raw-source manifest and candidate-only audit files. It never changes
an assignment; the current sources produce zero candidates because none exposes
a statistical-area identifier or ballot crosswalk.

## Production Pipeline

```bash
python scripts/run_pipeline.py
```

Reuse generated 1995, 2008, 2011, and 2022 geometry:

```bash
python scripts/run_pipeline.py --skip-geographies
```

Production stages:

- `fetch_election_results.py` fetches official K17-K25 ballot rows and writes a
  source manifest.
- `build_geographies.py` builds 2022 statistical/locality geometry, composites,
  custom geometry, display replacements, and the neutral land backdrop.
- `build_historical_geographies.py` builds canonical and display geometry for
  the 1995, 2008, and 2011 vintages. Reviewed current-locality cutouts remove
  fallback overlap from historical hosts; the reverse-priority operation emits
  an election-vintage fallback geometry when an official historical polygon
  must remain intact inside a newer locality boundary.
- `normalize_election_results.py` normalizes official ballot rows and party
  columns.
- `build_assignment_plan.py` applies envelope handling, locality identities,
  and reviewed custom classifications.
- `build_historical_ballot_assignments.py` applies the official crosswalks and
  the unique historical-area locality fallback, except for reviewed combined
  municipalities listed in
  `data/manual/historical_single_stat_fallback_exclusions.csv`.
- `audit_arcgis_assignment_reconstruction.py` emits K20/K21 unique exact
  partition candidates, checks valid/invalid totals per residual area, and
  attaches the reviewed decisions. The published approvals are one Tier A and
  one Tier C K21 partition; no tolerance-based Tier B decision is accepted.
- `build_final_geography_assignments.py` writes independent locality and
  statistical-area assignment fields and applies only approved exact or
  high-confidence reviewed links after official crosswalk assignments.
- `build_public_outputs.py` writes aggregates, contributions, coverage, and
  pending rows, plus display-only whole-locality or reviewed-component fallbacks where
  a locality has no supported area assignments.
- `audit_statistical_area_polling_group_evidence.py` first removes exact final
  ballot-to-area matches, then links official planned and final polling sites
  only through unique site, ballot-base, or normalized-location evidence.
- `build_statistical_area_polling_group_policy.py` first uses
  `polling_group_flow.py` to publish provably closed polygon/polling-group
  units. For the remaining networks, `polling_group_partition.py` starts with
  the detailed ownership from `polling_group_ownership.py` and merges polling
  groups only until each unit has majority precision and recall under planned,
  final-actual, and final-eligible weighting. Multiple polling groups may share
  one displayed polygon combination. Disconnected geometry is disclosed but
  never causes polling groups to merge. A planned-only site is reconciled to a
  final-result site only when candidate areas, normalized polling-place text,
  and eligible-voter arithmetic identify one unique target. Final decimal subdivisions still require
  stable site identity and exact area-set agreement in at least two
  direct-evidence elections. Exact closed units have no uncertainty notice.
- `build_statistical_area_result_aggregates.py` and
  `build_statistical_area_polling_group_displays.py` generate exact closed and
  representative presentation layers without changing row-level assignments.
  `build_reviewed_locality_statistical_displays.py` first audits every reviewed
  joined locality and historical merger against the active election vintage.
  It emits an exact display union only when a one-area host contains the full
  locality result, every attached polygon lacks an independent result, and no
  other display policy owns a component. Multi-area hosts remain audit rows so
  supported internal detail is never discarded automatically. A relationship
  reviewed in another election is emitted only as a continuity review
  candidate. `audit_joined_locality_continuity.py` then tests those candidates
  against the official K18/K19 register extracts and complete K20-K25 polling
  workbooks. Direct attachments and unique exact arithmetic can be confirmed;
  continuity must be bracketed by matching direct host evidence or supported
  backward by the first two adjacent later direct-evidence elections. The
  script records every decision and supports an idempotent `--apply` for only
  conflict-free approvals. The current run retains all 180 cases in the audit,
  with 38 applied and 142 covered, contradicted, or insufficient.
  Reviewed set-level display corrections are sourced from
  `data/manual/statistical_area_polling_group_display_reviews.csv`; they may
  replace generated polygon ownership but never rewrite the ballot table.
  The display builder reads the final provenance table so reviewed synthetic
  row assignments are retained when their polygons enter a joined display.
  The aggregate builder always rewrites its artifact from the current reviewed
  and generated policies, preventing stale geometry from surviving a rebuild.
- `audit_statistical_display_ownership.py` combines result-aggregate, polling-
  group, and manual display claims and fails the pipeline if any statistical
  area is owned by more than one displayed result in the same election.
- `audit_display_contributor_capacity.py` checks each rendered unit against
  final eligible voters assigned to all possible contributor polygons and,
  separately, against a lenient 125% total-population proxy. Pre-election area
  weights are retained as diagnostic evidence but are not treated as hard
  final capacities. `review_display_contributor_capacity_flags.py` adds
  adjacency, polling-site, final-ballot, and cross-election context. Human
  decisions are recorded in
  `data/manual/display_contributor_capacity_reviews.csv`.
- `build_public_data_release.py` publishes `public-data/v1` ballot CSVs,
  aggregate tables, full-resolution geography ZIPs, metadata, checksums, and
  release validation.

Missing official crosswalk rows stay pending unless another reviewed source
proves a unique exact assignment. Approved inferred relationships are labeled
in the final row-level provenance fields. Current gaps are documented only in
`docs/PROJECT_STATUS.md`; methodology is in
`docs/HISTORICAL_STATISTICAL_AREA_ASSIGNMENT.md`.

Reviewed row-level exceptions belong under `data/manual/`, never in generated
CSV files. `--skip-geographies` still validates every expected geometry asset.
The approved cross-election links are maintained in
`data/manual/cross_election_stat_area_reviews.csv`; the generated public copy
and each ballot row preserve their synthetic-link provenance.
The complete review of the thirteen specific ordinary crosswalk omissions is
recorded in `data/manual/omitted_ordinary_ballot_reviews.csv`.
