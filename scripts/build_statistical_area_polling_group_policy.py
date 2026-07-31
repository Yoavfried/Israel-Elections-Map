from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LOCAL_PYTHON = ROOT / ".local" / "python-geo"
if LOCAL_PYTHON.exists():
    sys.path.insert(0, str(LOCAL_PYTHON))
sys.path.insert(0, str(ROOT / "scripts"))

import geopandas as gpd
import pandas as pd

from build_statistical_area_result_aggregates import (
    ADJACENCY_TOLERANCE_METERS,
    METRIC_CRS,
)
from polling_group_flow import analyze_exact_flow
from polling_group_ownership import solve_polling_group_ownership


AUDIT_DIR = ROOT / "data" / "processed" / "audits"
SITE_AUDIT_PATH = AUDIT_DIR / "statistical_area_polling_group_sites.csv"
COMPONENT_AUDIT_PATH = (
    AUDIT_DIR / "statistical_area_polling_group_components.csv"
)
GEOMETRY_PATH = (
    ROOT
    / "data"
    / "processed"
    / "geographies"
    / "statistical_areas_2011.display.simplified.geojson"
)
OUTPUT_PATH = (
    AUDIT_DIR / "statistical_area_polling_group_policy_audit.csv"
)
SUMMARY_PATH = (
    AUDIT_DIR / "statistical_area_polling_group_policy_summary.json"
)
POLICY_PATH = AUDIT_DIR / "statistical_area_polling_group_policy.csv"
FALLBACK_PATH = AUDIT_DIR / "statistical_area_polling_group_fallbacks.csv"
EXACT_GROUP_PATH = (
    AUDIT_DIR / "statistical_area_polling_group_exact_groups.csv"
)
RESULTS_DIR = (
    ROOT / "data" / "processed" / "normalized" / "ballot_votes_wide"
)
ASSIGNMENTS_PATH = (
    ROOT
    / "data"
    / "processed"
    / "assignments"
    / "historical_ballot_assignments.csv"
)
TESTABLE_EVIDENCE = {
    "official_pre_and_post_balance_registers",
    "official_pre_balance_register_and_final_results",
}
REPRESENTATIVE_STATUSES = {
    "connected_solution",
    "solution_requires_disconnected_geometry",
}
FALLBACK_STATUSES = {
    "fewer_polygons_than_polling_groups",
    "no_every-group-owns-polygon_solution",
}
EXACT_COMPONENT_CLASSIFICATIONS = {
    "isolated_closed_aggregate",
    "isolated_near_balance_aggregate",
    "connected_closed_aggregate",
    "connected_near_balance_aggregate",
}
EXACT_NETWORK_BALANCES = {
    "exact",
    "within_3",
    "within_half_percent",
}


def clean(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def integer(value: Any) -> int:
    text = clean(value)
    return int(float(text)) if text else 0


def split_pipe(value: Any) -> list[str]:
    return sorted(
        {
            part.strip()
            for part in clean(value).split("|")
            if part.strip()
        }
    )


def ballot_base(value: Any) -> str:
    return clean(value).split(".", 1)[0]


def balance_class(difference: int, planned: int) -> str:
    if difference == 0:
        return "exact"
    if abs(difference) <= 3:
        return "within_3"
    if planned and abs(difference) / planned <= 0.005:
        return "within_half_percent"
    return "mismatch"


def read_area_weights(value: Any) -> dict[str, int]:
    text = clean(value)
    if not text:
        return {}
    parsed = json.loads(text)
    return {clean(area_id): integer(eligible) for area_id, eligible in parsed.items()}


def solve_ownership(
    area_ids: list[str],
    sites_by_id: dict[str, dict[str, Any]],
    geometry_by_id: dict[str, Any],
) -> dict[str, Any]:
    return solve_polling_group_ownership(
        area_ids,
        sites_by_id,
        geometry_by_id,
        metric_crs=METRIC_CRS,
        tolerance_meters=ADJACENCY_TOLERANCE_METERS,
    )


def build_exact_closed_units(
    component_id: str,
    component_sites: list[dict[str, Any]],
    area_ids: list[str],
    network_balance: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    area_supplies = {
        area_id: sum(
            read_area_weights(site["residual_area_planned_eligible"]).get(
                area_id,
                0,
            )
            for site in component_sites
        )
        for area_id in area_ids
    }
    group_demands = {
        clean(site["site_audit_id"]): integer(
            site["final_residual_eligible"]
        )
        for site in component_sites
    }
    allowed_areas_by_group = {
        clean(site["site_audit_id"]): set(
            split_pipe(site["residual_area_ids"])
        )
        for site in component_sites
    }
    sites_by_id = {
        clean(site["site_audit_id"]): site for site in component_sites
    }

    flow_analysis = None
    if (
        network_balance == "exact"
        and all(value > 0 for value in area_supplies.values())
        and all(value > 0 for value in group_demands.values())
    ):
        flow_analysis = analyze_exact_flow(
            area_supplies,
            group_demands,
            allowed_areas_by_group,
        )
        raw_units = [
            {
                "area_ids": list(flow_component.area_ids),
                "site_ids": list(flow_component.polling_group_ids),
                "planned_eligible": flow_component.eligible_voters,
                "final_eligible": flow_component.eligible_voters,
                "exactness_basis": "forced_zero_transport_components",
                "ownership_status": "exact_closed_flow_group",
            }
            for flow_component in flow_analysis.components
        ]
    else:
        raw_units = [
            {
                "area_ids": list(area_ids),
                "site_ids": sorted(group_demands),
                "planned_eligible": sum(area_supplies.values()),
                "final_eligible": sum(group_demands.values()),
                "exactness_basis": "closed_official_polling_network",
                "ownership_status": "exact_closed_network",
            }
        ]

    units: list[dict[str, Any]] = []
    for unit_number, raw_unit in enumerate(raw_units, start=1):
        unit_sites = [
            sites_by_id[site_id] for site_id in raw_unit["site_ids"]
        ]
        source_ballots = sorted(
            {
                ballot
                for site in unit_sites
                for ballot in split_pipe(site["residual_final_ballots"])
            }
        )
        if not source_ballots:
            raise ValueError(
                f"{component_id} exact unit {unit_number} has no final ballots"
            )
        units.append(
            {
                **raw_unit,
                "unit_number": unit_number,
                "source_ballots": source_ballots,
                "source_site_ids": sorted(
                    {
                        source_site_id
                        for site in unit_sites
                        for source_site_id in split_pipe(
                            site["planned_site_ids"]
                        )
                    }
                ),
                "final_site_ids": sorted(
                    {
                        final_site_id
                        for site in unit_sites
                        for final_site_id in split_pipe(site["final_site_ids"])
                    }
                ),
                "source_evidence": sorted(
                    {
                        clean(site["source_evidence"])
                        for site in unit_sites
                    }
                ),
            }
        )

    edge_bounds = {}
    forced_zero_edges: list[tuple[str, str]] = []
    if flow_analysis is not None:
        edge_bounds = {
            f"{area_id}->{site_id}": [minimum, maximum]
            for (area_id, site_id), (minimum, maximum) in sorted(
                flow_analysis.edge_bounds.items()
            )
        }
        forced_zero_edges = list(flow_analysis.forced_zero_edges)
    return units, {
        "area_supplies": area_supplies,
        "group_demands": group_demands,
        "edge_bounds": edge_bounds,
        "forced_zero_edges": forced_zero_edges,
        "flow_component_count": (
            len(flow_analysis.components)
            if flow_analysis is not None
            else 1
        ),
    }


def continuity_identity(site: dict[str, Any]) -> tuple[str, str, str]:
    return (
        clean(site["locality_code"]),
        clean(site["planned_site_ids"]),
        clean(site["site_labels"]),
    )


def build_continuity_candidates(
    sites: pd.DataFrame,
    geometry_by_id: dict[str, Any],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    direct_sites = [
        row
        for row in sites.to_dict("records")
        if clean(row["source_evidence"]) in TESTABLE_EVIDENCE
        and len(split_pipe(row["residual_area_ids"])) > 1
        and split_pipe(row["residual_final_ballots"])
    ]
    references_by_identity: dict[
        tuple[str, str, str], list[dict[str, Any]]
    ] = defaultdict(list)
    for site in direct_sites:
        identity = continuity_identity(site)
        if identity[1] and identity[2]:
            references_by_identity[identity].append(site)

    assignments = pd.read_csv(
        ASSIGNMENTS_PATH,
        dtype=str,
        encoding="utf-8-sig",
    ).fillna("")
    assignment_lookup = assignments.set_index("source_row_uid")[
        "stat_area_id"
    ].to_dict()
    target_elections = ("K20", "K22", "K23")
    target_results: dict[str, pd.DataFrame] = {}
    for election in target_elections:
        frame = pd.read_csv(
            RESULTS_DIR / f"{election.lower()}_ballot_votes.csv",
            dtype=str,
            encoding="utf-8-sig",
        ).fillna("")
        frame["source_kalpi"] = frame["source_kalpi"].map(clean)
        frame["source_locality_code"] = frame["source_locality_code"].map(clean)
        frame["ballot_base"] = frame["source_kalpi"].map(ballot_base)
        frame["eligible_voters"] = frame["eligible_voters"].map(integer)
        frame["stat_area_id"] = frame["source_row_uid"].map(
            assignment_lookup
        ).fillna("")
        target_results[election] = frame

    candidate_groups: list[dict[str, Any]] = []
    used_target_ballots: set[tuple[str, str, str]] = set()
    post_balance_sites = [
        row
        for row in sites.to_dict("records")
        if clean(row["election"]) in target_elections
        and clean(row["source_evidence"]).startswith(
            "official_post_balance_register"
        )
    ]
    for target_site in post_balance_sites:
        election = clean(target_site["election"])
        locality_code = clean(target_site["locality_code"])
        identity = continuity_identity(target_site)
        references = references_by_identity.get(identity, [])
        if not references:
            continue
        target_ballots = split_pipe(target_site["planned_ballots"])
        target_bases = sorted(
            {ballot_base(value) for value in target_ballots}
            - {"", "990"}
        )
        results = target_results[election]
        locality_results = results.loc[
            results["source_locality_code"].eq(locality_code)
        ]

        for base in target_bases:
            base_references = [
                reference
                for reference in references
                if base
                in {
                    ballot_base(value)
                    for value in split_pipe(
                        reference["residual_final_ballots"]
                    )
                }
            ]
            reference_elections = sorted(
                {clean(reference["election"]) for reference in base_references}
            )
            if len(reference_elections) < 2:
                continue
            reference_area_sets = [
                set(split_pipe(reference["residual_area_ids"]))
                for reference in base_references
            ]
            candidate_area_ids = sorted(
                set.intersection(*reference_area_sets)
                if reference_area_sets
                else set()
            )
            if len(candidate_area_ids) < 2:
                continue
            if any(
                area_id not in geometry_by_id
                for area_id in candidate_area_ids
            ):
                continue

            source_ballots = sorted(
                value
                for value in target_ballots
                if ballot_base(value) == base
            )
            result_rows = locality_results.loc[
                locality_results["source_kalpi"].isin(source_ballots)
            ].copy()
            if sorted(set(result_rows["source_kalpi"])) != source_ballots:
                continue
            result_hosts = sorted(
                set(result_rows["stat_area_id"]) - {""}
            )
            if not result_hosts or not set(result_hosts).issubset(
                candidate_area_ids
            ):
                continue
            target_keys = {
                (election, locality_code, source_ballot)
                for source_ballot in source_ballots
            }
            if target_keys & used_target_ballots:
                continue
            used_target_ballots.update(target_keys)

            reference_weights = {
                area_id: sum(
                    read_area_weights(
                        reference["residual_area_planned_eligible"]
                    ).get(area_id, 0)
                    for reference in base_references
                )
                for area_id in candidate_area_ids
            }
            planned_reference_total = sum(reference_weights.values())
            if planned_reference_total <= 0:
                continue
            group_id = (
                f"continuity:{election}:{locality_code}:"
                f"{clean(target_site['site_audit_id']).rsplit(':', 1)[-1]}:"
                f"{base}"
            )
            candidate_groups.append(
                {
                    "group_id": group_id,
                    "election": election,
                    "locality_code": locality_code,
                    "locality_name": clean(target_site["locality_name"]),
                    "source_site_audit_id": clean(
                        target_site["site_audit_id"]
                    ),
                    "source_site_ids": clean(target_site["planned_site_ids"]),
                    "final_site_ids": clean(target_site["final_site_ids"]),
                    "area_ids": set(candidate_area_ids),
                    "weights": reference_weights,
                    "planned": planned_reference_total,
                    "source_ballots": source_ballots,
                    "final_eligible": int(
                        result_rows["eligible_voters"].sum()
                    ),
                    "reference_elections": reference_elections,
                    "reference_site_audit_ids": sorted(
                        {
                            clean(reference["site_audit_id"])
                            for reference in base_references
                        }
                    ),
                    "reference_area_sets_differ": (
                        len(
                            {
                                tuple(sorted(area_set))
                                for area_set in reference_area_sets
                            }
                        )
                        > 1
                    ),
                }
            )

    groups_by_scope: dict[
        tuple[str, str], list[dict[str, Any]]
    ] = defaultdict(list)
    for group in candidate_groups:
        groups_by_scope[
            (clean(group["election"]), clean(group["locality_code"]))
        ].append(group)

    policy_rows: list[dict[str, Any]] = []
    fallback_rows: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    for (election, locality_code), scope_groups in sorted(
        groups_by_scope.items()
    ):
        parent: dict[str, str] = {}

        def find(value: str) -> str:
            parent.setdefault(value, value)
            if parent[value] != value:
                parent[value] = find(parent[value])
            return parent[value]

        def union(left: str, right: str) -> None:
            left_root = find(left)
            right_root = find(right)
            if left_root != right_root:
                parent[right_root] = left_root

        for group in scope_groups:
            area_ids = sorted(group["area_ids"])
            for area_id in area_ids:
                find(area_id)
            for area_id in area_ids[1:]:
                union(area_ids[0], area_id)

        component_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for group in scope_groups:
            first_area = min(group["area_ids"])
            component_groups[find(first_area)].append(group)

        for component_number, groups_in_component in enumerate(
            sorted(
                component_groups.values(),
                key=lambda values: min(
                    min(group["area_ids"]) for group in values
                ),
            ),
            start=1,
        ):
            component_id = (
                f"continuity:{election}:{locality_code}:"
                f"component:{component_number}"
            )
            area_ids = sorted(
                set().union(
                    *(group["area_ids"] for group in groups_in_component)
                )
            )
            ownership_groups = {
                clean(group["group_id"]): {
                    "area_ids": set(group["area_ids"]),
                    "planned": integer(group["planned"]),
                    "weights": dict(group["weights"]),
                }
                for group in groups_in_component
            }
            ownership_result = solve_ownership(
                area_ids,
                ownership_groups,
                geometry_by_id,
            )
            status = clean(ownership_result["status"])
            references = sorted(
                {
                    election_id
                    for group in groups_in_component
                    for election_id in group["reference_elections"]
                }
            )
            audit_rows.append(
                {
                    "aggregate_component_id": component_id,
                    "election": election,
                    "locality_code": locality_code,
                    "locality_name": clean(
                        groups_in_component[0]["locality_name"]
                    ),
                    "original_component_classification": (
                        "cross_election_consensus_continuity"
                    ),
                    "area_count": len(area_ids),
                    "polling_group_count": len(groups_in_component),
                    "stat_area_ids": "|".join(area_ids),
                    "polling_group_ids": "|".join(
                        sorted(
                            clean(group["group_id"])
                            for group in groups_in_component
                        )
                    ),
                    "network_planned_eligible": sum(
                        integer(group["planned"])
                        for group in groups_in_component
                    ),
                    "network_final_eligible": sum(
                        integer(group["final_eligible"])
                        for group in groups_in_component
                    ),
                    "eligible_difference": "",
                    "eligible_difference_share": "",
                    "network_balance": "not_comparable_cross_election",
                    "data_issues": "",
                    "evidence_warnings": (
                        "cross_election_continuity"
                    ),
                    "network_supported": True,
                    "ownership_status": status,
                    "minimum_represented_share": ownership_result.get(
                        "minimum_represented_share", ""
                    ),
                    "mean_represented_share": ownership_result.get(
                        "mean_represented_share", ""
                    ),
                    "total_represented_planned_eligible": (
                        ownership_result.get(
                            "total_represented_planned_eligible", ""
                        )
                    ),
                    "representative_ownership": json.dumps(
                        ownership_result.get("ownership", {}),
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                    "represented_share_by_group": json.dumps(
                        ownership_result.get("represented_shares", {}),
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                    "ownership_search_nodes": (
                        ownership_result["search"].visited_nodes
                        if "search" in ownership_result
                        else ""
                    ),
                    "ownership_search_limited": (
                        ownership_result["search"].search_limit_reached
                        if "search" in ownership_result
                        else ""
                    ),
                    "current_display_status": (
                        "generated_representative_units"
                        if status in REPRESENTATIVE_STATUSES
                        else "generated_exact_network_fallback"
                        if status in FALLBACK_STATUSES
                        else "not_generated"
                    ),
                }
            )

            if status in REPRESENTATIVE_STATUSES:
                ownership = ownership_result["ownership"]
                shares = ownership_result["represented_shares"]
                by_id = {
                    clean(group["group_id"]): group
                    for group in groups_in_component
                }
                for group_id in sorted(by_id):
                    group = by_id[group_id]
                    owned_ids = list(ownership[group_id])
                    represented = sum(
                        group["weights"].get(area_id, 0)
                        for area_id in owned_ids
                    )
                    warnings = ["cross_election_continuity"]
                    if group["reference_area_sets_differ"]:
                        warnings.append(
                            "reference_area_sets_intersected"
                        )
                    policy_rows.append(
                        {
                            "display_geography_id": (
                                f"display:polling-group:{group_id}"
                            ),
                            "election": election,
                            "locality_code": locality_code,
                            "locality_name": clean(group["locality_name"]),
                            "evidence_group_id": component_id,
                            "source_site_audit_id": clean(
                                group["source_site_audit_id"]
                            ),
                            "source_site_ids": clean(
                                group["source_site_ids"]
                            ),
                            "final_site_ids": clean(group["final_site_ids"]),
                            "owned_stat_area_ids": "|".join(owned_ids),
                            "planned_stat_area_ids": "|".join(
                                sorted(group["area_ids"])
                            ),
                            "ambiguous_final_ballots": "|".join(
                                group["source_ballots"]
                            ),
                            "planned_eligible_voters": integer(
                                group["planned"]
                            ),
                            "represented_planned_eligible_voters": represented,
                            "represented_planned_share": round(
                                float(shares[group_id]), 8
                            ),
                            "final_eligible_voters": integer(
                                group["final_eligible"]
                            ),
                            "component_network_balance": (
                                "not_comparable_cross_election"
                            ),
                            "component_eligible_difference": "",
                            "source_evidence": (
                                "official_cross_election_polling_site_continuity"
                            ),
                            "continuity_reference_elections": "|".join(
                                group["reference_elections"]
                            ),
                            "continuity_reference_site_audit_ids": "|".join(
                                group["reference_site_audit_ids"]
                            ),
                            "evidence_warnings": "|".join(warnings),
                            "ownership_status": status,
                            "ownership_policy": (
                                "maximize_minimum_represented_share_then_total_"
                                "with_unique_polygon_ownership"
                            ),
                            "review_status": "approved-rule-generated",
                            "note": (
                                "Exact target-election polling-group totals; "
                                f"candidate areas are the consensus intersection "
                                f"of exact site/base matches in "
                                f"{', '.join(group['reference_elections'])}."
                            ),
                        }
                    )
            elif status in FALLBACK_STATUSES:
                fallback_rows.append(
                    {
                        "display_geography_id": (
                            f"display:polling-network-fallback:"
                            f"{component_id}"
                        ),
                        "elections": election,
                        "component_stat_area_ids": "|".join(area_ids),
                        "aggregation_method": "sum-components",
                        "evidence_group_id": component_id,
                        "evidence_class": (
                            "representative_ownership_impossible"
                        ),
                        "review_status": "approved-rule-fallback",
                        "note": (
                            "Cross-election consensus network retained as an "
                            f"exact aggregate because {status.replace('_', ' ')}."
                        ),
                    }
                )

    return policy_rows, fallback_rows, audit_rows


def write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"Cannot write empty polling-group output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def validate_generated_policy(
    policy_rows: list[dict[str, Any]],
    fallback_rows: list[dict[str, Any]],
    audit_rows: list[dict[str, Any]],
) -> None:
    display_ids: set[str] = set()
    area_owners: dict[tuple[str, str], str] = {}
    ballot_owners: dict[tuple[str, str, str], str] = {}
    for row in policy_rows:
        display_id = clean(row["display_geography_id"])
        election = clean(row["election"])
        locality_code = clean(row["locality_code"])
        owned_ids = split_pipe(row["owned_stat_area_ids"])
        planned_ids = split_pipe(row["planned_stat_area_ids"])
        ballots = split_pipe(row["ambiguous_final_ballots"])
        if not display_id or display_id in display_ids:
            raise ValueError(f"Duplicate or blank generated display ID: {display_id!r}")
        if not owned_ids or not ballots:
            raise ValueError(f"{display_id} lacks owned polygons or final ballots")
        if not set(owned_ids).issubset(planned_ids):
            raise ValueError(
                f"{display_id} owns polygons outside its candidate set: "
                f"{sorted(set(owned_ids) - set(planned_ids))}"
            )
        display_ids.add(display_id)
        for area_id in owned_ids:
            key = (election, area_id)
            if key in area_owners:
                raise ValueError(
                    f"{election} polygon {area_id} is owned by both "
                    f"{area_owners[key]} and {display_id}"
                )
            area_owners[key] = display_id
        for ballot in ballots:
            key = (election, locality_code, ballot)
            if key in ballot_owners:
                raise ValueError(
                    f"{election}/{locality_code} ballot {ballot} is owned by both "
                    f"{ballot_owners[key]} and {display_id}"
                )
            ballot_owners[key] = display_id

    fallback_owners: dict[tuple[str, str], str] = {}
    for row in fallback_rows:
        display_id = clean(row["display_geography_id"])
        elections = split_pipe(row["elections"])
        area_ids = split_pipe(row["component_stat_area_ids"])
        if not display_id or not elections or not area_ids:
            raise ValueError(f"Incomplete generated fallback row: {row}")
        for election in elections:
            for area_id in area_ids:
                key = (election, area_id)
                if key in area_owners:
                    raise ValueError(
                        f"{display_id} fallback overlaps representative owner "
                        f"{area_owners[key]} on {election}/{area_id}"
                    )
                if key in fallback_owners:
                    raise ValueError(
                        f"{election} polygon {area_id} appears in fallbacks "
                        f"{fallback_owners[key]} and {display_id}"
                    )
                fallback_owners[key] = display_id

    limited = [
        clean(row["aggregate_component_id"])
        for row in audit_rows
        if row.get("ownership_search_limited") is True
        or clean(row.get("ownership_search_limited")).lower() == "true"
    ]
    if limited:
        raise ValueError(
            "Ownership search limit reached; generated policy is incomplete for "
            f"{limited}"
        )


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    sites = pd.read_csv(SITE_AUDIT_PATH, dtype=str, encoding="utf-8-sig").fillna("")
    components = pd.read_csv(
        COMPONENT_AUDIT_PATH,
        dtype=str,
        encoding="utf-8-sig",
    ).fillna("")
    geometry = gpd.read_file(GEOMETRY_PATH, engine="pyogrio")
    if geometry.crs is None:
        geometry = geometry.set_crs("EPSG:4326")
    geometry = geometry.to_crs("EPSG:4326")
    geometry_by_id = geometry.set_index("stat_area_id").geometry.to_dict()

    sites_by_id = {
        clean(row["site_audit_id"]): row
        for row in sites.to_dict("records")
    }
    output_rows: list[dict[str, Any]] = []
    policy_rows: list[dict[str, Any]] = []
    fallback_rows: list[dict[str, Any]] = []
    exact_group_rows: list[dict[str, Any]] = []

    for component in components.to_dict("records"):
        component_id = clean(component["aggregate_component_id"])
        site_ids = split_pipe(component["ambiguous_site_ids"])
        if not site_ids:
            continue
        source_area_ids = split_pipe(component["stat_area_ids"])
        source_component_sites = [sites_by_id[site_id] for site_id in site_ids]
        omitted_site_ids = sorted(
            clean(site["site_audit_id"])
            for site in source_component_sites
            if not split_pipe(site["residual_final_ballots"])
        )
        component_sites = [
            site
            for site in source_component_sites
            if split_pipe(site["residual_final_ballots"])
        ]
        if not component_sites:
            continue
        site_ids = sorted(
            clean(site["site_audit_id"]) for site in component_sites
        )
        area_ids = sorted(
            set().union(
                *(
                    set(split_pipe(site["residual_area_ids"]))
                    for site in component_sites
                )
            )
        )
        if len(area_ids) < 2:
            continue
        planned = sum(
            integer(site["planned_residual_eligible"])
            for site in component_sites
        )
        final = sum(
            integer(site["final_residual_eligible"])
            for site in component_sites
        )
        difference = final - planned
        difference_share = difference / planned if planned else 0.0
        network_balance = balance_class(difference, planned)
        source_evidence = sorted(
            {clean(site["source_evidence"]) for site in component_sites}
        )
        component_area_set = set(area_ids)
        external_host_ids = sorted(
            {
                host_id
                for site in component_sites
                for host_id in split_pipe(site["current_host_area_ids"])
                if host_id not in component_area_set
            }
        )
        data_issues: list[str] = []
        evidence_warnings: list[str] = []
        if omitted_site_ids:
            evidence_warnings.append(
                "planned_groups_without_final_results_omitted"
            )
        if source_evidence and any(
            evidence not in TESTABLE_EVIDENCE for evidence in source_evidence
        ):
            data_issues.append("source_has_no_pre_balance_register")
        if integer(component["missing_crosswalk_ballots"]):
            data_issues.append("missing_crosswalk_ballots")
        if integer(component["result_rows_without_site_in_locality"]):
            data_issues.append("result_rows_without_site")
        if any(integer(site["unmapped_planned_rows"]) for site in component_sites):
            data_issues.append("unmapped_planned_rows")
        if external_host_ids:
            data_issues.append("result_host_outside_component")
        if any(
            clean(site["final_register_balance"])
            not in {"not_available", "exact", "within_3"}
            for site in component_sites
        ):
            evidence_warnings.append("final_register_eligible_mismatch")
        if any(
            integer(site["final_register_rows_without_result"])
            for site in component_sites
        ):
            data_issues.append("final_register_rows_without_result")
        if any(
            integer(site["final_result_rows_without_register"])
            for site in component_sites
        ):
            data_issues.append("final_result_rows_without_register")
        if network_balance == "mismatch":
            evidence_warnings.append("planned_final_eligible_mismatch")

        network_supported = not data_issues
        component_classification = clean(component["classification"])
        exact_closed_candidate = (
            network_supported
            and component_classification
            in EXACT_COMPONENT_CLASSIFICATIONS
            and network_balance in EXACT_NETWORK_BALANCES
            and not evidence_warnings
        )
        exact_units: list[dict[str, Any]] = []
        exact_diagnostics: dict[str, Any] = {}
        ownership_result: dict[str, Any] = {"status": "not_tested"}
        if exact_closed_candidate:
            exact_units, exact_diagnostics = build_exact_closed_units(
                component_id,
                component_sites,
                area_ids,
                network_balance,
            )
            exact_statuses = {
                clean(unit["ownership_status"]) for unit in exact_units
            }
            ownership_result = {
                "status": (
                    "exact_closed_flow_groups"
                    if exact_statuses == {"exact_closed_flow_group"}
                    else "exact_closed_network"
                )
            }
        elif network_supported:
            ownership_sites = {
                clean(site["site_audit_id"]): {
                    "area_ids": set(split_pipe(site["residual_area_ids"])),
                    "planned": integer(site["planned_residual_eligible"]),
                    "weights": read_area_weights(
                        site["residual_area_planned_eligible"]
                    ),
                }
                for site in component_sites
            }
            ownership_result = solve_ownership(
                area_ids,
                ownership_sites,
                geometry_by_id,
            )

        ownership_status = clean(ownership_result["status"])
        if exact_closed_candidate:
            current_display_status = "generated_exact_closed_units"
        elif network_supported and ownership_status in REPRESENTATIVE_STATUSES:
            current_display_status = "generated_representative_units"
        elif network_supported and ownership_status in FALLBACK_STATUSES:
            current_display_status = "generated_exact_network_fallback"
        else:
            current_display_status = "not_generated"

        audit_row = {
            "aggregate_component_id": component_id,
            "election": clean(component["election"]),
            "locality_code": clean(component["locality_code"]),
            "locality_name": clean(component["locality_name"]),
            "original_component_classification": component_classification,
            "source_component_stat_area_ids": "|".join(source_area_ids),
            "omitted_planned_polling_group_ids": "|".join(
                omitted_site_ids
            ),
            "area_count": len(area_ids),
            "polling_group_count": len(site_ids),
            "stat_area_ids": "|".join(area_ids),
            "polling_group_ids": "|".join(site_ids),
            "network_planned_eligible": planned,
            "network_final_eligible": final,
            "eligible_difference": difference,
            "eligible_difference_share": round(difference_share, 8),
            "network_balance": network_balance,
            "data_issues": "|".join(sorted(set(data_issues))),
            "evidence_warnings": "|".join(
                sorted(set(evidence_warnings))
            ),
            "network_supported": network_supported,
            "ownership_status": ownership_result["status"],
            "minimum_represented_share": (
                round(ownership_result["minimum_represented_share"], 6)
                if "minimum_represented_share" in ownership_result
                else ""
            ),
            "mean_represented_share": (
                round(ownership_result["mean_represented_share"], 6)
                if "mean_represented_share" in ownership_result
                else ""
            ),
            "total_represented_planned_eligible": ownership_result.get(
                "total_represented_planned_eligible",
                "",
            ),
            "representative_ownership": json.dumps(
                ownership_result.get("ownership", {}),
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            "represented_share_by_group": json.dumps(
                ownership_result.get("represented_shares", {}),
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            "ownership_search_nodes": (
                ownership_result["search"].visited_nodes
                if "search" in ownership_result
                else ""
            ),
            "ownership_search_limited": (
                ownership_result["search"].search_limit_reached
                if "search" in ownership_result
                else ""
            ),
            "exact_closed_unit_count": len(exact_units),
            "flow_component_count": exact_diagnostics.get(
                "flow_component_count",
                "",
            ),
            "forced_zero_edge_count": len(
                exact_diagnostics.get("forced_zero_edges", [])
            ),
            "current_display_status": current_display_status,
        }
        output_rows.append(audit_row)

        if exact_closed_candidate:
            election = clean(component["election"])
            locality_code = clean(component["locality_code"])
            locality_name = clean(component["locality_name"])
            for unit in exact_units:
                unit_number = integer(unit["unit_number"])
                owned_ids = list(unit["area_ids"])
                unit_site_ids = list(unit["site_ids"])
                source_ballots = list(unit["source_ballots"])
                display_id = (
                    f"display:polling-exact:{component_id}:{unit_number}"
                )
                policy_rows.append(
                    {
                        "display_geography_id": display_id,
                        "election": election,
                        "locality_code": locality_code,
                        "locality_name": locality_name,
                        "evidence_group_id": component_id,
                        "source_site_audit_id": "|".join(unit_site_ids),
                        "source_site_ids": "|".join(
                            unit["source_site_ids"]
                        ),
                        "final_site_ids": "|".join(unit["final_site_ids"]),
                        "owned_stat_area_ids": "|".join(owned_ids),
                        "planned_stat_area_ids": "|".join(owned_ids),
                        "ambiguous_final_ballots": "|".join(
                            source_ballots
                        ),
                        "planned_eligible_voters": integer(
                            unit["planned_eligible"]
                        ),
                        "represented_planned_eligible_voters": integer(
                            unit["planned_eligible"]
                        ),
                        "represented_planned_share": 1.0,
                        "final_eligible_voters": integer(
                            unit["final_eligible"]
                        ),
                        "component_network_balance": network_balance,
                        "component_eligible_difference": difference,
                        "source_evidence": "|".join(
                            unit["source_evidence"]
                        ),
                        "continuity_reference_elections": "",
                        "continuity_reference_site_audit_ids": "",
                        "evidence_warnings": "",
                        "ownership_status": clean(
                            unit["ownership_status"]
                        ),
                        "ownership_policy": clean(
                            unit["exactness_basis"]
                        ),
                        "review_status": "approved-exact-closed",
                        "note": "",
                    }
                )
                exact_group_rows.append(
                    {
                        "display_geography_id": display_id,
                        "election": election,
                        "locality_code": locality_code,
                        "locality_name": locality_name,
                        "evidence_group_id": component_id,
                        "original_component_classification": (
                            component_classification
                        ),
                        "exactness_basis": clean(
                            unit["exactness_basis"]
                        ),
                        "stat_area_count": len(owned_ids),
                        "stat_area_ids": "|".join(owned_ids),
                        "polling_group_count": len(unit_site_ids),
                        "polling_group_ids": "|".join(unit_site_ids),
                        "final_ballot_count": len(source_ballots),
                        "final_ballots": "|".join(source_ballots),
                        "planned_eligible_voters": integer(
                            unit["planned_eligible"]
                        ),
                        "final_eligible_voters": integer(
                            unit["final_eligible"]
                        ),
                        "eligible_difference": (
                            integer(unit["final_eligible"])
                            - integer(unit["planned_eligible"])
                        ),
                        "network_balance": network_balance,
                        "forced_zero_edges": "|".join(
                            f"{area_id}->{site_id}"
                            for area_id, site_id in exact_diagnostics.get(
                                "forced_zero_edges",
                                [],
                            )
                        ),
                        "flow_edge_bounds": json.dumps(
                            exact_diagnostics.get("edge_bounds", {}),
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                        "review_status": "approved-exact-closed",
                    }
                )
        elif network_supported and ownership_status in REPRESENTATIVE_STATUSES:
            ownership = ownership_result["ownership"]
            represented_shares = ownership_result["represented_shares"]
            for site_id in site_ids:
                site = sites_by_id[site_id]
                owned_ids = list(ownership[site_id])
                planned_ids = split_pipe(site["residual_area_ids"])
                source_ballots = split_pipe(site["residual_final_ballots"])
                represented_eligible = sum(
                    read_area_weights(
                        site["residual_area_planned_eligible"]
                    ).get(area_id, 0)
                    for area_id in owned_ids
                )
                display_id = f"display:polling-group:{site_id}"
                policy_rows.append(
                    {
                        "display_geography_id": display_id,
                        "election": clean(component["election"]),
                        "locality_code": clean(component["locality_code"]),
                        "locality_name": clean(component["locality_name"]),
                        "evidence_group_id": component_id,
                        "source_site_audit_id": site_id,
                        "source_site_ids": clean(site["planned_site_ids"]),
                        "final_site_ids": clean(site["final_site_ids"]),
                        "owned_stat_area_ids": "|".join(owned_ids),
                        "planned_stat_area_ids": "|".join(planned_ids),
                        "ambiguous_final_ballots": "|".join(source_ballots),
                        "planned_eligible_voters": integer(
                            site["planned_residual_eligible"]
                        ),
                        "represented_planned_eligible_voters": represented_eligible,
                        "represented_planned_share": round(
                            float(represented_shares[site_id]), 8
                        ),
                        "final_eligible_voters": integer(
                            site["final_residual_eligible"]
                        ),
                        "component_network_balance": network_balance,
                        "component_eligible_difference": difference,
                        "source_evidence": clean(site["source_evidence"]),
                        "continuity_reference_elections": "",
                        "continuity_reference_site_audit_ids": "",
                        "evidence_warnings": "|".join(
                            sorted(set(evidence_warnings))
                        ),
                        "ownership_status": ownership_status,
                        "ownership_policy": (
                            "maximize_minimum_represented_share_then_total_"
                            "with_unique_polygon_ownership"
                        ),
                        "review_status": "approved-rule-generated",
                        "note": (
                            "Exact final polling-group totals; polygon ownership "
                            "is representative and does not split votes by area."
                        ),
                    }
                )
        elif network_supported and ownership_status in FALLBACK_STATUSES:
            election = clean(component["election"])
            locality_code = clean(component["locality_code"])
            fallback_rows.append(
                {
                    "display_geography_id": (
                        f"display:polling-network-fallback:"
                        f"{election}:{locality_code}:"
                        f"{component_id.rsplit(':', 1)[-1]}"
                    ),
                    "elections": election,
                    "component_stat_area_ids": "|".join(area_ids),
                    "aggregation_method": "sum-components",
                    "evidence_group_id": component_id,
                    "evidence_class": "representative_ownership_impossible",
                    "review_status": "approved-rule-fallback",
                    "note": (
                        f"Exact network aggregate retained because "
                        f"{ownership_status.replace('_', ' ')}."
                    ),
                }
            )

    continuity_policy, continuity_fallbacks, continuity_audit = (
        build_continuity_candidates(sites, geometry_by_id)
    )
    policy_rows.extend(continuity_policy)
    fallback_rows.extend(continuity_fallbacks)
    output_rows.extend(continuity_audit)

    validate_generated_policy(policy_rows, fallback_rows, output_rows)

    write_rows(OUTPUT_PATH, output_rows)
    write_rows(POLICY_PATH, policy_rows)
    write_rows(FALLBACK_PATH, fallback_rows)
    write_rows(EXACT_GROUP_PATH, exact_group_rows)
    frame = pd.DataFrame(output_rows)
    supported = frame.loc[frame["network_supported"].eq(True)].copy()
    policy_frame = pd.DataFrame(policy_rows)
    exact_frame = pd.DataFrame(exact_group_rows)
    representative_frame = policy_frame.loc[
        ~policy_frame["review_status"].eq("approved-exact-closed")
    ].copy()
    representative_scope_counts = []
    for election in sorted(set(policy_frame["election"])):
        election_rows = policy_frame.loc[policy_frame["election"].eq(election)]
        representative_scope_counts.append(
            {
                "election": election,
                "display_units": len(election_rows),
                "localities": int(election_rows["locality_code"].nunique()),
                "owned_polygon_memberships": sum(
                    len(split_pipe(value))
                    for value in election_rows["owned_stat_area_ids"]
                ),
            }
        )
    summary = {
        "scope": (
            "All testable statistical-area polling networks: direct official "
            "pre-election evidence in K21, K24, and K25; strict two-reference "
            "continuity in K22 and K23"
        ),
        "candidate_rule": (
            "Final polling-group identity and source coverage must be closed at "
            "the network boundary. Planned/final electorate differences are "
            "published as evidence warnings, never used to alter exact votes. "
            "Closed official networks are exact combined displays. When their "
            "eligible-voter totals balance exactly, transport-flow bounds remove "
            "impossible area-to-group edges and split the network into the "
            "smallest provably closed units. "
            "Every polling group must own at least one planned polygon; connected "
            "ownership maximizes the weakest represented planned-electorate share, "
            "then total represented electorate, with a stable tie-break only for "
            "the remaining representative displays."
        ),
        "multi_site_components_reviewed": len(frame),
        "network_supported_components": len(supported),
        "display_units": len(policy_rows),
        "exact_closed_display_units": len(exact_group_rows),
        "exact_closed_component_count": len(
            {
                row["evidence_group_id"]
                for row in exact_group_rows
            }
        ),
        "exact_closed_polygon_memberships": sum(
            len(split_pipe(row["stat_area_ids"]))
            for row in exact_group_rows
        ),
        "exact_closed_polling_groups": sum(
            len(split_pipe(row["polling_group_ids"]))
            for row in exact_group_rows
        ),
        "exact_closed_scope_counts": (
            exact_frame
            .groupby(["election", "exactness_basis"])
            .agg(
                display_units=("display_geography_id", "size"),
                component_count=("evidence_group_id", "nunique"),
                polygon_memberships=("stat_area_count", "sum"),
                polling_groups=("polling_group_count", "sum"),
            )
            .reset_index()
            .to_dict("records")
        ),
        "representative_display_units": len(representative_frame),
        "representative_display_units_by_evidence": (
            representative_frame
            .groupby(["election", "source_evidence"])
            .size()
            .rename("count")
            .reset_index()
            .to_dict("records")
        ),
        "representative_scope_counts": representative_scope_counts,
        "representative_component_count": len(
            set(representative_frame["evidence_group_id"])
        ),
        "broad_fallback_component_count": len(fallback_rows),
        "elections_with_representative_units": sorted(
            {clean(row["election"]) for row in policy_rows}
        ),
        "elections_without_qualifying_evidence": {
            "K17": "No compatible official polling-group register is available.",
            "K18": "No compatible official polling-group register is available.",
            "K19": "No compatible official polling-group register is available.",
            "K20": (
                "The available register is post-balance and lacks an official "
                "site identifier; it therefore cannot satisfy the approved "
                "direct or two-reference continuity rule."
            ),
        },
        "ownership_status_counts": (
            supported.groupby(["election", "ownership_status"])
            .size()
            .rename("count")
            .reset_index()
            .to_dict("records")
        ),
        "generated_display_status_counts": (
            supported.groupby(["current_display_status"])
            .size()
            .rename("count")
            .reset_index()
            .to_dict("records")
        ),
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    by_election = {
        row["election"]: row["count"]
        for row in summary["representative_display_units_by_evidence"]
    }
    print(
        "generated "
        f"{len(exact_group_rows)} exact closed units and "
        f"{len(representative_frame)} representative polling-group units "
        f"across {len(summary['elections_with_representative_units'])} elections "
        f"({', '.join(f'{key}={value}' for key, value in by_election.items())}); "
        f"{len(fallback_rows)} broad fallbacks"
    )


if __name__ == "__main__":
    main()
