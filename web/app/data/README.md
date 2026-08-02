# Map Context Geometry

`map-context-footprint.geojson` is a display-only land footprint used by the
web map. It combines the project's CBS-derived 2022 statistical-land backdrop
with the full West Bank Oslo-area perimeter from OpenStreetMap relation
`13283819`, dissolves their shared edge, keeps the outer land ring, and applies
a 5 metre Douglas-Peucker simplification. The part of the Ghajar statistical
polygon north of the OSM Lebanon boundary (relation `184843`) is then removed.
This avoids administrative maritime extensions in the Mediterranean and Gulf
of Eilat and excludes northern Ghajar from the displayed national footprint.

The footprint does not define election geography, sovereignty, ballot
assignment, or result coverage. It exists only to keep the vector basemap
visible across Israel and the full West Bank, mask surrounding land, and draw
an outer contextual boundary in the neutral map. Gaza is outside the
footprint. Roads, buildings, and Area A/B/C detail continue to come from the
configured vector-tile style. Vector labels are filtered to this footprint, so
labels in Gaza and surrounding countries are not drawn.

The CBS-derived source is documented with the other statistical geometry. The
West Bank and Lebanon boundary geometry was retrieved from OpenStreetMap
through Nominatim on 2026-08-02. OpenStreetMap data is available under the Open
Database License; see `THIRD_PARTY_NOTICES.md` and
<https://www.openstreetmap.org/copyright>.
