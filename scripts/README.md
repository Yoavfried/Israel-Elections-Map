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
  the 1995, 2008, and 2011 vintages.
- `normalize_election_results.py` normalizes official ballot rows and party
  columns.
- `build_assignment_plan.py` applies envelope handling, locality identities,
  and reviewed custom classifications.
- `build_historical_ballot_assignments.py` applies the official crosswalks and
  the unique historical-area locality fallback.
- `audit_arcgis_assignment_reconstruction.py` emits K20/K21 unique exact
  partition candidates, checks valid/invalid totals per residual area, and
  attaches the reviewed decisions. The published approvals are one Tier A and
  one Tier C K21 partition; no tolerance-based Tier B decision is accepted.
- `build_final_geography_assignments.py` writes independent locality and
  statistical-area assignment fields and applies only approved exact or
  high-confidence reviewed links after official crosswalk assignments.
- `build_public_outputs.py` writes aggregates, contributions, coverage, and
  pending rows, plus display-only whole-locality fallbacks for elections where
  a locality has no supported area assignments.
- `audit_statistical_area_polling_group_evidence.py` links official planned and
  final polling registers and emits nationwide overlapping-area networks.
- `build_statistical_area_polling_group_policy.py` first uses
  `polling_group_flow.py` to publish provably closed polygon/polling-group
  units, then uses `polling_group_ownership.py` for the remaining
  representative placements. Exact closed units have no uncertainty notice.
- `build_statistical_area_result_aggregates.py` and
  `build_statistical_area_polling_group_displays.py` generate broad fallback,
  exact closed, and representative presentation layers without changing
  row-level assignments.
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
