# Product Feature Plan

Last updated: 2026-07-31

This document records the intended design and delivery order for future map
features. It is not a completion tracker. Actual complete/in-progress state is
maintained only in `docs/PROJECT_STATUS.md`.

## Delivery Order

Search and the Wikipedia-link audit are complete. Statistical assignment work
continues in parallel; closing a source gap never means forcing a ballot onto a
polygon.

Current priority:

1. single-party map mode;
2. two-party comparison mode;
3. satellite, OSM vector, and 3D-building basemaps at the same priority.

The national-results baseline is implemented as a primary top-bar view and
remains the reference surface for the completed party-name, color, and
Wikipedia-link tables. Future analysis modes should use the same primary
navigation rather than being added to the geographic-level selector.

Responsive bilingual UX, accessibility, and regression QA are requirements for
every item, not a separate planned feature.

## Planned Features

### 1. Locality And Statistical-Area Search (Delivered Baseline)

The compiler now builds an offline, election-aware search index from the map's
own visible geography. It indexes Hebrew and English names,
locality/statistical-area codes, historical names, and reviewed aliases.

Implemented behavior:

- accessible combobox with keyboard navigation and autocomplete;
- exact-code and exact-name results first, then prefix and tolerant normalized
  matches;
- results are restricted to the selected election and label their geography
  mode; choosing a result in the other mode switches the map automatically;
- selecting a result fits its bounds, highlights it, and opens its result panel;
- visible polygons without mapped results remain searchable and open an explicit
  no-result state;
- no network dependency for locality or statistical-area lookup.

### 2. National Results (Delivered Baseline)

The election-level national view is available alongside the map.

Implemented behavior:

- nationwide votes and valid-vote share for every list;
- the election's legally applicable electoral threshold and a clear indication
  of which lists crossed it;
- exact final mandate counts from the official result, not an undocumented
  approximation of seat allocation;
- envelope votes included in the national totals;
- Hebrew and English party names and reviewed article links where available.

### 3. Single-Party Map Mode

Allow one election-specific party/list to be selected. Polygon color is a
sequential gradient derived from that party's reviewed base color: stronger
color means a higher share of valid votes and weaker color means a lower share.

Expected behavior:

- election-aware party search because ballot letters can change meaning;
- a numeric legend with a stated percentage domain;
- selecting a polygon still opens the complete area result;
- an optional circle mode where circle size represents that party's vote count
  and color represents its vote share;
- zero, missing, and statistically unresolved results remain distinguishable.

### 4. Two-Party Comparison

Allow two election-specific parties to define the two ends of a diverging
color scale. Each polygon receives a mixed color based on the local balance
between the selected parties.

Expected behavior:

- both selected parties and their base colors remain visible in the controls
  and legend;
- the comparison metric and neutral midpoint are stated explicitly;
- selecting a polygon opens the complete result while visually emphasizing the
  two compared parties;
- ties, zero votes for both parties, and missing results have explicit neutral
  states.

### 5. Basemap And 3D Suite

Satellite imagery, an OSM-derived vector basemap, and optional 3D buildings
share the same priority and follow the result-analysis modes above.

#### Satellite Basemap

Add a basemap selector with the existing neutral map and a satellite option.
Election polygons remain an interactive overlay rather than becoming part of
the imagery.

Required behavior:

- configurable raster-tile source rather than a hard-coded provider URL;
- visible provider/data attribution;
- polygon fill-opacity control so imagery remains inspectable;
- labels and boundaries remain legible over bright and dark imagery;
- provider terms, API-key handling, cost, caching, and Israel coverage reviewed
  before selection.

No satellite provider is selected yet. Esri/other commercial imagery must not be
used merely because an unauthenticated tile URL happens to work.

#### OpenStreetMap Vector Basemap And 3D Buildings

Add an OSM-derived vector basemap beneath the election polygons. OpenFreeMap is
a candidate because it exposes a MapLibre style and OSM-derived vector tiles;
self-hosted regional PMTiles remain the stronger long-term control option.

Expected behavior:

- streets, labels, POIs, and building footprints visible beneath results;
- optional 3D mode at close zoom using MapLibre `fill-extrusion` and available
  building height/min-height attributes;
- pitch/bearing controls appear only when 3D mode is active;
- election polygons, hover state, and click targets remain visually dominant;
- reduced-motion and low-performance fallbacks disable unnecessary extrusion;
- attribution is always visible.

Do not treat the community `tile.openstreetmap.org` or
`vector.openstreetmap.org` servers as an unlimited production backend. Their
policies require attribution and caching and prohibit bulk downloading. Tile
hosting must remain replaceable configuration.

## Technical Sequence

1. Add single-party polygon and circle presentation modes.
2. Add the two-party comparison mode.
3. Add a replaceable basemap/source abstraction without changing result IDs.
4. Add neutral/OSM/satellite selection, overlay opacity, and close-zoom 3D.
5. Run desktop/mobile, Hebrew/English, keyboard, performance, attribution, and
   result-click regression tests for every stage.

## Reference Policies And Capabilities

- OpenStreetMap raster tile policy:
  https://operations.osmfoundation.org/policies/tiles/
- OpenStreetMap vector tile policy:
  https://operations.osmfoundation.org/policies/vector/
- OpenFreeMap MapLibre quick start:
  https://openfreemap.org/quick_start/
- MapLibre layer/style specification, including raster and fill extrusion:
  https://maplibre.org/maplibre-style-spec/layers/
- Esri attribution requirements:
  https://developers.arcgis.com/documentation/glossary/data-attribution/
