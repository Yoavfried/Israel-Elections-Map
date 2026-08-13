# Israel Election Map Web App

Local-first React/TypeScript client for the K17-K25 pipeline. Primary top-bar
views expose the geographic map, a single-party vote-share map, and complete
national results, plus two-party comparison and coalition-results maps. The
app does not read working CSV files at runtime. A build-time compiler validates
them and writes disposable web assets under `public/data/v2/`.

Geographic views use an OSM-derived OpenFreeMap vector background by default.
The map selector can switch to the original neutral background, and the choice
is persisted with the other display preferences. Set
`VITE_VECTOR_BASEMAP_STYLE_URL` at build time to replace the default
`https://tiles.openfreemap.org/styles/positron` style without changing the
election layers or result IDs. Hebrew and Arabic vector labels use the pinned,
locally served MapLibre RTL text plugin; `VITE_RTL_TEXT_PLUGIN_URL` can replace
that asset URL for a downstream build.

Exact numbered-address lookup uses Photon at
`https://photon.komoot.io/api/` by default. Set `VITE_ADDRESS_GEOCODER_URL` to a
compatible self-hosted or contracted endpoint for production-scale use. The
service supplies coordinates only; the browser resolves each point locally
against the selected election's statistical geometry.

The vector presentation uses a dedicated CBS/OSM-derived Israel and
full-West-Bank land footprint. Land outside it, including Gaza and neighboring
countries, is painted with the style's water color, and vector labels are
restricted to the footprint. West Bank roads, buildings, place names, and
administrative detail remain visible. The same footprint supplies an outer
boundary in the neutral map, including the Jordan Valley edge. Maritime
administrative extensions and northern Ghajar are excluded from this
presentation geometry.

The portrait-mobile interface is map-first: it moves modes and selectors into
a compact header menu, keeps map controls available, raises search above the
on-screen keyboard, and presents closable result sheets with a fixed result
title and scrollable detail body. Landscape-phone support is outside the
current scope.

## Run Locally

Prerequisites:

- Node.js 20.19 or newer.
- Generated pipeline outputs under `../../data/processed/`.

```powershell
npm install
npm run dev
```

`npm run dev` rebuilds the web data and starts Vite on `http://localhost:4173`.

Useful commands:

```powershell
npm run data:build
npm test
npm run check
npm run build
```

To compile from another processed-data directory:

```powershell
npm run data:build -- --source C:\path\to\data\processed
```

## Build-Time Inputs

- `scripts/build-data.mjs` reads promoted outputs under `data/processed/` plus
  reviewed party, threshold, mandate, and display metadata under `data/manual/`
  and `web/app/config/`.
- Generated web assets are ignored by Git.
- The compiler writes to a staging directory and replaces only `web/app/public/data/v2/` after a successful build.
- The web build does not modify pipeline scripts or review files.

## Coverage Boundary

The compiler reads promoted public assignment outputs. Locality mode covers the complete K17-K25 geographic scope and includes reviewed election-specific composite municipalities and joined-register unions. Official envelope results appear as a separate selectable national aggregate.

Statistical mode uses official ballot-to-area crosswalks and election-specific
historical geometry: 1995 for K17, 2008 for K18, and 2011 for K19-K25. Result
payloads disclose mapped-voter coverage and preserve pending rows instead of
inferring their polygons.

Party/list metadata and presentation configuration are compiled into the map
separately from the downloadable public-data release.

The national-results view publishes every positive-vote list for the selected election,
including official votes, vote share, the applicable threshold, final
mandates, color-review state, and separate Hebrew/English Wikipedia controls.
Missing article links remain visibly disabled where the completed review found
no appropriate article.

The map includes an offline, election-aware bilingual search across localities,
statistical areas, historical names, reviewed aliases, and geography codes.
Selecting a match changes geography mode when needed, fits and highlights its
geometry, and opens either its result or an explicit no-result state.
Address-like queries containing a house number additionally trigger a
debounced network lookup. Only results confirming that house number are shown.
Each option contains the address and the election-specific statistical area;
selection opens that area and places a marker at the returned coordinate.

The single-party view reuses the same election-specific geography and result
details. It colors every result-bearing polygon on a continuous scale from zero
to the 95th percentile of positive vote shares for the selected list. Higher
outliers use the full party color, while a quadratic white-to-color ramp keeps
low relative shares pale and geography without a result retains a separate
neutral state. A second display option replaces those fills with circles: color
continues to represent vote share, circle area represents absolute votes, and
the 99th percentile of each area's leading-party vote total caps one smaller,
party-independent size scale. Positive circles receive a minimum visible party
tint so low-share results do not become large white discs. Every circle retains
the same result ID and complete click-through detail.

The two-party comparison view uses each selected party's share of their
combined local vote. A 50/50 result is white, either endpoint uses that party's
reviewed color, and separate neutral colors distinguish no votes for either
party from geography with no result. Selecting an area retains the complete
result and emphasizes both selected lists.

The coalition view uses a reviewed fixed member list for every election. It
maps the members' combined local vote share from white to the nationally
largest member's reviewed color, with the positive-share 95th percentile as
the full-color ceiling. K21 and K22 show the outgoing transitional coalition
because neither Knesset formed a government. Joint ballots in K21-K23 are
marked when only some component factions were represented in the outgoing or
first government. K23 excludes Yamina because only one member joined; the
Labor-Gesher-Meretz ballot remains included with a short member-level caveat.
Selecting an area shows the coalition total and emphasizes every included list.

The vector basemap is presentation context only. Buildings, roads, boundaries,
and localized labels render above translucent election fills; labels also sit
above election outlines, while markers remain in the top layer. Feature state,
selection, and hit testing remain attached to the election geometry.
Provider attribution is supplied through MapLibre whenever a remote background
is active. OSM attribution for the committed context boundary remains visible
in neutral mode too. If a remote style cannot load promptly, the client returns
to the neutral map rather than blocking the election results.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the data contract and
[`../../docs/PROJECT_STATUS.md`](../../docs/PROJECT_STATUS.md) for the sole
project completion tracker.

## License

The web application source, visual design, interaction design, copy, map
presentation, and presentation configuration are source-visible but all rights
reserved under [`../../LICENSE-WEBSITE`](../../LICENSE-WEBSITE). The separately
published data release is governed by the MIT Data License described in the
repository root.
