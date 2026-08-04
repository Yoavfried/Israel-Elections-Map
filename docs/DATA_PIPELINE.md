# Data Pipeline

Last updated: 2026-07-19

## Product Grain

The normalized fact table has one row per official election-result row or
ballot subdivision. A statistical-area assignment identifies the area served by
that ballot register. The browser performs no assignment or aggregation.

## Source Preparation

```powershell
python scripts/fetch_cbs_historical_geography.py
python scripts/fetch_election_results.py
python scripts/run_pipeline.py
```

Historical geometry and ArcGIS downloads are preparation inputs rather than
routine web-build dependencies. The CBS downloader inventories the public
catalog, verifies file signatures and expected lengths, and writes a SHA-256
manifest. The generic ArcGIS downloader pages through all object IDs instead of
trusting a potentially truncated query.

Reuse existing generated geography with:

```powershell
python scripts/run_pipeline.py --skip-geographies
```

## Stage Order

`scripts/run_pipeline.py` executes:

1. fetch K17-K25 official result rows;
2. build 2022 statistical areas, current localities, composites, and custom geometry;
3. build 1995, 2008, and 2011 historical geometry;
4. normalize election results;
5. build the reviewed locality and special-handling plan;
6. normalize the nine official CBS ballot crosswalks;
7. audit source schemas and catalog completeness;
8. audit and stage direct K23 CEC AGS assignments;
9. audit K20/K21 ArcGIS residual candidates and reviewed decisions;
10. audit and stage official CBS stable-ballot assignments;
11. build final row-level assignments in evidence-precedence order, including
    approved cross-election polling-register reviews;
12. classify every unresolved row and historical polygon coverage state;
13. aggregate statistical-area, locality, custom, envelope, contribution, and
    unresolved outputs;
14. audit official planned/final polling-group networks;
15. identify exact closed polygon/polling-group units with transport-flow
    bounds;
16. reconstruct consolidated final subdivisions only from strict
    two-reference polling-site continuity, then solve representative polygon
    ownership for the remaining networks;
17. generate exact closed, representative, and broad-fallback display layers;
18. build the committed schema-v2 `public-data/v1` release and validation report.

## Assignment Precedence

`scripts/build_final_geography_assignments.py` applies:

1. envelope and reviewed non-geographic rules;
2. reviewed historical overrides for specifically contradicted direct targets;
3. official CBS election-specific crosswalks;
4. direct official K23 CEC AGS;
5. approved exact ArcGIS residual reconstruction;
6. official CBS stable-ballot propagation with same-vintage consensus;
7. approved high-confidence cross-election polling-register continuity;
8. reviewed K17/K18 composite polling-register component evidence;
9. a locality fallback only when one historical area exists;
10. reviewed custom geography where no supported historical area exists;
11. unresolved historical assignment.

The output adds three general provenance fields:

- `assignment_evidence_class` groups the evidence hierarchy;
- `assignment_confidence` records `authoritative`, `high`, `moderate`,
  `not_applicable`, or `unresolved`;
- `assignment_is_synthetic_link` identifies inferred area links without
  implying synthetic vote data.

Synthetic-link builds are guarded by reviewed fingerprints and expected row and
voter totals. A changed mapping, evidence tier, or source reconciliation causes
the build to fail. Approximate arithmetic is not an assignment method.

## Historical Evidence Audits

### Source Fields

`scripts/audit_election_source_geography_fields.py` verifies that all nine CBS
crosswalks expose area fields, inventories the seven stable-ballot workbooks,
and checks archived CEC polling-place reports. Only K23 contains AGS among the
K20-K25 reports available locally.

### K23 AGS

`scripts/audit_k23_cec_stat_area_assignments.py` validates direct AGS against
existing assignments before staging pending rows. It requires a unique area,
withholds contradictions, and writes candidate, conflict, coverage, validation,
and summary artifacts.

### Stable Ballots

`scripts/audit_stable_ballot_assignments.py` builds components from the official
transition workbooks. It accepts a pending ballot only when all assigned
same-vintage members agree on one area. Decimal subdivisions share the
historical base ballot. Conflicts and cross-vintage transitions remain
published audit records rather than assignments.

### ArcGIS Residuals

`scripts/audit_arcgis_assignment_reconstruction.py` first classifies each
FeatureServer feature as a detailed area, a valid single-area locality total, or
a dissolved locality aggregate. Source metadata says Arab-locality areas were
merged, so dissolved aggregates cannot support detailed assignments.

Only reviewed, unique, exact residual partitions are staged. The current result
is nine K21 rows and zero K20 rows. No ArcGIS party or vote value enters the
official election fact table.

### Composite Polling Registers

`scripts/build_assignment_plan.py` validates the reviewed station ranges in
`data/manual/historical_composite_ballot_components.csv` against exact expected
row counts and rejects overlaps. The evidence identifies 164 K17/K18 rows with
their component locality. It supports an area link only when that component has
one canonical area in the active historical vintage; otherwise the component
identity is retained without inventing an area number.

### Reviewed Cross-Election Continuity

`data/manual/cross_election_stat_area_reviews.csv` contains 50 approved
high-confidence links. Each row fingerprints the election, locality, ballot,
eligible voters, and actual voters, and cites the official polling-register and
crosswalk evidence. The build rejects non-approved rows, changed source
identities, cross-locality targets, missing target geometry, or a vintage
mismatch. These are labeled synthetic links; no vote value is changed.

### Gap And Polygon Audit

`scripts/audit_historical_assignment_gaps.py` classifies all 5,549 pending rows,
compares K20/K21 detailed ArcGIS polygons where applicable, and writes
election-level polygon coverage, recurring crosswalk-locality omission, and
cross-election persistence tables.
Demographic population is labeled as a proxy and never treated as an
election-specific eligibility count.

### Reviewed Set-Level Displays

`data/manual/statistical_area_polling_group_display_reviews.csv` records
presentation-only corrections where source conflicts make a generated polygon
owner misleading but do not justify splitting votes. The display builder
releases the reviewed polygons and ballot rows from the generated partition,
dissolves the approved polygon set, and aggregates complete final ballot rows
onto that set. Row-level assignments and downloadable ballot tables remain
unchanged.

## Historical Geometry

`scripts/build_historical_geographies.py`:

- reads CBS 1995, 2008, and 2011 geometry;
- preserves distinct election-area IDs and ignores demographic reference fields
  as union instructions;
- produces stable IDs `stat<vintage>:<combined-code>`;
- constructs two 1995 targets from official transition keys, including the
  reverse-transition union for Modi'in Illit;
- adds 32 exact-ID 2011 geometry supplements from audited ArcGIS layers;
- creates separate display geometry with detailed footprints where canonical
  shapes are schematic;
- clips ordinary historical replacements against neighbors;
- marks all derivative tribal components as non-exclusive and combines them
  into one presentation-only marker in the web map, while retaining every exact
  component ID and result in the published data tables;
- preserves the reviewed detailed Ganei Modi'in overlay from K21;
- reuses the exact detailed Hebron footprint for the K17/K18 custom target and
  renders K17 Yehud statistical area 8 on the reviewed historical Newe Efrayim
  component polygon without changing its official transition assignment ID;
- never imports ArcGIS election totals.

The build summary separately inventories raw records, assignable IDs, multipart
pieces, structural exclusions, and supplements. Canonical feature counts are
2,661 for 1995, 3,030 for 2008, and 3,115 for
2011. `scripts/build_geographies.py` separately builds the 3,857-feature 2022
package for current locality display and future direct-crosswalk elections.

## Main Working Outputs

- `data/processed/geographies/statistical_areas_<vintage>.geojson`
- matching display GeoJSON, metadata CSV, and alias CSV files
- `data/processed/assignments/historical_ballot_crosswalk.csv`
- `data/processed/assignments/historical_ballot_assignments.csv`
- `data/processed/assignments/ballot_geography_assignments.csv`
- `data/processed/assignments/unresolved_statistical_area_assignment_rows.csv`
- `data/processed/audits/election_source_geography_field_audit.*`
- `data/processed/audits/k23_cec_ags_*`
- `data/processed/audits/stable_ballot_*`
- `data/processed/audits/arcgis_assignment_reconstruction_*`
- `data/processed/audits/historical_assignment_gap_*`
- `data/processed/audits/historical_crosswalk_locality_omission_recurrence.csv`
- `data/processed/audits/historical_polygon_*`
- `data/processed/audits/historical_municipality_display_fallbacks.csv`
- `data/processed/geographies/historical_geography_build_summary.json`
- `data/processed/public/<mode>/*.csv`

The curated repository release is written separately:

- `public-data/v1/ballots/*.csv`
- `public-data/v1/aggregates/<mode>/*.csv`
- `public-data/v1/geographies/*.zip` and feature-metadata CSVs
- `public-data/v1/metadata/*.csv`
- `public-data/v1/metadata/assignment-provenance/*`
- `public-data/v1/manifest.{csv,json}`
- `public-data/v1/validation.json`

The release builder rejects duplicate ballot rows, actual-voter totals that do
not equal valid plus invalid votes, missing geometry joins, party totals that do
not equal valid votes, and provenance totals that do not match the reviewed
decisions.

## Verified Coverage

Verified from the offline rebuild on 2026-08-03:

| Election | Vintage | Supported rows | Pending rows | Supported voter share | Locality share |
|---|---:|---:|---:|---:|---:|
| K17 | 1995 | 7,865 | 409 | 94.65% | 100% |
| K18 | 2008 | 8,741 | 518 | 94.14% | 100% |
| K19 | 2011 | 9,317 | 558 | 94.13% | 100% |
| K20 | 2011 | 9,545 | 567 | 93.55% | 100% |
| K21 | 2011 | 9,855 | 597 | 94.51% | 100% |
| K22 | 2011 | 9,922 | 609 | 93.65% | 100% |
| K23 | 2011 | 10,006 | 617 | 93.08% | 100% |
| K24 | 2011 | 11,251 | 868 | 94.71% | 100% |
| K25 | 2011 | 10,893 | 806 | 94.01% | 100% |

## Other Reviewed Inputs

- `data/manual/k17_eligible_voters.csv` restores K17 ordinary-register turnout
  and reconciles to 5,011,053 eligible voters. Its official scan locality code,
  locality name, and ballot number are validated against every ordinary K17
  result row so historical matching does not rely on modern merger aliases.
- `data/manual/composite_localities.csv` and
  `data/manual/joined_locality_composites.csv` control election-specific
  locality display unions.
- `data/manual/historical_single_stat_fallback_exclusions.csv` blocks the
  deterministic single-area fallback when an election result represents a
  reviewed combined municipality but the historical layer retains separate
  component polygons.
- `data/manual/locality_display_overrides.csv` controls reviewed historical
  names and visibility.
- `data/manual/statistical_area_display_overrides.csv` controls reviewed
  election-specific statistical-area visibility and names without changing
  canonical geometry or assignment identifiers.
- `data/manual/statistical_area_display_groups.csv` records presentation-only
  result grouping and marker treatment for component areas whose available
  footprints cannot be displayed as exclusive geography.
- `data/manual/historical_composite_ballot_components.csv` preserves reviewed
  K17/K18 polling-register ranges and component-locality evidence.
- `data/manual/historical_stat_area_overrides.csv` records five reviewed K19
  target corrections.
- `data/manual/arcgis_assignment_reconstruction_reviews.csv` records approved
  and rejected ArcGIS decisions.
- `data/manual/cross_election_stat_area_reviews.csv` records the 50 approved
  high-confidence polling-register continuity links and their source evidence.
- `data/manual/party_registry.csv` covers every election-specific result column;
  map colors remain presentation configuration under `web/app/`.

Polling-group display ownership is intentionally not a manual input. The
pipeline rebuilds it from the audited official-register evidence, validates
unique ballot and polygon ownership, and fails if either the flow analysis or
bounded partition solver does not finish. Exact final ballot matches are peeled
before unique site linkage. Planned counts then weight graph edges without
being treated as conserved final totals. Disconnected geometry never forces
otherwise distinct polling groups to merge. Planned-only sites are reconciled
only through unique agreement on candidate areas, polling-place text, and
eligible-voter arithmetic. The pipeline currently publishes 517 exact closed
units without uncertainty notices and 1,757 representative units with notices.
Multi-group representative units eliminate every former broad
network fallback; `build_statistical_area_result_aggregates.py` emits an empty
artifact so stale fallback geometry cannot survive a rebuild.

## Web Build

```powershell
cd web/app
npm install
npm run check
npm run dev
```

The compiler writes a schema-v5 catalog, schema-v2 map results, and schema-v1
national-result and election-aware geography-search assets under
`web/app/public/data/v2/`. Those browser contracts are separate from the public
download release's schema-v2 ballot tables.

`build_public_outputs.py` also emits a display-only locality aggregate when an
election/locality has zero supported area assignments. The frontend substitutes
that locality footprint for its empty component areas and exposes a notice.
This layer is excluded from assignment coverage and never writes an area ID
back to a ballot row.
