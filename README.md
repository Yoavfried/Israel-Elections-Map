# Israel Election Map

Bilingual web application and reproducible data pipeline for exploring K17-K25
Knesset election results nationally, by locality, and by
election-appropriate statistical area.

The map includes offline election-aware search across Hebrew and English
locality names, statistical areas, historical names, reviewed aliases, and
geography codes. Exact numbered-address lookup adds a network-assisted
OpenStreetMap/Photon coordinate search; the client then resolves that point
locally against the selected election's visible statistical geometry. A
separate single-party view colors those same geographies by
the selected list's local vote share while retaining the complete area result
on selection. A two-party comparison view adds a diverging head-to-head balance
without changing the underlying election or geography data. A coalition view
uses a reviewed election-specific member list to map the combined local vote
share of the first coalition, or the outgoing transitional coalition when no
government was formed.
The geographic views can place those election layers over a localized,
OSM-derived vector street map, with the original neutral background retained
as a persisted offline-friendly fallback. Single-party mode can switch from
area fills to vote circles: color represents local vote share and circle area
represents absolute party votes. Color is capped at the positive-share 95th
percentile; circle size uses one party-independent scale capped at the 99th
percentile of each area's leading-party vote total and a smaller maximum radius
to avoid dense oversized clusters.

The repository contains a Python data pipeline, a React/TypeScript/MapLibre
client, and a committed public-data release. Statistical results use direct CBS
ballot-to-area evidence where available, additional official AGS and
stable-ballot evidence, explicitly labeled reviewed inference, and matching
historical geometry.

## Download The Data

Ready-to-use files are committed under [`public-data/v1`](public-data/v1/). No
pipeline run is required.

| Election | Full ballot-row CSV | Statistical-area results | Locality results |
|---|---|---|---|
| K17 (2006) | [Download](public-data/v1/ballots/k17.csv?raw=1) | [Download](public-data/v1/aggregates/statistical-areas/k17.csv?raw=1) | [Download](public-data/v1/aggregates/localities/k17.csv?raw=1) |
| K18 (2009) | [Download](public-data/v1/ballots/k18.csv?raw=1) | [Download](public-data/v1/aggregates/statistical-areas/k18.csv?raw=1) | [Download](public-data/v1/aggregates/localities/k18.csv?raw=1) |
| K19 (2013) | [Download](public-data/v1/ballots/k19.csv?raw=1) | [Download](public-data/v1/aggregates/statistical-areas/k19.csv?raw=1) | [Download](public-data/v1/aggregates/localities/k19.csv?raw=1) |
| K20 (2015) | [Download](public-data/v1/ballots/k20.csv?raw=1) | [Download](public-data/v1/aggregates/statistical-areas/k20.csv?raw=1) | [Download](public-data/v1/aggregates/localities/k20.csv?raw=1) |
| K21 (April 2019) | [Download](public-data/v1/ballots/k21.csv?raw=1) | [Download](public-data/v1/aggregates/statistical-areas/k21.csv?raw=1) | [Download](public-data/v1/aggregates/localities/k21.csv?raw=1) |
| K22 (September 2019) | [Download](public-data/v1/ballots/k22.csv?raw=1) | [Download](public-data/v1/aggregates/statistical-areas/k22.csv?raw=1) | [Download](public-data/v1/aggregates/localities/k22.csv?raw=1) |
| K23 (2020) | [Download](public-data/v1/ballots/k23.csv?raw=1) | [Download](public-data/v1/aggregates/statistical-areas/k23.csv?raw=1) | [Download](public-data/v1/aggregates/localities/k23.csv?raw=1) |
| K24 (2021) | [Download](public-data/v1/ballots/k24.csv?raw=1) | [Download](public-data/v1/aggregates/statistical-areas/k24.csv?raw=1) | [Download](public-data/v1/aggregates/localities/k24.csv?raw=1) |
| K25 (2022) | [Download](public-data/v1/ballots/k25.csv?raw=1) | [Download](public-data/v1/aggregates/statistical-areas/k25.csv?raw=1) | [Download](public-data/v1/aggregates/localities/k25.csv?raw=1) |

The ballot CSVs contain every source result row, party-vote columns, and the
corresponding statistical-area and locality IDs. Polygon ZIPs expose the same
`geography_id`, so the join is direct. Assignment method/source fields identify
198 rows whose area link is inferred rather than copied from a direct official
crosswalk. Their vote values remain official, and the exact evidence class,
confidence, source, and synthetic-link flag are published on every row.

- [Complete download index and polygon packages](public-data/README.md)
- [Data dictionary and join examples](public-data/DATA_DICTIONARY.md)
- [Exact assignment and validation methodology](public-data/METHODOLOGY.md)
- [Machine-readable manifest and checksums](public-data/v1/manifest.csv?raw=1)

Map colors, UI labels, web-only polygon transformations, and interaction
settings remain protected presentation configuration under `web/app/` and the
explicit display-control exceptions in `data/manual/`; they are not part of the
reusable data tables.

## Geographic Assignment

Statistical-area assignment precedence is:

1. official envelope or reviewed non-geographic handling;
2. reviewed historical overrides where independent evidence disproves a direct
   crosswalk target;
3. official election-specific CBS ballot-to-statistical-area crosswalk;
4. direct K23 CEC AGS evidence;
5. reviewed exact ArcGIS residual reconstruction;
6. official CBS stable-ballot propagation when all same-vintage evidence agrees;
7. reviewed high-confidence polling-register continuity across elections;
8. reviewed K17/K18 polling-register evidence identifying a composite's
   component locality;
9. historical locality fallback only when that locality has one published area;
10. reviewed custom geography where no supported historical area exists;
11. explicit unresolved status.

Statistical mode uses 1995 areas for K17, 2008 for K18, and 2011 for K19-K25.
K25 remains on 2011 because its official crosswalk targets that vintage;
forcing those results onto 2022 areas would invent precision.

The public CBS crosswalks consistently omit some localities and individual
ballots. The release keeps these rows explicit rather than assigning them from
polling-place addresses. Source inventories, recurring-omission tables, and
component-locality evidence are included under
`public-data/v1/metadata/assignment-provenance/`.

When an election/locality or reviewed K17/K18 historical component has no
supported ballot-to-area assignment at all, the web map shows its total on a
display-only reviewed boundary with an explanatory info icon. Component shapes
retain the election-era composite's outer footprint. This does not assign those
ballots, change the downloadable tables, or increase the reported
statistical-area coverage.

## Run Locally

The full pipeline depends on official source files that are not committed.
Start with [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md) and
[`data/README.md`](data/README.md).

```powershell
python -m pip install -r requirements.txt
python scripts/fetch_cbs_historical_geography.py
python scripts/fetch_election_results.py
python scripts/run_pipeline.py
```

Reuse existing generated geometry with:

```powershell
python scripts/run_pipeline.py --skip-geographies
```

Run the web app:

```powershell
cd web/app
npm install
npm run dev
```

Vite serves the app at `http://localhost:4173`. The frontend compiler reads
promoted `data/processed/` outputs and reviewed election/presentation metadata,
then writes validated assets under `web/app/public/data/v2/`.

## Documentation

- [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) is the only completion
  tracker.
- [`docs/FEATURE_PLAN.md`](docs/FEATURE_PLAN.md) records the product roadmap and delivery order.
- [`docs/HISTORICAL_STATISTICAL_AREA_ASSIGNMENT.md`](docs/HISTORICAL_STATISTICAL_AREA_ASSIGNMENT.md)
  documents source hierarchy, vintages, matching rules, and coverage.
- [`docs/LOCALITY_MODE.md`](docs/LOCALITY_MODE.md) documents locality
  aggregation, composites, result-presence evidence, and envelopes.
- [`docs/DATA_PIPELINE.md`](docs/DATA_PIPELINE.md) documents the reproducible
  stage order and outputs.
- [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md) inventories election,
  geography, and party sources.
- [`docs/COMMERCIAL_USE_AUDIT.md`](docs/COMMERCIAL_USE_AUDIT.md) records
  explicitly published commercial-use permissions and obligations.
- [`web/app/docs/ARCHITECTURE.md`](web/app/docs/ARCHITECTURE.md) defines the
  frontend data contract and product boundary.

## Repository Layout

- `public-data/` - committed, versioned data downloads and geography packages.
- `data/manual/` - committed reviewed corrections and assignment overrides.
- `data/raw/` and `data/processed/` - local source and generated working data,
  intentionally ignored by Git.
- `docs/` - methodology, source notes, and decisions.
- `scripts/` - ingestion, normalization, geography, assignment, QA,
  aggregation, and public-release generation.
- `web/app/` - Vite, React, TypeScript, and MapLibre client.

## Licensing

This is a source-visible, split-license repository. It is not licensed as a
whole under MIT.

- The project-authored portions of `public-data/` and the non-presentation
  evidence tables under `data/manual/` are available under the
  [MIT Data License](LICENSE-DATA), so the reusable tables, metadata,
  provenance, methodology, and canonical polygon packages can be used freely.
- The website, pipeline and build source, tests, visual design, map
  presentation, web-only polygon unions and fallbacks, party-color
  configuration, copy, and project documentation are protected under the
  [Website and Project Materials Notice](LICENSE-WEBSITE).
  They may be inspected in this public repository but are not licensed for
  reuse, redistribution, modification, deployment, or derivative works.
- Official and third-party source material remains subject to its source terms;
  see [Third-Party Data Notices](THIRD_PARTY_NOTICES.md).
- The OSM-derived map-context database is separately available under ODbL 1.0
  as documented in [`web/app/data/README.md`](web/app/data/README.md).

The complete path-level boundary and the treatment of versions previously
published under MIT are recorded in the root [license notice](LICENSE). See the
[commercial-use audit](docs/COMMERCIAL_USE_AUDIT.md) for explicitly published
third-party reuse terms relevant to a commercial deployment.

See [`CONTRIBUTING.md`](CONTRIBUTING.md) before changing reviewed data or a
generated release. Do not commit credentials, machine-specific paths,
disposable investigation files, or raw source downloads.
