#!/usr/bin/env python3
"""Build inspectable context for every contributor-capacity audit flag.

The capacity audit intentionally casts a wide net. This companion script does
not change any result or geometry; it gathers the evidence needed to decide
whether a flag reflects an incomplete contributor set, a planned-to-final
register change, or an unsuitable historical population proxy.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
LOCAL_PYTHON = ROOT / ".local" / "python-geo"
if LOCAL_PYTHON.exists():
    sys.path.insert(0, str(LOCAL_PYTHON))

import geopandas as gpd
from shapely.ops import unary_union


PROCESSED = ROOT / "data" / "processed"
AUDITS = PROCESSED / "audits"
GEOGRAPHIES = PROCESSED / "geographies"
PUBLIC = PROCESSED / "public"

FLAGS_PATH = AUDITS / "display_contributor_capacity_flags.csv"
REVIEWS_PATH = ROOT / "data" / "manual" / "display_contributor_capacity_reviews.csv"
POLLING_METADATA_PATH = (
    GEOGRAPHIES / "statistical_area_polling_group_displays.metadata.csv"
)
POLLING_RESULTS_PATH = PUBLIC / "statistical_area_polling_group_displays.csv"
POLLING_SITES_PATH = AUDITS / "statistical_area_polling_group_sites.csv"
AGGREGATE_METADATA_PATH = GEOGRAPHIES / "statistical_area_result_aggregates.metadata.csv"
POLYGON_COVERAGE_PATH = AUDITS / "historical_polygon_coverage.csv"
GEOMETRY_PATH = GEOGRAPHIES / "statistical_areas_2011.display.simplified.geojson"

OUTPUT_PATH = AUDITS / "display_contributor_capacity_case_context.csv"
SUMMARY_PATH = AUDITS / "display_contributor_capacity_case_context_summary.json"

ELECTIONS = tuple(f"K{number}" for number in range(19, 26))
METRIC_CRS = "EPSG:2039"
ADJACENCY_TOLERANCE_METERS = 1.0

OUTPUT_FIELDS = (
    "case_id",
    "election",
    "locality_code",
    "locality_name",
    "unit_type",
    "display_geography_id",
    "flag_reason",
    "shown_stat_area_ids",
    "possible_contributor_stat_area_ids",
    "possible_inflow_stat_area_ids",
    "adjacent_stat_area_ids",
    "adjacent_stat_area_numbers",
    "nearest_stat_areas",
    "shown_population_proxy",
    "possible_contributor_population_proxy",
    "possible_contributors_plus_adjacent_population_proxy",
    "actual_voters",
    "final_eligible_voters",
    "planned_eligible_voters",
    "election_capacity",
    "source_ballots",
    "source_ballot_assignment_breakdown",
    "source_ballots_outside_possible_contributors",
    "source_ballot_final_eligible_within_possible_contributors",
    "source_ballot_final_eligible_outside_possible_contributors",
    "source_site_audit_ids",
    "planned_site_ids",
    "final_site_ids",
    "site_labels",
    "planned_area_weights",
    "site_all_stat_area_ids",
    "sibling_display_units",
    "current_adjacent_display_units",
    "cross_election_area_results",
    "cross_election_adjacent_area_results",
    "cross_election_display_owners",
    "direct_source_ballots",
    "direct_assignment_methods",
    "capacity_review_status",
    "capacity_review_decision",
    "replacement_display_geography_id",
    "capacity_review_evidence",
    "existing_notice",
)


def clean(value: Any) -> str:
    return str(value or "").strip()


def integer(value: Any) -> int:
    text = clean(value).replace(",", "")
    if not text:
        return 0
    try:
        return int(Decimal(text))
    except InvalidOperation:
        return 0


def split_pipe(value: Any) -> list[str]:
    return [part.strip() for part in clean(value).split("|") if part.strip()]


def pipe(values: Iterable[str]) -> str:
    return "|".join(sorted({clean(value) for value in values if clean(value)}))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def area_number(area_id: str) -> str:
    digits = clean(area_id).rsplit(":", 1)[-1]
    return str(int(digits[-4:])) if len(digits) >= 4 and digits[-4:].isdigit() else area_id


def ballot_id(value: Any) -> str:
    text = clean(value)
    if not text:
        return ""
    try:
        number = Decimal(text)
    except InvalidOperation:
        return text
    normalized = format(number.normalize(), "f")
    return normalized.rstrip("0").rstrip(".") if "." in normalized else normalized


def load_base_results() -> dict[str, dict[str, dict[str, str]]]:
    return {
        election: {
            clean(row["stat_area_id"]): row
            for row in read_csv(
                PUBLIC / "statistical_area_results" / f"{election.lower()}.csv"
            )
        }
        for election in ELECTIONS
    }


def load_population() -> dict[tuple[str, str], int]:
    values: dict[tuple[str, str], int] = {}
    for row in read_csv(POLYGON_COVERAGE_PATH):
        values[(clean(row["election"]), clean(row["stat_area_id"]))] = integer(
            row["population_proxy"]
        )
    return values


def load_polling_context(
    base_results: dict[str, dict[str, dict[str, str]]],
) -> tuple[
    dict[tuple[str, str], dict[str, str]],
    dict[tuple[str, str], dict[str, Any]],
    dict[tuple[str, str], list[dict[str, Any]]],
]:
    polling_results = {
        (clean(row["election"]), clean(row["geography_id"])): row
        for row in read_csv(POLLING_RESULTS_PATH)
    }
    metadata_by_key: dict[tuple[str, str], dict[str, str]] = {}
    owners: dict[tuple[str, str], dict[str, Any]] = {}
    siblings: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)

    for row in read_csv(POLLING_METADATA_PATH):
        election = clean(row["election"])
        display_id = clean(row["display_geography_id"])
        result = polling_results.get((election, display_id))
        if election not in ELECTIONS or result is None:
            continue
        metadata_by_key[(election, display_id)] = row
        owner = {
            "display_id": display_id,
            "shown": split_pipe(row["component_stat_area_ids"]),
            "planned": split_pipe(row["planned_stat_area_ids"]),
            "ballots": split_pipe(row["source_ballots"]),
            "eligible": integer(result["eligible_voters"]),
            "actual": integer(result["actual_voters"]),
            "precision": clean(row["assignment_precision"]),
        }
        for area_id in owner["shown"]:
            key = (election, area_id)
            if key in owners:
                raise ValueError(f"Duplicate polling display owner for {key}")
            owners[key] = owner
        siblings[(election, clean(row["evidence_group_id"]))].append(owner)

    for row in read_csv(AGGREGATE_METADATA_PATH):
        display_id = clean(row["display_geography_id"])
        shown = split_pipe(row["component_stat_area_ids"])
        for election in split_pipe(row.get("elections") or row.get("election")):
            if election not in ELECTIONS:
                continue
            source_rows = [base_results[election].get(area_id) for area_id in shown]
            source_rows = [source for source in source_rows if source is not None]
            if not source_rows:
                continue
            owner = {
                "display_id": display_id,
                "shown": shown,
                "planned": shown,
                "ballots": [],
                "eligible": sum(integer(source["eligible_voters"]) for source in source_rows),
                "actual": sum(integer(source["actual_voters"]) for source in source_rows),
                "precision": clean(row["evidence_class"]),
            }
            for area_id in shown:
                key = (election, area_id)
                if key in owners:
                    raise ValueError(f"Duplicate aggregate display owner for {key}")
                owners[key] = owner

    for election, areas in base_results.items():
        for area_id, row in areas.items():
            owners.setdefault(
                (election, area_id),
                {
                    "display_id": area_id,
                    "shown": [area_id],
                    "planned": [area_id],
                    "ballots": [],
                    "eligible": integer(row["eligible_voters"]),
                    "actual": integer(row["actual_voters"]),
                    "precision": "direct_area_result",
                },
            )

    return metadata_by_key, owners, siblings


def load_geometry_context() -> tuple[
    dict[str, Any],
    dict[str, set[str]],
    dict[str, list[tuple[str, float]]],
]:
    areas = gpd.read_file(GEOMETRY_PATH).to_crs(METRIC_CRS)
    areas["stat_area_id"] = areas["stat_area_id"].map(clean)
    geometry_by_id = dict(zip(areas["stat_area_id"], areas.geometry))
    adjacent: dict[str, set[str]] = defaultdict(set)
    nearest: dict[str, list[tuple[str, float]]] = {}

    for _, locality in areas.groupby(areas["locality_code"].astype(str)):
        records = list(zip(locality["stat_area_id"], locality.geometry))
        for left_index, (left_id, left_geometry) in enumerate(records):
            distances: list[tuple[str, float]] = []
            for right_index, (right_id, right_geometry) in enumerate(records):
                if left_index == right_index:
                    continue
                distance = float(left_geometry.distance(right_geometry))
                distances.append((right_id, distance))
                if distance <= ADJACENCY_TOLERANCE_METERS:
                    adjacent[left_id].add(right_id)
            nearest[left_id] = sorted(distances, key=lambda item: (item[1], item[0]))[:5]

    return geometry_by_id, adjacent, nearest


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    flags = read_csv(FLAGS_PATH)
    reviews = {
        (clean(row["election"]), clean(row["display_geography_id"])): row
        for row in read_csv(REVIEWS_PATH)
    }
    base_results = load_base_results()
    population = load_population()
    polling_metadata, display_owners, sibling_displays = load_polling_context(base_results)
    geometry_by_id, adjacent_by_id, nearest_by_id = load_geometry_context()
    sites_by_id = {
        clean(row["site_audit_id"]): row for row in read_csv(POLLING_SITES_PATH)
    }
    sites_by_election_locality: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for site in sites_by_id.values():
        sites_by_election_locality[
            (clean(site["election"]), clean(site["locality_code"]))
        ].append(site)

    ballot_rows = {
        election: read_csv(PUBLIC / "ballot_contributions" / f"{election.lower()}.csv")
        for election in ELECTIONS
    }

    output_rows: list[dict[str, Any]] = []
    for position, flag in enumerate(flags, start=1):
        election = clean(flag["election"])
        display_id = clean(flag["display_geography_id"])
        shown = set(split_pipe(flag["shown_stat_area_ids"]))
        contributors = set(split_pipe(flag["possible_contributor_stat_area_ids"]))
        metadata = polling_metadata.get((election, display_id), {})
        review = reviews.get((election, display_id), {})

        adjacent = set().union(*(adjacent_by_id.get(area_id, set()) for area_id in shown)) - shown
        nearest_distances: dict[str, float] = {}
        for area_id in shown:
            for neighbor_id, distance in nearest_by_id.get(area_id, []):
                if neighbor_id in shown:
                    continue
                nearest_distances[neighbor_id] = min(
                    distance, nearest_distances.get(neighbor_id, float("inf"))
                )
        nearest_values = [
            {
                "area": area_number(area_id),
                "id": area_id,
                "distance_m": round(distance, 1),
            }
            for area_id, distance in sorted(
                nearest_distances.items(), key=lambda item: (item[1], item[0])
            )[:5]
        ]

        source_site_ids = split_pipe(metadata.get("source_site_audit_id"))
        if not source_site_ids:
            source_site_ids = [
                clean(site["site_audit_id"])
                for site in sites_by_election_locality.get(
                    (election, clean(flag["locality_code"])), []
                )
                if shown & set(split_pipe(site.get("all_area_ids")))
            ]
        site_rows = [sites_by_id[site_id] for site_id in source_site_ids if site_id in sites_by_id]
        planned_weights: dict[str, int] = defaultdict(int)
        for site in site_rows:
            raw_weights = clean(site.get("residual_area_planned_eligible"))
            if not raw_weights:
                continue
            for area_id, value in json.loads(raw_weights).items():
                planned_weights[clean(area_id)] += integer(value)

        cross_election_results: dict[str, Any] = {}
        cross_election_adjacent_results: dict[str, Any] = {}
        cross_election_owners: dict[str, Any] = {}
        tracked_areas = sorted(shown | contributors)
        for comparison_election in ELECTIONS:
            area_values: dict[str, Any] = {}
            owner_values: dict[str, Any] = {}
            seen_owners: set[str] = set()
            for area_id in tracked_areas:
                result = base_results[comparison_election].get(area_id)
                area_values[area_number(area_id)] = (
                    {
                        "eligible": integer(result["eligible_voters"]),
                        "actual": integer(result["actual_voters"]),
                    }
                    if result is not None
                    else None
                )
                owner = display_owners.get((comparison_election, area_id))
                if owner is None or owner["display_id"] in seen_owners:
                    continue
                seen_owners.add(owner["display_id"])
                owner_values[owner["display_id"]] = {
                    "shown": [area_number(value) for value in owner["shown"]],
                    "actual": owner["actual"],
                    "eligible": owner["eligible"],
                    "precision": owner["precision"],
                }
            cross_election_results[comparison_election] = area_values
            adjacent_values: dict[str, Any] = {}
            for area_id in sorted(adjacent):
                result = base_results[comparison_election].get(area_id)
                adjacent_values[area_number(area_id)] = (
                    {
                        "eligible": integer(result["eligible_voters"]),
                        "actual": integer(result["actual_voters"]),
                    }
                    if result is not None
                    else None
                )
            cross_election_adjacent_results[comparison_election] = adjacent_values
            cross_election_owners[comparison_election] = owner_values

        adjacent_owner_values: dict[str, Any] = {}
        for area_id in sorted(adjacent):
            owner = display_owners.get((election, area_id))
            if owner is None:
                continue
            adjacent_owner_values[area_number(area_id)] = {
                "display_id": owner["display_id"],
                "shown": [area_number(value) for value in owner["shown"]],
                "actual": owner["actual"],
                "eligible": owner["eligible"],
                "precision": owner["precision"],
            }

        direct_rows = [
            row
            for row in ballot_rows[election]
            if clean(row.get("stat_area_id")) in shown
        ]
        direct_ballots = [ballot_id(row.get("source_kalpi")) for row in direct_rows]
        assignment_methods = sorted(
            {clean(row.get("final_assignment_method")) for row in direct_rows if clean(row.get("final_assignment_method"))}
        )

        source_ballot_ids = set(split_pipe(flag["source_ballots"]))
        source_rows = [
            row
            for row in ballot_rows[election]
            if clean(row.get("source_locality_code")) == clean(flag["locality_code"])
            and ballot_id(row.get("source_kalpi")) in source_ballot_ids
        ]
        source_breakdown: dict[str, dict[str, Any]] = {}
        outside_source_ballots: list[str] = []
        source_eligible_within = 0
        source_eligible_outside = 0
        for source in source_rows:
            area_id = clean(source.get("stat_area_id"))
            key = area_number(area_id) if area_id else "unassigned"
            bucket = source_breakdown.setdefault(
                key,
                {"area_id": area_id, "ballots": [], "eligible": 0, "actual": 0},
            )
            source_ballot = ballot_id(source.get("source_kalpi"))
            bucket["ballots"].append(source_ballot)
            bucket["eligible"] += integer(source.get("eligible_voters"))
            bucket["actual"] += integer(source.get("actual_voters"))
            if area_id in contributors:
                source_eligible_within += integer(source.get("eligible_voters"))
            else:
                source_eligible_outside += integer(source.get("eligible_voters"))
                outside_source_ballots.append(source_ballot)
        for bucket in source_breakdown.values():
            bucket["ballots"] = sorted(set(bucket["ballots"]))

        shown_population = sum(population.get((election, area_id), 0) for area_id in shown)
        contributor_population = sum(
            population.get((election, area_id), 0) for area_id in contributors
        )
        expanded = contributors | adjacent
        expanded_population = sum(
            population.get((election, area_id), 0) for area_id in expanded
        )
        evidence_group_id = clean(metadata.get("evidence_group_id"))

        output_rows.append(
            {
                "case_id": f"CAP-{position:02d}",
                "election": election,
                "locality_code": clean(flag["locality_code"]),
                "locality_name": clean(flag["locality_name"]),
                "unit_type": clean(flag["unit_type"]),
                "display_geography_id": display_id,
                "flag_reason": clean(flag["flag_reason"]),
                "shown_stat_area_ids": pipe(shown),
                "possible_contributor_stat_area_ids": pipe(contributors),
                "possible_inflow_stat_area_ids": clean(flag["possible_inflow_stat_area_ids"]),
                "adjacent_stat_area_ids": pipe(adjacent),
                "adjacent_stat_area_numbers": pipe(area_number(value) for value in adjacent),
                "nearest_stat_areas": compact_json(nearest_values),
                "shown_population_proxy": shown_population,
                "possible_contributor_population_proxy": contributor_population,
                "possible_contributors_plus_adjacent_population_proxy": expanded_population,
                "actual_voters": integer(flag["actual_voters"]),
                "final_eligible_voters": integer(flag["final_eligible_voters"]),
                "planned_eligible_voters": integer(flag["planned_eligible_voters"]),
                "election_capacity": integer(flag["election_capacity"]),
                "source_ballots": clean(flag["source_ballots"]),
                "source_ballot_assignment_breakdown": compact_json(source_breakdown),
                "source_ballots_outside_possible_contributors": pipe(outside_source_ballots),
                "source_ballot_final_eligible_within_possible_contributors": source_eligible_within,
                "source_ballot_final_eligible_outside_possible_contributors": source_eligible_outside,
                "source_site_audit_ids": pipe(source_site_ids),
                "planned_site_ids": pipe(
                    value for site in site_rows for value in split_pipe(site.get("planned_site_ids"))
                ),
                "final_site_ids": pipe(
                    value for site in site_rows for value in split_pipe(site.get("final_site_ids"))
                ),
                "site_labels": pipe(clean(site.get("site_labels")) for site in site_rows),
                "planned_area_weights": compact_json(
                    {area_number(key): value for key, value in sorted(planned_weights.items())}
                ),
                "site_all_stat_area_ids": pipe(
                    value for site in site_rows for value in split_pipe(site.get("all_area_ids"))
                ),
                "sibling_display_units": compact_json(
                    sibling_displays.get((election, evidence_group_id), [])
                ),
                "current_adjacent_display_units": compact_json(adjacent_owner_values),
                "cross_election_area_results": compact_json(cross_election_results),
                "cross_election_adjacent_area_results": compact_json(
                    cross_election_adjacent_results
                ),
                "cross_election_display_owners": compact_json(cross_election_owners),
                "direct_source_ballots": pipe(direct_ballots),
                "direct_assignment_methods": pipe(assignment_methods),
                "capacity_review_status": clean(review.get("review_status")),
                "capacity_review_decision": clean(review.get("decision")),
                "replacement_display_geography_id": clean(
                    review.get("replacement_display_geography_id")
                ),
                "capacity_review_evidence": clean(review.get("evidence_summary")),
                "existing_notice": clean(flag["existing_notice"]),
            }
        )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(output_rows)

    summary = {
        "definition": (
            "Review context for each display contributor-capacity flag. No result "
            "assignment or display geometry is modified."
        ),
        "case_count": len(output_rows),
        "election_backed_cases": sum(
            1 for row in output_rows if row["planned_eligible_voters"]
        ),
        "demographic_only_cases": sum(
            1 for row in output_rows if not row["planned_eligible_voters"]
        ),
        "recorded_review_decisions": len(reviews),
        "current_cases_reviewed_closed": sum(
            1 for row in output_rows if row["capacity_review_status"] == "reviewed-closed"
        ),
        "current_cases_open": sum(
            1 for row in output_rows if row["capacity_review_status"] != "reviewed-closed"
        ),
        "output": str(OUTPUT_PATH.relative_to(ROOT)),
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
