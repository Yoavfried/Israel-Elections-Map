from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from pipeline_common import PROCESSED_DIR, ROOT


STAGES = [
    ["scripts/fetch_election_results.py"],
    ["scripts/build_geographies.py"],
    ["scripts/build_historical_geographies.py"],
    ["scripts/build_k26_geography_supplements.py"],
    ["scripts/audit_k26_sources.py"],
    ["scripts/normalize_election_results.py"],
    ["scripts/build_k26_metadata.py"],
    ["scripts/build_assignment_plan.py"],
    ["scripts/build_historical_ballot_assignments.py"],
    ["scripts/audit_election_source_geography_fields.py"],
    ["scripts/audit_k23_cec_stat_area_assignments.py"],
    ["scripts/audit_arcgis_assignment_reconstruction.py"],
    ["scripts/audit_stable_ballot_assignments.py"],
    ["scripts/build_final_geography_assignments.py"],
    ["scripts/audit_historical_assignment_gaps.py"],
    ["scripts/build_public_outputs.py"],
    ["scripts/audit_statistical_area_polling_group_evidence.py"],
    ["scripts/audit_stable_ballot_site_safety.py"],
    ["scripts/build_statistical_area_polling_group_policy.py"],
    ["scripts/build_reviewed_locality_statistical_displays.py"],
    ["scripts/audit_joined_locality_continuity.py"],
    ["scripts/build_statistical_area_result_aggregates.py"],
    ["scripts/build_statistical_area_polling_group_displays.py"],
    ["scripts/audit_statistical_display_ownership.py"],
    ["scripts/audit_display_contributor_capacity.py"],
    ["scripts/review_display_contributor_capacity_flags.py"],
    ["scripts/build_public_data_release.py"],
]

GEOGRAPHY_OUTPUTS = [
    PROCESSED_DIR / "geographies" / "statistical_areas_2022.geojson",
    PROCESSED_DIR / "geographies" / "statistical_areas_2022.metadata.csv",
    PROCESSED_DIR / "geographies" / "localities_2022_dissolved.geojson",
    PROCESSED_DIR / "geographies" / "statistical_areas_2022.display.simplified.geojson",
    PROCESSED_DIR / "geographies" / "localities_2022_dissolved.display.simplified.geojson",
    PROCESSED_DIR / "geographies" / "composite_localities.simplified.geojson",
    PROCESSED_DIR / "geographies" / "statistical_areas_1995.geojson",
    PROCESSED_DIR / "geographies" / "statistical_areas_2008.geojson",
    PROCESSED_DIR / "geographies" / "statistical_areas_2011.geojson",
    PROCESSED_DIR / "geographies" / "statistical_areas_1995.display.simplified.geojson",
    PROCESSED_DIR / "geographies" / "statistical_areas_2008.display.simplified.geojson",
    PROCESSED_DIR / "geographies" / "statistical_areas_2011.display.simplified.geojson",
    PROCESSED_DIR / "geographies" / "statistical_areas_1995.metadata.csv",
    PROCESSED_DIR / "geographies" / "statistical_areas_2008.metadata.csv",
    PROCESSED_DIR / "geographies" / "statistical_areas_2011.metadata.csv",
    PROCESSED_DIR / "geographies" / "statistical_areas_1995.aliases.csv",
    PROCESSED_DIR / "geographies" / "statistical_areas_2008.aliases.csv",
    PROCESSED_DIR / "geographies" / "statistical_areas_2011.aliases.csv",
    PROCESSED_DIR
    / "geographies"
    / "historical_composite_component_display_geometries.geojson",
    PROCESSED_DIR
    / "geographies"
    / "historical_composite_component_display_geometries.metadata.csv",
    PROCESSED_DIR
    / "geographies"
    / "historical_locality_fallback_display_geometries.geojson",
    PROCESSED_DIR
    / "geographies"
    / "historical_locality_fallback_display_geometries.metadata.csv",
    PROCESSED_DIR / "geographies" / "statistical_area_result_aggregates.geojson",
    PROCESSED_DIR / "geographies" / "statistical_area_result_aggregates.metadata.csv",
    PROCESSED_DIR / "geographies" / "statistical_area_polling_group_displays.geojson",
    PROCESSED_DIR / "geographies" / "statistical_area_polling_group_displays.metadata.csv",
    PROCESSED_DIR / "public" / "statistical_area_polling_group_displays.csv",
]


def require_existing_geographies() -> None:
    missing = [path for path in GEOGRAPHY_OUTPUTS if not path.exists()]
    if not missing:
        return
    rendered = ", ".join(str(path.relative_to(ROOT)) for path in missing)
    raise SystemExit(
        "--skip-geographies requires existing generated geography files. "
        f"Missing: {rendered}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skip-geographies",
        action="store_true",
        help="Reuse existing generated geography files instead of running the GeoPandas stage.",
    )
    args = parser.parse_args()

    if args.skip_geographies:
        require_existing_geographies()
    for stage in STAGES:
        if args.skip_geographies and stage in (
            ["scripts/build_geographies.py"],
            ["scripts/build_historical_geographies.py"],
        ):
            print(f"\n==> {' '.join(stage)} (reusing existing outputs)", flush=True)
            continue
        print(f"\n==> {' '.join(stage)}", flush=True)
        subprocess.run([sys.executable, *stage], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
