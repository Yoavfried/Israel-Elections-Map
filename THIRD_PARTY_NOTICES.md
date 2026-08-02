# Third-Party Data Notices

The MIT Data License applies only to the project-authored portions of the paths
identified in the root `LICENSE` notice. It does not replace terms attached to
official source data, third-party content, trademarks, or bundled dependencies.
The website and other protected project materials are governed separately by
`LICENSE-WEBSITE`.

## Israel Central Bureau of Statistics

Statistical-area geometry, locality metadata, transition tables, and
ballot-to-area tables originate from the Israel Central Bureau of Statistics
(CBS). CBS publishes website information under its open end-user license,
which permits commercial and non-commercial reuse subject to conditions that
include source acknowledgement, non-endorsement, accuracy, privacy, and
third-party-rights limitations:

https://www.cbs.gov.il/en/Pages/Enduser-license.aspx

Exact product names, source URLs, access records, and checksums are retained in
the source manifest and `docs/DATA_SOURCES.md`. Derived files continue to carry
their source and method fields.

## Election Results

Ballot-level election results originate from official Central Elections
Committee and Israeli government data publications. The project does not
relicense official source files, logos, or other protected presentation. Users
of redistributed tables are responsible for complying with the terms at the
source publication.

## ArcGIS Feature Services

Two externally supplied ArcGIS FeatureServer layers are used for explicitly
identified geometry supplements, display detail, and reviewed aggregate
reconstruction evidence. Their service metadata does not state a reusable
content license. The project therefore makes no broader licensing claim for
those source geometries or aggregates. Every derivative use is labeled in
geography metadata or row-level assignment provenance.

## Kaplan Open Source Election Maps

The optional source audit can download public election-map payloads from
`elections.kaplanopensource.co.il` for source-grain and aggregate
reconciliation checks. Those raw payloads are ignored by Git and are not
redistributed in the public data release. The project makes no licensing claim
over that third-party content and does not import its vote values or geometry
into production outputs.

## OpenStreetMap Vector Basemap

When enabled, the web client requests a MapLibre style and vector-map resources
from OpenFreeMap. The style is based on OpenMapTiles and map data derived from
OpenStreetMap. The application displays the provider and data attribution
supplied with that service. No OpenFreeMap tiles are committed to or
redistributed with this repository.

The committed display-only `web/app/data/map-context-footprint.geojson`
combines the CBS-derived statistical-land backdrop described above with
OpenStreetMap relation `13283819` (the full West Bank Oslo-area perimeter).
The overlap between the Ghajar statistical polygon and OpenStreetMap relation
`184843` (Lebanon) is removed. The OpenStreetMap-derived portions remain ODbL
data and are not relicensed under either project license. The footprint defines
map presentation only, not election geography, sovereignty, ballot assignment,
or result coverage.

- OpenFreeMap: https://openfreemap.org/
- OpenMapTiles: https://openmaptiles.org/
- OpenStreetMap copyright and attribution: https://www.openstreetmap.org/copyright

The tile host is replaceable through web-build configuration. A downstream
deployment that changes providers is responsible for that provider's terms,
attribution, capacity, and caching requirements.

## Address Search

Numbered-address queries are sent to a Photon-compatible geocoder. The default
endpoint is the public Photon demonstration service at
`https://photon.komoot.io/api/`, which searches OpenStreetMap data. The browser
limits and debounces requests, requires an explicit matching house number, and
uses the returned coordinate only. Statistical-area assignment is performed
locally against this project's election-specific geometry.

- Photon: https://photon.komoot.io/
- Photon source and self-hosting documentation: https://github.com/komoot/photon
- OpenStreetMap copyright and attribution: https://www.openstreetmap.org/copyright

The public Photon service has no availability guarantee and is not a production
capacity commitment. `VITE_ADDRESS_GEOCODER_URL` can replace it with a
compatible self-hosted or contracted endpoint. Deployers are responsible for
the selected provider's terms, privacy disclosures, capacity, and attribution;
user-entered address text is transmitted to that endpoint.

Hebrew and Arabic vector labels are processed with the pinned
`@mapbox/mapbox-gl-rtl-text` package, served from the application build under
its BSD-2-Clause license. Its URL can also be replaced through web-build
configuration.

## Software Dependencies

Packages installed through Python and npm remain under their respective
licenses. See `requirements.txt`, `web/app/package.json`, and installed package
metadata for the applicable notices.
