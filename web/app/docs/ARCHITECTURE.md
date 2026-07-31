# Frontend architecture and implementation plan

## Product boundary

The first product is a static, local-first web application. It reads versioned
assets generated from the existing Python pipeline and does not own election
ingestion, assignment, or aggregation.

The web app supports:

- K17–K25 election selection.
- A primary national-results view with every positive-vote list, final votes, threshold,
  mandates, colors, and Wikipedia controls.
- Election-specific historical statistical-area mode and dissolved-2022-locality mode.
- English and Hebrew, including document-level LTR/RTL switching.
- Desktop and mobile layouts.
- Explicit mapped/unmapped vote coverage.
- Custom reviewed geographic buckets when they have results in an election.
- Display-only whole-locality totals when an election/locality has zero
  supported statistical-area assignments.
- Election-specific historical composite municipalities and joined polling-register unions in locality mode.
- Official envelope results as a selectable national, non-map result.

“Locality” is the contract term rather than “municipality”: the dissolved CBS layer contains localities, not only incorporated municipalities.

## Data flow

```text
data/processed CSV + GeoJSON
reviewed data/manual election + party metadata
            |
            v
scripts/build-data.mjs
  - validates IDs and numeric fields
  - joins bilingual geography metadata
  - prunes GeoJSON properties
  - attaches stable feature IDs
  - merges mode-tagged custom geography results
  - applies election-specific composite visibility and joined-host result aliases
  - applies reviewed historical locality names and no-result visibility
  - substitutes documented whole-locality fallbacks for entirely unassigned localities
  - attaches envelope aggregates
  - validates national votes, election thresholds, and final mandate totals
  - emits mode-specific coverage and provenance
            |
            v
public/data/v2/
  catalog.json
  geographies/*.geojson
  results/<election>/*.json
            |
            v
Zod-validated browser data client
            |
            v
MapLibre feature state + React detail panels
```

The browser loads the catalog first, then only the selected election/mode result file. Each election carries `geographiesByMode`, so statistical geometry changes with the election: K17 loads 1995, K18 loads 2008, and K19-K25 load 2011. Locality mode uses dissolved 2022 geometry. Statistical assets also declare a simplified, non-interactive 2022 land backdrop; MapLibre paints it neutral grey below the historical result polygons so changing vintage does not turn uncovered Israeli land into background. For a locality with zero supported area assignments, the compiler adds a display-only current locality or reviewed composite footprint to the historical asset, hides its empty statistical components only in that election, and attaches the locality aggregate. The compiler removes source-only fields and rounds web coordinates to six decimal places. Each geography asset also has marker GeoJSON for marker-capable custom buckets and point-like proxies. The marker layer filters that asset to exact IDs present in the selected result payload, while reviewed detailed settlement and custom footprints remain polygonal.

Locality geometry retains CBS no-jurisdiction and regional-council display footprints even when they have no election result. MapLibre renders these features with the neutral unmapped fill and does not make them selectable. Both the statistical-area and locality IDs for Kinneret are filtered from polygon rendering, leaving water and non-polygon background areas unfilled.

## Versioned Contracts

`catalog.json` schema version 4 is the discovery and provenance document. Map
result payloads remain schema version 2; national result payloads use schema
version 1. The catalog contains:

- `schemaVersion` and content-derived `buildId`.
- Election labels, map and national result URLs, `statisticalAreaVintage`, and mode-specific geography assets.
- Geography labels, feature counts, geometry URLs, and Israel bounds.
- Per-election, per-mode mapped, pending, and unmapped vote coverage.
- SHA-256 and byte length for generated assets.
- Party-color review status, including support for future provisional entries.

Each result asset contains:

- Election and geography identity.
- Coverage repeated at the asset boundary.
- Party/ballot-letter definitions with bilingual labels and color-review status.
- Geography records with totals, nullable turnout, winner/margin, dynamic ballot-letter vote columns converted into `partyVotes`, and an optional bilingual notice. A null turnout means the source has no eligible-voter denominator. K17 ordinary geography records now use the recovered ballot-level denominator; its envelope result remains null because no geographic envelope register is published.
- One optional envelope record combining official envelope rows and reviewed `special:envelope_votes` rows; it uses the same validated party-vote contract but has no map feature.
- `hiddenGeographyIds`, used both to replace component localities with an active composite and to suppress reviewed no-result 2022 features in the relevant election. For a joined polling register, the compiler aliases the one published host result to the union before hiding its components.

Each national result asset contains every published list in vote order, its
official votes and share, threshold status, final mandate count, color status,
and Hebrew/English Wikipedia candidates. Election-level fields include valid
votes, the legal threshold share and minimum vote count, represented-list and
candidate-list counts, and official source URLs. The compiler requires every
election's mandates to sum to 120 and rejects threshold/mandate contradictions.

The compiler recomputes winner/share fields from party totals and requires their sum to equal `valid_votes`. Documented exclusions remove all 12 zero-filled columns for lists that did not run between K18 and K24 from both map and national-result payloads. The rows remain in the source registry for auditability, and an undeclared zero-vote registry row fails the build. The trailing K18 `ת. עדכון` source-metadata field is also excluded, separately from the party registry. All exclusions are surfaced in `catalog.json`; undeclared mismatches fail the build.

Stable feature IDs are the join boundary:

- `stat1995:<combined-code>`, `stat2008:<combined-code>`, `stat2011:<combined-code>`, or `stat2022:<combined-code>` for statistical areas.
- `loc:<SEMEL_YISHUV>` for localities.
- `composite:<key>` for reviewed election-specific historical municipalities and joined-result display unions.
- `custom:<key>` for reviewed synthetic geographies.
- `municipality-fallback:<vintage>:<locality-id>` for a display-only
  whole-locality result in statistical mode.
- `envelope:official` for the separate national envelope result; this ID intentionally has no geometry.

The browser validates every catalog, map-result, and national-result payload
before rendering it.

## Party registry

Ballot letters are not stable party identities across elections. `data/manual/party_registry.csv` therefore keys all 309 source columns by election plus source result column and stores the official ballot code, full Hebrew list name, concise display names, national vote total, source provenance, and Hebrew/English Wikipedia URL candidates separately. Published payloads contain 297 actual lists after the 12 documented K18-K24 non-runner exclusions.

The compiler requires exact registry/result-column coverage except for explicitly declared exclusions. It reconciles every published party's registry national total against locality, custom, and envelope output before publishing. Map payloads expose the full Hebrew list name and optional Wikipedia URLs. The national view presents separate Hebrew and English controls and visibly disables missing candidates.

Registry coverage and metadata review are different completion states. Coverage of all 309 source columns and review of the K17-K25 published display names are complete; English presentation falls back to the reviewed Hebrew name where no separate label is maintained. Wikipedia links remain a working snapshot, and populated-link counts must not be presented as proof that every match or every blank has been editorially resolved. A generated-data regression check requires link-presence continuity when the same reviewed identity appears in multiple elections. Explicit reviewed exceptions cover identical short labels used by different slates, such as `כח להשפיע`; similarly named but distinct lists are not propagated automatically.

Color precedence is election-specific source-column override, then reviewed official-ballot-letter default, then a deterministic fallback keyed only by official ballot letter. This keeps a letter visually stable across elections while allowing explicit exceptions in `config/party-overrides.json`. All 297 published K17-K25 lists now have reviewed colors, and recurring identities retain their reviewed color through later elections even when their ballot letters change.

The deterministic placeholder mechanism remains available for future unreviewed additions, but no current K17-K25 published list uses it.

Cross-election lineage is intentionally not inferred. A shared ballot-letter color is a display convention and must not silently force one identity onto distinct lists that reused a letter.

## Geometry strategy

The compiler publishes separate pruned GeoJSON assets for 1995, 2008, 2011, and 2022 statistical areas plus current localities. `scripts/build_geographies.py` also dissolves the visible locality footprints into a compact land backdrop, excluding Kinneret, every detailed West Bank locality footprint, and unresolved tiny point proxies. Polygon-only normalization after simplification prevents stray geometry collections. Schema version 3 keeps the result contract stable while allowing an election to select its own geometry, marker, and optional backdrop URLs.

The migration boundary for production is intentionally narrow: replace each catalog `geometryUrl` with a PMTiles/vector-tile source and adapt only `MapCanvas`. Result contracts, controls, localization, feature IDs, and panels remain unchanged.

Move to tiles before public launch if any of these remain true after compression and hosting tests:

- Statistical-area geometry transfer is above roughly 3–5 MB compressed.
- Mobile parsing or first interaction is visibly delayed.
- Lower-end mobile devices show memory pressure.

## Responsive and bilingual behavior

- CSS uses logical properties so the layout mirrors under RTL.
- The header and controls remain reachable above the map.
- Desktop uses floating side panels; mobile uses a full-width stacked control and result rail over the map.
- The national comparison table reflows into labeled two-column party rows on
  narrow screens rather than requiring horizontal scrolling.
- Language, election, and geography preferences are stored in one versioned, minimal local-storage record.
- Number and percent formatting use `he-IL` or `en-IL`.

## Coverage and integrity rules

- A polygon without mapped results remains visible but muted.
- The UI never interprets an absent polygon result as zero votes.
- A locality with no supported area assignment can be colored only through a
  `municipality-fallback` record. The details-panel info icon states that the
  whole-locality result and boundary are display-only; coverage and ballot
  assignments remain unchanged.
- Mapped coverage remains available in generated map metadata. The removed
  map-wide coverage bubble is not treated as assignment evidence; uncertainty
  is disclosed on affected geographic results.
- Coverage is mode-specific: locality result-row coverage is complete;
  historical statistical coverage ranges from 93.06% to 95.47% by election.
  The partial-presence locality audit remains open.
- Envelope votes are excluded from polygon coverage and remain visible through the separate national result control.
- Active composite localities hide their 2022 component features; inactive composites are hidden. A joined-register union replaces exactly one published host result and is rejected if another union claims that host or an attached component has a standalone result. Its visible title/code remain the host's, and attached polygon names are exposed separately through the details-panel info tooltip. Other hidden-result conflicts remain fatal.
- `data/manual/locality_display_overrides.csv` can preserve an election-time name on 2022 geometry or hide a reviewed feature that has no standalone result. The geometry remains canonical and the same hidden-result rejection applies. `data/manual/statistical_area_display_overrides.csv` independently hides reviewed election-vintage display proxies, including standalone Ganei Modi'in in K19/K20 and the evacuated Gaza features in K17, without changing assignment geometry.
- Custom geometries remain in the canonical geometry asset but are filtered out of rendering and hit-testing unless the selected result asset contains their ID.
- Custom result aggregates are tagged by geography mode. A row can therefore use a real historical statistical polygon while retaining its reviewed custom grouping in locality mode without being omitted or counted twice.
- Marker-capable custom buckets and point-like proxies render as fixed-size markers only when their exact ID has a selected-election result. Multi-part proxy results use `MultiPoint`. The K17/K18 Hebron custom target and Ganei Modi'in from K21 use audited detailed polygons. Tribal results use one combined marker in every election. For K19-K25 the compiler replaces the exact tribal map records with the verified custom aggregate and hides the component features; it fails if any additive total or party column differs. This changes presentation only, while public ballot and statistical-area tables retain the exact component IDs.
- Compiler errors are fatal for missing metadata, duplicate result IDs, invalid numbers, or missing required output files.

## Project Tracking

This document defines the frontend architecture and invariants; it does not
track completion or roadmap state. The repository's sole completion tracker is
[`docs/PROJECT_STATUS.md`](../../../docs/PROJECT_STATUS.md).

## Architectural Non-goals

- No browser-side election ingestion or assignment logic.
- No server database or API.
- No claim that derivative ArcGIS display footprints are complete official CBS boundaries.
- No public basemap dependency or API key.
- No attempt to invent cross-election party lineage without an explicit reviewed lineage table.
