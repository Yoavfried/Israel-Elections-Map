#!/usr/bin/env python3
"""Flag displayed statistical-area results that exceed contributor capacity.

This is intentionally a narrow review audit. It does not alter geography or
result assignments. Election-backed capacity is the final eligible-voter total
currently assigned to every polygon that could contribute to a display. The
pre-election register remains diagnostic evidence, not a hard final capacity.
Otherwise, a display is flagged only when actual voters exceed 125% of the
complete total-population proxy for every possible contributor polygon.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
PUBLIC = PROCESSED / "public"
GEOGRAPHIES = PROCESSED / "geographies"
AUDITS = PROCESSED / "audits"
MANUAL = ROOT / "data" / "manual"

ELECTIONS = tuple(f"K{number}" for number in range(17, 26))
DEMOGRAPHIC_LENIENCY = Decimal("1.25")

POLLING_RESULTS_PATH = PUBLIC / "statistical_area_polling_group_displays.csv"
POLLING_METADATA_PATH = (
    GEOGRAPHIES / "statistical_area_polling_group_displays.metadata.csv"
)
POLLING_POLICY_PATH = AUDITS / "statistical_area_polling_group_policy.csv"
POLLING_GEOMETRY_PATH = (
    GEOGRAPHIES / "statistical_area_polling_group_displays.geojson"
)
AGGREGATE_METADATA_PATH = GEOGRAPHIES / "statistical_area_result_aggregates.metadata.csv"
AGGREGATE_GEOMETRY_PATH = GEOGRAPHIES / "statistical_area_result_aggregates.geojson"
POLYGON_COVERAGE_PATH = AUDITS / "historical_polygon_coverage.csv"
DISPLAY_OVERRIDES_PATH = MANUAL / "statistical_area_display_overrides.csv"

OUTPUT_PATH = AUDITS / "display_contributor_capacity_audit.csv"
FLAGS_PATH = AUDITS / "display_contributor_capacity_flags.csv"
SUMMARY_PATH = AUDITS / "display_contributor_capacity_audit_summary.json"

OUTPUT_FIELDS = (
    "election",
    "unit_type",
    "display_geography_id",
    "locality_code",
    "locality_name",
    "shown_stat_area_ids",
    "possible_contributor_stat_area_ids",
    "possible_inflow_stat_area_ids",
    "assignment_precision",
    "source_ballots",
    "final_eligible_voters",
    "actual_voters",
    "valid_votes",
    "planned_eligible_voters",
    "ambiguous_final_eligible_voters",
    "preserved_direct_eligible_voters",
    "supplemental_source_eligible_voters",
    "election_capacity",
    "actual_to_election_capacity",
    "election_capacity_excess_voters",
    "demographic_population_proxy",
    "demographic_coverage_complete",
    "demographic_lenient_capacity",
    "actual_to_demographic_capacity",
    "demographic_capacity_excess_voters",
    "flag_reason",
    "severity",
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


def join_pipe(values: Iterable[str]) -> str:
    return "|".join(sorted({clean(value) for value in values if clean(value)}))


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


def ratio(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return ""
    return f"{numerator / denominator:.6f}"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def read_polygon_features(path: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    features: dict[str, dict[str, Any]] = {}
    for feature in payload.get("features", []):
        geometry_type = clean((feature.get("geometry") or {}).get("type"))
        if geometry_type not in {"Polygon", "MultiPolygon"}:
            continue
        feature_id = clean(feature.get("id") or (feature.get("properties") or {}).get("custom_id"))
        if feature_id:
            features[feature_id] = feature
    return features


def load_demographics() -> dict[tuple[str, str], tuple[int, bool]]:
    values: dict[tuple[str, str], tuple[int, bool]] = {}
    complete_statuses = {"positive_population_proxy", "zero_population_proxy"}
    for row in read_csv(POLYGON_COVERAGE_PATH):
        key = (clean(row["election"]), clean(row["stat_area_id"]))
        values[key] = (
            integer(row["population_proxy"]),
            clean(row["population_evidence_status"]) in complete_statuses,
        )
    return values


def load_hidden_areas() -> dict[str, set[str]]:
    hidden: dict[str, set[str]] = defaultdict(set)
    for row in read_csv(DISPLAY_OVERRIDES_PATH):
        if clean(row["visibility"]) != "hidden":
            continue
        for election in split_pipe(row["elections"]):
            hidden[election].add(clean(row["stat_area_id"]))
    return hidden


def demographic_capacity(
    election: str,
    area_ids: set[str],
    demographics: dict[tuple[str, str], tuple[int, bool]],
) -> tuple[int, bool, int]:
    if not area_ids:
        return 0, False, 0
    population = 0
    complete = True
    for area_id in area_ids:
        value = demographics.get((election, area_id))
        if value is None or not value[1]:
            complete = False
            continue
        population += value[0]
    lenient_capacity = int(Decimal(population) * DEMOGRAPHIC_LENIENCY)
    return population, complete, lenient_capacity


def existing_notice(feature: dict[str, Any] | None) -> str:
    properties = (feature or {}).get("properties") or {}
    return clean(properties.get("notice_he") or properties.get("note"))


def classify(
    *,
    actual_voters: int,
    election_capacity: int,
    has_election_capacity: bool,
    demographic_capacity_value: int,
    demographic_complete: bool,
) -> tuple[str, str, int, int]:
    election_excess = (
        max(0, actual_voters - election_capacity) if has_election_capacity else 0
    )
    demographic_excess = (
        max(0, actual_voters - demographic_capacity_value)
        if demographic_complete and demographic_capacity_value > 0
        else 0
    )
    election_flag = has_election_capacity and election_excess > 0
    demographic_flag = (
        demographic_complete
        and demographic_capacity_value > 0
        and demographic_excess > 0
    )
    if election_flag and demographic_flag:
        return "election_and_demographic_capacity_exceeded", "high", election_excess, demographic_excess
    if election_flag:
        return "election_capacity_exceeded", "high", election_excess, 0
    if demographic_flag:
        return "demographic_capacity_exceeded", "review", 0, demographic_excess
    if demographic_complete and demographic_capacity_value == 0 and actual_voters > 0:
        return "zero_population_proxy_with_results", "information", 0, actual_voters
    return "", "", 0, 0


def audit_row(
    *,
    election: str,
    unit_type: str,
    display_id: str,
    locality_code: str,
    locality_name: str,
    shown_ids: set[str],
    contributor_ids: set[str],
    precision: str,
    source_ballots: list[str],
    eligible_voters: int,
    actual_voters: int,
    valid_votes: int,
    planned_eligible: int,
    ambiguous_final_eligible: int,
    supplemental_source_eligible: int,
    election_capacity: int,
    has_election_capacity: bool,
    demographics: dict[tuple[str, str], tuple[int, bool]],
    notice: str,
) -> dict[str, Any]:
    population, demographic_complete, lenient_capacity = demographic_capacity(
        election, contributor_ids, demographics
    )
    flag_reason, severity, election_excess, demographic_excess = classify(
        actual_voters=actual_voters,
        election_capacity=election_capacity,
        has_election_capacity=has_election_capacity,
        demographic_capacity_value=lenient_capacity,
        demographic_complete=demographic_complete,
    )
    preserved_eligible = max(0, eligible_voters - ambiguous_final_eligible)
    possible_inflow = contributor_ids - shown_ids
    return {
        "election": election,
        "unit_type": unit_type,
        "display_geography_id": display_id,
        "locality_code": locality_code,
        "locality_name": locality_name,
        "shown_stat_area_ids": join_pipe(shown_ids),
        "possible_contributor_stat_area_ids": join_pipe(contributor_ids),
        "possible_inflow_stat_area_ids": join_pipe(possible_inflow),
        "assignment_precision": precision,
        "source_ballots": join_pipe(source_ballots),
        "final_eligible_voters": eligible_voters,
        "actual_voters": actual_voters,
        "valid_votes": valid_votes,
        "planned_eligible_voters": planned_eligible if has_election_capacity else "",
        "ambiguous_final_eligible_voters": (
            ambiguous_final_eligible if has_election_capacity else ""
        ),
        "preserved_direct_eligible_voters": (
            preserved_eligible if has_election_capacity else ""
        ),
        "supplemental_source_eligible_voters": (
            supplemental_source_eligible if has_election_capacity else ""
        ),
        "election_capacity": election_capacity if has_election_capacity else "",
        "actual_to_election_capacity": (
            ratio(actual_voters, election_capacity) if has_election_capacity else ""
        ),
        "election_capacity_excess_voters": election_excess,
        "demographic_population_proxy": population,
        "demographic_coverage_complete": str(demographic_complete).lower(),
        "demographic_lenient_capacity": lenient_capacity if demographic_complete else "",
        "actual_to_demographic_capacity": (
            ratio(actual_voters, lenient_capacity)
            if demographic_complete and lenient_capacity > 0
            else ""
        ),
        "demographic_capacity_excess_voters": demographic_excess,
        "flag_reason": flag_reason,
        "severity": severity,
        "existing_notice": notice,
    }


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    demographics = load_demographics()
    hidden_areas = load_hidden_areas()
    polling_features = read_polygon_features(POLLING_GEOMETRY_PATH)
    aggregate_features = read_polygon_features(AGGREGATE_GEOMETRY_PATH)

    base_results = {
        election: read_csv(PUBLIC / "statistical_area_results" / f"{election.lower()}.csv")
        for election in ELECTIONS
    }
    base_by_area = {
        election: {clean(row["stat_area_id"]): row for row in rows}
        for election, rows in base_results.items()
    }
    ballot_contributions = {
        election: {
            (clean(row["source_locality_code"]), ballot_id(row["source_kalpi"])): row
            for row in read_csv(
                PUBLIC / "ballot_contributions" / f"{election.lower()}.csv"
            )
        }
        for election in ELECTIONS
    }

    claimed_areas: dict[str, set[str]] = defaultdict(set)
    audit_rows: list[dict[str, Any]] = []

    polling_results = {
        (clean(row["election"]), clean(row["geography_id"])): row
        for row in read_csv(POLLING_RESULTS_PATH)
    }
    polling_policy = {
        (clean(row["election"]), clean(row["display_geography_id"])): row
        for row in read_csv(POLLING_POLICY_PATH)
    }
    for metadata in read_csv(POLLING_METADATA_PATH):
        election = clean(metadata["election"])
        display_id = clean(metadata["display_geography_id"])
        if election not in ELECTIONS or display_id not in polling_features:
            continue
        result = polling_results.get((election, display_id))
        if result is None:
            raise ValueError(f"Missing polling display result: {election} {display_id}")
        shown_ids = set(split_pipe(metadata["component_stat_area_ids"]))
        contributor_ids = shown_ids | set(split_pipe(metadata["planned_stat_area_ids"]))
        source_ballots = [ballot_id(value) for value in split_pipe(metadata["source_ballots"])]
        locality_code = clean(metadata["locality_code"])
        eligible_voters = integer(result["eligible_voters"])
        planned_eligible = integer(metadata["planned_eligible_voters"])
        has_planned_evidence = planned_eligible > 0
        ambiguous_final_eligible = 0
        if has_planned_evidence:
            policy = polling_policy.get((election, display_id))
            if policy is None:
                raise ValueError(
                    f"Missing polling display policy: {election} {display_id}"
                )
            policy_ballots = {
                ballot_id(value)
                for value in split_pipe(policy["ambiguous_final_ballots"])
            }
            if set(source_ballots) != policy_ballots:
                raise ValueError(
                    f"{display_id} policy ballot set changed: "
                    f"{source_ballots} != {sorted(policy_ballots)}"
                )
            if planned_eligible != integer(policy["planned_eligible_voters"]):
                raise ValueError(f"{display_id} planned eligible total changed")
            ambiguous_final_eligible = integer(policy["final_eligible_voters"])
            preserved_eligible = eligible_voters - ambiguous_final_eligible
            if preserved_eligible < 0:
                raise ValueError(f"{display_id} has negative preserved eligible voters")
        base_contributor_capacity = sum(
            integer(base_by_area[election][area_id]["eligible_voters"])
            for area_id in contributor_ids
            if area_id in base_by_area[election]
        )
        source_eligible_within_contributors = sum(
            integer(source["eligible_voters"])
            for source_ballot in source_ballots
            if (
                source := ballot_contributions[election].get(
                    (locality_code, source_ballot)
                )
            )
            is not None
            and clean(source["stat_area_id"]) in contributor_ids
        )
        supplemental_source_eligible = max(
            0, ambiguous_final_eligible - source_eligible_within_contributors
        )
        election_capacity = base_contributor_capacity + supplemental_source_eligible
        has_election_capacity = election_capacity > 0
        claimed_areas[election].update(shown_ids)
        audit_rows.append(
            audit_row(
                election=election,
                unit_type="polling_group_display",
                display_id=display_id,
                locality_code=locality_code,
                locality_name=clean(result["locality_name"]),
                shown_ids=shown_ids,
                contributor_ids=contributor_ids,
                precision=clean(metadata["assignment_precision"]),
                source_ballots=source_ballots,
                eligible_voters=eligible_voters,
                actual_voters=integer(result["actual_voters"]),
                valid_votes=integer(result["valid_votes"]),
                planned_eligible=planned_eligible,
                ambiguous_final_eligible=ambiguous_final_eligible,
                supplemental_source_eligible=supplemental_source_eligible,
                election_capacity=election_capacity,
                has_election_capacity=has_election_capacity,
                demographics=demographics,
                notice=existing_notice(polling_features.get(display_id)),
            )
        )

    for metadata in read_csv(AGGREGATE_METADATA_PATH):
        display_id = clean(metadata["display_geography_id"])
        if display_id not in aggregate_features:
            continue
        elections = split_pipe(metadata.get("elections") or metadata.get("election"))
        shown_ids = set(split_pipe(metadata["component_stat_area_ids"]))
        for election in elections:
            if election not in ELECTIONS:
                continue
            source_rows = [
                base_by_area[election][area_id]
                for area_id in shown_ids
                if area_id in base_by_area[election]
            ]
            if not source_rows:
                continue
            claimed_areas[election].update(shown_ids)
            audit_rows.append(
                audit_row(
                    election=election,
                    unit_type="result_aggregate_display",
                    display_id=display_id,
                    locality_code=clean(metadata["locality_code"]),
                    locality_name=clean(metadata["locality_name_he"]),
                    shown_ids=shown_ids,
                    contributor_ids=set(shown_ids),
                    precision=clean(metadata["evidence_class"]),
                    source_ballots=[],
                    eligible_voters=sum(integer(row["eligible_voters"]) for row in source_rows),
                    actual_voters=sum(integer(row["actual_voters"]) for row in source_rows),
                    valid_votes=sum(integer(row["valid_votes"]) for row in source_rows),
                    planned_eligible=0,
                    ambiguous_final_eligible=0,
                    supplemental_source_eligible=0,
                    election_capacity=0,
                    has_election_capacity=False,
                    demographics=demographics,
                    notice=existing_notice(aggregate_features.get(display_id)),
                )
            )

    for election, rows in base_results.items():
        for row in rows:
            area_id = clean(row["stat_area_id"])
            if area_id in claimed_areas[election] or area_id in hidden_areas[election]:
                continue
            audit_rows.append(
                audit_row(
                    election=election,
                    unit_type="single_stat_area",
                    display_id=area_id,
                    locality_code=clean(row["locality_code"]),
                    locality_name=clean(row["locality_name"]),
                    shown_ids={area_id},
                    contributor_ids={area_id},
                    precision="direct_area_result",
                    source_ballots=[],
                    eligible_voters=integer(row["eligible_voters"]),
                    actual_voters=integer(row["actual_voters"]),
                    valid_votes=integer(row["valid_votes"]),
                    planned_eligible=0,
                    ambiguous_final_eligible=0,
                    supplemental_source_eligible=0,
                    election_capacity=0,
                    has_election_capacity=False,
                    demographics=demographics,
                    notice="",
                )
            )

    audit_rows.sort(
        key=lambda row: (
            row["election"],
            row["locality_code"],
            row["unit_type"],
            row["display_geography_id"],
        )
    )
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(audit_rows)

    signaled = [row for row in audit_rows if row["flag_reason"]]
    flagged = [row for row in signaled if row["severity"] != "information"]
    informational = [row for row in signaled if row["severity"] == "information"]
    with FLAGS_PATH.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(flagged)
    reason_counts = Counter(clean(row["flag_reason"]) for row in flagged)
    election_counts = Counter(clean(row["election"]) for row in flagged)
    informational_counts = Counter(clean(row["flag_reason"]) for row in informational)
    type_counts = Counter(clean(row["unit_type"]) for row in audit_rows)
    top_flags = sorted(
        flagged,
        key=lambda row: (
            integer(row["election_capacity_excess_voters"])
            + integer(row["demographic_capacity_excess_voters"]),
            integer(row["actual_voters"]),
        ),
        reverse=True,
    )[:50]
    summary = {
        "definition": (
            "Displayed actual voters are compared with final eligible voters assigned "
            "to every possible contributor polygon and with 125% of complete total-"
            "population coverage. Pre-election register weights are diagnostic only. "
            "This is a review audit, not an assignment rule."
        ),
        "demographic_leniency_multiplier": float(DEMOGRAPHIC_LENIENCY),
        "display_units": len(audit_rows),
        "display_units_by_type": dict(sorted(type_counts.items())),
        "flagged_units": len(flagged),
        "flagged_by_reason": dict(sorted(reason_counts.items())),
        "flagged_by_election": dict(sorted(election_counts.items())),
        "informational_units": len(informational),
        "informational_by_reason": dict(sorted(informational_counts.items())),
        "top_flags": [
            {field: row[field] for field in OUTPUT_FIELDS if field in row}
            for row in top_flags
        ],
        "output": str(OUTPUT_PATH.relative_to(ROOT)),
        "flags_output": str(FLAGS_PATH.relative_to(ROOT)),
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {key: value for key, value in summary.items() if key != "top_flags"},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
