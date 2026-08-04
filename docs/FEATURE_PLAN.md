# Product Feature Plan

Last updated: 2026-08-04

This document records the intended design and delivery order for future map
features. It is not a completion tracker. Actual complete/in-progress state is
maintained only in `docs/PROJECT_STATUS.md`.

## Delivery Order

Search and the Wikipedia-link audit are complete. Statistical assignment work
continues in parallel; closing a source gap never means forcing a ballot onto a
polygon.

Current priority is the map-first mobile rewrite plus continuing desktop UX,
accessibility, performance, and regression work. Satellite imagery and 3D
buildings are not planned product modes.

The national-results baseline is implemented as a primary top-bar view and
remains the reference surface for the completed party-name, color, and
Wikipedia-link tables. Future analysis modes should use the same primary
navigation rather than being added to the geographic-level selector.

Responsive bilingual UX, accessibility, and regression QA are requirements for
every item. The existing narrow-screen stack is only an interim compatibility
layout: because it does not preserve a useful map viewport, a complete mobile
rewrite is also a defined product task rather than completed responsive work.

## Planned Features

### Mobile Map Rewrite

Replace the current stacked narrow-screen shell with a map-first mobile
experience. The existing mobile CSS may remain useful for QA while this is
built, but it is not the target design and should not constrain the rewrite.

Required behavior:

- keep a useful portion of the interactive map visible in every core state;
- move controls and selected-area results into collapsible, sheet-based, or
  similarly space-efficient surfaces;
- preserve search, area selection, basemap switching, party modes, and full
  result access without permanent map occlusion;
- verify Hebrew and Arabic direction, touch targets, safe areas, keyboard
  access, and representative phone viewport screenshots before completion.

### 1. Geography And Address Search (Delivered Baseline)

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

Numbered-address lookup is also implemented in the same combobox. It uses a
debounced, bounded Photon request to obtain exact house coordinates, rejects
street/locality centroids that do not confirm the requested house number, and
then resolves the coordinate locally against the selected election's visible
statistical geometry. One suggestion block shows both the address and resolved
area. Selecting it switches to statistical mode, opens the area result, and
places an address marker. The geocoder endpoint is configurable; address lookup
requires network access and should use a self-hosted or contracted service at
production scale.

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

### 3. Single-Party Map Mode (Delivered Baseline)

One election-specific party/list can be selected. Polygon color is a
sequential gradient derived from that party's reviewed base color: stronger
color means a higher share of valid votes and weaker color means a lower share.

Implemented behavior:

- an election-specific selector that never carries a ballot-letter identity
  into another election;
- a numeric legend from zero to the 95th percentile of positive polygon vote
  shares in the selected election and geography mode; higher outliers use the
  full party color, while a quadratic white-to-color ramp keeps low relative
  shares visually close to white;
- selecting a polygon still opens the complete area result;
- zero, missing, and statistically unresolved results remain distinguishable.

The delivered display toggle also provides vote circles. Circle color uses the
same vote-share scale, circle area represents absolute votes, and the 99th
percentile of each area's leading-party vote total caps one shared,
party-independent size scale. A smaller maximum radius and a minimum visible
party tint prevent dense fields of oversized white circles.
Circles retain the result IDs and full click-through details of their source
areas.

### 4. Two-Party Comparison (Delivered Baseline)

Two election-specific parties define the ends of a diverging color scale. Each
polygon receives a mixed color based on each party's share of their combined
vote in that result.

Implemented behavior:

- both selected parties and their base colors remain visible in the controls
  and legend;
- the head-to-head metric has a white 50/50 midpoint and reaches either
  reviewed party color at its endpoint;
- selecting a polygon opens the complete result while visually emphasizing the
  two compared parties;
- ties, zero votes for both parties, and missing results have explicit neutral
  states.

### 5. Coalition Results (Delivered Baseline)

The coalition view uses a reviewed election-specific list of ballot IDs. It
shows the first coalition formed after each election, or the outgoing
transitional coalition when that Knesset did not form a government.

Implemented behavior:

- K21 and K22 are explicitly labeled as transitional-coalition results;
- the map sums all configured member lists and uses a white-to-color scale
  capped at the 95th percentile of positive coalition shares;
- the scale uses the reviewed color of the coalition member with the largest
  national vote total in that election;
- selecting a polygon shows a coalition total and emphasizes every coalition
  list in the complete result breakdown;
- K21-K23 disclose joint-list limitations wherever only some ballot components
  were represented in the outgoing or first government; K23 excludes Yamina
  and retains Labor-Gesher-Meretz with the reviewed member-level caveat.

### 6. OSM Vector Basemap (Delivered Baseline)

Geographic views now use OpenFreeMap's light OSM-derived vector style by
default, with the original neutral map retained in a persisted selector and
automatic style-load fallback.

Implemented behavior:

- streets, boundaries, buildings, POIs, and localized place/road labels;
- election fills beneath buildings, roads, boundaries, and labels, with labels
  above election outlines and markers retained in the top layer;
- a precise CBS/OSM-derived Israel and full-West-Bank land footprint that masks
  surrounding land and labels without hiding West Bank detail, excludes
  maritime extensions and northern Ghajar, and supplies the neutral map's
  Jordan Valley outer boundary;
- provider attribution visible whenever the vector background is active;
- a build-time `VITE_VECTOR_BASEMAP_STYLE_URL` override, leaving result IDs and
  election data independent of the tile host;
- repeated vector/neutral switching without losing the selected election,
  geography, analysis mode, or feature state.

Self-hosted regional PMTiles remain the stronger long-term control option.
Do not treat the community `tile.openstreetmap.org` or
`vector.openstreetmap.org` servers as an unlimited production backend.

## Technical Sequence

1. Preserve replaceable neutral/vector styles without changing result IDs.
2. Build the map-first mobile shell without constraining the desktop layout.
3. Continue Hebrew/English, keyboard, performance, attribution, and result-click
   regression tests for every stage.

## Reference Policies And Capabilities

- OpenStreetMap raster tile policy:
  https://operations.osmfoundation.org/policies/tiles/
- OpenStreetMap vector tile policy:
  https://operations.osmfoundation.org/policies/vector/
- OpenFreeMap MapLibre quick start:
  https://openfreemap.org/quick_start/
- MapLibre layer/style specification:
  https://maplibre.org/maplibre-style-spec/layers/
