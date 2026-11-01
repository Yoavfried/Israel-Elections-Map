"""Snap web-only shapes safely and carve newer locality footprints from backgrounds.

Canonical downloadable geography and ballot assignments are never changed.
Smaller 2022 footprints keep their shape; overlapping larger display shapes make
space for them. Historical precision repair is topology-preserving; current
coverage cutouts retain exact intersection coordinates through web export.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".local" / "python-geo"))

from pyproj import Transformer
from shapely import STRtree, difference, make_valid, set_precision, union_all
from shapely.geometry import Polygon, mapping, shape
from shapely.ops import transform

GRID = 0.000001
CUTOUT_CLEARANCE = 0.00000001  # About one millimetre; avoids coincident-edge roundoff.
GEOGRAPHIES = ROOT / "data/processed/geographies"


def polygonal(geometry):
    if geometry.geom_type in {"Polygon", "MultiPolygon"}:
        return geometry
    return union_all([polygonal(part) for part in getattr(geometry, "geoms", [])]) if hasattr(geometry, "geoms") else Polygon()


def sanitize_geometry(geometry):
    result = set_precision(polygonal(make_valid(geometry)), GRID, mode="valid_output")
    if result.is_empty or not result.is_valid:
        raise ValueError("Web geometry precision repair removed or invalidated a polygon")
    return result


def carve_overlaps(geometries, ids):
    project = Transformer.from_crs(4326, 2039, always_xy=True).transform
    sizes = [transform(project, geometry).area for geometry in geometries]
    tree = STRtree(geometries)
    processed = set()
    output = list(geometries)
    changes = []
    for i in sorted(range(len(geometries)), key=lambda index: (sizes[index], ids[index])):
        blockers = [output[int(j)] for j in tree.query(geometries[i], predicate="intersects") if int(j) in processed and geometries[i].intersection(output[int(j)]).area > 0]
        if blockers:
            candidate = polygonal(difference(geometries[i], union_all(blockers).buffer(CUTOUT_CLEARANCE)))
            if candidate.is_empty:
                raise ValueError(f"Overlap cleanup would erase {ids[i]}; explicit ownership review required")
            candidate = polygonal(make_valid(candidate))
            removed = sizes[i] - transform(project, candidate).area
            if removed > 0.01:
                changes.append({"id": ids[i], "removed_overlap_m2": round(removed, 3)})
            output[i] = candidate
        processed.add(i)
    return output, changes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-only", action="store_true")
    args = parser.parse_args()
    paths = [
        *[GEOGRAPHIES / f"statistical_areas_{vintage}.display.simplified.geojson" for vintage in (1995, 2008, 2011, 2022)],
        *[GEOGRAPHIES / name for name in (
            "localities_2022_dissolved.display.simplified.geojson",
            "historical_composite_component_display_geometries.geojson",
            "historical_locality_fallback_display_geometries.geojson",
            "statistical_area_result_aggregates.geojson",
            "statistical_area_polling_group_displays.geojson",
        )],
    ]
    summary = []
    for path in paths:
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        current_shapes = path.name in {"statistical_areas_2022.display.simplified.geojson", "localities_2022_dissolved.display.simplified.geojson"}
        geometries = [
            polygonal(make_valid(shape(feature["geometry"])))
            if current_shapes or feature["properties"].get("elections") == "K26"
            else sanitize_geometry(shape(feature["geometry"]))
            for feature in payload["features"]
        ]
        changes = []
        if path.name in {"statistical_areas_2022.display.simplified.geojson", "localities_2022_dissolved.display.simplified.geojson"}:
            field = "stat_area_id" if path.name.startswith("statistical") else "locality_id"
            ids = [str(feature["properties"][field]) for feature in payload["features"]]
            # These predecessor polygons are intentionally hidden in K26, whose
            # Shaar Shomron polygon already contains both component footprints.
            positions = [i for i, feature in enumerate(payload["features"]) if str(feature["properties"].get("locality_code")) not in {"3720", "3778"}]
            cleaned, changes = carve_overlaps([geometries[i] for i in positions], [ids[i] for i in positions])
            for index, geometry in zip(positions, cleaned):
                geometries[index] = geometry
        for feature, geometry in zip(payload["features"], geometries):
            feature["geometry"] = mapping(geometry)
        path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        summary.append({"file": path.name, "valid_shapes": len(geometries), "cutouts": changes})
    fallback_path = GEOGRAPHIES / "historical_locality_fallback_display_geometries.geojson"
    fallback_payload = json.loads(fallback_path.read_text(encoding="utf-8"))
    fallback_payload["features"] = [feature for feature in fallback_payload["features"] if feature["properties"].get("stat_area_vintage") != 2022]
    stats = json.loads((GEOGRAPHIES / "statistical_areas_2022.display.simplified.geojson").read_text(encoding="utf-8"))["features"]
    fallback_rows_path = ROOT / "data/processed/public/municipality_display_fallbacks/k26.csv"
    if fallback_rows_path.exists():
        with fallback_rows_path.open(encoding="utf-8-sig", newline="") as handle:
            fallbacks = list(csv.DictReader(handle))
        import pyogrio
        fallback_codes = {int(row["locality_code"]) for row in fallbacks}
        full_frame = pyogrio.read_dataframe(
            GEOGRAPHIES / "statistical_areas_2022.display.geojson",
            columns=["locality_code"],
            where="locality_code IN (" + ",".join(map(str, sorted(fallback_codes))) + ")",
        )
        full_by_code = {int(code): group.geometry.union_all().simplify(0.00005, preserve_topology=True) for code, group in full_frame.groupby("locality_code")}
        for row in fallbacks:
            components = [feature for feature in stats if str(feature["properties"].get("locality_code")) == row["locality_code"]]
            if not components:
                raise ValueError(f"K26 fallback lacks statistical coverage: {row['locality_code']}")
            geometry = full_by_code.get(int(row["locality_code"]))
            if geometry is None:
                geometry = union_all([shape(feature["geometry"]) for feature in components])
            if not geometry.is_valid:
                raise ValueError(f"Invalid K26 statistical fallback union: {row['locality_code']}")
            fallback_payload["features"].append({
                "type": "Feature",
                "properties": {"fallback_geography_id": row["fallback_geography_id"], "stat_area_vintage": 2022, "elections": "K26", "boundary_source": "current_statistical_display_union"},
                "geometry": mapping(geometry),
            })
        fallback_path.write_text(json.dumps(fallback_payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    group_path = GEOGRAPHIES / "statistical_area_polling_group_displays.geojson"
    if not args.base_only and group_path.exists() and fallback_rows_path.exists():
        group_payload = json.loads(group_path.read_text(encoding="utf-8"))
        current_groups = [feature for feature in group_payload["features"] if feature["properties"].get("elections") == "K26"]
        owned = {area for feature in current_groups for area in feature["properties"]["component_stat_area_ids"].split("|")}
        fallback_codes = {row["locality_code"] for row in fallbacks}
        from geography_display_helpers import is_point_proxy
        project = Transformer.from_crs(4326, 2039, always_xy=True).transform
        plain = []
        for feature in stats:
            p = feature["properties"]
            code = int(p["locality_code"])
            if p["stat_area_id"] in owned or str(code) in fallback_codes or code in {3720, 3778, 9920}:
                continue
            if (3500 <= code < 4000 or code in {1791, 1792, 1793, 1794, 3488, 9400}) and is_point_proxy(transform(project, shape(feature["geometry"]))):
                continue
            plain.append(feature)
        current_fallbacks = [feature for feature in fallback_payload["features"] if feature["properties"].get("stat_area_vintage") == 2022]
        active = plain + current_groups + current_fallbacks
        ids = [str(feature["properties"].get("stat_area_id") or feature["properties"].get("custom_id") or feature["properties"]["fallback_geography_id"]) for feature in active]
        cleaned, changes = carve_overlaps([shape(feature["geometry"]) for feature in active], ids)
        for feature, geometry in zip(active, cleaned):
            feature["geometry"] = mapping(geometry)
        # Write only presentation layers; result rows and ownership IDs stay intact.
        for path, payload in (
            (GEOGRAPHIES / "statistical_areas_2022.display.simplified.geojson", {"type": "FeatureCollection", "features": stats}),
            (group_path, group_payload),
            (fallback_path, fallback_payload),
        ):
            path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        summary.append({"file": "K26-final-display-partition", "valid_shapes": len(active), "cutouts": changes})
    output = ROOT / "data/processed/audits/map_display_geometry_cleanup.json"
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps([{**row, "cutouts": len(row["cutouts"])} for row in summary], indent=2))


if __name__ == "__main__":
    main()
