# Israel Election Map Web App

Local-first React/TypeScript client for the K17-K25 pipeline. Primary top-bar
views expose the geographic map and complete national results. The app does not
read working CSV files at runtime. A build-time compiler validates them and
writes disposable web assets under `public/data/v2/`.

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

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the data contract and
[`../../docs/PROJECT_STATUS.md`](../../docs/PROJECT_STATUS.md) for the sole
project completion tracker.

## License

The web application source, visual design, interaction design, copy, map
presentation, and presentation configuration are source-visible but all rights
reserved under [`../../LICENSE-WEBSITE`](../../LICENSE-WEBSITE). The separately
published data release is governed by the MIT Data License described in the
repository root.
