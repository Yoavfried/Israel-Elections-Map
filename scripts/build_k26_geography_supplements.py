"""Add only newly needed, exact-ID CBS 2022 areas from the 2025 publication.

Existing geometries are never replaced. New locality footprints are active in K26
only; historical-election geometry and results remain unchanged.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".local" / "python-geo"))

import geopandas as gpd
import pandas as pd

from build_geographies import build_localities, metadata_from_stats
from pipeline_common import PROCESSED_DIR, RAW_DIR, write_csv, write_json

OUT = PROCESSED_DIR / "geographies"


def append_features(path: Path, frame: gpd.GeoDataFrame, id_field: str) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    existing = {feature["properties"][id_field]: index for index, feature in enumerate(payload["features"])}
    additions = json.loads(frame.to_json(drop_id=True))["features"]
    for feature in additions:
        key = feature["properties"][id_field]
        if key not in existing:
            payload["features"].append(feature)
        else:
            payload["features"][existing[key]] = feature
    write_json(path, payload)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    source_dir = RAW_DIR / "k26" / "geography"
    packages = list(source_dir.rglob("*.gdb"))
    if len(packages) != 1:
        raise ValueError("Expected one extracted CBS 2025 FileGDB for K26 supplements")
    localities_path = OUT / "localities_2022.metadata.csv"
    localities = pd.read_csv(localities_path, dtype=str).fillna("")
    ballots = pd.read_csv(RAW_DIR / "k26" / "localities.csv", dtype=str).fillna("")
    owned = localities[localities.display_geometry_source == "official_cbs_2025_publication_stat22_supplement"]
    needed = (set(ballots["סמל ישוב"]) - set(localities.locality_code) - {"0"}) | set(owned.locality_code)
    # Military/non-geographic and tribal rows retain their reviewed custom rules.
    source = gpd.read_file(packages[0], engine="pyogrio")
    source = source[source.SEMEL_YISHUV.astype(str).isin(needed)].copy()
    if source.empty:
        print("K26 CBS supplements already present")
        return
    source = source.rename(columns={
        "SEMEL_YISHUV": "locality_code", "SHEM_YISHUV": "locality_name_he",
        "SHEM_YISHUV_ENGLISH": "locality_name_en", "STAT22": "stat_2022",
        "YISHUV_STAT22": "yishuv_stat_2022", "Main_Function_Code": "COD_TIFKUD",
    })
    source["locality_name_en"] = source.locality_name_en.fillna("")
    source["locality_id"] = source.locality_code.map(lambda value: f"loc:{value}")
    source["stat_area_id"] = source.yishuv_stat_2022.map(lambda value: f"stat2022:{value}")
    source["geometry"] = source.geometry.make_valid()
    source["display_mode"] = source.geometry.area.map(lambda value: "marker" if value < 20_000 else "polygon")
    footprints = build_localities(source).to_crs(4326)
    source = source.to_crs(4326)
    source["display_geometry_source"] = "official_cbs_2025_publication_stat22_supplement"
    footprints["display_geometry_source"] = source["display_geometry_source"].iloc[0]
    footprints["active_elections"] = "K26"
    footprints["display_mode"] = footprints.to_crs(2039).geometry.area.map(lambda value: "marker" if value < 20_000 else "polygon")
    stats_path = OUT / "statistical_areas_2022.metadata.csv"
    stats = pd.read_csv(stats_path, dtype=str).fillna("")
    added_stats = pd.DataFrame(metadata_from_stats(source))
    stats = stats[~stats.stat_area_id.isin(added_stats.stat_area_id)]
    pd.concat([stats, added_stats], ignore_index=True).to_csv(stats_path, index=False, encoding="utf-8-sig")
    for suffix in (".geojson", ".simplified.geojson", ".display.simplified.geojson"):
        area_frame, locality_frame = source.copy(), footprints.copy()
        if suffix == ".display.simplified.geojson":
            composites = json.loads((OUT / "composite_localities.simplified.geojson").read_text(encoding="utf-8"))
            shaar = next(feature for feature in composites["features"] if feature["properties"]["composite_locality_id"] == "composite:shaar-shomron")
            from shapely.geometry import shape
            for frame in (area_frame, locality_frame):
                selected = frame.locality_code == 3826
                frame.loc[selected, "geometry"] = gpd.GeoSeries([shape(shaar["geometry"])], index=frame.index[selected], crs=4326)
                frame.loc[selected, "display_mode"] = "polygon"
            locality_frame["component_locality_ids"] = ""
            locality_frame.loc[locality_frame.locality_code == 3826, "component_locality_ids"] = "loc:3720|loc:3778"
        append_features(OUT / f"statistical_areas_2022{suffix}", area_frame, "stat_area_id")
        append_features(OUT / f"localities_2022_dissolved{suffix}", locality_frame, "locality_id")
    rows = []
    for _, row in footprints.iterrows():
        min_x, min_y, max_x, max_y = row.geometry.bounds
        rows.append({
            "locality_id": row.locality_id, "locality_code": row.locality_code,
            "locality_name_he": row.locality_name_he, "locality_name_en": row.locality_name_en,
            "stat_area_count": row.stat_area_count, "single_stat_area": row.single_stat_area,
            "stat_area_ids": row.stat_area_id, "stat_2022_values": row.stat_2022,
            "yishuv_stat_2022_values": row.yishuv_stat_2022,
            "cod_tifkud_values": row.COD_TIFKUD, "has_function_code": row.has_function_code,
            "display_geometry_source": row.display_geometry_source,
            "min_lon": min_x, "min_lat": min_y, "max_lon": max_x, "max_lat": max_y,
        })
    localities = localities[~localities.locality_id.isin(footprints.locality_id)]
    pd.concat([localities, pd.DataFrame(rows)], ignore_index=True).to_csv(localities_path, index=False, encoding="utf-8-sig")
    write_csv(OUT / "k26_geography_supplements.csv", rows, list(rows[0]))
    print(f"K26 exact-ID CBS supplements: {len(source)} areas, {len(rows)} localities")


if __name__ == "__main__":
    main()
