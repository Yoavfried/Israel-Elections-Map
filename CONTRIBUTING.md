# Contributing

Contributions should preserve source provenance and avoid inventing geographic precision.

## Setup

1. Install Python dependencies from `requirements.txt` and Node.js 20.19 or newer.
2. Prepare ignored raw inputs as documented in `docs/DATA_SOURCES.md` and `data/README.md`.
3. Run `python scripts/run_pipeline.py` or reuse existing geography with `--skip-geographies`.
4. Run `npm install` in `web/app/` and use `npm run check` before submitting changes.

## Data Changes

- Put reviewed corrections and overrides in `data/manual/`, with source evidence in the row notes or relevant methodology document.
- Do not edit generated files in `data/processed/` or `web/app/public/data/` by hand.
- Do not edit `public-data/v1` by hand. Change the source pipeline or release
  builder, regenerate it, and review the manifest and validation report.
- Do not infer voter geography without election-specific assignment evidence.
- Label every approved inferred link with a distinct row-level method/source;
  never present it as an official crosswalk assignment.
- Do not replace official totals with derivative ArcGIS values.
- Keep assignment geometry and display-only geometry provenance separate.

## Public Repository Hygiene

- Do not commit credentials, API tokens, private contact data, machine-specific
  paths, raw downloads, uncurated generated data, logs, or files under `work/`.
  The versioned `public-data/` release is the intentional generated-data
  exception.
- Use environment variables for optional service credentials. Commit only documented example configuration with placeholder values.
- Keep documentation factual and source-oriented. Avoid private deployment domains or notes that depend on one contributor's machine.

## Change Checks

- Data pipeline changes should run the affected Python stage and its downstream reconciliation checks.
- Public-data changes should run `python scripts/build_public_data_release.py`
  and verify `public-data/v1/validation.json` plus the manifest checksums.
- Frontend or compiler changes should pass `npm run check` in `web/app/`.
- User-facing map changes should be checked in Hebrew and English and at desktop and mobile widths.
- Update `docs/PROJECT_STATUS.md` only when a workstream's actual completion state changes.

## Contribution Licensing

- Contributions to `public-data/` or `data/manual/` are submitted under the
  MIT Data License in `LICENSE-DATA`.
- Contributions elsewhere are submitted for inclusion in the protected
  project. By submitting such a contribution, you grant Yoav Fried a
  perpetual, worldwide, royalty-free right to use, reproduce, modify,
  distribute, sublicense, and publish that contribution as part of this
  project under `LICENSE-WEBSITE`. You retain copyright in your contribution.
- Official and third-party data remain subject to the source terms described
  in `THIRD_PARTY_NOTICES.md`.

Do not submit material that you do not have the right to contribute under the
applicable terms.
