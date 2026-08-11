from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path
from typing import Any

LOCAL_PYTHON = Path(__file__).resolve().parents[1] / ".local" / "python-geo"
if LOCAL_PYTHON.exists():
    sys.path.insert(0, str(LOCAL_PYTHON))
LOCAL_AUDIT_PYTHON = Path(__file__).resolve().parents[1] / ".local" / "python-audit"
if LOCAL_AUDIT_PYTHON.exists():
    sys.path.insert(0, str(LOCAL_AUDIT_PYTHON))

import geopandas as gpd
import pandas as pd
from shapely import coverage_is_valid, coverage_simplify

from pipeline_common import (
    MANUAL_DIR,
    PROCESSED_DIR,
    RAW_DIR,
    ROOT,
    ensure_dir,
    write_csv,
    write_json,
)
from geography_display_helpers import (
    apply_detailed_display_geometries,
    load_arcgis_detail_by_locality,
)


SOURCE_DIR = RAW_DIR / "cbs_historical_geography"
EXTRACTED_DIR = SOURCE_DIR / "extracted"
OUT_DIR = PROCESSED_DIR / "geographies"
ARCGIS_DIR = RAW_DIR / "arcgis"
REVIEWED_WEST_BANK_DETAILS_PATH = (
    MANUAL_DIR / "west_bank_display_boundary_replacements.geojson"
)
STATISTICAL_DISPLAY_GROUPS_PATH = (
    MANUAL_DIR / "statistical_area_display_groups.csv"
)
HISTORICAL_COMPONENT_DISPLAY_POLICY_PATH = (
    MANUAL_DIR / "historical_composite_component_display_geometries.csv"
)
HISTORICAL_LOCALITY_BOUNDARY_POLICY_PATH = (
    MANUAL_DIR / "historical_locality_boundary_overrides.csv"
)
CURRENT_LOCALITIES_PATH = OUT_DIR / "localities_2022_dissolved.geojson"
CURRENT_LOCALITY_DISPLAY_PATH = (
    OUT_DIR / "localities_2022_dissolved.display.simplified.geojson"
)
HISTORICAL_COMPONENT_DISPLAY_GEOMETRIES_PATH = (
    OUT_DIR / "historical_composite_component_display_geometries.geojson"
)
HISTORICAL_COMPONENT_DISPLAY_METADATA_PATH = (
    OUT_DIR / "historical_composite_component_display_geometries.metadata.csv"
)
HISTORICAL_LOCALITY_FALLBACK_GEOMETRIES_PATH = (
    OUT_DIR / "historical_locality_fallback_display_geometries.geojson"
)
HISTORICAL_LOCALITY_FALLBACK_METADATA_PATH = (
    OUT_DIR / "historical_locality_fallback_display_geometries.metadata.csv"
)
ARCGIS_2011_SUPPLEMENT_IDS = {
    9390001,
    9560001,
    9570001,
    9580001,
    9600001,
    9610001,
    9630001,
    9640001,
    9650001,
    9660001,
    9670001,
    9680001,
    9690001,
    9700001,
    9720001,
    9760001,
    9860001,
    10410001,
    11690001,
    11700001,
    12340001,
    34000001,
    36370001,
    37970001,
    27100001,
    14110001,
    14120001,
    14130001,
    14140001,
    14150001,
    14160001,
    14180001,
}
ARCGIS_2011_SUPPLEMENT_SOURCES = [
    {
        "path": "elections2015_statistical_areas.geojson",
        "area_id": "YeshuvStat",
        "locality_code": "SemelYeshuv",
        "stat_area_number": "StatZone",
        "locality_name_he": "ShemYeshuv",
        "locality_name_en": "ShemYeshuvEng",
        "source": "arcgis_systematics_elections2015_exact_id_supplement",
    },
    {
        "path": "elections2019_statistical_areas.geojson",
        "area_id": "CityStat11",
        "locality_code": "CityCode",
        "stat_area_number": "StatZone11",
        "locality_name_he": "CityNameHeb",
        "locality_name_en": "CityNameEng",
        "source": "arcgis_systematics_elections2019_exact_id_supplement",
    },
]
TRANSITION_1995_TARGETS = {
    (9400, 8): {
        "locality_name_he": "\u05d9\u05d4\u05d5\u05d3-\u05e0\u05d5\u05d5\u05d4 \u05d0\u05e4\u05e8\u05d9\u05dd",
        "locality_name_en": "YEHUD-NEWE EFRAYIM",
    }
}
REVERSE_TRANSITION_1995_SOURCES = {
    (3797, 1): {
        "locality_name_he": "\u05de\u05d5\u05d3\u05d9\u05e2\u05d9\u05df \u05e2\u05d9\u05dc\u05d9\u05ea",
        "locality_name_en": "MODI'IN ILLIT",
    }
}
NON_EXCLUSIVE_DISPLAY_MARKERS = {
    1995: {"stat1995:1062001"},
    2011: {
        "stat2011:14110001",
        "stat2011:27100001",
    },
}
DISPLAY_GEOMETRY_REPRESENTATIVE_SOURCES = {
    1995: {"stat1995:9400008": "stat1995:1062001"},
}
DISPLAY_DETAIL_OVERLAY_CODES = {2011: {3823}}
UNSIMPLIFIED_DISPLAY_VINTAGES = {1995, 2008}

VINTAGES = {
    1995: {
        "archive": "statistical_areas_1995.zip",
        "gdb": "city_stat_95.gdb",
        "layer": "city_stat_95",
        "columns": {
            "locality_code": "CITY",
            "locality_name_he": "SHEM_IVRIT",
            "locality_name_en": "NAME",
            "stat_area_number": "N_STAT",
            "yishuv_stat": "CITY_STA",
        },
    },
    2008: {
        "archive": "statisticalareas_demography2008.gdb.zip",
        "gdb": "statisticalareas_demography2008.gdb",
        "layer": "statisticalareas_demography2008",
        "columns": {
            "locality_code": "SEMEL_YISHUV",
            "locality_name_he": "Shem_Yishuv",
            "locality_name_en": "Shem_Yishuv_English",
            "stat_area_number": "STAT08",
            "yishuv_stat": "YISHUV_STAT08",
        },
    },
    2011: {
        "archive": "statisticalareas_2020_demography.gdb.zip",
        "gdb": "statisticalareas_2020_demography.gdb",
        "layer": "statisticalareas_2020_demography",
        "columns": {
            "locality_code": "SEMEL_YISHUV",
            "locality_name_he": "SHEM_YISHUV",
            "locality_name_en": "SHEM_YISHUV_ENGLISH",
            "stat_area_number": "STAT11",
            "yishuv_stat": "YISHUV_STAT11",
        },
    },
}


def extract_archive(archive: Path, expected_gdb: Path) -> None:
    if expected_gdb.exists():
        return
    if not archive.exists():
        raise FileNotFoundError(f"Missing CBS archive: {archive}")
    ensure_dir(EXTRACTED_DIR)
    with zipfile.ZipFile(archive) as source:
        source.extractall(EXTRACTED_DIR)
    if not expected_gdb.exists():
        raise FileNotFoundError(
            f"{archive.name} did not contain expected FileGDB {expected_gdb.name}"
        )


def integer_series(values: pd.Series) -> pd.Series:
    return pd.to_numeric(values, errors="coerce").round().astype("Int64")


def preferred_text(values: pd.Series) -> str:
    cleaned = values.fillna("").astype(str).str.strip()
    cleaned = cleaned[cleaned != ""]
    if cleaned.empty:
        return ""
    modes = cleaned.mode()
    return str(modes.iloc[0] if not modes.empty else cleaned.iloc[0])


def clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def load_display_group_marker_ids() -> dict[int, set[str]]:
    if not STATISTICAL_DISPLAY_GROUPS_PATH.exists():
        raise FileNotFoundError(
            f"Missing display-group policy: {STATISTICAL_DISPLAY_GROUPS_PATH}"
        )
    rows = pd.read_csv(STATISTICAL_DISPLAY_GROUPS_PATH, dtype=str).fillna("")
    required = {"component_stat_area_id", "component_display_mode"}
    missing_columns = required - set(rows.columns)
    if missing_columns:
        raise ValueError(
            f"Display-group policy is missing columns: {sorted(missing_columns)}"
        )

    marker_ids_by_vintage: dict[int, set[str]] = {}
    marker_rows = rows[rows["component_display_mode"].str.strip() == "marker"]
    for raw_id in marker_rows["component_stat_area_id"]:
        stat_area_id = clean_text(raw_id)
        prefix, separator, _ = stat_area_id.partition(":")
        vintage_text = prefix.removeprefix("stat")
        if separator != ":" or not vintage_text.isdigit():
            raise ValueError(
                f"Invalid display-group statistical-area ID: {stat_area_id}"
            )
        marker_ids_by_vintage.setdefault(int(vintage_text), set()).add(
            stat_area_id
        )
    return marker_ids_by_vintage


def valid_geometry(geometry: Any, crs: Any) -> Any:
    return gpd.GeoSeries([geometry], crs=crs).make_valid().iloc[0]


def read_vintage(
    vintage: int,
) -> tuple[gpd.GeoDataFrame, list[dict[str, Any]], dict[str, Any]]:
    config = VINTAGES[vintage]
    archive = SOURCE_DIR / str(config["archive"])
    gdb = EXTRACTED_DIR / str(config["gdb"])
    extract_archive(archive, gdb)

    raw = gpd.read_file(gdb, layer=str(config["layer"]), engine="pyogrio")
    columns = config["columns"]
    stats = raw.rename(columns={source: target for target, source in columns.items()})
    stats["locality_code"] = integer_series(stats["locality_code"])
    stats["stat_area_number"] = integer_series(stats["stat_area_number"])
    stats["yishuv_stat"] = integer_series(stats["yishuv_stat"])
    usable_geometry = stats.geometry.notna() & ~stats.geometry.is_empty
    assignable = (
        stats["locality_code"].notna()
        & (stats["locality_code"] > 0)
        & stats["stat_area_number"].notna()
        & stats["yishuv_stat"].notna()
        & usable_geometry
    )
    excluded = stats[~assignable].copy()
    exclusion_reason = pd.Series("assignable", index=stats.index, dtype="object")
    exclusion_reason.loc[~usable_geometry] = "missing_geometry"
    exclusion_reason.loc[
        usable_geometry
        & (stats["locality_code"].isna() | (stats["locality_code"] <= 0))
    ] = "missing_or_nonpositive_locality_code"
    exclusion_reason.loc[
        usable_geometry
        & stats["locality_code"].notna()
        & (stats["locality_code"] > 0)
        & stats["stat_area_number"].isna()
    ] = "missing_stat_area_number"
    exclusion_reason.loc[
        usable_geometry
        & stats["locality_code"].notna()
        & (stats["locality_code"] > 0)
        & stats["stat_area_number"].notna()
        & stats["yishuv_stat"].isna()
    ] = "missing_combined_area_id"
    excluded["exclusion_reason"] = exclusion_reason.loc[excluded.index]
    stats = stats[assignable].copy()
    for column in ["locality_code", "stat_area_number", "yishuv_stat"]:
        stats[column] = stats[column].astype("int64")
    stats["source_stat_area_number"] = stats["stat_area_number"]
    stats["source_yishuv_stat"] = stats["yishuv_stat"]
    corrected_source_ids = 0
    if vintage == 1995:
        recomputed_ids = stats["locality_code"] * 1000 + stats["stat_area_number"]
        corrected_source_ids = int((stats["source_yishuv_stat"] != recomputed_ids).sum())
        stats["source_yishuv_stat"] = (
            stats["locality_code"] * 1000 + stats["source_stat_area_number"]
        )
    if vintage == 1995:
        # The source repeats CITY_STA 7900214 on one Petah Tiqwa STAT 212 row.
        stats["yishuv_stat"] = (
            stats["locality_code"] * 1000 + stats["stat_area_number"]
        )
    aliases = stats[
        [
            "locality_code",
            "source_stat_area_number",
            "source_yishuv_stat",
            "stat_area_number",
            "yishuv_stat",
        ]
    ].drop_duplicates()
    conflicts = aliases.groupby("source_yishuv_stat")["yishuv_stat"].nunique()
    if (conflicts > 1).any():
        raise ValueError(f"CBS {vintage} source area maps to multiple published unions")
    alias_rows = [
        {
            "stat_area_vintage": vintage,
            "locality_code": int(row.locality_code),
            "source_stat_area_number": int(row.source_stat_area_number),
            "source_yishuv_stat": int(row.source_yishuv_stat),
            "source_stat_area_id": f"stat{vintage}:{int(row.source_yishuv_stat)}",
            "canonical_stat_area_number": int(row.stat_area_number),
            "canonical_yishuv_stat": int(row.yishuv_stat),
            "canonical_stat_area_id": f"stat{vintage}:{int(row.yishuv_stat)}",
            "is_identity": int(row.source_yishuv_stat) == int(row.yishuv_stat),
            "alias_reason": "identity",
        }
        for row in aliases.itertuples(index=False)
    ]
    if any(not row["is_identity"] for row in alias_rows):
        raise ValueError(
            f"CBS {vintage} source IDs must remain distinct assignment IDs"
        )
    stats["locality_name_he"] = stats["locality_name_he"].fillna("").astype(str)
    stats["locality_name_en"] = stats["locality_name_en"].fillna("").astype(str)
    for yishuv_stat, group in stats.groupby("yishuv_stat"):
        for column in ["locality_code", "stat_area_number"]:
            if group[column].nunique() != 1:
                raise ValueError(
                    f"CBS {vintage} area {yishuv_stat} has conflicting {column} values"
                )
    metadata = (
        stats.groupby("yishuv_stat", as_index=False)
        .agg(
            locality_code=("locality_code", "first"),
            locality_name_he=("locality_name_he", preferred_text),
            locality_name_en=("locality_name_en", preferred_text),
            stat_area_number=("stat_area_number", "first"),
        )
    )
    geometries = stats[["yishuv_stat", "geometry"]].dissolve(
        by="yishuv_stat", as_index=False
    )
    stats = gpd.GeoDataFrame(
        metadata.merge(geometries, on="yishuv_stat", validate="one_to_one"),
        geometry="geometry",
        crs=raw.crs,
    )
    stats["stat_area_vintage"] = vintage
    stats["locality_id"] = stats["locality_code"].map(lambda value: f"loc:{value}")
    stats["stat_area_id"] = stats["yishuv_stat"].map(
        lambda value: f"stat{vintage}:{value}"
    )
    stats["geometry"] = stats.geometry.make_valid()
    stats["geometry_source"] = "official_cbs"

    if stats["stat_area_id"].duplicated().any():
        duplicates = sorted(
            stats.loc[stats["stat_area_id"].duplicated(), "stat_area_id"].unique()
        )
        raise ValueError(
            f"CBS {vintage} layer has duplicate statistical-area IDs: {duplicates[:10]}"
        )
    excluded_positive = excluded[
        excluded["locality_code"].notna() & (excluded["locality_code"] > 0)
    ].copy()
    excluded_positive_rows = []
    for row in excluded_positive.itertuples(index=False):
        excluded_positive_rows.append(
            {
                "locality_code": int(row.locality_code),
                "locality_name_he": clean_text(
                    getattr(row, "locality_name_he", "")
                ),
                "locality_name_en": clean_text(
                    getattr(row, "locality_name_en", "")
                ),
                "exclusion_reason": str(row.exclusion_reason),
            }
        )
    source_inventory = {
        "archive": str(config["archive"]),
        "gdb": str(config["gdb"]),
        "layer": str(config["layer"]),
        "raw_feature_rows": int(len(raw)),
        "assignable_source_geometry_rows": int(assignable.sum()),
        "unique_assignment_area_ids_before_supplements": int(stats["stat_area_id"].nunique()),
        "additional_geometry_rows_sharing_an_area_id": int(
            assignable.sum() - stats["stat_area_id"].nunique()
        ),
        "excluded_source_rows": int((~assignable).sum()),
        "exclusion_reason_counts": {
            str(reason): int(count)
            for reason, count in excluded["exclusion_reason"].value_counts().to_dict().items()
        },
        "excluded_positive_locality_rows": excluded_positive_rows,
        "corrected_malformed_source_area_ids": corrected_source_ids,
    }
    return stats, alias_rows, source_inventory


def identity_alias(vintage: int, row: pd.Series, reason: str) -> dict[str, Any]:
    return {
        "stat_area_vintage": vintage,
        "locality_code": int(row["locality_code"]),
        "source_stat_area_number": int(row["stat_area_number"]),
        "source_yishuv_stat": int(row["yishuv_stat"]),
        "source_stat_area_id": row["stat_area_id"],
        "canonical_stat_area_number": int(row["stat_area_number"]),
        "canonical_yishuv_stat": int(row["yishuv_stat"]),
        "canonical_stat_area_id": row["stat_area_id"],
        "is_identity": True,
        "alias_reason": reason,
    }


def add_1995_transition_unions(
    stats: gpd.GeoDataFrame,
) -> tuple[gpd.GeoDataFrame, list[dict[str, Any]]]:
    path = SOURCE_DIR / "statistical_area_conversion_key_1995.xls"
    if not path.exists():
        raise FileNotFoundError(f"Missing CBS 1995 transition key: {path}")
    transition = pd.read_excel(path, sheet_name="\u05de\u05e4\u05ea\u05d7 1995", dtype=str).fillna("")
    transition["source_locality_code"] = integer_series(
        transition["LocalityCode1995"]
    )
    transition["source_stat_area_number"] = integer_series(
        transition["StatAreaCode1995"]
    )
    transition["target_locality_code"] = integer_series(
        transition["LocalityCode2008"]
    )
    transition["target_stat_area_number"] = integer_series(
        transition["StatAreaCode2008"]
    )

    additions: list[gpd.GeoDataFrame] = []
    aliases: list[dict[str, Any]] = []
    for (locality_code, stat_area_number), names in TRANSITION_1995_TARGETS.items():
        yishuv_stat = locality_code * 1000 + stat_area_number
        stat_area_id = f"stat1995:{yishuv_stat}"
        if (stats["stat_area_id"] == stat_area_id).any():
            continue
        links = transition[
            (transition["target_locality_code"] == locality_code)
            & (transition["target_stat_area_number"] == stat_area_number)
        ].copy()
        links = links[
            links["source_locality_code"].notna()
            & links["source_stat_area_number"].notna()
        ]
        source_ids = {
            int(row.source_locality_code) * 1000 + int(row.source_stat_area_number)
            for row in links.itertuples(index=False)
        }
        parts = stats[stats["yishuv_stat"].isin(source_ids)]
        if not source_ids or set(parts["yishuv_stat"]) != source_ids:
            missing = sorted(source_ids - set(parts["yishuv_stat"]))
            raise ValueError(
                f"CBS transition union {stat_area_id} is missing 1995 components: {missing}"
            )
        record = {
            "locality_code": locality_code,
            "locality_name_he": names["locality_name_he"],
            "locality_name_en": names["locality_name_en"],
            "stat_area_number": stat_area_number,
            "yishuv_stat": yishuv_stat,
            "stat_area_vintage": 1995,
            "locality_id": f"loc:{locality_code}",
            "stat_area_id": stat_area_id,
            "geometry_source": "official_cbs_1995_to_2008_transition_union",
            "geometry": valid_geometry(parts.geometry.union_all(), stats.crs),
        }
        addition = gpd.GeoDataFrame([record], geometry="geometry", crs=stats.crs)
        additions.append(addition)
        aliases.append(
            identity_alias(1995, addition.iloc[0], "official_cbs_transition_union")
        )
    if additions:
        stats = gpd.GeoDataFrame(
            pd.concat([stats, *additions], ignore_index=True),
            geometry="geometry",
            crs=stats.crs,
        )
    return stats, aliases


def add_1995_reverse_transition_unions(
    stats: gpd.GeoDataFrame,
    target_2008: gpd.GeoDataFrame,
) -> tuple[gpd.GeoDataFrame, list[dict[str, Any]]]:
    path = SOURCE_DIR / "statistical_area_conversion_key_1995.xls"
    if not path.exists():
        raise FileNotFoundError(f"Missing CBS 1995 transition key: {path}")
    transition = pd.read_excel(
        path, sheet_name="\u05de\u05e4\u05ea\u05d7 1995", dtype=str
    ).fillna("")
    transition["source_locality_code"] = integer_series(
        transition["LocalityCode1995"]
    )
    transition["source_stat_area_number"] = integer_series(
        transition["StatAreaCode1995"]
    )
    transition["target_locality_code"] = integer_series(
        transition["LocalityCode2008"]
    )
    transition["target_stat_area_number"] = integer_series(
        transition["StatAreaCode2008"]
    )
    target_2008 = target_2008.to_crs(stats.crs)

    additions: list[gpd.GeoDataFrame] = []
    aliases: list[dict[str, Any]] = []
    for (
        locality_code,
        stat_area_number,
    ), names in REVERSE_TRANSITION_1995_SOURCES.items():
        yishuv_stat = locality_code * 1000 + stat_area_number
        stat_area_id = f"stat1995:{yishuv_stat}"
        if (stats["stat_area_id"] == stat_area_id).any():
            continue
        links = transition[
            (transition["source_locality_code"] == locality_code)
            & (transition["source_stat_area_number"] == stat_area_number)
            & transition["target_locality_code"].notna()
            & transition["target_stat_area_number"].notna()
        ][["target_locality_code", "target_stat_area_number"]].drop_duplicates()
        target_keys = {
            (int(row.target_locality_code), int(row.target_stat_area_number))
            for row in links.itertuples(index=False)
        }
        parts = target_2008[
            [
                (int(row.locality_code), int(row.stat_area_number)) in target_keys
                for row in target_2008.itertuples(index=False)
            ]
        ]
        found_keys = {
            (int(row.locality_code), int(row.stat_area_number))
            for row in parts.itertuples(index=False)
        }
        if not target_keys or found_keys != target_keys:
            missing = sorted(target_keys - found_keys)
            raise ValueError(
                f"CBS reverse transition union {stat_area_id} is missing 2008 targets: {missing}"
            )
        record = {
            "locality_code": locality_code,
            "locality_name_he": names["locality_name_he"],
            "locality_name_en": names["locality_name_en"],
            "stat_area_number": stat_area_number,
            "yishuv_stat": yishuv_stat,
            "stat_area_vintage": 1995,
            "locality_id": f"loc:{locality_code}",
            "stat_area_id": stat_area_id,
            "geometry_source": "official_cbs_1995_transition_reconstructed_from_2008_targets",
            "geometry": valid_geometry(parts.geometry.union_all(), stats.crs),
        }
        addition = gpd.GeoDataFrame([record], geometry="geometry", crs=stats.crs)
        additions.append(addition)
        aliases.append(
            identity_alias(
                1995,
                addition.iloc[0],
                "official_cbs_reverse_transition_union",
            )
        )
    if additions:
        stats = gpd.GeoDataFrame(
            pd.concat([stats, *additions], ignore_index=True),
            geometry="geometry",
            crs=stats.crs,
        )
    return stats, aliases


def add_2011_arcgis_exact_id_supplements(
    stats: gpd.GeoDataFrame,
) -> tuple[gpd.GeoDataFrame, list[dict[str, Any]]]:
    source_frames: list[gpd.GeoDataFrame] = []
    for config in ARCGIS_2011_SUPPLEMENT_SOURCES:
        path = ARCGIS_DIR / str(config["path"])
        if not path.exists():
            raise FileNotFoundError(f"Missing audited ArcGIS layer: {path}")
        source = gpd.read_file(path, engine="pyogrio")
        source = source.rename(
            columns={
                str(config["area_id"]): "yishuv_stat",
                str(config["locality_code"]): "locality_code",
                str(config["stat_area_number"]): "stat_area_number",
                str(config["locality_name_he"]): "locality_name_he",
                str(config["locality_name_en"]): "locality_name_en",
            }
        )
        source["yishuv_stat"] = integer_series(source["yishuv_stat"])
        source = source[source["yishuv_stat"].isin(ARCGIS_2011_SUPPLEMENT_IDS)].copy()
        source["supplement_source"] = str(config["source"])
        source_frames.append(
            source[
                [
                    "yishuv_stat",
                    "locality_code",
                    "stat_area_number",
                    "locality_name_he",
                    "locality_name_en",
                    "supplement_source",
                    "geometry",
                ]
            ].to_crs(stats.crs)
        )
    source = gpd.GeoDataFrame(
        pd.concat(source_frames, ignore_index=True), geometry="geometry", crs=stats.crs
    )

    additions: list[gpd.GeoDataFrame] = []
    aliases: list[dict[str, Any]] = []
    existing_ids = set(stats["yishuv_stat"])
    for yishuv_stat in sorted(ARCGIS_2011_SUPPLEMENT_IDS):
        if yishuv_stat in existing_ids:
            continue
        matches = source[source["yishuv_stat"] == yishuv_stat]
        if matches.empty:
            raise ValueError(
                f"ArcGIS supplement {yishuv_stat} has no matching feature"
            )
        match = matches.iloc[0]
        locality_code = int(match["locality_code"])
        stat_area_number = int(match["stat_area_number"])
        record = {
            "locality_code": locality_code,
            "locality_name_he": preferred_text(pd.Series([match["locality_name_he"]])),
            "locality_name_en": preferred_text(pd.Series([match["locality_name_en"]])),
            "stat_area_number": stat_area_number,
            "yishuv_stat": yishuv_stat,
            "stat_area_vintage": 2011,
            "locality_id": f"loc:{locality_code}",
            "stat_area_id": f"stat2011:{yishuv_stat}",
            "geometry_source": match["supplement_source"],
            "geometry": valid_geometry(match.geometry, stats.crs),
        }
        addition = gpd.GeoDataFrame([record], geometry="geometry", crs=stats.crs)
        additions.append(addition)
        aliases.append(
            identity_alias(2011, addition.iloc[0], "arcgis_exact_id_supplement")
        )
    if additions:
        stats = gpd.GeoDataFrame(
            pd.concat([stats, *additions], ignore_index=True),
            geometry="geometry",
            crs=stats.crs,
        )
    return stats, aliases


def validate_vintage(stats: gpd.GeoDataFrame, vintage: int) -> None:
    required = [
        "stat_area_id",
        "stat_area_vintage",
        "yishuv_stat",
        "locality_code",
        "stat_area_number",
        "geometry_source",
    ]
    missing_columns = [column for column in required if column not in stats]
    if missing_columns:
        raise ValueError(f"{vintage} geography is missing columns: {missing_columns}")
    duplicate_ids = sorted(
        stats.loc[stats["stat_area_id"].duplicated(keep=False), "stat_area_id"].unique()
    )
    if duplicate_ids:
        raise ValueError(f"{vintage} geography has duplicate IDs: {duplicate_ids[:10]}")
    if stats[required].isna().any().any() or (stats["geometry_source"] == "").any():
        raise ValueError(f"{vintage} geography has blank required metadata")
    if stats.geometry.isna().any() or stats.geometry.is_empty.any():
        raise ValueError(f"{vintage} geography has missing or empty geometry")
    if not stats.geometry.is_valid.all():
        raise ValueError(f"{vintage} geography has invalid geometry")


def public_columns(stats: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    columns = [
        "stat_area_id",
        "stat_area_vintage",
        "yishuv_stat",
        "locality_id",
        "locality_code",
        "locality_name_he",
        "locality_name_en",
        "stat_area_number",
        "geometry_source",
        "display_geometry_source",
        "display_mode",
        "geometry",
    ]
    output = stats.copy()
    if "display_geometry_source" not in output:
        output["display_geometry_source"] = output.get(
            "geometry_source", "official_cbs"
        )
    if "display_mode" not in output:
        output["display_mode"] = ""
    return output[columns]


def simplify(stats: gpd.GeoDataFrame, tolerance: float) -> gpd.GeoDataFrame:
    output = stats.copy()
    output["geometry"] = output.geometry.simplify(
        tolerance, preserve_topology=True
    ).make_valid()
    return output


def simplify_official_coverages(
    stats: gpd.GeoDataFrame,
    tolerance: float,
) -> gpd.GeoDataFrame:
    """Simplify shared CBS boundaries once per locality without creating seams."""
    output = simplify(stats, tolerance)
    for _, locality in stats.groupby("locality_code", sort=False):
        official = locality.loc[
            locality["display_geometry_source"].eq("official_cbs")
            & locality["display_mode"].fillna("").ne("marker")
        ]
        if len(official) < 2:
            continue
        geometries = official.geometry.to_numpy()
        if not coverage_is_valid(geometries):
            continue
        output.loc[official.index, "geometry"] = gpd.GeoSeries(
            coverage_simplify(geometries, tolerance),
            index=official.index,
            crs=stats.crs,
        )
    return output


def validate_no_material_display_overlaps(
    stats: gpd.GeoDataFrame,
    vintage: int,
    minimum_area_m2: float = 1.0,
    ignored_ids: set[str] | None = None,
) -> None:
    ignored_ids = ignored_ids or set()
    polygons = stats.loc[
        stats["display_mode"].fillna("").ne("marker")
        & ~stats["stat_area_id"].isin(ignored_ids)
    ].to_crs("EPSG:2039")
    failures: list[tuple[str, str, float]] = []
    for left_position, right_position in zip(
        *polygons.sindex.query(polygons.geometry, predicate="intersects")
    ):
        if left_position >= right_position:
            continue
        left = polygons.iloc[left_position]
        right = polygons.iloc[right_position]
        overlap_area = left.geometry.intersection(right.geometry).area
        if overlap_area > minimum_area_m2:
            failures.append(
                (
                    str(left["stat_area_id"]),
                    str(right["stat_area_id"]),
                    round(overlap_area, 3),
                )
            )
    if failures:
        raise ValueError(
            f"{vintage} display geometry has material polygon overlaps: {failures[:10]}"
        )


def validate_official_locality_coverages(
    stats: gpd.GeoDataFrame,
    vintage: int,
    minimum_area_m2: float = 2.0,
) -> None:
    """Reject simplification seams inside an official locality coverage."""
    polygons = stats.loc[
        stats["display_mode"].fillna("").ne("marker")
        & stats["display_geometry_source"].eq("official_cbs")
    ].to_crs("EPSG:2039").reset_index(drop=True)
    failures: list[tuple[str, str, float]] = []
    for left_position, right_position in zip(
        *polygons.sindex.query(polygons.geometry, predicate="intersects")
    ):
        if left_position >= right_position:
            continue
        left = polygons.iloc[left_position]
        right = polygons.iloc[right_position]
        if left["locality_code"] != right["locality_code"]:
            continue
        overlap_area = left.geometry.intersection(right.geometry).area
        if overlap_area > minimum_area_m2:
            failures.append(
                (
                    str(left["stat_area_id"]),
                    str(right["stat_area_id"]),
                    round(overlap_area, 3),
                )
            )
    if failures:
        raise ValueError(
            f"{vintage} official locality coverage has simplification overlaps: "
            f"{failures[:10]}"
        )


def validate_supplement_overlap_markers(
    stats: gpd.GeoDataFrame,
    vintage: int,
    marker_ids: set[str],
    maximum_unmarked_overlap_share: float = 0.05,
) -> None:
    projected = stats.to_crs("EPSG:2039").reset_index(drop=True)
    supplements = projected[
        projected["geometry_source"].astype(str).str.startswith("arcgis_")
    ].reset_index(drop=True)
    failures: list[tuple[str, str, float]] = []
    for supplement_position, area_position in zip(
        *projected.sindex.query(supplements.geometry, predicate="intersects")
    ):
        supplement = supplements.iloc[supplement_position]
        area = projected.iloc[area_position]
        if supplement["stat_area_id"] == area["stat_area_id"]:
            continue
        overlap_share = (
            supplement.geometry.intersection(area.geometry).area
            / supplement.geometry.area
        )
        if (
            overlap_share > maximum_unmarked_overlap_share
            and supplement["stat_area_id"] not in marker_ids
        ):
            failures.append(
                (
                    str(supplement["stat_area_id"]),
                    str(area["stat_area_id"]),
                    round(overlap_share, 4),
                )
            )
    if failures:
        raise ValueError(
            f"{vintage} ArcGIS supplements with material overlaps must render "
            f"as markers: {failures[:10]}"
        )


def polygon_parts(geometry: Any) -> list[Any]:
    if geometry.is_empty:
        return []
    if geometry.geom_type == "Polygon":
        return [geometry]
    if not hasattr(geometry, "geoms"):
        return []
    return [
        polygon
        for part in geometry.geoms
        for polygon in polygon_parts(part)
    ]


def build_historical_component_display_geometries(
    official: gpd.GeoDataFrame,
    current_localities: gpd.GeoDataFrame,
    policy: pd.DataFrame,
    vintage: int,
    maximum_error_m2: float = 1.0,
) -> tuple[gpd.GeoDataFrame, list[dict[str, Any]]]:
    vintage_policy = policy[policy["stat_area_vintage"] == vintage].copy()
    if vintage_policy.empty:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326"), []

    projected_official = official.to_crs("EPSG:2039")
    projected_localities = current_localities.to_crs("EPSG:2039")
    feature_rows: list[dict[str, Any]] = []
    metadata: list[dict[str, Any]] = []

    for footprint_code, group in vintage_policy.groupby(
        "historical_footprint_locality_code", sort=True
    ):
        footprint_rows = projected_official[
            projected_official["locality_code"] == footprint_code
        ]
        if footprint_rows.empty:
            raise ValueError(
                f"Historical component display policy references missing {vintage} "
                f"footprint locality {footprint_code}"
            )
        historical_footprint = valid_geometry(
            footprint_rows.geometry.union_all(), projected_official.crs
        )

        component_seeds: dict[int, Any] = {}
        component_properties: dict[int, pd.Series] = {}
        for policy_row in group.itertuples(index=False):
            component_code = int(policy_row.component_locality_code)
            matches = projected_localities[
                projected_localities["locality_code"] == component_code
            ]
            if len(matches) != 1:
                raise ValueError(
                    f"Historical component display policy {vintage}/{component_code} "
                    f"resolved to {len(matches)} current locality geometries"
                )
            locality = matches.iloc[0]
            seed = valid_geometry(
                historical_footprint.intersection(locality.geometry),
                projected_official.crs,
            )
            if seed.is_empty or seed.area <= maximum_error_m2:
                raise ValueError(
                    f"Historical component display policy {vintage}/{component_code} "
                    "does not intersect its historical footprint"
                )
            component_seeds[component_code] = seed
            component_properties[component_code] = locality

        seed_items = sorted(component_seeds.items())
        for left_index, (left_code, left_geometry) in enumerate(seed_items):
            for right_code, right_geometry in seed_items[left_index + 1 :]:
                overlap_area = left_geometry.intersection(right_geometry).area
                if overlap_area > maximum_error_m2:
                    raise ValueError(
                        f"Historical component seeds {vintage}/{left_code} and "
                        f"{right_code} overlap by {overlap_area:.3f} square metres"
                    )

        seed_union = gpd.GeoSeries(
            list(component_seeds.values()), crs=projected_official.crs
        ).union_all()
        uncovered = valid_geometry(
            historical_footprint.difference(seed_union), projected_official.crs
        )
        assigned_parts: dict[int, list[Any]] = {
            component_code: [] for component_code in component_seeds
        }
        for part in polygon_parts(uncovered):
            if part.is_empty or part.area <= 0:
                continue
            candidates = []
            for component_code, seed in seed_items:
                shared_boundary = part.boundary.intersection(seed.boundary).length
                candidates.append(
                    (
                        -round(shared_boundary, 6),
                        round(part.distance(seed), 6),
                        component_code,
                    )
                )
            selected_code = min(candidates)[2]
            assigned_parts[selected_code].append(part)

        final_geometries: dict[int, Any] = {}
        for component_code, seed in seed_items:
            parts = [seed, *assigned_parts[component_code]]
            final_geometries[component_code] = valid_geometry(
                gpd.GeoSeries(parts, crs=projected_official.crs).union_all(),
                projected_official.crs,
            )

        final_union = gpd.GeoSeries(
            list(final_geometries.values()), crs=projected_official.crs
        ).union_all()
        coverage_error = final_union.symmetric_difference(historical_footprint).area
        if coverage_error > maximum_error_m2:
            raise ValueError(
                f"Historical component partition {vintage}/{footprint_code} differs "
                f"from its footprint by {coverage_error:.3f} square metres"
            )
        for left_index, (left_code, left_geometry) in enumerate(
            sorted(final_geometries.items())
        ):
            for right_code, right_geometry in sorted(final_geometries.items())[
                left_index + 1 :
            ]:
                overlap_area = left_geometry.intersection(right_geometry).area
                if overlap_area > maximum_error_m2:
                    raise ValueError(
                        f"Historical component display geometries {vintage}/{left_code} "
                        f"and {right_code} overlap by {overlap_area:.3f} square metres"
                    )

        for policy_row in group.itertuples(index=False):
            component_code = int(policy_row.component_locality_code)
            locality = component_properties[component_code]
            geometry = final_geometries[component_code]
            fallback_id = (
                f"municipality-component-fallback:{vintage}:loc:{component_code}"
            )
            assigned_leftover_area = sum(
                part.area for part in assigned_parts[component_code]
            )
            feature_rows.append(
                {
                    "fallback_geography_id": fallback_id,
                    "election": str(policy_row.election),
                    "stat_area_vintage": vintage,
                    "historical_footprint_locality_code": int(footprint_code),
                    "locality_id": f"loc:{component_code}",
                    "locality_code": component_code,
                    "locality_name_he": clean_text(locality["locality_name_he"]),
                    "locality_name_en": clean_text(locality["locality_name_en"]),
                    "boundary_rule": str(policy_row.boundary_rule),
                    "geometry_source": (
                        "reviewed_historical_footprint_partition_by_"
                        "current_component_boundary"
                    ),
                    "geometry": geometry,
                }
            )
            metadata.append(
                {
                    "fallback_geography_id": fallback_id,
                    "election": str(policy_row.election),
                    "stat_area_vintage": vintage,
                    "historical_footprint_locality_code": int(footprint_code),
                    "component_locality_code": component_code,
                    "component_locality_name_he": clean_text(
                        locality["locality_name_he"]
                    ),
                    "boundary_rule": str(policy_row.boundary_rule),
                    "historical_footprint_area_m2": round(
                        historical_footprint.area, 3
                    ),
                    "current_boundary_seed_area_m2": round(
                        component_seeds[component_code].area, 3
                    ),
                    "assigned_historical_edge_area_m2": round(
                        assigned_leftover_area, 3
                    ),
                    "display_geometry_area_m2": round(geometry.area, 3),
                    "group_coverage_error_m2": round(coverage_error, 6),
                    "note": str(policy_row.note),
                }
            )

    features = gpd.GeoDataFrame(
        feature_rows, geometry="geometry", crs=projected_official.crs
    ).to_crs("EPSG:4326")
    if features["fallback_geography_id"].duplicated().any():
        raise ValueError("Historical component display policy produced duplicate IDs")
    return features, metadata


def apply_display_geometry_representatives(
    display: gpd.GeoDataFrame,
    representatives: dict[str, str],
) -> tuple[gpd.GeoDataFrame, dict[str, str]]:
    display = display.copy()
    applied: dict[str, str] = {}
    for target_id, source_id in representatives.items():
        target_indices = display.index[display["stat_area_id"] == target_id].tolist()
        source_rows = display[display["stat_area_id"] == source_id]
        if len(target_indices) != 1 or len(source_rows) != 1:
            raise ValueError(
                f"Display geometry representative {target_id} -> {source_id} "
                f"resolved to {len(target_indices)} targets and {len(source_rows)} sources"
            )
        display.at[target_indices[0], "geometry"] = source_rows.geometry.iloc[0]
        display.at[target_indices[0], "display_geometry_source"] = (
            f"representative_component:{source_id}"
        )
        applied[target_id] = source_id
    return display, applied


def apply_reviewed_current_locality_boundaries(
    display: gpd.GeoDataFrame,
    current_localities: gpd.GeoDataFrame,
    policy: pd.DataFrame,
    vintage: int,
    maximum_overlap_m2: float = 1.0,
    maximum_overlap_share_delta_pct: float = 0.01,
) -> tuple[
    gpd.GeoDataFrame,
    dict[str, str],
    list[str],
    gpd.GeoDataFrame,
    list[dict[str, Any]],
]:
    fallback_columns = [
        "fallback_geography_id",
        "stat_area_vintage",
        "locality_id",
        "locality_code",
        "locality_name_he",
        "locality_name_en",
        "boundary_source",
        "subtracted_stat_area_ids",
        "geometry",
    ]

    def empty_fallback_geometries() -> gpd.GeoDataFrame:
        return gpd.GeoDataFrame(
            columns=fallback_columns,
            geometry="geometry",
            crs="EPSG:4326",
        )

    vintage_policy = policy[policy["stat_area_vintage"] == vintage]
    if vintage_policy.empty:
        return display, {}, [], empty_fallback_geometries(), []

    projected = display.to_crs("EPSG:2039")
    projected_localities = current_localities.to_crs(projected.crs)
    original_geometries = projected.set_index("stat_area_id").geometry.to_dict()
    base_candidates: dict[int, Any] = {}
    locality_properties: dict[int, dict[str, Any]] = {}
    for locality_code in sorted(set(vintage_policy["current_locality_code"])):
        locality_rows = projected_localities[
            projected_localities["locality_code"] == locality_code
        ]
        if len(locality_rows) != 1:
            raise ValueError(
                f"Historical locality boundary policy loc:{locality_code} resolved "
                f"to {len(locality_rows)} current localities"
            )
        locality = locality_rows.iloc[0]
        candidate = valid_geometry(locality.geometry, projected.crs)
        if candidate.is_empty or candidate.geom_type not in {
            "Polygon",
            "MultiPolygon",
        }:
            raise ValueError(
                f"Historical locality boundary policy loc:{locality_code} "
                "has no polygon geometry"
            )
        base_candidates[locality_code] = candidate
        locality_properties[locality_code] = {
            "locality_id": clean_text(locality.get("locality_id"))
            or f"loc:{locality_code}",
            "locality_name_he": clean_text(locality.get("locality_name_he")),
            "locality_name_en": clean_text(locality.get("locality_name_en")),
        }

    fallback_override_candidates: dict[int, Any] = {}
    fallback_override_targets: dict[int, list[str]] = {}
    reverse_policy = vintage_policy[
        vintage_policy["operation"].eq(
            "subtract_historical_from_current_locality"
        )
    ]
    for row in reverse_policy.itertuples(index=False):
        target_id = clean_text(row.stat_area_id)
        locality_code = int(row.current_locality_code)
        target_indices = projected.index[
            projected["stat_area_id"] == target_id
        ].tolist()
        if len(target_indices) != 1:
            raise ValueError(
                f"Historical fallback boundary policy {target_id} resolved to "
                f"{len(target_indices)} historical targets"
            )
        base_candidate = base_candidates[locality_code]
        original_target = original_geometries[target_id]
        expected_overlap_share_pct = float(row.expected_overlap_share_pct)
        actual_overlap_share_pct = (
            original_target.intersection(base_candidate).area
            / base_candidate.area
            * 100
        )
        if (
            abs(actual_overlap_share_pct - expected_overlap_share_pct)
            > maximum_overlap_share_delta_pct
        ):
            raise ValueError(
                f"Historical fallback cutout {target_id} / loc:{locality_code} "
                f"expected {expected_overlap_share_pct:.3f}% overlap but found "
                f"{actual_overlap_share_pct:.3f}%"
            )
        current_candidate = fallback_override_candidates.get(
            locality_code, base_candidate
        )
        cut_geometry = valid_geometry(
            current_candidate.difference(original_target), projected.crs
        )
        if cut_geometry.is_empty or cut_geometry.geom_type not in {
            "Polygon",
            "MultiPolygon",
        }:
            raise ValueError(
                f"Historical fallback cutout empties or invalidates loc:{locality_code}"
            )
        fallback_override_candidates[locality_code] = cut_geometry
        fallback_override_targets.setdefault(locality_code, []).append(target_id)

    operation_sources: dict[str, list[str]] = {}
    approval_sources: dict[str, str] = {}
    replacement_targets: set[str] = set()
    cutout_candidates: dict[int, Any] = {}
    approved_no_overlap_candidates: dict[int, Any] = {}
    hidden_ids: set[str] = set()

    for row in vintage_policy.itertuples(index=False):
        operation = clean_text(row.operation)
        if operation == "subtract_historical_from_current_locality":
            continue
        target_id = clean_text(row.stat_area_id)
        locality_code = int(row.current_locality_code)
        target_indices = (
            []
            if operation == "approve_current_locality_no_overlap"
            else projected.index[projected["stat_area_id"] == target_id].tolist()
        )
        if (
            operation != "approve_current_locality_no_overlap"
            and len(target_indices) != 1
        ):
            raise ValueError(
                f"Historical locality boundary policy {target_id} resolved to "
                f"{len(target_indices)} targets"
            )

        row_hidden_ids = {
            value.strip()
            for value in clean_text(row.hidden_stat_area_ids).split("|")
            if value.strip()
        }
        missing_hidden_ids = row_hidden_ids - set(projected["stat_area_id"])
        if missing_hidden_ids:
            raise ValueError(
                f"Historical locality boundary policy {target_id} hides missing IDs: "
                f"{sorted(missing_hidden_ids)}"
            )
        if target_id and target_id in row_hidden_ids:
            raise ValueError(
                f"Historical locality boundary policy cannot hide its target: {target_id}"
            )
        if operation != "replace_with_current_locality" and row_hidden_ids:
            raise ValueError(
                f"Historical locality operation {operation} cannot hide other areas"
            )
        hidden_ids.update(row_hidden_ids)

        base_candidate = base_candidates[locality_code]
        candidate = fallback_override_candidates.get(locality_code, base_candidate)

        if operation == "approve_current_locality_no_overlap":
            approved_no_overlap_candidates[locality_code] = candidate
            approval_sources[f"loc:{locality_code}"] = (
                "reviewed_current_locality_no_overlap"
            )
            continue
        if operation == "replace_with_current_locality":
            projected.at[target_indices[0], "geometry"] = candidate
            source = f"reviewed_current_locality_boundary:loc:{locality_code}"
            replacement_targets.add(target_id)
        elif operation == "subtract_current_locality":
            expected_overlap_share_pct = float(row.expected_overlap_share_pct)
            original_target = original_geometries[target_id]
            actual_overlap_share_pct = (
                original_target.intersection(base_candidate).area
                / base_candidate.area
                * 100
            )
            if (
                abs(actual_overlap_share_pct - expected_overlap_share_pct)
                > maximum_overlap_share_delta_pct
            ):
                raise ValueError(
                    f"Historical locality cutout {target_id} / loc:{locality_code} "
                    f"expected {expected_overlap_share_pct:.3f}% overlap but found "
                    f"{actual_overlap_share_pct:.3f}%"
                )
            cut_geometry = valid_geometry(
                projected.at[target_indices[0], "geometry"].difference(candidate),
                projected.crs,
            )
            if cut_geometry.is_empty or cut_geometry.geom_type not in {
                "Polygon",
                "MultiPolygon",
            }:
                raise ValueError(
                    f"Historical locality cutout empties or invalidates {target_id}"
                )
            projected.at[target_indices[0], "geometry"] = cut_geometry
            source = f"reviewed_current_locality_cutout:loc:{locality_code}"
            cutout_candidates[locality_code] = candidate
        else:
            raise ValueError(
                f"Unsupported historical locality boundary operation: {operation}"
            )
        operation_sources.setdefault(target_id, []).append(source)

    applied_sources: dict[str, str] = dict(approval_sources)
    for target_id, sources in operation_sources.items():
        source = "|".join(sorted(set(sources)))
        target_index = projected.index[
            projected["stat_area_id"] == target_id
        ].tolist()[0]
        projected.at[target_index, "display_geometry_source"] = source
        applied_sources[target_id] = source

    conflicting_ids = hidden_ids & set(operation_sources)
    if conflicting_ids:
        raise ValueError(
            "Historical locality boundary policy both modifies and hides IDs: "
            f"{sorted(conflicting_ids)}"
        )
    for target_id in replacement_targets:
        target = projected[projected["stat_area_id"] == target_id].geometry.iloc[0]
        others = projected[
            ~projected["stat_area_id"].isin({target_id, *hidden_ids})
        ].reset_index(drop=True)
        failures: list[tuple[str, float]] = []
        for position in others.sindex.query(target, predicate="intersects"):
            other = others.iloc[position]
            overlap_area = target.intersection(other.geometry).area
            if overlap_area > maximum_overlap_m2:
                failures.append((str(other["stat_area_id"]), round(overlap_area, 3)))
        if failures:
            raise ValueError(
                f"Reviewed current boundary {target_id} overlaps historical display "
                f"areas: {failures[:10]}"
            )

    visible_historical = projected[
        ~projected["stat_area_id"].isin(hidden_ids)
    ].reset_index(drop=True)
    for locality_code, candidate in fallback_override_candidates.items():
        cutout_candidates.setdefault(locality_code, candidate)
    reviewed_candidates = [
        ("cutout", cutout_candidates),
        ("no-overlap approval", approved_no_overlap_candidates),
    ]
    for review_label, candidates in reviewed_candidates:
        for locality_code, candidate in candidates.items():
            failures: list[tuple[str, float]] = []
            candidate_historical = visible_historical[
                visible_historical["locality_code"] != locality_code
            ].reset_index(drop=True)
            for position in candidate_historical.sindex.query(
                candidate, predicate="intersects"
            ):
                historical = candidate_historical.iloc[position]
                overlap_area = candidate.intersection(historical.geometry).area
                if overlap_area > maximum_overlap_m2:
                    failures.append(
                        (str(historical["stat_area_id"]), round(overlap_area, 3))
                    )
            if failures:
                raise ValueError(
                    f"Reviewed locality {review_label} loc:{locality_code} still "
                    f"overlaps historical display areas: {failures[:10]}"
                )

    fallback_features: list[dict[str, Any]] = []
    fallback_metadata: list[dict[str, Any]] = []
    for locality_code, geometry in sorted(fallback_override_candidates.items()):
        properties = locality_properties[locality_code]
        target_ids = sorted(set(fallback_override_targets[locality_code]))
        source = "reviewed_historical_area_cutout:" + "|".join(target_ids)
        fallback_geography_id = (
            f"municipality-fallback:{vintage}:loc:{locality_code}"
        )
        fallback_features.append(
            {
                "fallback_geography_id": fallback_geography_id,
                "stat_area_vintage": vintage,
                "locality_id": properties["locality_id"],
                "locality_code": locality_code,
                "locality_name_he": properties["locality_name_he"],
                "locality_name_en": properties["locality_name_en"],
                "boundary_source": source,
                "subtracted_stat_area_ids": "|".join(target_ids),
                "geometry": geometry,
            }
        )
        fallback_metadata.append(
            {
                "fallback_geography_id": fallback_geography_id,
                "stat_area_vintage": vintage,
                "locality_id": properties["locality_id"],
                "locality_code": locality_code,
                "locality_name_he": properties["locality_name_he"],
                "locality_name_en": properties["locality_name_en"],
                "boundary_source": source,
                "subtracted_stat_area_ids": "|".join(target_ids),
                "original_area_m2": round(base_candidates[locality_code].area, 3),
                "display_area_m2": round(geometry.area, 3),
            }
        )
    fallback_geometries = (
        gpd.GeoDataFrame(
            fallback_features,
            columns=fallback_columns,
            geometry="geometry",
            crs=projected.crs,
        ).to_crs("EPSG:4326")
        if fallback_features
        else empty_fallback_geometries()
    )

    return (
        projected.to_crs("EPSG:4326"),
        applied_sources,
        sorted(hidden_ids),
        fallback_geometries,
        fallback_metadata,
    )


def write_geojson(stats: gpd.GeoDataFrame, path: Path) -> None:
    ensure_dir(path.parent)
    stats.to_file(path, driver="GeoJSON", encoding="utf-8", index=False)


def metadata_rows(official: gpd.GeoDataFrame) -> list[dict[str, Any]]:
    projected = official.to_crs("EPSG:2039")
    wgs84 = official.to_crs("EPSG:4326")
    rows: list[dict[str, Any]] = []
    for index, row in wgs84.iterrows():
        bounds = row.geometry.bounds
        rows.append(
            {
                "stat_area_id": row["stat_area_id"],
                "stat_area_vintage": row["stat_area_vintage"],
                "yishuv_stat": row["yishuv_stat"],
                "locality_id": row["locality_id"],
                "locality_code": row["locality_code"],
                "locality_name_he": row["locality_name_he"],
                "locality_name_en": row["locality_name_en"],
                "stat_area_number": row["stat_area_number"],
                "geometry_source": row.get("geometry_source", "official_cbs"),
                "geometry_area_m2": round(projected.loc[index].geometry.area, 3),
                "min_lon": bounds[0],
                "min_lat": bounds[1],
                "max_lon": bounds[2],
                "max_lat": bounds[3],
            }
        )
    return rows


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--simplify-tolerance", type=float, default=0.00005)
    args = parser.parse_args()

    detailed_by_locality = load_arcgis_detail_by_locality(
        ARCGIS_DIR,
        REVIEWED_WEST_BANK_DETAILS_PATH,
    )
    summary: dict[str, Any] = {
        "display_detail_localities_available": len(detailed_by_locality),
        "vintages": {},
    }
    source_vintages = {
        vintage: read_vintage(vintage) for vintage in sorted(VINTAGES)
    }
    if not HISTORICAL_COMPONENT_DISPLAY_POLICY_PATH.exists():
        raise FileNotFoundError(
            "Missing historical component display policy: "
            f"{HISTORICAL_COMPONENT_DISPLAY_POLICY_PATH}"
        )
    if not HISTORICAL_LOCALITY_BOUNDARY_POLICY_PATH.exists():
        raise FileNotFoundError(
            "Missing historical locality boundary policy: "
            f"{HISTORICAL_LOCALITY_BOUNDARY_POLICY_PATH}"
        )
    if not CURRENT_LOCALITIES_PATH.exists():
        raise FileNotFoundError(
            f"Missing current locality geometry: {CURRENT_LOCALITIES_PATH}"
        )
    if not CURRENT_LOCALITY_DISPLAY_PATH.exists():
        raise FileNotFoundError(
            "Missing current locality display geometry: "
            f"{CURRENT_LOCALITY_DISPLAY_PATH}"
        )
    component_display_policy = pd.read_csv(
        HISTORICAL_COMPONENT_DISPLAY_POLICY_PATH, dtype=str
    ).fillna("")
    required_component_policy_columns = {
        "election",
        "stat_area_vintage",
        "historical_footprint_locality_code",
        "component_locality_code",
        "boundary_rule",
        "note",
    }
    missing_component_policy_columns = required_component_policy_columns - set(
        component_display_policy.columns
    )
    if missing_component_policy_columns:
        raise ValueError(
            "Historical component display policy is missing columns: "
            f"{sorted(missing_component_policy_columns)}"
        )
    for column in [
        "stat_area_vintage",
        "historical_footprint_locality_code",
        "component_locality_code",
    ]:
        component_display_policy[column] = pd.to_numeric(
            component_display_policy[column], errors="raise"
        ).astype("int64")
    locality_boundary_policy = pd.read_csv(
        HISTORICAL_LOCALITY_BOUNDARY_POLICY_PATH, dtype=str
    ).fillna("")
    required_locality_boundary_columns = {
        "stat_area_vintage",
        "elections",
        "operation",
        "stat_area_id",
        "current_locality_code",
        "hidden_stat_area_ids",
        "expected_overlap_share_pct",
        "note",
    }
    missing_locality_boundary_columns = required_locality_boundary_columns - set(
        locality_boundary_policy.columns
    )
    if missing_locality_boundary_columns:
        raise ValueError(
            "Historical locality boundary policy is missing columns: "
            f"{sorted(missing_locality_boundary_columns)}"
        )
    for column in ["stat_area_vintage", "current_locality_code"]:
        locality_boundary_policy[column] = pd.to_numeric(
            locality_boundary_policy[column], errors="raise"
        ).astype("int64")
    allowed_locality_boundary_operations = {
        "approve_current_locality_no_overlap",
        "replace_with_current_locality",
        "subtract_historical_from_current_locality",
        "subtract_current_locality",
    }
    invalid_locality_boundary_operations = sorted(
        set(locality_boundary_policy["operation"])
        - allowed_locality_boundary_operations
    )
    if invalid_locality_boundary_operations:
        raise ValueError(
            "Historical locality boundary policy has invalid operations: "
            f"{invalid_locality_boundary_operations}"
        )
    duplicate_locality_boundary_operations = locality_boundary_policy.duplicated(
        subset=[
            "stat_area_vintage",
            "operation",
            "stat_area_id",
            "current_locality_code",
        ]
    )
    if duplicate_locality_boundary_operations.any():
        raise ValueError(
            "Historical locality boundary policy has duplicate operations"
        )
    replacement_policy = locality_boundary_policy[
        locality_boundary_policy["operation"].eq("replace_with_current_locality")
    ]
    if replacement_policy.duplicated(
        subset=["stat_area_vintage", "stat_area_id"]
    ).any():
        raise ValueError(
            "Historical locality boundary policy replaces the same target more than once"
        )
    target_operations = locality_boundary_policy[
        locality_boundary_policy["stat_area_id"].ne("")
    ]
    mixed_target_operations = (
        target_operations.groupby(
            ["stat_area_vintage", "stat_area_id"], sort=False
        )["operation"]
        .nunique()
        .gt(1)
    )
    if mixed_target_operations.any():
        raise ValueError(
            "Historical locality boundary policy mixes replacement and cutout "
            "operations on one target"
        )
    cutout_policy = locality_boundary_policy[
        locality_boundary_policy["operation"].isin(
            [
                "subtract_current_locality",
                "subtract_historical_from_current_locality",
            ]
        )
    ]
    cutout_overlap_shares = pd.to_numeric(
        cutout_policy["expected_overlap_share_pct"], errors="coerce"
    )
    if (
        cutout_overlap_shares.isna().any()
        or cutout_overlap_shares.le(0).any()
        or cutout_overlap_shares.gt(100).any()
    ):
        raise ValueError(
            "Historical locality cutouts require an expected overlap share in (0, 100]"
        )
    no_overlap_policy = locality_boundary_policy[
        locality_boundary_policy["operation"].eq(
            "approve_current_locality_no_overlap"
        )
    ]
    no_overlap_shares = pd.to_numeric(
        no_overlap_policy["expected_overlap_share_pct"], errors="coerce"
    )
    if (
        no_overlap_policy["stat_area_id"].ne("").any()
        or no_overlap_policy["hidden_stat_area_ids"].ne("").any()
        or no_overlap_shares.isna().any()
        or no_overlap_shares.ne(0).any()
    ):
        raise ValueError(
            "Historical no-overlap approvals require a blank target, no hidden "
            "areas, and an expected overlap share of zero"
        )
    geometry_operations = locality_boundary_policy[
        locality_boundary_policy["operation"].ne(
            "approve_current_locality_no_overlap"
        )
    ]
    if geometry_operations["stat_area_id"].eq("").any():
        raise ValueError(
            "Historical locality geometry operations require a target area ID"
        )
    current_localities = gpd.read_file(CURRENT_LOCALITIES_PATH, engine="pyogrio")
    current_locality_display = gpd.read_file(
        CURRENT_LOCALITY_DISPLAY_PATH, engine="pyogrio"
    )
    component_display_frames: list[gpd.GeoDataFrame] = []
    component_display_metadata: list[dict[str, Any]] = []
    locality_fallback_frames: list[gpd.GeoDataFrame] = []
    locality_fallback_metadata: list[dict[str, Any]] = []
    display_group_marker_ids = load_display_group_marker_ids()
    for vintage in sorted(VINTAGES):
        official, alias_rows, source_inventory = source_vintages[vintage]
        official = official.copy()
        alias_rows = list(alias_rows)
        supplements: list[dict[str, Any]] = []
        if vintage == 1995:
            official, supplements = add_1995_transition_unions(official)
            official, reverse_supplements = add_1995_reverse_transition_unions(
                official,
                source_vintages[2008][0],
            )
            supplements.extend(reverse_supplements)
        elif vintage == 2011:
            official, supplements = add_2011_arcgis_exact_id_supplements(official)
        alias_rows.extend(supplements)
        validate_vintage(official, vintage)
        component_features, component_metadata = (
            build_historical_component_display_geometries(
                official,
                current_localities,
                component_display_policy,
                vintage,
            )
        )
        if not component_features.empty:
            component_display_frames.append(component_features)
            component_display_metadata.extend(component_metadata)
        official_wgs84 = official.to_crs("EPSG:4326")
        display, replacements, rejected_codes = apply_detailed_display_geometries(
            official,
            detailed_by_locality,
            "official_cbs",
            DISPLAY_DETAIL_OVERLAY_CODES.get(vintage, set()),
        )
        display, geometry_representatives = apply_display_geometry_representatives(
            display,
            DISPLAY_GEOMETRY_REPRESENTATIVE_SOURCES.get(vintage, {}),
        )
        (
            display,
            current_locality_boundary_overrides,
            boundary_hidden_display_ids,
            locality_fallback_overrides,
            vintage_locality_fallback_metadata,
        ) = apply_reviewed_current_locality_boundaries(
            display,
            current_locality_display,
            locality_boundary_policy,
            vintage,
        )
        if not locality_fallback_overrides.empty:
            locality_fallback_frames.append(locality_fallback_overrides)
            locality_fallback_metadata.extend(vintage_locality_fallback_metadata)
        display["display_mode"] = ""
        marker_ids = set(NON_EXCLUSIVE_DISPLAY_MARKERS.get(vintage, set())) | set(
            display_group_marker_ids.get(vintage, set())
        )
        missing_marker_ids = marker_ids - set(official["stat_area_id"])
        if missing_marker_ids:
            raise ValueError(
                f"{vintage} display policy references missing areas: "
                f"{sorted(missing_marker_ids)}"
            )
        validate_supplement_overlap_markers(
            official,
            vintage,
            marker_ids,
        )
        display.loc[display["stat_area_id"].isin(marker_ids), "display_mode"] = "marker"
        official_public = public_columns(official_wgs84)
        display_public = public_columns(display)

        write_geojson(
            official_public,
            OUT_DIR / f"statistical_areas_{vintage}.geojson",
        )
        display_output = (
            display_public
            if vintage in UNSIMPLIFIED_DISPLAY_VINTAGES
            else (
                simplify_official_coverages(
                    display_public,
                    args.simplify_tolerance,
                )
                if vintage == 2011
                else simplify(display_public, args.simplify_tolerance)
            )
        )
        if vintage in UNSIMPLIFIED_DISPLAY_VINTAGES:
            validate_no_material_display_overlaps(
                display_output,
                vintage,
                ignored_ids=set(boundary_hidden_display_ids),
            )
        if vintage == 2011:
            validate_official_locality_coverages(display_output, vintage)
        write_geojson(
            display_output,
            OUT_DIR / f"statistical_areas_{vintage}.display.simplified.geojson",
        )
        rows = metadata_rows(official)
        write_csv(
            OUT_DIR / f"statistical_areas_{vintage}.metadata.csv",
            rows,
            list(rows[0].keys()) if rows else [],
        )
        write_csv(
            OUT_DIR / f"statistical_areas_{vintage}.aliases.csv",
            alias_rows,
            list(alias_rows[0].keys()) if alias_rows else [],
        )
        summary["vintages"][str(vintage)] = {
            "features": len(official),
            "localities": int(official["locality_code"].nunique()),
            "source_area_aliases": len(alias_rows),
            "assignment_geometry_supplements": len(supplements),
            "display_geometry_replacements": replacements,
            "display_geometry_rejected_codes": sorted(set(rejected_codes)),
            "non_exclusive_display_markers": sorted(marker_ids),
            "display_geometry_representative_sources": geometry_representatives,
            "current_locality_boundary_overrides": current_locality_boundary_overrides,
            "current_locality_fallback_geometry_overrides": len(
                locality_fallback_overrides
            ),
            "boundary_override_hidden_ids": boundary_hidden_display_ids,
            "display_geometry_simplified": vintage not in UNSIMPLIFIED_DISPLAY_VINTAGES,
            "source_inventory_audit": source_inventory,
            "bounds_wgs84": {
                "min_lon": float(official_wgs84.total_bounds[0]),
                "min_lat": float(official_wgs84.total_bounds[1]),
                "max_lon": float(official_wgs84.total_bounds[2]),
                "max_lat": float(official_wgs84.total_bounds[3]),
            },
        }
        print(
            f"{vintage}: features={len(official)} localities={official['locality_code'].nunique()} "
            f"display_replacements={replacements}"
        )

    if not component_display_frames:
        raise ValueError("Historical component display policy produced no geometries")
    component_display_geometries = gpd.GeoDataFrame(
        pd.concat(component_display_frames, ignore_index=True),
        geometry="geometry",
        crs="EPSG:4326",
    )
    expected_component_display_ids = {
        f"municipality-component-fallback:{int(row.stat_area_vintage)}:"
        f"loc:{int(row.component_locality_code)}"
        for row in component_display_policy.itertuples(index=False)
    }
    actual_component_display_ids = set(
        component_display_geometries["fallback_geography_id"]
    )
    if actual_component_display_ids != expected_component_display_ids:
        raise ValueError(
            "Historical component display geometry IDs do not match policy: "
            f"missing={sorted(expected_component_display_ids - actual_component_display_ids)} "
            f"extra={sorted(actual_component_display_ids - expected_component_display_ids)}"
        )
    write_geojson(
        component_display_geometries,
        HISTORICAL_COMPONENT_DISPLAY_GEOMETRIES_PATH,
    )
    write_csv(
        HISTORICAL_COMPONENT_DISPLAY_METADATA_PATH,
        component_display_metadata,
        list(component_display_metadata[0].keys()),
    )
    summary["historical_composite_component_display_geometries"] = {
        "features": len(component_display_geometries),
        "policy": str(HISTORICAL_COMPONENT_DISPLAY_POLICY_PATH.relative_to(ROOT)),
        "geometry": str(
            HISTORICAL_COMPONENT_DISPLAY_GEOMETRIES_PATH.relative_to(ROOT)
        ),
        "metadata": str(
            HISTORICAL_COMPONENT_DISPLAY_METADATA_PATH.relative_to(ROOT)
        ),
    }
    locality_fallback_geometries = (
        gpd.GeoDataFrame(
            pd.concat(locality_fallback_frames, ignore_index=True),
            geometry="geometry",
            crs="EPSG:4326",
        )
        if locality_fallback_frames
        else gpd.GeoDataFrame(
            columns=[
                "fallback_geography_id",
                "stat_area_vintage",
                "locality_id",
                "locality_code",
                "locality_name_he",
                "locality_name_en",
                "boundary_source",
                "subtracted_stat_area_ids",
                "geometry",
            ],
            geometry="geometry",
            crs="EPSG:4326",
        )
    )
    if locality_fallback_geometries["fallback_geography_id"].duplicated().any():
        raise ValueError("Historical locality fallback overrides have duplicate IDs")
    write_geojson(
        locality_fallback_geometries,
        HISTORICAL_LOCALITY_FALLBACK_GEOMETRIES_PATH,
    )
    write_csv(
        HISTORICAL_LOCALITY_FALLBACK_METADATA_PATH,
        locality_fallback_metadata,
        list(locality_fallback_metadata[0].keys())
        if locality_fallback_metadata
        else [
            "fallback_geography_id",
            "stat_area_vintage",
            "locality_id",
            "locality_code",
            "locality_name_he",
            "locality_name_en",
            "boundary_source",
            "subtracted_stat_area_ids",
            "original_area_m2",
            "display_area_m2",
        ],
    )
    summary["historical_locality_fallback_display_geometries"] = {
        "features": len(locality_fallback_geometries),
        "policy": str(HISTORICAL_LOCALITY_BOUNDARY_POLICY_PATH.relative_to(ROOT)),
        "geometry": str(
            HISTORICAL_LOCALITY_FALLBACK_GEOMETRIES_PATH.relative_to(ROOT)
        ),
        "metadata": str(
            HISTORICAL_LOCALITY_FALLBACK_METADATA_PATH.relative_to(ROOT)
        ),
    }
    write_json(OUT_DIR / "historical_geography_build_summary.json", summary)


if __name__ == "__main__":
    main()
