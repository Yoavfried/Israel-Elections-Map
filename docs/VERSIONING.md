# Release Versioning

Data releases and website releases are separate products and use independent
version numbers. A website update does not change the public-data version, and
a corrected data release does not require a website release.

## Public Data

Public-data versions have exactly two numeric levels: `major.minor`.

- `v1.1`, `v1.2`, and later minor releases correct values, provenance,
  geometry, validation output, or documentation without changing the table
  columns, join contract, file organization, or included elections.
- `v2.0` and later major releases are used when columns or their meaning
  change, an election is added, join identifiers or file organization change,
  or another substantial expansion changes the data contract.
- There is no patch-level public-data version.

The current major line remains in `public-data/v1/` so download links stay
simple. Exact published snapshots should be identified with Git tags or GitHub
releases such as `data-v1.1`; a tagged snapshot is never silently rewritten.
The manifest's `schema_version` is a machine-format marker and is not the
public release number.

Data users do not need to recreate the pipeline. The committed CSV, ZIP,
metadata, manifest, checksum, and validation files are the supported public
distribution.

## Website

The website uses the independent version in `web/app/package.json` and normal
three-part semantic versioning:

- patch: website bug fixes with no intended feature change;
- minor: new or materially changed product features and UX;
- major: an incompatible product contract or major public relaunch.

Website versions cover the protected application, including its design,
colors, map presentation, interaction modes, and frontend code. They do not
version or relicense the downloadable data.
