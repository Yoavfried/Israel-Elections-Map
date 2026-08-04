# Commercial-Use Audit

Last reviewed: 2026-08-03

This document records published reuse terms for repository inputs, services,
and redistributed outputs relevant to a deployment intended to make money. It
lists only terms that a source explicitly publishes. Methodological provenance
for all sources remains in `docs/DATA_SOURCES.md`. This is an engineering source
audit, not legal advice.

## Bottom Line

The copyright owner may commercialize the project-authored website and
pipeline. The components listed below have published terms that permit
commercial use when their conditions are followed.

## Classification

| Component | Commercial status | Required treatment |
|---|---|---|
| Project-authored website, pipeline, design, copy, and party colors | Clear for the copyright owner | The owner is not restricted by `LICENSE-WEBSITE`. Third parties receive no commercial reuse grant for current protected material. |
| Project-authored portions of `public-data/**` and non-presentation evidence files under `data/manual/**` | Clear | MIT permits commercial reuse. The five presentation-control exceptions are listed in the root `LICENSE`; upstream source terms still apply to embedded official or third-party material. |
| Official K17-K25 election results | Clear, with a generic open-data label | The official data.gov.il package is public, `isopen: true`, and `Other (Open)`. Preserve package/source provenance and do not imply official endorsement. |
| Official CBS geometry, crosswalks, transition tables, locality data, and census attributes | Clear with conditions | CBS expressly permits commercial use. Follow its source-acknowledgement, accuracy, privacy, third-party-rights, and non-endorsement conditions. |
| `map-context-footprint.geojson` | Clear with ODbL duties | It contains OSM-derived boundary data. Keep OSM attribution, identify ODbL, and distribute an adapted database under ODbL. This does not license the website code or design. |
| OpenFreeMap vector tiles/style service | Clear with attribution | Commercial use is explicitly allowed. Keep provider/OpenMapTiles/OSM attribution. The public service has no SLA, so self-hosting or a contracted provider is an operational decision. |
| Photon software and OSM geocoder data | Clear with conditions | Photon is Apache-2.0 and OSM data is ODbL. The public demo allows reasonable project traffic but may throttle or ban extensive use and gives no availability guarantee. Use a self-hosted or contracted endpoint for a paid service at scale. |
| Wikipedia links | Clear as links | The app links to articles and does not copy article text or media. Any future copied summaries or images need a separate CC/trademark review. |
| Party/list names, ballot letters, vote totals, and mandates | Clear as factual identification | The app uses no party logos. Keep a non-affiliation statement and avoid suggesting party endorsement. |
| npm runtime and build dependencies | Clear | Installed packages use MIT, ISC, BSD, Apache-2.0, MPL-2.0, 0BSD, or compatible dual licences. Retain required copyright/licence notices in distributions. MPL applies only to the relevant dependency files, not to project code merely using them. |
| Python pipeline dependencies | Clear | Direct requirements use commercial-compatible BSD, MIT, or similarly permissive licences. Preserve notices if distributing a bundled pipeline/runtime. |
| System fonts | Clear for normal web use | The app references installed system fonts and does not redistribute font files. |

## Commercial Deployment Requirements

Before charging users, running advertising, or selling access:

1. Publish an accessible Sources/Legal page containing CBS, OSM/OpenMapTiles,
   OpenFreeMap, and software notices plus a clear non-affiliation
   statement.
2. Publish a privacy notice explaining that exact address text is transmitted
   to the configured geocoder and that tile providers receive ordinary web
   request metadata. The current code contains no analytics, advertising, or
   payment SDK.
3. Use production-capacity providers or self-hosting for geocoding and map
   tiles where uptime and request volume matter. This is an operational
   requirement even where free commercial use is legally allowed.
4. Preserve a dated copy of upstream terms used for each
   release so later source-term changes do not erase the audit trail.

## Repository-Licence Caveat

The split licence protects current project-authored website and pipeline
material from unlicensed third-party reuse. It does not restrict the copyright
owner's own commercial deployment.

Versions published under the repository's earlier MIT licence remain
commercially reusable by anyone under that grant. The later split licence
cannot withdraw rights already granted in those older versions, so it protects
new work but does not create complete exclusivity over the earlier codebase.

## Primary Terms Checked

- CBS end-user licence: https://www.cbs.gov.il/en/Pages/Enduser-license.aspx
- Official election-results package: https://data.gov.il/api/3/action/package_show?id=26f9fa06-fcd7-4173-8df5-65797b63e857
- OpenStreetMap copyright/ODbL: https://www.openstreetmap.org/copyright
- OpenFreeMap terms and commercial-use statement: https://openfreemap.org/tos/ and https://openfreemap.org/
- Photon licence and public-demo policy: https://github.com/komoot/photon
