from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

LOCAL_PYTHON = Path(__file__).resolve().parents[1] / ".local" / "python-geo"
if LOCAL_PYTHON.exists():
    sys.path.insert(0, str(LOCAL_PYTHON))

import geopandas as gpd
import pandas as pd
from shapely.geometry import mapping
from shapely.ops import unary_union


ROOT = Path(__file__).resolve().parents[1]
GENERATED_FALLBACK_PATH = (
    ROOT
    / "data"
    / "processed"
    / "audits"
    / "statistical_area_polling_group_fallbacks.csv"
)
REVIEWED_LOCALITY_DISPLAY_PATH = (
    ROOT
    / "data"
    / "processed"
    / "audits"
    / "reviewed_locality_statistical_displays.csv"
)
MANUAL_REVIEW_PATH = (
    ROOT
    / "data"
    / "manual"
    / "statistical_area_result_display_reviews.csv"
)
SOURCE_PATHS = [
    ROOT
    / "data"
    / "processed"
    / "geographies"
    / f"statistical_areas_{vintage}.display.simplified.geojson"
    for vintage in (1995, 2008, 2011, 2022)
]
OUTPUT_PATH = (
    ROOT
    / "data"
    / "processed"
    / "geographies"
    / "statistical_area_result_aggregates.geojson"
)
METADATA_PATH = (
    ROOT
    / "data"
    / "processed"
    / "geographies"
    / "statistical_area_result_aggregates.metadata.csv"
)
METRIC_CRS = "EPSG:2039"
ADJACENCY_TOLERANCE_METERS = 1.0
METADATA_FIELDS = [
    "display_geography_id",
    "election",
    "elections",
    "locality_code",
    "locality_name_he",
    "locality_name_en",
    "component_locality_codes",
    "component_locality_names_he",
    "component_locality_names_en",
    "component_count",
    "component_stat_area_ids",
    "component_stat_area_numbers",
    "component_adjacency",
    "geometry_part_count",
    "aggregation_method",
    "evidence_group_id",
    "evidence_class",
    "review_status",
    "note",
]


def split_pipe(value: str) -> list[str]:
    return [part.strip() for part in str(value or "").split("|") if part.strip()]


def optional_value(row: dict[str, str], field: str) -> str:
    return str(row.get(field) or "").strip()


def is_connected(geometries: list, tolerance_meters: float) -> bool:
    if len(geometries) < 2:
        return True
    projected = gpd.GeoSeries(geometries, crs="EPSG:4326").to_crs(METRIC_CRS)
    neighbors: dict[int, set[int]] = defaultdict(set)
    for left_index, left in enumerate(projected):
        for right_index in range(left_index + 1, len(projected)):
            right = projected.iloc[right_index]
            if left.distance(right) <= tolerance_meters:
                neighbors[left_index].add(right_index)
                neighbors[right_index].add(left_index)

    visited = {0}
    pending = [0]
    while pending:
        current = pending.pop()
        for neighbor in neighbors[current]:
            if neighbor not in visited:
                visited.add(neighbor)
                pending.append(neighbor)
    return len(visited) == len(geometries)


def dissolved_component_geometry(geometries: list[object]) -> dict[str, object]:
    """Dissolve shared borders so an aggregate is drawn as one map area."""
    dissolved = unary_union(geometries)
    if dissolved.is_empty:
        raise ValueError("Display aggregate has no polygon components")
    if dissolved.geom_type not in {"Polygon", "MultiPolygon"}:
        raise ValueError(
            f"Unsupported dissolved aggregate geometry: {dissolved.geom_type}"
        )
    return mapping(dissolved)


def write_csv(
    path: Path,
    rows: list[dict[str, object]],
    fieldnames: list[str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames or list(rows[0]),
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    with GENERATED_FALLBACK_PATH.open(
        encoding="utf-8-sig", newline=""
    ) as handle:
        configured_groups = list(csv.DictReader(handle))
    if REVIEWED_LOCALITY_DISPLAY_PATH.exists():
        with REVIEWED_LOCALITY_DISPLAY_PATH.open(
            encoding="utf-8-sig", newline=""
        ) as handle:
            configured_groups.extend(csv.DictReader(handle))
    if MANUAL_REVIEW_PATH.exists():
        with MANUAL_REVIEW_PATH.open(
            encoding="utf-8-sig", newline=""
        ) as handle:
            configured_groups.extend(csv.DictReader(handle))
    if not configured_groups:
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(
            json.dumps(
                {
                    "type": "FeatureCollection",
                    "name": "statistical_area_result_aggregates",
                    "features": [],
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
        write_csv(METADATA_PATH, [], METADATA_FIELDS)
        print("generated 0 statistical-area result fallbacks")
        return

    source_frames: list[gpd.GeoDataFrame] = []
    for source_path in SOURCE_PATHS:
        source_frame = gpd.read_file(source_path, engine="pyogrio")
        if "stat_area_number" not in source_frame:
            source_frame["stat_area_number"] = source_frame["stat_2022"]
        if source_frame.crs is None:
            source_frame = source_frame.set_crs("EPSG:4326")
        source_frames.append(source_frame.to_crs("EPSG:4326"))
    source = gpd.GeoDataFrame(
        pd.concat(source_frames, ignore_index=True),
        geometry="geometry",
        crs="EPSG:4326",
    )
    source_by_id = source.set_index("stat_area_id", drop=False)

    features: list[dict[str, object]] = []
    metadata_rows: list[dict[str, object]] = []
    seen_display_ids: set[str] = set()
    component_owners: dict[str, dict[str, str]] = defaultdict(dict)

    for row in configured_groups:
        display_id = str(row["display_geography_id"]).strip()
        election_ids = split_pipe(row["elections"])
        component_ids = split_pipe(row["component_stat_area_ids"])
        aggregation_method = str(row["aggregation_method"]).strip()
        review_status = str(row["review_status"]).strip()

        if not display_id or display_id in seen_display_ids:
            raise ValueError(f"Duplicate or blank display aggregate ID: {display_id!r}")
        if len(election_ids) != 1:
            raise ValueError(f"{display_id} must be scoped to exactly one election")
        if len(component_ids) < 2:
            raise ValueError(f"{display_id} must contain at least two statistical areas")
        if aggregation_method != "sum-components":
            raise ValueError(f"{display_id} has unsupported aggregation method {aggregation_method!r}")
        if review_status not in {
            "approved-high-confidence",
            "approved-rule-fallback",
        }:
            raise ValueError(f"{display_id} is not approved for display")

        election_id = election_ids[0]
        for component_id in component_ids:
            owner = component_owners[election_id].get(component_id)
            if owner:
                raise ValueError(
                    f"{election_id} component {component_id} is reused by {owner} and {display_id}"
                )
            component_owners[election_id][component_id] = display_id
            if component_id not in source_by_id.index:
                raise ValueError(f"{display_id} references unavailable area {component_id}")

        components = source_by_id.loc[component_ids]
        evidence_class = str(row["evidence_class"]).strip()
        locality_codes = {str(value) for value in components["locality_code"]}
        allow_cross_locality = evidence_class in {
            "official_register_attachment_exact",
            "official_register_attachment_representative",
            "reviewed_cross_election_polling_network",
        }
        if len(locality_codes) != 1 and not allow_cross_locality:
            raise ValueError(f"{display_id} crosses locality codes: {sorted(locality_codes)}")

        geometries = list(components.geometry)
        display_geometry = dissolved_component_geometry(geometries)
        part_count = (
            1
            if display_geometry["type"] == "Polygon"
            else len(display_geometry["coordinates"])
        )
        adjacency = (
            "connected"
            if is_connected(geometries, ADJACENCY_TOLERANCE_METERS)
            else "disconnected"
        )

        first = components.iloc[0]
        locality_code = optional_value(row, "display_locality_code") or str(
            first["locality_code"]
        )
        locality_name_he = optional_value(row, "display_locality_name_he") or str(
            first["locality_name_he"]
        ).strip()
        locality_name_en = optional_value(row, "display_locality_name_en") or str(
            first["locality_name_en"]
        ).strip()
        area_numbers = [str(int(value)) for value in components["stat_area_number"]]
        area_label = ", ".join(area_numbers)
        name_he = optional_value(row, "display_name_he") or (
            f"{locality_name_he} · {area_label}"
        )
        name_en = optional_value(row, "display_name_en") or (
            f"{locality_name_en} · {area_label}"
        )
        if evidence_class == "official_register_attachment_exact":
            notice_he = ""
            notice_en = ""
        elif evidence_class == "official_register_attachment_representative":
            notice_he = (
                "לא ניתן לשייך את הקולות לאזורים אלה בנפרד. "
                "התוצאה מוצגת על קבוצה מצומצמת לפי צירופי הקלפיות ברשימה הרשמית."
            )
            notice_en = (
                "Votes cannot be split between these areas. The result is shown on a "
                "compact group using the official polling-register attachments."
            )
        elif evidence_class == "reviewed_polling_network_residual":
            notice_he = (
                f"תוצאות האזורים הסטטיסטיים {area_label} מוצגות יחד. "
                "רשימות הקלפיות הרשמיות לפני ואחרי האיזון מקשרות את הקלפיות "
                "בין האזורים, אך אינן מאפשרות לשחזר חלוקה אמינה ביניהם."
            )
            notice_en = (
                f"Results for statistical areas {area_label} are shown together. "
                "The official planned and final polling registers connect the ballots "
                "across these areas but do not support a reliable internal split."
            )
        elif evidence_class == "reviewed_cross_election_polling_network":
            notice_he = (
                f"תוצאות האזורים הסטטיסטיים {area_label} מוצגות יחד. "
                "רשת הקלפיות מתועדת ברשימות הרשמיות של הבחירות הסמוכות, "
                "ומיפויי הקלפיות הרשמיים אינם חוצים את גבול הקבוצה; "
                "אין מקור שמאפשר חלוקה פנימית אמינה."
            )
            notice_en = (
                f"Results for statistical areas {area_label} are shown together. "
                "Official registers in the adjacent elections document this polling network, "
                "and the official ballot mappings do not cross its boundary; "
                "no source supports a reliable internal split."
            )
        elif evidence_class == "reviewed_polling_network_near_balance":
            differences = {"K24": (18, "0.07%"), "K25": (26, "0.14%")}
            difference, percentage = differences[election_id]
            notice_he = (
                f"תוצאות {len(component_ids)} האזורים הסטטיסטיים האלה מוצגות יחד. "
                "רשימות הקלפיות המתוכננות והתוצאות הסופיות יוצרות רשת סגורה; "
                f"סך בעלי זכות הבחירה שונה ב-{difference} בלבד ({percentage}), "
                "אך אין מקור שמאפשר לשחזר את החלוקה הפנימית."
            )
            notice_en = (
                f"Results for these {len(component_ids)} statistical areas are shown together. "
                "The official planned register and final results form a closed network; "
                f"their eligible-voter totals differ by only {difference} ({percentage}), "
                "but no source supports reconstructing the internal split."
            )
        elif evidence_class == "representative_ownership_impossible":
            notice_he = (
                f"תוצאות האזורים הסטטיסטיים {area_label} מוצגות יחד. "
                "קיימות יותר קבוצות קלפיות מפוליגונים זמינים, או שלכמה קבוצות יש "
                "אותו פוליגון מועמד יחיד; לכן אי אפשר להציג כל תוצאה פעם אחת בלי "
                "חפיפה. ספירת הקולות היא סכום מדויק, לא חלוקה משוערת."
            )
            notice_en = (
                f"Results for statistical areas {area_label} are shown together. "
                "There are more polling groups than available polygons, or multiple "
                "groups have the same sole candidate polygon, so each exact result "
                "cannot be placed once without overlap. The displayed total is an "
                "exact sum, not an estimated split."
            )
        else:
            notice_he = (
                f"התוצאה משלבת את האזורים הסטטיסטיים {area_label} בבחירות האלה. "
                "המקורות הרשמיים מראים שקבוצת הקלפיות שייכת לאזורים האלה יחד, "
                "אך אינם מאפשרים לפצל את התוצאה ביניהם באופן אמין."
            )
            notice_en = (
                f"This result combines statistical areas {area_label} for this election. "
                "The official sources place the polling group within these areas collectively, "
                "but do not support a reliable split between them."
            )
        configured_notice_he = optional_value(row, "notice_he")
        configured_notice_en = optional_value(row, "notice_en")
        if configured_notice_he:
            notice_he = configured_notice_he
        if configured_notice_en:
            notice_en = configured_notice_en
        if adjacency == "disconnected" and (notice_he or notice_en):
            notice_he += " הפוליגונים המרכיבים אינם צמודים זה לזה."
            notice_en += " The component polygons are not adjacent."

        geometry_source = (
            evidence_class
            if evidence_class.startswith("reviewed_")
            else f"reviewed_{evidence_class}"
        )
        component_locality_codes = "|".join(
            dict.fromkeys(str(value) for value in components["locality_code"])
        )
        component_locality_names_he = "|".join(
            dict.fromkeys(str(value).strip() for value in components["locality_name_he"])
        )
        component_locality_names_en = "|".join(
            dict.fromkeys(str(value).strip() for value in components["locality_name_en"])
        )
        properties = {
            "custom_id": display_id,
            "custom_key": display_id,
            "name_he": name_he,
            "name_en": name_en,
            "display_mode": "polygon",
            "geometry_source": geometry_source,
            "elections": election_id,
            "locality_code": locality_code,
            "component_locality_codes": component_locality_codes,
            "component_locality_names_he": component_locality_names_he,
            "component_locality_names_en": component_locality_names_en,
            "component_stat_area_ids": "|".join(component_ids),
            "component_stat_area_numbers": "|".join(area_numbers),
            "component_adjacency": adjacency,
            "geometry_part_count": part_count,
            "aggregation_method": aggregation_method,
            "evidence_group_id": str(row["evidence_group_id"]).strip(),
            "evidence_class": evidence_class,
            "review_status": review_status,
            "notice_he": notice_he,
            "notice_en": notice_en,
            "note": str(row["note"]).strip(),
        }
        features.append(
            {
                "type": "Feature",
                "id": display_id,
                "properties": properties,
                "geometry": display_geometry,
            }
        )
        metadata_rows.append(
            {
                "display_geography_id": display_id,
                "election": election_id,
                "elections": election_id,
                "locality_code": locality_code,
                "locality_name_he": locality_name_he,
                "locality_name_en": locality_name_en,
                "component_locality_codes": component_locality_codes,
                "component_locality_names_he": component_locality_names_he,
                "component_locality_names_en": component_locality_names_en,
                "component_count": len(component_ids),
                "component_stat_area_ids": "|".join(component_ids),
                "component_stat_area_numbers": "|".join(area_numbers),
                "component_adjacency": adjacency,
                "geometry_part_count": part_count,
                "aggregation_method": aggregation_method,
                "evidence_group_id": str(row["evidence_group_id"]).strip(),
                "evidence_class": evidence_class,
                "review_status": review_status,
                "note": str(row["note"]).strip(),
            }
        )
        seen_display_ids.add(display_id)

    feature_collection = {
        "type": "FeatureCollection",
        "name": "statistical_area_result_aggregates",
        "features": features,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        f"{json.dumps(feature_collection, ensure_ascii=False, separators=(',', ':'))}\n",
        encoding="utf-8",
    )
    write_csv(METADATA_PATH, metadata_rows)

    election_counts = Counter(row["election"] for row in metadata_rows)
    adjacency_counts = Counter(row["component_adjacency"] for row in metadata_rows)
    print(
        "built "
        f"{len(features)} statistical-area result aggregates "
        f"({dict(sorted(election_counts.items()))}; {dict(sorted(adjacency_counts.items()))})"
    )


if __name__ == "__main__":
    main()
