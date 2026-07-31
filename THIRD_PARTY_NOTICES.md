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

## Software Dependencies

Packages installed through Python and npm remain under their respective
licenses. See `requirements.txt`, `web/app/package.json`, and installed package
metadata for the applicable notices.
