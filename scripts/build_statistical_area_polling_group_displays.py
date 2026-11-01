from __future__ import annotations

import argparse
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
from pipeline_common import preserve_other_elections

from build_public_outputs import (
    NUMERIC_CORE,
    add_winner_fields,
    numeric,
    party_columns,
)
from build_statistical_area_result_aggregates import (
    ADJACENCY_TOLERANCE_METERS,
    is_connected,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = (
    ROOT
    / "data"
    / "processed"
    / "audits"
    / "statistical_area_polling_group_policy.csv"
)
REVIEW_CONFIG_PATH = (
    ROOT
    / "data"
    / "manual"
    / "statistical_area_polling_group_display_reviews.csv"
)
SOURCE_GEOMETRY_PATH = (
    ROOT
    / "data"
    / "processed"
    / "geographies"
    / "statistical_areas_2011.display.simplified.geojson"
)
ASSIGNMENTS_PATH = (
    ROOT
    / "data"
    / "processed"
    / "assignments"
    / "ballot_geography_assignments.csv"
)
RESULTS_DIR = ROOT / "data" / "processed" / "normalized" / "ballot_votes_wide"
OUTPUT_GEOMETRY_PATH = (
    ROOT
    / "data"
    / "processed"
    / "geographies"
    / "statistical_area_polling_group_displays.geojson"
)
OUTPUT_METADATA_PATH = (
    ROOT
    / "data"
    / "processed"
    / "geographies"
    / "statistical_area_polling_group_displays.metadata.csv"
)
OUTPUT_RESULTS_PATH = (
    ROOT
    / "data"
    / "processed"
    / "public"
    / "statistical_area_polling_group_displays.csv"
)


def clean(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    return text[:-2] if text.endswith(".0") else text


def split_pipe(value: object) -> list[str]:
    return [part.strip() for part in str(value or "").split("|") if part.strip()]


def append_pipe(value: object, addition: str) -> str:
    parts = split_pipe(value)
    if addition not in parts:
        parts.append(addition)
    return "|".join(parts)


def apply_reviewed_display_groups(
    configured_groups: list[dict[str, str]],
    review_groups: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Apply explicit presentation reviews without changing ballot assignments."""
    adjusted = [dict(row) for row in configured_groups]
    for review in review_groups:
        display_id = clean(review.get("display_geography_id", ""))
        election = clean(review.get("election", ""))
        locality_code = clean(review.get("locality_code", ""))
        owned_ids = split_pipe(review.get("owned_stat_area_ids", ""))
        planned_ids = split_pipe(review.get("planned_stat_area_ids", ""))
        source_ballots = split_pipe(review.get("ambiguous_final_ballots", ""))
        released_ballots = split_pipe(review.get("released_final_ballots", ""))
        claimed_ballots = set(source_ballots) | set(released_ballots)
        if not display_id or not election or not locality_code:
            raise ValueError("Reviewed polling display has a blank identity field")
        if not owned_ids or not source_ballots:
            raise ValueError(f"{display_id} lacks reviewed areas or final ballots")
        if not set(owned_ids).issubset(planned_ids):
            raise ValueError(f"{display_id} owns areas outside its reviewed set")

        revised_rows: list[dict[str, str]] = []
        for row in adjusted:
            same_scope = (
                clean(row.get("election", "")) == election
                and clean(row.get("locality_code", "")) == locality_code
            )
            if not same_scope:
                revised_rows.append(row)
                continue

            remaining_owned = [
                area_id
                for area_id in split_pipe(row.get("owned_stat_area_ids", ""))
                if area_id not in set(owned_ids)
            ]
            remaining_ballots = [
                ballot
                for ballot in split_pipe(row.get("ambiguous_final_ballots", ""))
                if ballot not in claimed_ballots
            ]
            changed = (
                remaining_owned
                != split_pipe(row.get("owned_stat_area_ids", ""))
                or remaining_ballots
                != split_pipe(row.get("ambiguous_final_ballots", ""))
            )
            if not changed:
                revised_rows.append(row)
                continue
            if not remaining_owned or not remaining_ballots:
                continue

            revised = dict(row)
            revised["owned_stat_area_ids"] = "|".join(remaining_owned)
            revised["ambiguous_final_ballots"] = "|".join(remaining_ballots)
            revised["planned_eligible_voters"] = "0"
            revised["represented_planned_eligible_voters"] = "0"
            revised["represented_planned_share"] = "0"
            revised["component_network_balance"] = "reviewed_display_override"
            revised["component_eligible_difference"] = ""
            revised["evidence_warnings"] = append_pipe(
                revised.get("evidence_warnings", ""),
                "reviewed_display_override",
            )
            revised["ownership_status"] = "best_effort_detail_preserved"
            revised["ownership_policy"] = "reviewed_display_override_remainder"
            revised["review_status"] = "approved-rule-generated"
            revised_rows.append(revised)

        revised_rows.append(
            {
                "display_geography_id": display_id,
                "election": election,
                "locality_code": locality_code,
                "locality_name": clean(review.get("locality_name", "")),
                "evidence_group_id": f"reviewed:{election}:{locality_code}:{display_id}",
                "source_site_audit_id": clean(
                    review.get("source_site_audit_id", "")
                ),
                "source_site_ids": clean(review.get("source_site_ids", "")),
                "final_site_ids": clean(review.get("final_site_ids", "")),
                "owned_stat_area_ids": "|".join(owned_ids),
                "planned_stat_area_ids": "|".join(planned_ids),
                "ambiguous_final_ballots": "|".join(source_ballots),
                "planned_eligible_voters": "0",
                "represented_planned_eligible_voters": "0",
                "represented_planned_share": "0",
                "final_eligible_voters": "0",
                "component_network_balance": "not_comparable_reviewed_display",
                "component_eligible_difference": "",
                "source_evidence": clean(review.get("source_evidence", "")),
                "continuity_reference_elections": clean(
                    review.get("continuity_reference_elections", "")
                ),
                "continuity_reference_site_audit_ids": clean(
                    review.get("continuity_reference_site_audit_ids", "")
                ),
                "evidence_warnings": clean(review.get("evidence_warnings", "")),
                "ownership_status": clean(
                    review.get("ownership_status", "best_effort_detail_preserved")
                ),
                "ownership_policy": clean(
                    review.get("ownership_policy", "reviewed_set_level_merge")
                ),
                "review_status": clean(
                    review.get("review_status", "approved-rule-generated")
                ),
                "note": clean(review.get("note", "")),
            }
        )
        adjusted = revised_rows
    return adjusted


def dissolved_component_geometry(geometries: list[object]) -> dict[str, object]:
    """Dissolve shared borders so one result record reads as one map area."""
    dissolved = unary_union(geometries)
    if dissolved.is_empty:
        raise ValueError("Polling-group display has no polygon components")
    if dissolved.geom_type not in {"Polygon", "MultiPolygon"}:
        raise ValueError(
            f"Unsupported dissolved component geometry type: {dissolved.geom_type}"
        )
    return mapping(dissolved)


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"Cannot write an empty CSV: {path}")
    fieldnames: list[str] = []
    seen_fields: set[str] = set()
    for row in rows:
        for field in row:
            if field not in seen_fields:
                seen_fields.add(field)
                fieldnames.append(field)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_notice(
    *,
    exact_assignment: bool,
    possible_inflow_numbers: list[str],
    possible_outflow_numbers: list[str],
) -> tuple[str, str]:
    if exact_assignment:
        return "", ""

    inflow_he = ", ".join(possible_inflow_numbers)
    outflow_he = ", ".join(possible_outflow_numbers)
    inflow_en = ", ".join(possible_inflow_numbers)
    outflow_en = ", ".join(possible_outflow_numbers)
    base_he = "לא ניתן לשייך קולות לאזור במדויק."
    base_en = "Votes cannot be assigned to this area precisely."

    if possible_inflow_numbers and possible_outflow_numbers:
        return (
            f"{base_he} ייתכן שקולות מאזורים אלה מוצגים באזורים {outflow_he}. "
            f"בנוסף, ייתכן שתוצאה זו כוללת קולות מהאזורים {inflow_he}.",
            f"{base_en} Votes from these areas may be displayed in areas "
            f"{outflow_en}. This result may also include votes from areas "
            f"{inflow_en}.",
        )
    if possible_outflow_numbers:
        return (
            f"{base_he} ייתכן שקולות מאזורים אלה מוצגים באזורים {outflow_he}.",
            f"{base_en} Votes from these areas may be displayed in areas "
            f"{outflow_en}.",
        )
    if possible_inflow_numbers:
        return (
            f"{base_he} ייתכן שתוצאה זו כוללת קולות מהאזורים {inflow_he}.",
            f"{base_en} This result may include votes from areas {inflow_en}.",
        )
    return base_he, base_en


def build_election(
    configured_groups: list[dict[str, str]],
    geometry_by_id: gpd.GeoDataFrame,
    election_results: pd.DataFrame,
    assignments: pd.DataFrame,
    election: str,
    locality_code: str,
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    Counter[str],
]:
    results = election_results.loc[
        election_results["_locality_code"].eq(locality_code)
    ].drop(columns="_locality_code").copy()
    parties = party_columns(results)
    locality_assignments = assignments.loc[
        assignments["_locality_code"].eq(locality_code),
        ["source_row_uid", "stat_area_id"],
    ]
    results = results.merge(
        locality_assignments,
        on="source_row_uid",
        how="left",
        validate="one_to_one",
    )
    results["stat_area_id"] = results["stat_area_id"].fillna("")

    seen_display_ids: set[str] = set()
    area_owner: dict[str, str] = {}
    ballot_owner: dict[str, str] = {}
    group_context: dict[str, dict[str, object]] = {}
    geometry_features: list[dict[str, object]] = []
    metadata_rows: list[dict[str, object]] = []

    for row in configured_groups:
        display_id = clean(row["display_geography_id"])
        row_election = clean(row["election"])
        row_locality_code = clean(row["locality_code"])
        owned_ids = split_pipe(row["owned_stat_area_ids"])
        planned_ids = split_pipe(row["planned_stat_area_ids"])
        source_ballots = split_pipe(row["ambiguous_final_ballots"])
        if display_id in seen_display_ids or not display_id:
            raise ValueError(f"Duplicate or blank display ID: {display_id!r}")
        if row_election != election or row_locality_code != locality_code:
            raise ValueError(
                f"Polling-group scope changed: "
                f"{row_election}/{row_locality_code} != {election}/{locality_code}"
            )
        review_status = clean(row["review_status"])
        exact_assignment = review_status == "approved-exact-closed"
        if review_status not in {
            "approved-rule-generated",
            "approved-exact-closed",
        }:
            raise ValueError(f"{display_id} is not approved for display")
        if not owned_ids or not source_ballots:
            raise ValueError(f"{display_id} lacks owned areas or final ballots")
        if not set(owned_ids).issubset(planned_ids):
            raise ValueError(
                f"{display_id} owns areas outside its planned set: "
                f"{sorted(set(owned_ids) - set(planned_ids))}"
            )

        for area_id in owned_ids:
            if area_id in area_owner:
                raise ValueError(
                    f"Area {area_id} is owned by {area_owner[area_id]} and {display_id}"
                )
            if area_id not in geometry_by_id.index:
                raise ValueError(f"{display_id} references unavailable area {area_id}")
            area_owner[area_id] = display_id
        for source_ballot in source_ballots:
            if source_ballot in ballot_owner:
                raise ValueError(
                    f"Ballot {source_ballot} is owned by "
                    f"{ballot_owner[source_ballot]} and {display_id}"
                )
            ballot_owner[source_ballot] = display_id

        planned_total = int(clean(row["planned_eligible_voters"]))
        represented_total = int(clean(row["represented_planned_eligible_voters"]))
        represented_share = represented_total / planned_total if planned_total else 0.0
        configured_share = float(clean(row["represented_planned_share"]))
        if abs(represented_share - configured_share) > 1e-6:
            raise ValueError(
                f"{display_id} represented share changed: "
                f"{represented_share} != {configured_share}"
            )

        components = geometry_by_id.loc[owned_ids]
        if len(set(components["locality_code"].map(clean))) != 1:
            raise ValueError(f"{display_id} crosses locality codes")
        geometries = list(components.geometry)
        display_geometry = dissolved_component_geometry(geometries)
        connected = is_connected(geometries, ADJACENCY_TOLERANCE_METERS)
        ownership_status = clean(row["ownership_status"])
        if ownership_status in {
            "connected_solution",
            "robust_mutual_majority_partition",
            "cross_election_robust_partition",
        } and not connected:
            raise ValueError(f"{display_id} ownership geometry is disconnected")
        if ownership_status not in {
            "connected_solution",
            "solution_requires_disconnected_geometry",
            "exact_closed_flow_group",
            "exact_closed_network",
            "exact_topological_component",
            "robust_mutual_majority_partition",
            "robust_mutual_majority_partition_disconnected",
            "best_effort_detail_preserved",
            "cross_election_robust_partition",
            "cross_election_robust_partition_disconnected",
            "cross_election_detail_preserved",
        }:
            raise ValueError(
                f"{display_id} has unsupported ownership status {ownership_status!r}"
            )
        part_count = (
            1
            if display_geometry["type"] == "Polygon"
            else len(display_geometry["coordinates"])
        )
        area_numbers = [str(int(value)) for value in components["stat_area_number"]]
        omitted_ids = sorted(set(planned_ids) - set(owned_ids))
        first = components.iloc[0]
        locality_name_he = clean(first["locality_name_he"])
        locality_name_en = clean(first["locality_name_en"])
        group_context[display_id] = {
            "row": row,
            "owned_ids": owned_ids,
            "planned_ids": planned_ids,
            "source_ballots": source_ballots,
            "area_numbers": area_numbers,
            "omitted_ids": omitted_ids,
            "planned_total": planned_total,
            "represented_total": represented_total,
            "represented_share": represented_share,
            "locality_name_he": locality_name_he,
            "locality_name_en": locality_name_en,
            "display_geometry": display_geometry,
            "part_count": part_count,
            "connected": connected,
            "exact_assignment": exact_assignment,
        }
        seen_display_ids.add(display_id)

    candidate_displays_by_area: dict[str, set[str]] = defaultdict(set)
    for display_id, context in group_context.items():
        for area_id in context["planned_ids"]:  # type: ignore[union-attr]
            candidate_displays_by_area[area_id].add(display_id)

    def area_number(area_id: str) -> str:
        return str(int(geometry_by_id.loc[area_id, "stat_area_number"]))

    def area_sort_key(area_id: str) -> tuple[int, str]:
        return int(area_number(area_id)), area_id

    for display_id, context in group_context.items():
        owned_ids = set(context["owned_ids"])  # type: ignore[arg-type]
        planned_ids = set(context["planned_ids"])  # type: ignore[arg-type]
        possible_inflow_ids = sorted(
            planned_ids - owned_ids,
            key=area_sort_key,
        )
        possible_outflow_ids = sorted(
            {
                destination_area_id
                for owned_area_id in owned_ids
                for other_display_id in candidate_displays_by_area[owned_area_id]
                if other_display_id != display_id
                for destination_area_id in group_context[other_display_id][
                    "owned_ids"
                ]  # type: ignore[union-attr]
                if destination_area_id not in owned_ids
            },
            key=area_sort_key,
        )
        if context["exact_assignment"]:
            possible_inflow_ids = []
            possible_outflow_ids = []
        ambiguity_type = (
            "inflow_and_outflow"
            if possible_inflow_ids and possible_outflow_ids
            else "possible_outflow"
            if possible_outflow_ids
            else "possible_inflow"
            if possible_inflow_ids
            else "undirected_uncertainty"
        )
        context["possible_inflow_ids"] = possible_inflow_ids
        context["possible_inflow_numbers"] = [
            area_number(area_id) for area_id in possible_inflow_ids
        ]
        context["possible_outflow_ids"] = possible_outflow_ids
        context["possible_outflow_numbers"] = [
            area_number(area_id) for area_id in possible_outflow_ids
        ]
        context["ambiguity_type"] = (
            "exact" if context["exact_assignment"] else ambiguity_type
        )

    network_area_ids = set(area_owner)
    configured_ballots = set(ballot_owner)
    configured_result_ballots = set(results["source_kalpi"]) & configured_ballots
    if configured_result_ballots != configured_ballots:
        raise ValueError(
            "Configured final ballots are missing from results: "
            f"{sorted(configured_ballots - configured_result_ballots)}"
        )

    scoped_results = results.loc[
        results["stat_area_id"].isin(network_area_ids)
        | results["source_kalpi"].isin(configured_ballots)
    ].copy()
    scoped_results["display_geography_id"] = scoped_results["source_kalpi"].map(
        ballot_owner
    )
    needs_area_owner = scoped_results["display_geography_id"].isna()
    scoped_results.loc[needs_area_owner, "display_geography_id"] = scoped_results.loc[
        needs_area_owner, "stat_area_id"
    ].map(area_owner)
    if scoped_results["display_geography_id"].isna().any():
        missing = scoped_results.loc[
            scoped_results["display_geography_id"].isna(),
            ["source_row_uid", "source_kalpi", "stat_area_id"],
        ]
        raise ValueError(f"Scoped result rows lack display ownership:\n{missing}")

    scoped_results = numeric(scoped_results, NUMERIC_CORE + parties)
    value_columns = NUMERIC_CORE + parties
    grouped = scoped_results.groupby("display_geography_id", dropna=False)
    aggregated = grouped[value_columns].sum().reset_index()
    aggregated["contributing_rows"] = grouped.size().to_numpy()
    aggregated["contributing_kalpis"] = grouped["source_kalpi"].nunique().to_numpy()
    aggregated = add_winner_fields(aggregated, parties)

    result_rows: list[dict[str, object]] = []
    for aggregate_row in aggregated.to_dict("records"):
        display_id = clean(aggregate_row["display_geography_id"])
        context = group_context[display_id]
        ambiguous_count = int(
            scoped_results.loc[
                scoped_results["display_geography_id"].eq(display_id)
                & scoped_results["source_kalpi"].isin(
                    context["source_ballots"]  # type: ignore[arg-type]
                )
            ].shape[0]
        )
        preserved_count = int(aggregate_row["contributing_rows"]) - ambiguous_count
        notice_he, notice_en = build_notice(
            exact_assignment=bool(context["exact_assignment"]),
            possible_inflow_numbers=context[  # type: ignore[arg-type]
                "possible_inflow_numbers"
            ],
            possible_outflow_numbers=context[  # type: ignore[arg-type]
                "possible_outflow_numbers"
            ],
        )
        display_area_label = ", ".join(context["area_numbers"])
        feature = {
            "type": "Feature",
            "id": display_id,
            "properties": {
                "custom_id": display_id,
                "custom_key": display_id,
                "name_he": f"{context['locality_name_he']} · {display_area_label}",
                "name_en": f"{context['locality_name_en']} · {display_area_label}",
                "display_mode": "polygon",
                "geometry_source": (
                    "reviewed_exact_polling_group"
                    if context["exact_assignment"]
                    else "reviewed_representative_polling_group"
                ),
                "elections": election,
                "locality_code": locality_code,
                "component_stat_area_ids": "|".join(context["owned_ids"]),
                "planned_stat_area_ids": "|".join(context["planned_ids"]),
                "source_ballots": "|".join(context["source_ballots"]),
                "planned_eligible_voters": context["planned_total"],
                "represented_planned_eligible_voters": context["represented_total"],
                "represented_planned_share": round(
                    float(context["represented_share"]), 6
                ),
                "component_adjacency": (
                    "connected" if context["connected"] else "disconnected"
                ),
                "evidence_group_id": clean(context["row"]["evidence_group_id"]),
                "source_evidence": clean(context["row"]["source_evidence"]),
                "evidence_warnings": clean(context["row"]["evidence_warnings"]),
                "ownership_status": clean(context["row"]["ownership_status"]),
                "ownership_policy": clean(context["row"]["ownership_policy"]),
                "review_status": clean(context["row"]["review_status"]),
                "assignment_precision": (
                    "exact"
                    if context["exact_assignment"]
                    else "representative"
                ),
                "ambiguity_type": context["ambiguity_type"],
                "possible_inflow_stat_area_ids": "|".join(
                    context["possible_inflow_ids"]
                ),
                "possible_inflow_stat_area_numbers": "|".join(
                    context["possible_inflow_numbers"]
                ),
                "possible_outflow_display_stat_area_ids": "|".join(
                    context["possible_outflow_ids"]
                ),
                "possible_outflow_display_stat_area_numbers": "|".join(
                    context["possible_outflow_numbers"]
                ),
                "notice_he": notice_he,
                "notice_en": notice_en,
                "note": clean(context["row"]["note"]),
            },
            "geometry": context["display_geometry"],
        }
        geometry_features.append(feature)
        metadata_rows.append(
            {
                "display_geography_id": display_id,
                "election": election,
                "locality_code": locality_code,
                "evidence_group_id": clean(context["row"]["evidence_group_id"]),
                "source_site_ids": clean(context["row"]["source_site_ids"]),
                "final_site_ids": clean(context["row"]["final_site_ids"]),
                "source_site_audit_id": clean(context["row"]["source_site_audit_id"]),
                "component_count": len(context["owned_ids"]),
                "component_stat_area_ids": "|".join(context["owned_ids"]),
                "component_stat_area_numbers": "|".join(context["area_numbers"]),
                "planned_stat_area_ids": "|".join(context["planned_ids"]),
                "omitted_shared_stat_area_ids": "|".join(context["omitted_ids"]),
                "source_ballots": "|".join(context["source_ballots"]),
                "planned_eligible_voters": context["planned_total"],
                "represented_planned_eligible_voters": context["represented_total"],
                "represented_planned_share": round(
                    float(context["represented_share"]), 6
                ),
                "source_result_rows": int(aggregate_row["contributing_rows"]),
                "ambiguous_result_rows": ambiguous_count,
                "preserved_direct_result_rows": preserved_count,
                "geometry_part_count": context["part_count"],
                "component_adjacency": (
                    "connected" if context["connected"] else "disconnected"
                ),
                "source_evidence": clean(context["row"]["source_evidence"]),
                "evidence_warnings": clean(context["row"]["evidence_warnings"]),
                "ownership_status": clean(context["row"]["ownership_status"]),
                "review_status": clean(context["row"]["review_status"]),
                "assignment_precision": (
                    "exact"
                    if context["exact_assignment"]
                    else "representative"
                ),
                "ambiguity_type": context["ambiguity_type"],
                "possible_inflow_stat_area_ids": "|".join(
                    context["possible_inflow_ids"]
                ),
                "possible_inflow_stat_area_numbers": "|".join(
                    context["possible_inflow_numbers"]
                ),
                "possible_outflow_display_stat_area_ids": "|".join(
                    context["possible_outflow_ids"]
                ),
                "possible_outflow_display_stat_area_numbers": "|".join(
                    context["possible_outflow_numbers"]
                ),
            }
        )
        result_rows.append(
            {
                "election": election,
                "geography_mode": "statistical-area",
                "custom_geography_id": display_id,
                "geography_id": display_id,
                "locality_name": context["locality_name_he"],
                "component_stat_area_ids": "|".join(context["owned_ids"]),
                "contributing_rows": int(aggregate_row["contributing_rows"]),
                "contributing_kalpis": int(aggregate_row["contributing_kalpis"]),
                **{column: int(aggregate_row[column]) for column in NUMERIC_CORE},
                **{party: int(aggregate_row[party]) for party in parties},
                "winning_ballot_letter": clean(
                    aggregate_row["winning_ballot_letter"]
                ),
                "winning_votes": int(aggregate_row["winning_votes"]),
                "runner_up_votes": int(aggregate_row["runner_up_votes"]),
                "margin_votes": int(aggregate_row["margin_votes"]),
                "winning_vote_share": float(
                    aggregate_row["winning_vote_share"]
                ),
            }
        )

    source_totals = scoped_results[value_columns].sum()
    display_totals = pd.DataFrame(result_rows)[value_columns].sum()
    mismatches = {
        column: (int(source_totals[column]), int(display_totals[column]))
        for column in value_columns
        if int(source_totals[column]) != int(display_totals[column])
    }
    if mismatches:
        raise ValueError(f"Polling-group display totals do not reconcile: {mismatches}")

    totals = Counter(
        {
            "eligible_voters": int(source_totals["eligible_voters"]),
            "actual_voters": int(source_totals["actual_voters"]),
            "valid_votes": int(source_totals["valid_votes"]),
        }
    )
    return geometry_features, metadata_rows, result_rows, totals


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--election")
    args = parser.parse_args()
    with CONFIG_PATH.open(encoding="utf-8-sig", newline="") as handle:
        configured_groups = list(csv.DictReader(handle))
    if not configured_groups:
        raise SystemExit(f"No polling-group display policy found in {CONFIG_PATH}")
    if REVIEW_CONFIG_PATH.exists():
        with REVIEW_CONFIG_PATH.open(encoding="utf-8-sig", newline="") as handle:
            review_groups = list(csv.DictReader(handle))
        configured_groups = apply_reviewed_display_groups(
            configured_groups,
            review_groups,
        )
    if args.election:
        configured_groups = [row for row in configured_groups if clean(row["election"]) == args.election]

    display_ids = [clean(row["display_geography_id"]) for row in configured_groups]
    duplicates = sorted(
        display_id
        for display_id, count in Counter(display_ids).items()
        if not display_id or count > 1
    )
    if duplicates:
        raise ValueError(f"Duplicate or blank display IDs: {duplicates}")

    source_geometry = gpd.read_file(SOURCE_GEOMETRY_PATH, engine="pyogrio")
    if source_geometry.crs is None:
        source_geometry = source_geometry.set_crs("EPSG:4326")
    source_geometry = source_geometry.to_crs("EPSG:4326")
    current_geometry = gpd.read_file(SOURCE_GEOMETRY_PATH.with_name("statistical_areas_2022.display.simplified.geojson"), engine="pyogrio").to_crs("EPSG:4326")
    current_geometry["stat_area_number"] = current_geometry["stat_2022"]
    source_geometry = pd.concat([source_geometry, current_geometry], ignore_index=True)
    geometry_by_id = source_geometry.set_index("stat_area_id", drop=False)

    groups_by_scope: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in configured_groups:
        groups_by_scope[(clean(row["election"]), clean(row["locality_code"]))].append(
            row
        )

    elections = sorted({election for election, _ in groups_by_scope})
    results_by_election: dict[str, pd.DataFrame] = {}
    for election in elections:
        election_results = pd.read_csv(
            RESULTS_DIR / f"{election.lower()}_ballot_votes.csv",
            dtype=str,
            encoding="utf-8-sig",
        ).fillna("")
        election_results = election_results.loc[
            election_results["election"].eq(election)
        ].copy()
        election_results["_locality_code"] = election_results[
            "source_locality_code"
        ].map(clean)
        results_by_election[election] = election_results

    assignments = pd.read_csv(
        ASSIGNMENTS_PATH,
        dtype=str,
        encoding="utf-8-sig",
    ).fillna("")
    assignments = assignments.loc[assignments["election"].isin(elections)].copy()
    assignments["_locality_code"] = assignments["source_locality_code"].map(clean)
    assignments_by_election = {
        election: assignments.loc[assignments["election"].eq(election)].copy()
        for election in elections
    }

    geometry_features: list[dict[str, object]] = []
    metadata_rows: list[dict[str, object]] = []
    result_rows: list[dict[str, object]] = []
    groups_by_election: Counter[str] = Counter()
    exact_groups_by_election: Counter[str] = Counter()
    localities_by_election: dict[str, set[str]] = defaultdict(set)
    owned_areas_by_election: dict[str, set[str]] = defaultdict(set)
    for (election, locality_code), scope_groups in sorted(groups_by_scope.items()):
        scope_geometry, scope_metadata, scope_results, totals = build_election(
            scope_groups,
            geometry_by_id,
            results_by_election[election],
            assignments_by_election[election],
            election,
            locality_code,
        )
        geometry_features.extend(scope_geometry)
        metadata_rows.extend(scope_metadata)
        result_rows.extend(scope_results)
        shares = [
            float(row["represented_planned_share"]) for row in scope_metadata
        ]
        owned_area_ids = {
            area_id
            for row in scope_metadata
            for area_id in split_pipe(row["component_stat_area_ids"])
        }
        if not shares or not totals:
            raise ValueError(
                f"{election}/{locality_code} produced an empty polling-group scope"
            )
        groups_by_election[election] += len(scope_results)
        exact_groups_by_election[election] += sum(
            row["assignment_precision"] == "exact"
            for row in scope_metadata
        )
        localities_by_election[election].add(locality_code)
        owned_areas_by_election[election].update(owned_area_ids)

    feature_collection = {
        "type": "FeatureCollection",
        "name": "statistical_area_polling_group_displays",
        "features": geometry_features,
    }
    if args.election:
        previous = json.loads(OUTPUT_GEOMETRY_PATH.read_text(encoding="utf-8"))
        feature_collection["features"] = [feature for feature in previous["features"] if feature["properties"]["elections"] != args.election] + geometry_features
        metadata_rows = preserve_other_elections(OUTPUT_METADATA_PATH, metadata_rows, args.election)
        result_rows = preserve_other_elections(OUTPUT_RESULTS_PATH, result_rows, args.election)
    OUTPUT_GEOMETRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_GEOMETRY_PATH.write_text(
        f"{json.dumps(feature_collection, ensure_ascii=False, separators=(',', ':'))}\n",
        encoding="utf-8",
    )
    write_csv(OUTPUT_METADATA_PATH, metadata_rows)
    write_csv(OUTPUT_RESULTS_PATH, result_rows)

    print(
        f"built {len(result_rows)} polling-group displays: "
        + ", ".join(
            (
                f"{election}={groups_by_election[election]} groups/"
                f"{exact_groups_by_election[election]} exact/"
                f"{groups_by_election[election] - exact_groups_by_election[election]} "
                "representative/"
                f"{len(localities_by_election[election])} localities/"
                f"{len(owned_areas_by_election[election])} polygons"
            )
            for election in sorted(groups_by_election)
        )
    )


if __name__ == "__main__":
    main()
