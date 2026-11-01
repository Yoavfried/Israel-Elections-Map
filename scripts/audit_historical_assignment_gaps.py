from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

LOCAL_PYTHON = Path(__file__).resolve().parents[1] / ".local" / "python-geo"
if LOCAL_PYTHON.exists():
    sys.path.insert(0, str(LOCAL_PYTHON))

import geopandas as gpd
import pandas as pd

from pipeline_common import MANUAL_DIR, PROCESSED_DIR, RAW_DIR, write_csv, write_json


ASSIGNMENTS = PROCESSED_DIR / "assignments" / "ballot_geography_assignments.csv"
HISTORICAL_ASSIGNMENTS = (
    PROCESSED_DIR / "assignments" / "historical_ballot_assignments.csv"
)
HISTORICAL_CROSSWALK = (
    PROCESSED_DIR / "assignments" / "historical_ballot_crosswalk.csv"
)
GEOGRAPHY_DIR = PROCESSED_DIR / "geographies"
ARCGIS_LOCALITY_AUDIT = (
    PROCESSED_DIR / "audits" / "arcgis_assignment_reconstruction_localities.csv"
)
OMITTED_ORDINARY_BALLOT_REVIEWS = (
    MANUAL_DIR / "omitted_ordinary_ballot_reviews.csv"
)
OUT_DIR = PROCESSED_DIR / "audits"

ELECTION_VINTAGES = {
    "K17": 1995,
    "K18": 2008,
    "K19": 2011,
    "K20": 2011,
    "K21": 2011,
    "K22": 2011,
    "K23": 2011,
    "K24": 2011,
    "K25": 2011,
}
PENDING_STATUSES = {
    "no_direct_historical_assignment",
    "crosswalk_area_missing_geometry",
    "unresolved",
}

DEMOGRAPHY_CONFIG = {
    2008: {
        "path": RAW_DIR
        / "cbs_historical_geography"
        / "extracted"
        / "statisticalareas_demography2008.gdb",
        "layer": "statisticalareas_demography2008",
        "area_id": "YISHUV_STAT08",
        "population": "Pop_Total",
        "age_20_plus": ["age_20_29", "age_30_64", "age_65_up"],
        "scale": 1000,
        "reference_year": 2008,
        "source": "CBS 2008 Census statistical-area demographics",
    },
    2011: {
        "path": RAW_DIR
        / "cbs_historical_geography"
        / "extracted"
        / "statisticalareas_2020_demography.gdb",
        "layer": "statisticalareas_2020_demography",
        "area_id": "YISHUV_STAT11",
        "population": "Pop_Total",
        "age_20_plus": [
            "age_20_24",
            "age_25_29",
            "age_30_34",
            "age_35_39",
            "age_40_44",
            "age_45_49",
            "age_50_54",
            "age_55_59",
            "age_60_64",
            "age_65_69",
            "age_70_74",
            "age_75_79",
            "age_80_84",
            "age_85_up",
        ],
        "scale": 1,
        "reference_year": 2020,
        "source": "CBS 2020 demographics on 2011 statistical-area boundaries",
    },
}

ARCGIS_CONFIG = {
    "K20": {
        "path": RAW_DIR / "arcgis" / "elections2015_statistical_areas.geojson",
        "area_id": "YeshuvStat",
        "locality_code": "SemelYeshuv",
        "stat_area": "StatZone",
        "ballot_count": "kalpiot_no",
        "eligible_voters": "בזב",
        "actual_voters": "מצביעים",
    },
    "K21": {
        "path": RAW_DIR / "arcgis" / "elections2019_statistical_areas.geojson",
        "area_id": "CityStat11",
        "locality_code": "CityCode",
        "stat_area": "StatZone11",
        "ballot_count": "NumKalpi",
        "eligible_voters": "Bazab",
        "actual_voters": "Voters",
    },
}


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, dtype=str, encoding="utf-8-sig").fillna("")


def integer(value: Any) -> int:
    if value in (None, "") or pd.isna(value):
        return 0
    return int(round(float(str(value).replace(",", ""))))


def normalized_code(value: Any) -> str:
    if value in (None, "") or pd.isna(value):
        return ""
    try:
        return str(int(float(str(value))))
    except ValueError:
        return ""


def normalized_name(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def csv_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return frame.where(pd.notna(frame), "").to_dict("records")


def write_frame(path: Path, frame: pd.DataFrame) -> None:
    write_csv(path, csv_records(frame), list(frame.columns))


def load_metadata() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for vintage in sorted(set(ELECTION_VINTAGES.values())):
        frame = read_csv(
            GEOGRAPHY_DIR / f"statistical_areas_{vintage}.metadata.csv"
        )
        frame["stat_area_vintage"] = str(vintage)
        frame["locality_code"] = frame["locality_code"].map(normalized_code)
        frames.append(frame)
    metadata = pd.concat(frames, ignore_index=True, sort=False).fillna("")
    if metadata["stat_area_id"].duplicated().any():
        duplicates = metadata.loc[
            metadata["stat_area_id"].duplicated(keep=False), "stat_area_id"
        ].tolist()
        raise ValueError(f"Duplicate historical statistical-area IDs: {duplicates[:10]}")
    return metadata


def load_population_proxies() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for vintage, config in DEMOGRAPHY_CONFIG.items():
        source = gpd.read_file(
            config["path"],
            layer=str(config["layer"]),
            engine="pyogrio",
            ignore_geometry=True,
        )
        area_ids = pd.to_numeric(source[config["area_id"]], errors="coerce")
        population = pd.to_numeric(source[config["population"]], errors="coerce")
        ages = source[config["age_20_plus"]].apply(
            pd.to_numeric, errors="coerce"
        )
        for index in source.index[area_ids.notna()]:
            area_id = int(round(float(area_ids.loc[index])))
            population_value = population.loc[index]
            age_values = ages.loc[index]
            scale = int(config["scale"])
            rows.append(
                {
                    "stat_area_id": f"stat{vintage}:{area_id}",
                    "population_proxy": (
                        int(round(float(population_value) * scale))
                        if pd.notna(population_value)
                        else ""
                    ),
                    "age_20_plus_population_proxy": (
                        int(round(float(age_values.sum()) * scale))
                        if age_values.notna().all()
                        else ""
                    ),
                    "population_reference_year": config["reference_year"],
                    "population_proxy_source": config["source"],
                }
            )
    proxies = pd.DataFrame(rows)
    if proxies["stat_area_id"].duplicated().any():
        raise ValueError("Demographic source contains duplicate statistical-area IDs")
    return proxies


def load_arcgis_area_totals(
    metadata: pd.DataFrame,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    aliases = read_csv(GEOGRAPHY_DIR / "statistical_areas_2011.aliases.csv")
    source_to_canonical = {
        integer(row["source_yishuv_stat"]): row["canonical_stat_area_id"]
        for row in aliases.to_dict("records")
    }
    published_counts = (
        metadata[metadata["stat_area_vintage"] == "2011"]
        .groupby("locality_code")["stat_area_id"]
        .nunique()
        .to_dict()
    )
    rows: list[dict[str, Any]] = []
    missing_aliases: list[dict[str, Any]] = []
    for election, config in ARCGIS_CONFIG.items():
        collection = json.loads(Path(config["path"]).read_text(encoding="utf-8"))
        features = collection.get("features", [])
        feature_counts: dict[str, int] = {}
        for feature in features:
            properties = feature.get("properties") or {}
            locality_code = normalized_code(properties.get(config["locality_code"]))
            feature_counts[locality_code] = feature_counts.get(locality_code, 0) + 1
        for feature in features:
            properties = feature.get("properties") or {}
            source_area_id = integer(properties.get(config["area_id"]))
            locality_code = normalized_code(properties.get(config["locality_code"]))
            source_stat_area_number = integer(properties.get(config["stat_area"]))
            source_feature_count = feature_counts.get(locality_code, 0)
            published_stat_areas = int(published_counts.get(locality_code, 0))
            stat_area_id = source_to_canonical.get(source_area_id, "")
            if not stat_area_id:
                missing_aliases.append(
                    {
                        "election": election,
                        "source_area_id": source_area_id,
                    }
                )
                continue
            if source_feature_count == 1 and published_stat_areas > 1:
                comparison_status = "dissolved_locality_aggregate"
                comparison_explanation = (
                    "The ArcGIS layer has one feature for a locality with multiple "
                    "published 2011 statistical areas. It is a locality aggregate and "
                    "cannot be compared with the aliased area polygon."
                )
            elif published_stat_areas == 1:
                comparison_status = "single_statistical_area_locality"
                comparison_explanation = (
                    "The locality has one published 2011 statistical area, so the "
                    "ArcGIS locality total is also an area total."
                )
            else:
                comparison_status = "detailed_statistical_area"
                comparison_explanation = (
                    "The ArcGIS layer contains multiple features for this locality; "
                    "this record identifies one statistical area."
                )
            rows.append(
                {
                    "election": election,
                    "stat_area_id": stat_area_id,
                    "arcgis_source_area_id": source_area_id,
                    "arcgis_source_locality_code": locality_code,
                    "arcgis_source_stat_area_number": source_stat_area_number,
                    "arcgis_locality_feature_count": source_feature_count,
                    "arcgis_published_stat_areas": published_stat_areas,
                    "arcgis_comparison_status": comparison_status,
                    "arcgis_comparison_explanation": comparison_explanation,
                    "arcgis_ballot_count": integer(
                        properties.get(config["ballot_count"])
                    ),
                    "arcgis_eligible_voters": integer(
                        properties.get(config["eligible_voters"])
                    ),
                    "arcgis_actual_voters": integer(
                        properties.get(config["actual_voters"])
                    ),
                }
            )
    totals = pd.DataFrame(rows)
    if totals.duplicated(["election", "stat_area_id"]).any():
        raise ValueError("ArcGIS source maps multiple area totals to one published ID")
    return totals, missing_aliases


def effective_locality_code(row: pd.Series) -> str:
    for column in ["locality_code", "locality_result_code", "source_locality_code"]:
        code = normalized_code(row.get(column, ""))
        if code:
            return code
    return ""


def gap_reason(
    row: pd.Series,
    metadata_localities: dict[int, set[str]],
    metadata_locality_names: dict[int, dict[str, set[str]]],
    crosswalk_localities: set[tuple[str, str]],
) -> tuple[str, str, str, str]:
    election = str(row["election"])
    vintage = ELECTION_VINTAGES[election]
    locality_code = str(row["effective_locality_code"])
    ballot_base = str(row.get("ballot_base", ""))

    if ballot_base == "990":
        return (
            "central_ballot_990_locality_only",
            "intentionally_locality_only",
            "high",
            "Ballot 990 is a central ballot for voters registered in the locality without a supported area-level allocation; in this multi-area locality no statistical-area assignment is defensible.",
        )
    component_evidence = (
        str(row.get("final_assignment_source", ""))
        == "reviewed_composite_component_evidence"
    )
    if component_evidence and locality_code:
        target_name = normalized_name(row.get("locality_name", ""))
        active_names = metadata_locality_names[vintage].get(locality_code, set())
        if locality_code not in metadata_localities[vintage] or target_name not in active_names:
            return (
                "component_locality_nested_in_historical_composite_geography",
                "component_identity_only_with_current_sources",
                "high",
                "The polling-place register identifies the component locality, but the active historical layer stores that land only under the election-time composite municipality. No ballot-to-area crosswalk separates the component within that parent geography.",
            )
        return (
            "component_locality_multiple_areas_without_crosswalk",
            "component_identity_only_with_current_sources",
            "high",
            "The polling-place register identifies the component locality, but that component contains multiple areas in the active vintage and no ballot-to-area crosswalk supports a unique one.",
        )
    if not locality_code:
        if election == "K17" and row.get("source_locality_name", "") in {
            "באקה-ג'ת",
            "עיר כרמל",
            "שגור",
        }:
            return (
                "historical_composite_municipality_without_stat_area_crosswalk",
                "irreducible_with_current_sources",
                "high",
                "The K17 source uses a historical composite municipality. Its component polygons support locality-mode display, but no official ballot-to-statistical-area crosswalk or stability evidence separates these ballots among the component areas.",
            )
        return (
            "missing_or_composite_locality_code",
            "irreducible_with_current_sources",
            "high",
            "The election row cannot be reduced to one historical locality code, so no compatible statistical-area lookup can be made.",
        )
    if locality_code not in metadata_localities[vintage]:
        return (
            "locality_identity_absent_from_active_historical_vintage",
            "irreducible_with_current_sources",
            "high",
            "No statistical-area identity exists for this independent locality in the active historical vintage. Its land may be present under an older parent or surrounding locality, but a later-vintage boundary is not silently substituted.",
        )
    if (election, locality_code) not in crosswalk_localities:
        return (
            "entire_locality_omitted_from_official_crosswalk",
            "irreducible_with_current_sources",
            "high",
            "The official CBS ballot crosswalk contains no rows for this locality in this election, and no approved direct or arithmetic evidence resolves this ballot.",
        )
    return (
        "specific_ballot_omitted_from_official_crosswalk",
        "irreducible_with_current_sources",
        "high",
        "The official CBS crosswalk covers the locality but omits this ballot, and no approved direct, stable-ballot, or exact aggregate evidence resolves it.",
    )


def build_gap_rows(
    assignments: pd.DataFrame,
    historical: pd.DataFrame,
    metadata: pd.DataFrame,
    crosswalk: pd.DataFrame,
    arcgis_localities: pd.DataFrame,
    omitted_ballot_reviews: pd.DataFrame,
) -> pd.DataFrame:
    pending = assignments[
        assignments["geography_assignment_status"].isin(PENDING_STATUSES)
    ].copy()
    history_fields = historical[
        ["source_row_uid", "ballot_base", "historical_assignment_status"]
    ]
    pending = pending.merge(
        history_fields, on="source_row_uid", how="left", validate="one_to_one"
    ).fillna("")
    pending["effective_locality_code"] = pending.apply(
        effective_locality_code, axis=1
    )
    pending["effective_locality_name"] = pending.apply(
        lambda row: row.get("locality_name", "")
        or row.get("locality_result_name", "")
        or row.get("source_locality_name", ""),
        axis=1,
    )

    metadata_localities = {
        vintage: set(
            metadata.loc[
                metadata["stat_area_vintage"] == str(vintage), "locality_code"
            ]
        )
        for vintage in set(ELECTION_VINTAGES.values())
    }
    metadata_locality_names: dict[int, dict[str, set[str]]] = {}
    for vintage in set(ELECTION_VINTAGES.values()):
        vintage_rows = metadata[metadata["stat_area_vintage"] == str(vintage)]
        metadata_locality_names[vintage] = {
            str(code): {
                normalized_name(value)
                for value in group["locality_name_he"]
                if normalized_name(value)
            }
            for code, group in vintage_rows.groupby("locality_code")
        }
    crosswalk_localities = {
        (str(row["election"]), normalized_code(row["locality_code"]))
        for row in crosswalk.to_dict("records")
        if normalized_code(row["locality_code"])
    }
    reasons = pending.apply(
        lambda row: gap_reason(
            row,
            metadata_localities,
            metadata_locality_names,
            crosswalk_localities,
        ),
        axis=1,
        result_type="expand",
    )
    reasons.columns = [
        "gap_reason_code",
        "resolution_state",
        "classification_confidence",
        "gap_explanation",
    ]
    pending = pd.concat([pending.reset_index(drop=True), reasons], axis=1)

    if not omitted_ballot_reviews.empty:
        exact_set_reviews = omitted_ballot_reviews[
            omitted_ballot_reviews["decision"] == "approved_exact_set_display"
        ].set_index("source_row_uid")
        reviewed_rows = pending["source_row_uid"].isin(exact_set_reviews.index)
        for index in pending.index[reviewed_rows]:
            review = exact_set_reviews.loc[pending.at[index, "source_row_uid"]]
            target_areas = str(review.get("target_stat_area_ids", ""))
            display_id = str(review.get("published_treatment", ""))
            pending.at[index, "resolution_state"] = "resolved_exact_set_display"
            pending.at[index, "classification_confidence"] = str(
                review.get("confidence", "high")
            )
            pending.at[index, "gap_explanation"] = (
                "No defensible row-level area exists, but reviewed polling-register "
                f"evidence closes this ballot inside {target_areas}. Its votes publish "
                f"once through {display_id}; no internal area split is asserted."
            )

    if not arcgis_localities.empty:
        arcgis = arcgis_localities[
            [
                "election",
                "source_locality_code",
                "status",
                "reason",
                "review_decision",
                "review_basis",
            ]
        ].copy()
        arcgis["effective_locality_code"] = arcgis["source_locality_code"].map(
            normalized_code
        )
        arcgis = arcgis.rename(
            columns={
                "status": "arcgis_audit_status",
                "reason": "arcgis_audit_reason",
                "review_decision": "arcgis_review_decision",
                "review_basis": "arcgis_review_basis",
            }
        ).drop(columns="source_locality_code")
        pending = pending.merge(
            arcgis,
            on=["election", "effective_locality_code"],
            how="left",
            validate="many_to_one",
        ).fillna("")
    else:
        for column in [
            "arcgis_audit_status",
            "arcgis_audit_reason",
            "arcgis_review_decision",
            "arcgis_review_basis",
        ]:
            pending[column] = ""

    pending["eligible_voters"] = pending["eligible_voters"].map(integer)
    pending["actual_voters"] = pending["actual_voters"].map(integer)
    pending["stat_area_vintage"] = pending["election"].map(ELECTION_VINTAGES)
    columns = [
        "source_row_uid",
        "election",
        "stat_area_vintage",
        "source_locality_code",
        "source_locality_name",
        "effective_locality_code",
        "effective_locality_name",
        "source_kalpi",
        "ballot_base",
        "eligible_voters",
        "actual_voters",
        "gap_reason_code",
        "resolution_state",
        "classification_confidence",
        "gap_explanation",
        "arcgis_audit_status",
        "arcgis_audit_reason",
        "arcgis_review_decision",
        "arcgis_review_basis",
        "final_assignment_method",
        "final_assignment_source",
        "unresolved_reason",
    ]
    return pending[columns].sort_values(
        ["election", "effective_locality_code", "source_kalpi", "source_row_uid"],
        ascending=[True, True, True, True],
        kind="stable",
    )


def build_locality_summary(gaps: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        gaps.groupby(
            [
                "election",
                "stat_area_vintage",
                "gap_reason_code",
                "resolution_state",
                "effective_locality_code",
                "effective_locality_name",
            ],
            dropna=False,
            as_index=False,
        )
        .agg(
            pending_ballot_rows=("source_row_uid", "count"),
            pending_eligible_voters=("eligible_voters", "sum"),
            pending_actual_voters=("actual_voters", "sum"),
            arcgis_audit_status=("arcgis_audit_status", lambda values: "|".join(sorted({value for value in values if value}))),
            arcgis_review_decision=("arcgis_review_decision", lambda values: "|".join(sorted({value for value in values if value}))),
        )
    )
    return grouped.sort_values(
        ["election", "gap_reason_code", "effective_locality_code"], kind="stable"
    )


def build_election_summary(gaps: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        gaps.groupby(
            ["election", "stat_area_vintage", "gap_reason_code", "resolution_state"],
            as_index=False,
        )
        .agg(
            pending_ballot_rows=("source_row_uid", "count"),
            pending_localities=("effective_locality_code", lambda values: len(set(values))),
            pending_eligible_voters=("eligible_voters", "sum"),
            pending_actual_voters=("actual_voters", "sum"),
        )
    )
    totals = (
        gaps.groupby(["election", "stat_area_vintage"], as_index=False)
        .agg(
            pending_ballot_rows=("source_row_uid", "count"),
            pending_localities=("effective_locality_code", lambda values: len(set(values))),
            pending_eligible_voters=("eligible_voters", "sum"),
            pending_actual_voters=("actual_voters", "sum"),
        )
    )
    totals["gap_reason_code"] = "all_pending_rows"
    totals["resolution_state"] = "mixed"
    totals = totals[grouped.columns]
    return pd.concat([grouped, totals], ignore_index=True).sort_values(
        ["election", "gap_reason_code"], kind="stable"
    )


def build_crosswalk_omission_recurrence(gaps: pd.DataFrame) -> pd.DataFrame:
    omitted = gaps[
        gaps["gap_reason_code"] == "entire_locality_omitted_from_official_crosswalk"
    ].copy()
    columns = [
        "effective_locality_code",
        "effective_locality_name",
        "omitted_elections",
        "omitted_election_count",
        "pending_ballot_rows",
        "pending_eligible_voters",
        "pending_actual_voters",
        "recurrence_class",
    ]
    if omitted.empty:
        return pd.DataFrame(columns=columns)
    recurrence = (
        omitted.groupby("effective_locality_code", as_index=False)
        .agg(
            effective_locality_name=(
                "effective_locality_name",
                lambda values: next((value for value in values if value), ""),
            ),
            omitted_elections=(
                "election",
                lambda values: "|".join(
                    sorted(set(values), key=lambda value: int(str(value)[1:]))
                ),
            ),
            omitted_election_count=("election", lambda values: len(set(values))),
            pending_ballot_rows=("source_row_uid", "count"),
            pending_eligible_voters=("eligible_voters", "sum"),
            pending_actual_voters=("actual_voters", "sum"),
        )
    )
    recurrence["recurrence_class"] = recurrence["omitted_election_count"].map(
        lambda count: (
            "all_nine_elections"
            if count == len(ELECTION_VINTAGES)
            else "seven_or_eight_elections"
            if count >= 7
            else "four_to_six_elections"
            if count >= 4
            else "one_to_three_elections"
        )
    )
    return recurrence[columns].sort_values(
        ["omitted_election_count", "effective_locality_code"],
        ascending=[False, True],
        kind="stable",
    )


def polygon_status(row: pd.Series) -> tuple[str, str, bool, str]:
    if (
        integer(row["assigned_ballot_rows"]) > 0
        and integer(row["locality_actionable_pending_ballot_rows"]) > 0
    ):
        return (
            "assigned_ballots_with_unresolved_locality_rows",
            "This area has assigned ballots, but its locality also has unresolved non-central ballot rows that could affect one or more areas.",
            True,
            "unresolved_locality_ballots",
        )
    if integer(row["assigned_ballot_rows"]) > 0:
        return (
            "assigned_ballots",
            "Ballot results are assigned to this statistical area.",
            False,
            "none",
        )
    arcgis_is_area_level = row["arcgis_comparison_status"] in {
        "detailed_statistical_area",
        "single_statistical_area_locality",
    }
    if (
        arcgis_is_area_level
        and integer(row["arcgis_ballot_count"])
        == integer(row["special_non_geographic_rows"])
        and integer(row["arcgis_eligible_voters"])
        == integer(row["special_non_geographic_eligible_voters"])
        and integer(row["arcgis_actual_voters"])
        == integer(row["special_non_geographic_actual_voters"])
        and integer(row["arcgis_ballot_count"]) > 0
    ):
        return (
            "arcgis_total_matches_special_non_geographic_rows",
            "The ArcGIS area total exactly matches reviewed military or other special non-geographic rows; it is retained as provenance, not treated as a residential assignment gap.",
            False,
            "exact_special_non_geographic_total",
        )
    if arcgis_is_area_level and (
        integer(row["arcgis_ballot_count"]) > 0
        or integer(row["arcgis_eligible_voters"]) > 0
    ):
        return (
            "unassigned_official_area_total",
            "The K20/K21 ArcGIS layer reports ballots or eligible voters for this area, but no ballot row is assigned after reviewed reconstruction.",
            True,
            "official_area_electorate",
        )
    if integer(row["locality_actionable_pending_ballot_rows"]) > 0:
        return (
            "unassigned_locality_has_pending_ballots",
            "The locality has unresolved ballot rows that may belong to this area, but available evidence does not identify which rows.",
            True,
            "unresolved_locality_ballots",
        )
    if integer(row["locality_ballot_rows"]) > 0:
        return (
            "unassigned_locality_has_only_other_area_assignments",
            "The election has ballot rows for this locality, but the official and approved evidence assigns none to this area.",
            False,
            "population_proxy_only" if integer(row["population_proxy"]) > 0 else "unknown",
        )
    return (
        "unassigned_no_locality_ballot_rows",
        "The election data has no ordinary locality-level ballot row that can be assigned to this area.",
        False,
        "population_proxy_only" if integer(row["population_proxy"]) > 0 else "unknown",
    )


def build_polygon_coverage(
    assignments: pd.DataFrame,
    gaps: pd.DataFrame,
    metadata: pd.DataFrame,
    population: pd.DataFrame,
    arcgis_totals: pd.DataFrame,
) -> pd.DataFrame:
    working = assignments.copy()
    working["effective_locality_code"] = working.apply(effective_locality_code, axis=1)
    working["eligible_voters"] = working["eligible_voters"].map(integer)
    working["actual_voters"] = working["actual_voters"].map(integer)
    working["is_locality_mapped_bool"] = working["is_locality_mapped"].map(truthy)

    assigned = working[working["stat_area_id"] != ""].copy()
    assigned_summary = (
        assigned.groupby(["election", "stat_area_id"], as_index=False)
        .agg(
            assigned_ballot_rows=("source_row_uid", "count"),
            assigned_eligible_voters=("eligible_voters", "sum"),
            assigned_actual_voters=("actual_voters", "sum"),
            assignment_methods=(
                "final_assignment_method",
                lambda values: "|".join(sorted(set(values))),
            ),
        )
    )
    locality_rows = working[
        working["is_locality_mapped_bool"] & (working["effective_locality_code"] != "")
    ]
    locality_summary = (
        locality_rows.groupby(["election", "effective_locality_code"], as_index=False)
        .agg(
            locality_ballot_rows=("source_row_uid", "count"),
            locality_eligible_voters=("eligible_voters", "sum"),
            locality_actual_voters=("actual_voters", "sum"),
        )
    )
    special_rows = working[
        (working["geography_assignment_status"] == "special_non_geographic")
        & (working["effective_locality_code"] != "")
    ]
    special_summary = (
        special_rows.groupby(
            ["election", "effective_locality_code"], as_index=False
        )
        .agg(
            special_non_geographic_rows=("source_row_uid", "count"),
            special_non_geographic_eligible_voters=("eligible_voters", "sum"),
            special_non_geographic_actual_voters=("actual_voters", "sum"),
        )
    )
    pending_summary = (
        gaps.groupby(["election", "effective_locality_code"], as_index=False)
        .agg(
            locality_pending_ballot_rows=("source_row_uid", "count"),
            locality_pending_eligible_voters=("eligible_voters", "sum"),
            locality_pending_actual_voters=("actual_voters", "sum"),
            locality_gap_reason_codes=(
                "gap_reason_code", lambda values: "|".join(sorted(set(values)))
            ),
        )
    )
    actionable_gaps = gaps[
        gaps["resolution_state"] != "intentionally_locality_only"
    ]
    actionable_pending_summary = (
        actionable_gaps.groupby(
            ["election", "effective_locality_code"], as_index=False
        )
        .agg(
            locality_actionable_pending_ballot_rows=("source_row_uid", "count"),
            locality_actionable_pending_eligible_voters=("eligible_voters", "sum"),
            locality_actionable_pending_actual_voters=("actual_voters", "sum"),
        )
    )

    frames: list[pd.DataFrame] = []
    for election, vintage in ELECTION_VINTAGES.items():
        frame = metadata[metadata["stat_area_vintage"] == str(vintage)].copy()
        frame.insert(0, "election", election)
        frames.append(frame)
    coverage = pd.concat(frames, ignore_index=True, sort=False).fillna("")
    coverage = coverage.merge(
        population, on="stat_area_id", how="left", validate="many_to_one"
    ).fillna("")
    coverage = coverage.merge(
        assigned_summary,
        on=["election", "stat_area_id"],
        how="left",
        validate="one_to_one",
    ).fillna("")
    coverage = coverage.merge(
        locality_summary,
        left_on=["election", "locality_code"],
        right_on=["election", "effective_locality_code"],
        how="left",
        validate="many_to_one",
    ).fillna("")
    coverage = coverage.drop(columns=["effective_locality_code"], errors="ignore")
    coverage = coverage.merge(
        pending_summary,
        left_on=["election", "locality_code"],
        right_on=["election", "effective_locality_code"],
        how="left",
        validate="many_to_one",
    ).fillna("")
    coverage = coverage.drop(columns=["effective_locality_code"], errors="ignore")
    coverage = coverage.merge(
        actionable_pending_summary,
        left_on=["election", "locality_code"],
        right_on=["election", "effective_locality_code"],
        how="left",
        validate="many_to_one",
    ).fillna("")
    coverage = coverage.drop(columns=["effective_locality_code"], errors="ignore")
    coverage = coverage.merge(
        special_summary,
        left_on=["election", "locality_code"],
        right_on=["election", "effective_locality_code"],
        how="left",
        validate="many_to_one",
    ).fillna("")
    coverage = coverage.drop(columns=["effective_locality_code"], errors="ignore")
    coverage = coverage.merge(
        arcgis_totals,
        on=["election", "stat_area_id"],
        how="left",
        validate="one_to_one",
    ).fillna("")

    numeric_columns = [
        "population_proxy",
        "age_20_plus_population_proxy",
        "assigned_ballot_rows",
        "assigned_eligible_voters",
        "assigned_actual_voters",
        "locality_ballot_rows",
        "locality_eligible_voters",
        "locality_actual_voters",
        "locality_pending_ballot_rows",
        "locality_pending_eligible_voters",
        "locality_pending_actual_voters",
        "locality_actionable_pending_ballot_rows",
        "locality_actionable_pending_eligible_voters",
        "locality_actionable_pending_actual_voters",
        "special_non_geographic_rows",
        "special_non_geographic_eligible_voters",
        "special_non_geographic_actual_voters",
        "arcgis_source_stat_area_number",
        "arcgis_locality_feature_count",
        "arcgis_published_stat_areas",
        "arcgis_ballot_count",
        "arcgis_eligible_voters",
        "arcgis_actual_voters",
    ]
    for column in numeric_columns:
        coverage[column] = coverage[column].map(integer)
    status = coverage.apply(polygon_status, axis=1, result_type="expand")
    status.columns = [
        "polygon_assignment_status",
        "polygon_assignment_explanation",
        "requires_assignment_followup",
        "unassigned_evidence_strength",
    ]
    coverage = pd.concat([coverage, status], axis=1)
    coverage["population_evidence_status"] = coverage.apply(
        lambda row: (
            "positive_population_proxy"
            if integer(row["population_proxy"]) > 0
            else "zero_population_proxy"
            if row["population_proxy_source"] and integer(row["population_proxy"]) == 0
            else "suppressed_or_missing_population_proxy"
            if row["population_proxy_source"]
            else "no_population_proxy_for_vintage_or_supplement"
        ),
        axis=1,
    )
    coverage["arcgis_minus_assigned_eligible_voters"] = coverage.apply(
        lambda row: (
            integer(row["arcgis_eligible_voters"])
            - integer(row["assigned_eligible_voters"])
            if row["arcgis_comparison_status"]
            in {"detailed_statistical_area", "single_statistical_area_locality"}
            else ""
        ),
        axis=1,
    )
    coverage["arcgis_minus_assigned_actual_voters"] = coverage.apply(
        lambda row: (
            integer(row["arcgis_actual_voters"])
            - integer(row["assigned_actual_voters"])
            if row["arcgis_comparison_status"]
            in {"detailed_statistical_area", "single_statistical_area_locality"}
            else ""
        ),
        axis=1,
    )
    columns = [
        "election",
        "stat_area_vintage",
        "stat_area_id",
        "yishuv_stat",
        "stat_area_number",
        "locality_code",
        "locality_name_he",
        "locality_name_en",
        "geometry_source",
        "polygon_assignment_status",
        "polygon_assignment_explanation",
        "requires_assignment_followup",
        "unassigned_evidence_strength",
        "assigned_ballot_rows",
        "assigned_eligible_voters",
        "assigned_actual_voters",
        "assignment_methods",
        "locality_ballot_rows",
        "locality_eligible_voters",
        "locality_actual_voters",
        "locality_pending_ballot_rows",
        "locality_pending_eligible_voters",
        "locality_pending_actual_voters",
        "locality_gap_reason_codes",
        "locality_actionable_pending_ballot_rows",
        "locality_actionable_pending_eligible_voters",
        "locality_actionable_pending_actual_voters",
        "special_non_geographic_rows",
        "special_non_geographic_eligible_voters",
        "special_non_geographic_actual_voters",
        "arcgis_source_area_id",
        "arcgis_source_locality_code",
        "arcgis_source_stat_area_number",
        "arcgis_locality_feature_count",
        "arcgis_published_stat_areas",
        "arcgis_comparison_status",
        "arcgis_comparison_explanation",
        "arcgis_ballot_count",
        "arcgis_eligible_voters",
        "arcgis_actual_voters",
        "arcgis_minus_assigned_eligible_voters",
        "arcgis_minus_assigned_actual_voters",
        "population_proxy",
        "age_20_plus_population_proxy",
        "population_reference_year",
        "population_proxy_source",
        "population_evidence_status",
    ]
    return coverage[columns].sort_values(
        ["election", "locality_code", "stat_area_number", "stat_area_id"],
        kind="stable",
    )


def build_polygon_persistence(coverage: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for stat_area_id, group in coverage.groupby("stat_area_id", sort=True):
        assigned = group[group["assigned_ballot_rows"] > 0]
        unassigned = group[group["assigned_ballot_rows"] == 0]
        official_gaps = group[
            group["polygon_assignment_status"] == "unassigned_official_area_total"
        ]
        followup = group[group["requires_assignment_followup"] == True]  # noqa: E712
        first = group.iloc[0]
        if len(assigned) == len(group):
            persistence_status = "assigned_in_every_supported_election"
        elif len(assigned) > 0:
            persistence_status = "intermittently_unassigned"
        elif integer(first["population_proxy"]) > 0:
            persistence_status = "never_assigned_with_positive_population_proxy"
        else:
            persistence_status = "never_assigned_without_positive_population_proxy"
        records.append(
            {
                "stat_area_id": stat_area_id,
                "stat_area_vintage": first["stat_area_vintage"],
                "locality_code": first["locality_code"],
                "locality_name_he": first["locality_name_he"],
                "stat_area_number": first["stat_area_number"],
                "elections_using_vintage": len(group),
                "assigned_elections_count": len(assigned),
                "assigned_elections": "|".join(assigned["election"].tolist()),
                "unassigned_elections_count": len(unassigned),
                "unassigned_elections": "|".join(unassigned["election"].tolist()),
                "official_area_electorate_gap_elections": "|".join(
                    official_gaps["election"].tolist()
                ),
                "followup_elections": "|".join(followup["election"].tolist()),
                "persistence_status": persistence_status,
                "never_assigned_in_supported_elections": len(assigned) == 0,
                "population_proxy": first["population_proxy"],
                "age_20_plus_population_proxy": first[
                    "age_20_plus_population_proxy"
                ],
                "population_reference_year": first["population_reference_year"],
                "population_proxy_source": first["population_proxy_source"],
            }
        )
    return pd.DataFrame(records)


def build_polygon_summary(coverage: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for election, group in coverage.groupby("election", sort=True):
        statuses = group["polygon_assignment_status"].value_counts()
        rows.append(
            {
                "election": election,
                "stat_area_vintage": group.iloc[0]["stat_area_vintage"],
                "statistical_area_polygons": len(group),
                "polygons_with_assigned_ballots": int(
                    (group["assigned_ballot_rows"] > 0).sum()
                ),
                "assigned_polygons_in_localities_with_pending_ballots": int(
                    statuses.get(
                        "assigned_ballots_with_unresolved_locality_rows", 0
                    )
                ),
                "polygons_without_assigned_ballots": int(
                    (group["assigned_ballot_rows"] == 0).sum()
                ),
                "arcgis_detailed_or_single_area_records": int(
                    group["arcgis_comparison_status"].isin(
                        {
                            "detailed_statistical_area",
                            "single_statistical_area_locality",
                        }
                    ).sum()
                ),
                "arcgis_dissolved_locality_aggregate_records": int(
                    (
                        group["arcgis_comparison_status"]
                        == "dissolved_locality_aggregate"
                    ).sum()
                ),
                "unassigned_polygons_with_official_arcgis_electorate": int(
                    statuses.get("unassigned_official_area_total", 0)
                ),
                "arcgis_polygons_matching_special_non_geographic_rows": int(
                    statuses.get(
                        "arcgis_total_matches_special_non_geographic_rows", 0
                    )
                ),
                "unassigned_polygons_in_localities_with_pending_ballots": int(
                    statuses.get("unassigned_locality_has_pending_ballots", 0)
                ),
                "unassigned_polygons_with_positive_population_proxy": int(
                    (
                        (group["assigned_ballot_rows"] == 0)
                        & (group["population_proxy"] > 0)
                    ).sum()
                ),
                "polygons_requiring_assignment_followup": int(
                    group["requires_assignment_followup"].sum()
                ),
            }
        )
    return pd.DataFrame(rows)


def build_municipality_assignment_audit(coverage: pd.DataFrame) -> pd.DataFrame:
    """Summarize ballot and polygon gaps in municipalities with some assignment."""
    rows: list[dict[str, Any]] = []
    for (election, locality_code), group in coverage.groupby(
        ["election", "locality_code"], sort=True
    ):
        assigned = group[group["assigned_ballot_rows"] > 0]
        if assigned.empty:
            continue
        empty = group[group["assigned_ballot_rows"] == 0]
        first = group.iloc[0]
        pending_rows = integer(first["locality_pending_ballot_rows"])
        actionable_pending_rows = integer(
            first["locality_actionable_pending_ballot_rows"]
        )
        empty_positive_population = empty[empty["population_proxy"] > 0]
        empty_official_electorate = empty[
            empty["arcgis_eligible_voters"] > 0
        ]
        intentionally_locality_only_rows = pending_rows - actionable_pending_rows
        if actionable_pending_rows and len(empty):
            review_status = "unassigned_ballots_and_empty_polygons"
        elif actionable_pending_rows:
            review_status = "unassigned_ballots_only"
        elif len(empty):
            review_status = "empty_polygons_only"
        else:
            review_status = "complete_within_available_evidence"
        rows.append(
            {
                "election": election,
                "stat_area_vintage": first["stat_area_vintage"],
                "locality_code": locality_code,
                "locality_name_he": first["locality_name_he"],
                "locality_name_en": first["locality_name_en"],
                "review_status": review_status,
                "locality_ballot_rows": integer(first["locality_ballot_rows"]),
                "assigned_ballot_rows": int(assigned["assigned_ballot_rows"].sum()),
                "unassigned_ballot_rows": pending_rows,
                "actionable_unassigned_ballot_rows": actionable_pending_rows,
                "intentionally_locality_only_ballot_rows": (
                    intentionally_locality_only_rows
                ),
                "locality_eligible_voters": integer(first["locality_eligible_voters"]),
                "assigned_eligible_voters": int(
                    assigned["assigned_eligible_voters"].sum()
                ),
                "unassigned_eligible_voters": integer(
                    first["locality_pending_eligible_voters"]
                ),
                "actionable_unassigned_eligible_voters": integer(
                    first["locality_actionable_pending_eligible_voters"]
                ),
                "intentionally_locality_only_eligible_voters": (
                    integer(first["locality_pending_eligible_voters"])
                    - integer(first["locality_actionable_pending_eligible_voters"])
                ),
                "locality_actual_voters": integer(first["locality_actual_voters"]),
                "assigned_actual_voters": int(
                    assigned["assigned_actual_voters"].sum()
                ),
                "unassigned_actual_voters": integer(
                    first["locality_pending_actual_voters"]
                ),
                "actionable_unassigned_actual_voters": integer(
                    first["locality_actionable_pending_actual_voters"]
                ),
                "intentionally_locality_only_actual_voters": (
                    integer(first["locality_pending_actual_voters"])
                    - integer(first["locality_actionable_pending_actual_voters"])
                ),
                "statistical_area_polygons": len(group),
                "polygons_with_assigned_ballots": len(assigned),
                "empty_polygons": len(empty),
                "empty_polygons_with_positive_population_proxy": len(
                    empty_positive_population
                ),
                "empty_positive_population_proxy": int(
                    empty_positive_population["population_proxy"].sum()
                ),
                "empty_positive_age_20_plus_population_proxy": int(
                    empty_positive_population["age_20_plus_population_proxy"].sum()
                ),
                "empty_polygons_with_official_arcgis_electorate": len(
                    empty_official_electorate
                ),
                "empty_polygon_arcgis_eligible_voters": int(
                    empty_official_electorate["arcgis_eligible_voters"].sum()
                ),
                "empty_polygon_arcgis_actual_voters": int(
                    empty_official_electorate["arcgis_actual_voters"].sum()
                ),
                "gap_reason_codes": first["locality_gap_reason_codes"],
            }
        )
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    return result.sort_values(
        [
            "election",
            "unassigned_actual_voters",
            "empty_polygons_with_positive_population_proxy",
            "empty_polygons",
            "locality_code",
        ],
        ascending=[True, False, False, False, True],
        kind="stable",
    )


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    assignments = read_csv(ASSIGNMENTS)
    # K26 uses 2022 geography and has a separate pre-balance source audit.
    assignments = assignments[assignments["election"].isin(ELECTION_VINTAGES)].copy()
    historical = read_csv(HISTORICAL_ASSIGNMENTS)
    crosswalk = read_csv(HISTORICAL_CROSSWALK)
    metadata = load_metadata()
    population = load_population_proxies()
    arcgis_localities = (
        read_csv(ARCGIS_LOCALITY_AUDIT)
        if ARCGIS_LOCALITY_AUDIT.exists()
        else pd.DataFrame()
    )
    omitted_ballot_reviews = (
        read_csv(OMITTED_ORDINARY_BALLOT_REVIEWS)
        if OMITTED_ORDINARY_BALLOT_REVIEWS.exists()
        else pd.DataFrame()
    )
    arcgis_totals, missing_arcgis_aliases = load_arcgis_area_totals(metadata)

    gaps = build_gap_rows(
        assignments,
        historical,
        metadata,
        crosswalk,
        arcgis_localities,
        omitted_ballot_reviews,
    )
    locality_summary = build_locality_summary(gaps)
    election_summary = build_election_summary(gaps)
    omission_recurrence = build_crosswalk_omission_recurrence(gaps)
    polygon_coverage = build_polygon_coverage(
        assignments, gaps, metadata, population, arcgis_totals
    )
    polygon_persistence = build_polygon_persistence(polygon_coverage)
    polygon_summary = build_polygon_summary(polygon_coverage)
    municipality_assignment_audit = build_municipality_assignment_audit(
        polygon_coverage
    )

    expected_pending = assignments[
        assignments["geography_assignment_status"].isin(PENDING_STATUSES)
    ]
    if len(gaps) != len(expected_pending):
        raise ValueError("Gap audit does not cover every pending assignment row")
    if set(gaps["source_row_uid"]) != set(expected_pending["source_row_uid"]):
        raise ValueError("Gap audit row IDs differ from final pending assignments")

    write_frame(OUT_DIR / "historical_assignment_gap_rows.csv", gaps)
    write_frame(
        OUT_DIR / "historical_assignment_gap_localities.csv", locality_summary
    )
    write_frame(
        OUT_DIR / "historical_assignment_gap_summary.csv", election_summary
    )
    write_frame(
        OUT_DIR / "historical_crosswalk_locality_omission_recurrence.csv",
        omission_recurrence,
    )
    write_frame(OUT_DIR / "historical_polygon_coverage.csv", polygon_coverage)
    write_frame(
        OUT_DIR / "historical_polygon_assignment_persistence.csv",
        polygon_persistence,
    )
    write_frame(OUT_DIR / "historical_polygon_coverage_summary.csv", polygon_summary)
    write_frame(
        OUT_DIR / "historical_municipality_assignment_audit.csv",
        municipality_assignment_audit,
    )

    reason_counts = (
        gaps.groupby(["election", "gap_reason_code"], as_index=False)
        .agg(
            rows=("source_row_uid", "count"),
            eligible_voters=("eligible_voters", "sum"),
            actual_voters=("actual_voters", "sum"),
        )
        .to_dict("records")
    )
    write_json(
        OUT_DIR / "historical_assignment_gap_summary.json",
        {
            "status": "complete",
            "pending_rows": len(gaps),
            "pending_eligible_voters": int(gaps["eligible_voters"].sum()),
            "pending_actual_voters": int(gaps["actual_voters"].sum()),
            "central_ballot_990_rows": int(
                (
                    gaps["gap_reason_code"]
                    == "central_ballot_990_locality_only"
                ).sum()
            ),
            "reason_counts": reason_counts,
            "crosswalk_localities_omitted_in_all_nine_elections": int(
                (
                    omission_recurrence["omitted_election_count"]
                    == len(ELECTION_VINTAGES)
                ).sum()
            ),
            "crosswalk_omission_context": (
                "CBS methodology documents incomplete residential address anchoring "
                "in 36 of 38 Arab and Druze statistical-area localities. The recurrence "
                "table is an observed source-coverage audit, not an ethnicity classifier."
            ),
            "polygon_summary": polygon_summary.to_dict("records"),
            "polygon_persistence_status_counts": {
                str(key): int(value)
                for key, value in polygon_persistence[
                    "persistence_status"
                ].value_counts().to_dict().items()
            },
            "arcgis_area_records_without_published_alias": missing_arcgis_aliases,
            "population_proxy_warning": (
                "Population and age-20-plus fields are reference-year resident "
                "proxies, not election-specific eligible-voter counts."
            ),
            "arcgis_comparison_warning": (
                "ArcGIS features marked dissolved_locality_aggregate are locality "
                "totals and are never interpreted as detailed statistical-area totals."
            ),
        },
    )

    print(f"pending_rows_classified={len(gaps)}")
    print(
        "intentional_central_ballot_990_rows="
        f"{(gaps['gap_reason_code'] == 'central_ballot_990_locality_only').sum()}"
    )
    for row in polygon_summary.to_dict("records"):
        print(
            f"{row['election']}: polygons={row['statistical_area_polygons']} "
            f"assigned={row['polygons_with_assigned_ballots']} "
            f"followup={row['polygons_requiring_assignment_followup']}"
        )


if __name__ == "__main__":
    main()
