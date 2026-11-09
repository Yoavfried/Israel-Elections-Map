from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

LOCAL_PYTHON = Path(__file__).resolve().parents[1] / ".local" / "python-geo"
if LOCAL_PYTHON.exists():
    sys.path.insert(0, str(LOCAL_PYTHON))

import geopandas as gpd
import pandas as pd
from pyproj import Transformer
from shapely import union_all
from shapely.geometry import GeometryCollection, MultiPolygon, Point, Polygon
from shapely.ops import transform

from pipeline_common import MANUAL_DIR, PROCESSED_DIR, RAW_DIR, ensure_dir, write_csv, write_json
from geography_display_helpers import (
    POINT_PROXY_MAX_AREA_M2,
    WEST_BANK_DETAIL_CODES,
    apply_detailed_display_geometries,
    load_arcgis_detail_by_locality,
)


GDB_PATH = RAW_DIR / "ezorim_statistiim_2022.gdb"
LAYER_NAME = "statistical_areas_2022"
OUT_DIR = PROCESSED_DIR / "geographies"
ARCGIS_DIR = RAW_DIR / "arcgis"
REVIEWED_WEST_BANK_DETAILS_PATH = (
    MANUAL_DIR / "west_bank_display_boundary_replacements.geojson"
)
COMPOSITE_LOCALITIES_PATH = MANUAL_DIR / "composite_localities.csv"
JOINED_LOCALITY_COMPOSITES_PATH = MANUAL_DIR / "joined_locality_composites.csv"
ELECTIONS = {f"K{number}" for number in range(17, 27)}
SPECIAL_POINT_PROXY_LOCALITY_CODES = {1791, 1792, 1793, 1794, 3488}

CUSTOM_GEOGRAPHIES = [
    {
        "custom_id": "custom:tribal_negev",
        "custom_key": "TRIBE",
        "name_he": "\u05e9\u05d1\u05d8\u05d9\u05dd / \u05e4\u05d6\u05d5\u05e8\u05d4 \u05d1\u05e0\u05d2\u05d1",
        "name_en": "Negev tribal/dispersed-settlement bucket",
        "geometry_kind": "reviewed_buffer",
        "lon": 34.93,
        "lat": 31.22,
        "radius_m": 3500,
        "display_mode": "marker",
        "geometry_source": "reviewed_synthetic_buffer",
        "note": "Synthetic point-size polygon for reviewed tribal/dispersed-settlement rows.",
    },
    {
        "custom_id": "custom:hebron",
        "custom_key": "HEBRON",
        "name_he": "\u05d7\u05d1\u05e8\u05d5\u05df",
        "name_en": "Hebron custom bucket",
        "geometry_kind": "arcgis_exact_id",
        "source_path": "elections2015_statistical_areas.geojson",
        "source_id_field": "YeshuvStat",
        "source_id": 34000001,
        "source_stat_area_id": "stat2011:34000001",
        "display_mode": "polygon",
        "geometry_source": "arcgis_systematics_elections2015_exact_id_reuse",
        "note": "Detailed Hebron footprint reused from the audited 2011 exact-ID geometry.",
    },
]


def clean_int(value: Any) -> int | None:
    if pd.isna(value):
        return None
    return int(value)


def read_statistical_areas() -> gpd.GeoDataFrame:
    if not GDB_PATH.exists():
        raise FileNotFoundError(f"Missing canonical FileGDB: {GDB_PATH}")

    gdf = gpd.read_file(GDB_PATH, layer=LAYER_NAME, engine="pyogrio")
    gdf = gdf.rename(
        columns={
            "SEMEL_YISHUV": "locality_code",
            "SHEM_YISHUV": "locality_name_he",
            "SHEM_YISHUV_ENGLISH": "locality_name_en",
            "STAT_2022": "stat_2022",
            "YISHUV_STAT_2022": "yishuv_stat_2022",
        }
    )
    gdf["locality_code"] = gdf["locality_code"].map(clean_int)
    gdf["locality_name_he"] = gdf["locality_name_he"].fillna("")
    gdf["locality_name_en"] = gdf["locality_name_en"].fillna("")
    gdf["stat_2022"] = gdf["stat_2022"].map(clean_int)
    gdf["yishuv_stat_2022"] = gdf["yishuv_stat_2022"].map(clean_int)
    gdf["locality_id"] = gdf["locality_code"].map(lambda value: f"loc:{value}" if value is not None else "")
    gdf["stat_area_id"] = gdf["yishuv_stat_2022"].map(lambda value: f"stat2022:{value}" if value is not None else "")
    gdf["geometry"] = gdf.geometry.make_valid()
    return gdf


def write_geojson(gdf: gpd.GeoDataFrame, path) -> None:
    ensure_dir(path.parent)
    gdf.to_file(path, driver="GeoJSON", encoding="utf-8", index=False)


def metadata_from_stats(stats_4326: gpd.GeoDataFrame) -> list[dict[str, Any]]:
    bounds = stats_4326.bounds
    rows: list[dict[str, Any]] = []
    for index, row in stats_4326.drop(columns="geometry").iterrows():
        row_bounds = bounds.loc[index]
        rows.append(
            {
                "stat_area_id": row["stat_area_id"],
                "yishuv_stat_2022": row["yishuv_stat_2022"],
                "locality_id": row["locality_id"],
                "locality_code": row["locality_code"],
                "locality_name_he": row["locality_name_he"],
                "locality_name_en": row["locality_name_en"],
                "stat_2022": row["stat_2022"],
                "rova": row.get("ROVA", ""),
                "tat_rova": row.get("TAT_ROVA", ""),
                "cod_tifkud": row.get("COD_TIFKUD", ""),
                "min_lon": row_bounds["minx"],
                "min_lat": row_bounds["miny"],
                "max_lon": row_bounds["maxx"],
                "max_lat": row_bounds["maxy"],
            }
        )
    return rows


def build_localities(stats: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    def join_int_values(values) -> str:
        cleaned = sorted({int(value) for value in values if pd.notna(value)})
        return "|".join(str(value) for value in cleaned)

    def join_text_values(values) -> str:
        cleaned = sorted({str(value) for value in values if pd.notna(value) and str(value)})
        return "|".join(cleaned)

    stats_for_dissolve = stats[
        [
            "locality_code",
            "locality_id",
            "locality_name_he",
            "locality_name_en",
            "stat_area_id",
            "stat_2022",
            "yishuv_stat_2022",
            "COD_TIFKUD",
            "geometry",
        ]
    ].copy()
    stats_for_dissolve["stat_area_count"] = 1

    dissolved = stats_for_dissolve.dissolve(
        by=["locality_code", "locality_id", "locality_name_he", "locality_name_en"],
        aggfunc={
            "stat_area_count": "sum",
            "stat_area_id": join_text_values,
            "stat_2022": join_int_values,
            "yishuv_stat_2022": join_int_values,
            "COD_TIFKUD": join_int_values,
        },
        as_index=False,
        dropna=False,
    )
    dissolved["geometry"] = dissolved.geometry.make_valid()

    source_coverage = union_all(stats_for_dissolve.geometry)
    dissolved_coverage = union_all(dissolved.geometry)
    missing_area = source_coverage.difference(dissolved_coverage).area
    if missing_area > 1:
        raise ValueError(
            f"Dissolved locality layer dropped {missing_area:,.1f} square metres of source coverage"
        )

    dissolved["single_stat_area"] = dissolved["stat_area_count"] == 1
    dissolved["has_function_code"] = dissolved["COD_TIFKUD"].astype(str) != ""
    return dissolved


def split_pipe_values(value: Any) -> list[str]:
    return [part.strip() for part in str(value or "").split("|") if part.strip()]


def locality_code_text(value: Any) -> str:
    if pd.isna(value) or str(value).strip() == "":
        return ""
    return str(int(float(value)))


def joined_composite_config(localities: gpd.GeoDataFrame) -> pd.DataFrame:
    if not JOINED_LOCALITY_COMPOSITES_PATH.exists():
        raise FileNotFoundError(
            f"Missing reviewed joined-locality table: {JOINED_LOCALITY_COMPOSITES_PATH}"
        )

    source = pd.read_csv(
        JOINED_LOCALITY_COMPOSITES_PATH,
        dtype=str,
        encoding="utf-8-sig",
    ).fillna("")
    required = {
        "joined_composite_id",
        "election",
        "host_locality_code",
        "host_kalpi",
        "component_locality_codes",
        "evidence_status",
        "evidence_method",
        "note",
    }
    missing_columns = sorted(required - set(source.columns))
    if missing_columns:
        raise ValueError(
            "Joined-locality table is missing columns: " + ", ".join(missing_columns)
        )
    if source["joined_composite_id"].duplicated().any():
        duplicates = sorted(
            source.loc[
                source["joined_composite_id"].duplicated(), "joined_composite_id"
            ].unique()
        )
        raise ValueError(f"Duplicate joined-locality IDs: {', '.join(duplicates)}")

    locality_by_code = {
        locality_code_text(row["locality_code"]): row
        for row in localities.drop(columns="geometry").to_dict("records")
    }
    seen_components: set[tuple[str, str]] = set()
    rows: list[dict[str, str]] = []
    for row in source.to_dict("records"):
        composite_id = row["joined_composite_id"].strip()
        election = row["election"].strip()
        host_code = locality_code_text(row["host_locality_code"])
        component_codes = [
            locality_code_text(code)
            for code in split_pipe_values(row["component_locality_codes"])
        ]
        if not composite_id or election not in ELECTIONS:
            raise ValueError(f"Invalid joined-locality row: {row}")
        if len(component_codes) < 2 or len(component_codes) != len(set(component_codes)):
            raise ValueError(
                f"{composite_id} must contain at least two unique locality codes"
            )
        if component_codes[0] != host_code:
            raise ValueError(f"{composite_id} must list its host locality first")
        missing_codes = sorted(set(component_codes) - set(locality_by_code))
        if missing_codes:
            raise ValueError(
                f"{composite_id} references missing 2022 locality codes: "
                + ", ".join(missing_codes)
            )
        if row["evidence_status"] not in {"confirmed", "strong"}:
            raise ValueError(
                f"{composite_id} has invalid evidence status: {row['evidence_status']}"
            )
        for code in component_codes:
            key = (election, code)
            if key in seen_components:
                raise ValueError(
                    f"{election} locality {code} belongs to more than one joined composite"
                )
            seen_components.add(key)

        component_names_he = [
            locality_by_code[code]["locality_name_he"] for code in component_codes
        ]
        component_names_en = [
            locality_by_code[code]["locality_name_en"]
            or locality_by_code[code]["locality_name_he"]
            for code in component_codes
        ]
        rows.append(
            {
                "composite_locality_id": composite_id,
                "elections": election,
                "source_locality_name": locality_by_code[host_code]["locality_name_he"],
                "name_he": component_names_he[0],
                "name_en": component_names_en[0],
                "included_locality_names_he": "|".join(component_names_he[1:]),
                "included_locality_names_en": "|".join(component_names_en[1:]),
                "component_locality_codes": "|".join(component_codes),
                "display_mode": row.get("display_mode", "").strip(),
                "note": row["note"].strip(),
                "composite_kind": "joined_polling_register",
                "host_locality_code": host_code,
                "host_kalpi": row["host_kalpi"].strip(),
                "evidence_status": row["evidence_status"].strip(),
                "evidence_method": row["evidence_method"].strip(),
            }
        )
    return pd.DataFrame(rows)


def build_composite_localities(localities: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if not COMPOSITE_LOCALITIES_PATH.exists():
        raise FileNotFoundError(
            f"Missing reviewed composite-locality table: {COMPOSITE_LOCALITIES_PATH}"
        )

    historical = pd.read_csv(
        COMPOSITE_LOCALITIES_PATH,
        dtype=str,
        encoding="utf-8-sig",
    ).fillna("")
    required = {
        "composite_locality_id",
        "elections",
        "source_locality_name",
        "name_he",
        "name_en",
        "component_locality_codes",
        "display_mode",
        "note",
    }
    missing_columns = sorted(required - set(historical.columns))
    if missing_columns:
        raise ValueError(f"Composite-locality table is missing columns: {', '.join(missing_columns)}")
    if historical["composite_locality_id"].duplicated().any():
        duplicates = sorted(
            historical.loc[
                historical["composite_locality_id"].duplicated(), "composite_locality_id"
            ].unique()
        )
        raise ValueError(f"Duplicate composite locality IDs: {', '.join(duplicates)}")

    historical["composite_kind"] = "historical_municipality"
    historical["host_locality_code"] = ""
    historical["host_kalpi"] = ""
    historical["evidence_status"] = "confirmed"
    historical["evidence_method"] = "reviewed_historical_municipality"
    config = pd.concat(
        [historical, joined_composite_config(localities)],
        ignore_index=True,
        sort=False,
    ).fillna("")
    if config["composite_locality_id"].duplicated().any():
        duplicates = sorted(
            config.loc[
                config["composite_locality_id"].duplicated(), "composite_locality_id"
            ].unique()
        )
        raise ValueError(f"Duplicate composite locality IDs: {', '.join(duplicates)}")

    features: list[dict[str, Any]] = []
    available_codes = {
        locality_code_text(code) for code in localities["locality_code"] if pd.notna(code)
    }
    for row in config.to_dict("records"):
        component_codes = split_pipe_values(row["component_locality_codes"])
        if not component_codes:
            raise ValueError(f"{row['composite_locality_id']} has no component locality codes")
        if row["display_mode"] not in {"", "polygon", "marker"}:
            raise ValueError(
                f"{row['composite_locality_id']} has invalid display mode: {row['display_mode']}"
            )
        missing_codes = sorted(set(component_codes) - available_codes)
        if missing_codes:
            raise ValueError(
                f"{row['composite_locality_id']} references missing 2022 locality codes: {', '.join(missing_codes)}"
            )
        components = localities[
            localities["locality_code"]
            .map(locality_code_text)
            .isin(component_codes)
        ]
        features.append(
            {
                **row,
                "component_locality_codes": "|".join(component_codes),
                "component_locality_ids": "|".join(f"loc:{code}" for code in component_codes),
                "geometry": union_all(components.geometry.to_numpy()),
            }
        )

    composites = gpd.GeoDataFrame(features, geometry="geometry", crs=localities.crs)
    composites["geometry"] = composites.geometry.make_valid()
    return composites


def locality_metadata(localities_4326: gpd.GeoDataFrame) -> list[dict[str, Any]]:
    bounds = localities_4326.bounds
    rows: list[dict[str, Any]] = []
    for index, row in localities_4326.drop(columns="geometry").iterrows():
        row_bounds = bounds.loc[index]
        rows.append(
            {
                "locality_id": row["locality_id"],
                "locality_code": row["locality_code"],
                "locality_name_he": row["locality_name_he"],
                "locality_name_en": row["locality_name_en"],
                "stat_area_count": row["stat_area_count"],
                "single_stat_area": row["single_stat_area"],
                "stat_area_ids": row["stat_area_id"],
                "stat_2022_values": row["stat_2022"],
                "yishuv_stat_2022_values": row["yishuv_stat_2022"],
                "cod_tifkud_values": row["COD_TIFKUD"],
                "has_function_code": row["has_function_code"],
                "display_geometry_source": row.get(
                    "display_geometry_source", "official_cbs_2022_dissolved"
                ),
                "min_lon": row_bounds["minx"],
                "min_lat": row_bounds["miny"],
                "max_lon": row_bounds["maxx"],
                "max_lat": row_bounds["maxy"],
            }
        )
    return rows


def composite_locality_metadata(composites_4326: gpd.GeoDataFrame) -> list[dict[str, Any]]:
    bounds = composites_4326.bounds
    rows: list[dict[str, Any]] = []
    for index, row in composites_4326.drop(columns="geometry").iterrows():
        row_bounds = bounds.loc[index]
        rows.append(
            {
                **row.to_dict(),
                "min_lon": row_bounds["minx"],
                "min_lat": row_bounds["miny"],
                "max_lon": row_bounds["maxx"],
                "max_lat": row_bounds["maxy"],
            }
        )
    return rows


def custom_geographies() -> gpd.GeoDataFrame:
    to_itm = Transformer.from_crs("EPSG:4326", "EPSG:2039", always_xy=True)
    to_wgs84 = Transformer.from_crs("EPSG:2039", "EPSG:4326", always_xy=True)

    features = []
    for item in CUSTOM_GEOGRAPHIES:
        record = dict(item)
        geometry_kind = record.pop("geometry_kind")
        if geometry_kind == "reviewed_buffer":
            point_itm = transform(
                to_itm.transform,
                Point(record["lon"], record["lat"]),
            )
            geometry = transform(
                to_wgs84.transform,
                point_itm.buffer(record["radius_m"], quad_segs=48),
            )
        elif geometry_kind == "arcgis_exact_id":
            source_path = ARCGIS_DIR / str(record.pop("source_path"))
            source_id_field = str(record.pop("source_id_field"))
            source_id = int(record.pop("source_id"))
            if not source_path.exists():
                raise FileNotFoundError(
                    f"Missing custom-geometry source: {source_path}"
                )
            source = gpd.read_file(source_path, engine="pyogrio")
            source_ids = pd.to_numeric(
                source[source_id_field], errors="coerce"
            ).round().astype("Int64")
            matches = source[source_ids == source_id]
            if len(matches) != 1:
                raise ValueError(
                    f"Expected one {source_id_field}={source_id} feature in "
                    f"{source_path.name}, found {len(matches)}"
                )
            geometry = matches.to_crs("EPSG:4326").geometry.iloc[0]
        else:
            raise ValueError(f"Unknown custom geometry kind: {geometry_kind}")
        features.append({**record, "geometry": geometry})

    return gpd.GeoDataFrame(features, geometry="geometry", crs="EPSG:4326")


def simplify(gdf: gpd.GeoDataFrame, tolerance: float) -> gpd.GeoDataFrame:
    simplified = gdf.copy()
    simplified["geometry"] = simplified.geometry.simplify(tolerance, preserve_topology=True).make_valid()
    return simplified


def polygonal_geometry(geometry: Any) -> Polygon | MultiPolygon:
    if isinstance(geometry, (Polygon, MultiPolygon)):
        return geometry
    if isinstance(geometry, GeometryCollection):
        parts = [
            polygonal_geometry(part)
            for part in geometry.geoms
            if isinstance(part, (Polygon, MultiPolygon, GeometryCollection))
        ]
        polygonal = [part for part in parts if not part.is_empty]
        return union_all(polygonal) if polygonal else Polygon()
    return Polygon()


def simplify_polygonal(
    gdf: gpd.GeoDataFrame, tolerance: float
) -> gpd.GeoDataFrame:
    simplified = simplify(gdf, tolerance)
    simplified["geometry"] = simplified.geometry.map(polygonal_geometry)
    if simplified.geometry.is_empty.any():
        raise ValueError("Polygon simplification removed all polygonal geometry")
    return simplified


def build_statistical_area_land_backdrop(
    localities: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    projected = localities.to_crs("EPSG:2039").copy()
    locality_codes = pd.to_numeric(projected["locality_code"], errors="coerce").astype("Int64")
    west_bank_locality = locality_codes.isin(WEST_BANK_DETAIL_CODES)
    point_proxy = locality_codes.isin(SPECIAL_POINT_PROXY_LOCALITY_CODES) & (
        projected.geometry.area < POINT_PROXY_MAX_AREA_M2
    )
    included = projected[(locality_codes != 9920) & ~west_bank_locality & ~point_proxy]
    coverage = union_all(included.geometry.to_numpy())
    if not coverage.is_valid:
        coverage = gpd.GeoSeries([coverage], crs=projected.crs).make_valid().iloc[0]
    coverage = polygonal_geometry(coverage)
    if coverage.is_empty:
        raise ValueError("Could not build the statistical-area land backdrop")

    return gpd.GeoDataFrame(
        [{"backdrop_id": "statistical-area-backdrop", "geometry": coverage}],
        geometry="geometry",
        crs=projected.crs,
    ).to_crs("EPSG:4326")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--simplify-tolerance", type=float, default=0.00005)
    args = parser.parse_args()

    stats = read_statistical_areas()
    detailed_by_locality = load_arcgis_detail_by_locality(
        ARCGIS_DIR,
        REVIEWED_WEST_BANK_DETAILS_PATH,
    )
    stats_4326 = stats.to_crs("EPSG:4326")
    stats_display, stat_display_replacements, stat_display_rejected = (
        apply_detailed_display_geometries(
            stats,
            detailed_by_locality,
            "official_cbs_2022",
        )
    )
    localities_source_crs = build_localities(stats)
    localities = localities_source_crs.to_crs("EPSG:4326")
    localities_display, locality_display_replacements, locality_display_rejected = (
        apply_detailed_display_geometries(
            localities_source_crs,
            detailed_by_locality,
            "official_cbs_2022_dissolved",
        )
    )
    statistical_area_land_backdrop = build_statistical_area_land_backdrop(
        localities_display
    )
    composites = build_composite_localities(
        localities_display.to_crs(localities_source_crs.crs)
    ).to_crs("EPSG:4326")
    custom = custom_geographies()

    write_geojson(stats_4326, OUT_DIR / "statistical_areas_2022.geojson")
    write_geojson(
        stats_display,
        OUT_DIR / "statistical_areas_2022.display.geojson",
    )
    write_geojson(localities, OUT_DIR / "localities_2022_dissolved.geojson")
    write_geojson(
        localities_display,
        OUT_DIR / "localities_2022_dissolved.display.geojson",
    )
    write_geojson(
        statistical_area_land_backdrop,
        OUT_DIR / "statistical_area_land_backdrop.geojson",
    )
    write_geojson(composites, OUT_DIR / "composite_localities.geojson")
    write_geojson(custom, OUT_DIR / "custom_geographies.geojson")

    if args.simplify_tolerance > 0:
        write_geojson(
            simplify(stats_4326, args.simplify_tolerance),
            OUT_DIR / "statistical_areas_2022.simplified.geojson",
        )
        write_geojson(
            simplify(stats_display, args.simplify_tolerance),
            OUT_DIR / "statistical_areas_2022.display.simplified.geojson",
        )
        write_geojson(
            simplify(localities, args.simplify_tolerance),
            OUT_DIR / "localities_2022_dissolved.simplified.geojson",
        )
        write_geojson(
            simplify(localities_display, args.simplify_tolerance),
            OUT_DIR / "localities_2022_dissolved.display.simplified.geojson",
        )
        write_geojson(
            simplify_polygonal(
                statistical_area_land_backdrop,
                args.simplify_tolerance * 10,
            ),
            OUT_DIR / "statistical_area_land_backdrop.simplified.geojson",
        )
        write_geojson(
            simplify(composites, args.simplify_tolerance),
            OUT_DIR / "composite_localities.simplified.geojson",
        )

    stat_rows = metadata_from_stats(stats_4326)
    locality_rows = locality_metadata(localities_display)
    composite_rows = composite_locality_metadata(composites)
    write_csv(
        OUT_DIR / "statistical_areas_2022.metadata.csv",
        stat_rows,
        list(stat_rows[0].keys()),
    )
    write_csv(
        OUT_DIR / "localities_2022.metadata.csv",
        locality_rows,
        list(locality_rows[0].keys()),
    )
    write_csv(
        OUT_DIR / "composite_localities.metadata.csv",
        composite_rows,
        list(composite_rows[0].keys()),
    )

    summary = {
        "source": str(GDB_PATH.relative_to(RAW_DIR.parent)).replace("\\", "/"),
        "layer": LAYER_NAME,
        "source_crs": str(stats.crs),
        "output_crs": "EPSG:4326",
        "statistical_area_features": int(len(stats)),
        "unique_stat_area_ids": int(stats["stat_area_id"].nunique()),
        "locality_features": int(len(localities)),
        "single_stat_localities": int(localities["single_stat_area"].sum()),
        "multi_stat_localities": int((~localities["single_stat_area"]).sum()),
        "composite_localities": int(len(composites)),
        "arcgis_display_detail_localities_available": len(detailed_by_locality),
        "statistical_area_display_replacements": stat_display_replacements,
        "statistical_area_display_rejected_codes": sorted(set(stat_display_rejected)),
        "locality_display_replacements": locality_display_replacements,
        "locality_display_rejected_codes": sorted(set(locality_display_rejected)),
        "historical_composite_localities": int(
            (composites["composite_kind"] == "historical_municipality").sum()
        ),
        "joined_result_composites": int(
            (composites["composite_kind"] == "joined_polling_register").sum()
        ),
        "custom_geographies": int(len(custom)),
        "simplify_tolerance": args.simplify_tolerance,
        "bounds_wgs84": {
            "min_lon": float(stats_4326.total_bounds[0]),
            "min_lat": float(stats_4326.total_bounds[1]),
            "max_lon": float(stats_4326.total_bounds[2]),
            "max_lat": float(stats_4326.total_bounds[3]),
        },
    }
    write_json(OUT_DIR / "geography_build_summary.json", summary)

    print(f"statistical_area_features={summary['statistical_area_features']}")
    print(f"locality_features={summary['locality_features']}")
    print(f"single_stat_localities={summary['single_stat_localities']}")
    print(f"multi_stat_localities={summary['multi_stat_localities']}")
    print(f"composite_localities={summary['composite_localities']}")
    print(
        "historical_composite_localities="
        f"{summary['historical_composite_localities']}"
    )
    print(f"joined_result_composites={summary['joined_result_composites']}")
    print(f"custom_geographies={summary['custom_geographies']}")
    print(f"out_dir={OUT_DIR.relative_to(PROCESSED_DIR.parent)}")


if __name__ == "__main__":
    main()
