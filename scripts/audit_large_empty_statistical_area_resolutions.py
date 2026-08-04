#!/usr/bin/env python3
"""Find evidence-backed resolutions for populated polygons rendered without results."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

from audit_statistical_area_polling_group_evidence import (
    SOURCES,
    ballot_base,
    clean,
    read_source,
)


ROOT = Path(__file__).resolve().parents[1]
AUDIT_DIR = ROOT / "data" / "processed" / "audits"
ASSIGNMENT_DIR = ROOT / "data" / "processed" / "assignments"
RESULT_DIR = ROOT / "data" / "processed" / "normalized" / "ballot_votes_wide"
PUBLIC_RESULT_DIR = ROOT / "data" / "processed" / "public" / "statistical_area_results"

EMPTY_AUDIT_PATH = AUDIT_DIR / "rendered_empty_statistical_area_audit.csv"
CROSSWALK_PATH = ASSIGNMENT_DIR / "historical_ballot_crosswalk.csv"
ASSIGNMENTS_PATH = ASSIGNMENT_DIR / "historical_ballot_assignments.csv"
OUTPUT_PATH = AUDIT_DIR / "large_empty_statistical_area_resolution_candidates.csv"
SUMMARY_PATH = AUDIT_DIR / "large_empty_statistical_area_resolution_summary.json"

ELECTIONS = [f"K{number}" for number in range(18, 26)]
ELECTION_INDEX = {election: index for index, election in enumerate(ELECTIONS)}


def split_pipe(value: Any) -> list[str]:
    return [part.strip() for part in str(value or "").split("|") if part.strip()]


def pipe(values: Any) -> str:
    return "|".join(sorted({clean(value) for value in values if clean(value)}))


def integer(value: Any) -> int:
    text = clean(value).replace(",", "")
    return int(round(float(text))) if text else 0


def numeric_key(value: Any) -> tuple[int, str]:
    text = clean(value)
    try:
        return int(float(text)), text
    except ValueError:
        return 10**9, text


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, encoding="utf-8-sig").fillna("")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"Cannot write an empty audit: {path}")
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for field in row:
            if field not in seen:
                fields.append(field)
                seen.add(field)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def load_polling_registers(
    assignment_lookup: dict[tuple[str, str, str], str],
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for election, config in SOURCES.items():
        source = config.final or config.planned
        frame = read_source(source)
        frame["election"] = election
        frame["locality_code"] = frame["locality_code"].map(clean)
        frame["ballot_base"] = frame["source_kalpi"].map(ballot_base)
        frame["stat_area_id"] = [
            assignment_lookup.get((election, locality_code, base), "")
            for locality_code, base in zip(
                frame["locality_code"], frame["ballot_base"], strict=True
            )
        ]
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def build_assignment_lookup(assignments: pd.DataFrame) -> dict[tuple[str, str, str], str]:
    assignments = assignments.copy()
    assignments["source_locality_code"] = assignments[
        "source_locality_code"
    ].map(clean)
    assignments["ballot_base"] = assignments["ballot_base"].map(clean)
    output: dict[tuple[str, str, str], str] = {}
    for key, group in assignments.groupby(
        ["election", "source_locality_code", "ballot_base"], dropna=False
    ):
        area_ids = sorted(set(group.loc[group["stat_area_id"].ne(""), "stat_area_id"]))
        if len(area_ids) == 1:
            output[(clean(key[0]), clean(key[1]), clean(key[2]))] = area_ids[0]
    return output


def load_result_rows() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for election in ELECTIONS:
        path = RESULT_DIR / f"{election.lower()}_ballot_votes.csv"
        if not path.exists():
            continue
        frame = read_csv(path)
        frame["source_locality_code"] = frame["source_locality_code"].map(clean)
        frame["source_kalpi"] = frame["source_kalpi"].map(clean)
        frame["ballot_base"] = frame["source_kalpi"].map(ballot_base)
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def load_area_result_history() -> dict[tuple[str, str], int]:
    output: dict[tuple[str, str], int] = {}
    for election in ELECTIONS:
        path = PUBLIC_RESULT_DIR / f"{election.lower()}.csv"
        if not path.exists():
            continue
        for row in read_csv(path).to_dict("records"):
            output[(election, clean(row.get("stat_area_id")))] = integer(
                row.get("actual_voters")
            )
    return output


def adjacent_elections(election: str) -> set[str]:
    index = ELECTION_INDEX[election]
    return {
        candidate
        for candidate, candidate_index in ELECTION_INDEX.items()
        if abs(candidate_index - index) == 1
    }


def target_ballots_for_register_rows(
    result_rows: pd.DataFrame,
    election: str,
    locality_code: str,
    bases: set[str],
) -> pd.DataFrame:
    if not bases:
        return result_rows.iloc[0:0]
    return result_rows.loc[
        result_rows["election"].eq(election)
        & result_rows["source_locality_code"].eq(locality_code)
        & result_rows["ballot_base"].isin(bases)
    ].copy()


def classify_place_continuity(
    *,
    election: str,
    locality_code: str,
    stat_area_id: str,
    polling: pd.DataFrame,
    result_rows: pd.DataFrame,
) -> dict[str, Any]:
    empty = {
        "reference_elections": "",
        "reference_location_count": 0,
        "target_location_match_count": 0,
        "target_matched_ballots": "",
        "target_matched_ballot_count": 0,
        "target_matched_eligible_voters": 0,
        "target_matched_actual_voters": 0,
        "strict_host_area_ids": "",
        "adjacent_host_area_ids": "",
        "all_host_area_ids": "",
        "continuity_class": "no_compatible_polling_register",
        "candidate_host_area_ids": "",
    }
    if election not in SOURCES:
        return empty

    locality_polling = polling.loc[polling["locality_code"].eq(locality_code)]
    references = locality_polling.loc[
        locality_polling["election"].ne(election)
        & locality_polling["stat_area_id"].eq(stat_area_id)
        & locality_polling["location_key"].ne("|")
    ].copy()
    if references.empty:
        return {**empty, "continuity_class": "no_other_election_place_evidence"}

    target = locality_polling.loc[
        locality_polling["election"].eq(election)
        & locality_polling["location_key"].ne("|")
    ].copy()
    all_locations = set(references["location_key"])
    adjacent_names = adjacent_elections(election)
    adjacent_references = references.loc[references["election"].isin(adjacent_names)]
    adjacent_locations = set(adjacent_references["location_key"])

    all_matches = target.loc[target["location_key"].isin(all_locations)]
    adjacent_matches = target.loc[target["location_key"].isin(adjacent_locations)]
    strict_matches = target.merge(
        adjacent_references[["location_key", "ballot_base"]].drop_duplicates(),
        on=["location_key", "ballot_base"],
        how="inner",
    )

    strict_hosts = set(strict_matches["stat_area_id"]) - {""}
    adjacent_hosts = set(adjacent_matches["stat_area_id"]) - {""}
    all_hosts = set(all_matches["stat_area_id"]) - {""}

    if len(strict_hosts) == 1:
        continuity_class = "unique_adjacent_same_ballot_and_place_host"
        candidate_hosts = strict_hosts
        selected_matches = strict_matches
    elif len(adjacent_hosts) == 1:
        continuity_class = "unique_adjacent_exact_place_host"
        candidate_hosts = adjacent_hosts
        selected_matches = adjacent_matches
    elif len(adjacent_hosts) > 1:
        continuity_class = "conflicting_adjacent_exact_place_hosts"
        candidate_hosts = adjacent_hosts
        selected_matches = adjacent_matches
    elif len(all_hosts) == 1:
        continuity_class = "unique_nonadjacent_exact_place_host"
        candidate_hosts = all_hosts
        selected_matches = all_matches
    elif len(all_hosts) > 1:
        continuity_class = "conflicting_nonadjacent_exact_place_hosts"
        candidate_hosts = all_hosts
        selected_matches = all_matches
    else:
        continuity_class = "no_current_exact_place_match"
        candidate_hosts = set()
        selected_matches = target.iloc[0:0]

    selected_bases = set(selected_matches["ballot_base"])
    matched_results = target_ballots_for_register_rows(
        result_rows, election, locality_code, selected_bases
    )
    return {
        "reference_elections": pipe(references["election"]),
        "reference_location_count": references["location_key"].nunique(),
        "target_location_match_count": len(selected_matches),
        "target_matched_ballots": pipe(matched_results["source_kalpi"]),
        "target_matched_ballot_count": matched_results["source_kalpi"].nunique(),
        "target_matched_eligible_voters": sum(
            integer(value) for value in matched_results["eligible_voters"]
        ),
        "target_matched_actual_voters": sum(
            integer(value) for value in matched_results["actual_voters"]
        ),
        "strict_host_area_ids": pipe(strict_hosts),
        "adjacent_host_area_ids": pipe(adjacent_hosts),
        "all_host_area_ids": pipe(all_hosts),
        "continuity_class": continuity_class,
        "candidate_host_area_ids": pipe(candidate_hosts),
    }


def classify_crosswalk_register_place(
    *,
    election: str,
    locality_code: str,
    crosswalk_ballots: set[str],
    polling: pd.DataFrame,
    result_rows: pd.DataFrame,
) -> dict[str, Any]:
    empty = {
        "crosswalk_register_ballots": "",
        "crosswalk_register_eligible_voters": 0,
        "same_place_final_ballots": "",
        "same_place_final_eligible_voters": 0,
        "same_place_final_actual_voters": 0,
        "same_place_host_area_ids": "",
        "same_place_evidence_class": "no_compatible_polling_register",
    }
    if election not in SOURCES or not crosswalk_ballots:
        return empty

    locality_polling = polling.loc[
        polling["election"].eq(election)
        & polling["locality_code"].eq(locality_code)
    ].copy()
    target_register = locality_polling.loc[
        locality_polling["ballot_base"].isin(crosswalk_ballots)
        & locality_polling["location_key"].ne("|")
    ].copy()
    if target_register.empty:
        return {**empty, "same_place_evidence_class": "crosswalk_ballot_absent_from_register"}

    locality_results = result_rows.loc[
        result_rows["election"].eq(election)
        & result_rows["source_locality_code"].eq(locality_code)
    ].copy()
    result_bases = set(locality_results["ballot_base"])
    peers = locality_polling.loc[
        locality_polling["location_key"].isin(set(target_register["location_key"]))
        & locality_polling["ballot_base"].isin(result_bases)
        & ~locality_polling["ballot_base"].isin(crosswalk_ballots)
    ].copy()
    peer_bases = set(peers["ballot_base"])
    peer_results = locality_results.loc[
        locality_results["ballot_base"].isin(peer_bases)
    ].copy()
    host_area_ids = set(peers["stat_area_id"]) - {""}

    if not peers.empty and len(host_area_ids) == 1:
        evidence_class = "unique_same_election_register_place_host"
    elif not peers.empty and len(host_area_ids) > 1:
        evidence_class = "multiple_same_election_register_place_hosts"
    elif not peers.empty:
        evidence_class = "same_election_register_place_host_unassigned"
    else:
        evidence_class = "crosswalk_register_row_without_final_place_peer"

    return {
        "crosswalk_register_ballots": pipe(target_register["source_kalpi"]),
        "crosswalk_register_eligible_voters": sum(
            integer(value) for value in target_register["eligible"]
        ),
        "same_place_final_ballots": pipe(peer_results["source_kalpi"]),
        "same_place_final_eligible_voters": sum(
            integer(value) for value in peer_results["eligible_voters"]
        ),
        "same_place_final_actual_voters": sum(
            integer(value) for value in peer_results["actual_voters"]
        ),
        "same_place_host_area_ids": pipe(host_area_ids),
        "same_place_evidence_class": evidence_class,
    }


def proposed_resolution(row: dict[str, Any]) -> tuple[str, str]:
    evidence = clean(row["evidence_category"])
    continuity = clean(row["continuity_class"])
    matched_ballots = integer(row["target_matched_ballot_count"])
    same_place = clean(row.get("same_place_evidence_class"))
    register_eligible = integer(row.get("crosswalk_register_eligible_voters"))
    adult_population_proxy = integer(row.get("age_20_plus_population_proxy"))
    if evidence == "positive_population_only":
        return "historical_or_institutional_review", "not_applicable"
    if same_place in {
        "unique_same_election_register_place_host",
        "multiple_same_election_register_place_hosts",
    } and register_eligible == 0:
        if adult_population_proxy >= 500:
            return "official_zero_eligible_populated_area_review", "high"
        return "official_zero_eligible_register", "high"
    if same_place == "unique_same_election_register_place_host":
        return "same_election_register_display_merge", "high"
    if same_place == "multiple_same_election_register_place_hosts":
        return "same_election_register_set_review", "medium"
    if continuity in {
        "unique_adjacent_same_ballot_and_place_host",
        "unique_adjacent_exact_place_host",
    } and matched_ballots:
        return "compact_cross_election_display_merge", "high"
    if continuity == "unique_nonadjacent_exact_place_host" and matched_ballots:
        return "compact_cross_election_display_merge", "medium"
    if continuity.startswith("conflicting_") and matched_ballots:
        return "reviewed_set_level_display_merge", "medium"
    if continuity == "no_current_exact_place_match":
        return "no_result_evidence_after_place_search", "high"
    if continuity == "no_other_election_place_evidence":
        return "no_cross_election_place_evidence", "high"
    return "requires_historical_source_review", "unresolved"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--population-threshold", type=int, default=500)
    args = parser.parse_args()

    empty_audit = read_csv(EMPTY_AUDIT_PATH)
    large = empty_audit.loc[
        empty_audit["population_proxy"].map(integer).ge(args.population_threshold)
    ].copy()

    crosswalk = read_csv(CROSSWALK_PATH)
    crosswalk["locality_code"] = crosswalk["locality_code"].map(clean)
    crosswalk["ballot_number"] = crosswalk["ballot_number"].map(clean)
    crosswalk_by_area: dict[tuple[str, str], list[str]] = defaultdict(list)
    for item in crosswalk.to_dict("records"):
        crosswalk_by_area[(item["election"], item["stat_area_id"])].append(
            item["ballot_number"]
        )

    assignments = read_csv(ASSIGNMENTS_PATH)
    assignment_lookup = build_assignment_lookup(assignments)
    polling = load_polling_registers(assignment_lookup)
    polling["location_key"] = polling["location_key"].map(clean)
    result_rows = load_result_rows()
    area_history = load_area_result_history()

    rows: list[dict[str, Any]] = []
    for source in large.to_dict("records"):
        election = clean(source["election"])
        locality_code = clean(source["locality_code"])
        stat_area_id = clean(source["stat_area_id"])
        history = [
            f"{candidate}:{area_history.get((candidate, stat_area_id), 0)}"
            for candidate in ELECTIONS
        ]
        continuity = classify_place_continuity(
            election=election,
            locality_code=locality_code,
            stat_area_id=stat_area_id,
            polling=polling,
            result_rows=result_rows,
        )
        crosswalk_ballots = {
            ballot_base(value)
            for value in crosswalk_by_area[(election, stat_area_id)]
            if ballot_base(value)
        }
        register_place = classify_crosswalk_register_place(
            election=election,
            locality_code=locality_code,
            crosswalk_ballots=crosswalk_ballots,
            polling=polling,
            result_rows=result_rows,
        )
        row = {
            "election": election,
            "stat_area_vintage": source["stat_area_vintage"],
            "stat_area_id": stat_area_id,
            "locality_code": locality_code,
            "locality_name_he": source["locality_name_he"],
            "stat_area_number": source["stat_area_number"],
            "population_proxy": source["population_proxy"],
            "age_20_plus_population_proxy": source[
                "age_20_plus_population_proxy"
            ],
            "evidence_category": source["evidence_category"],
            "blank_elections": source["blank_elections"],
            "official_crosswalk_ballots": pipe(
                crosswalk_by_area[(election, stat_area_id)]
            ),
            "actual_voter_history": "|".join(history),
            **register_place,
            **continuity,
        }
        resolution, confidence = proposed_resolution(row)
        row["proposed_resolution"] = resolution
        row["resolution_confidence"] = confidence
        rows.append(row)

    rows.sort(
        key=lambda row: (
            ELECTION_INDEX[row["election"]],
            numeric_key(row["locality_code"]),
            numeric_key(row["stat_area_number"]),
        )
    )
    write_csv(OUTPUT_PATH, rows)

    summary = {
        "population_threshold": args.population_threshold,
        "case_count": len(rows),
        "unique_stat_area_count": len({row["stat_area_id"] for row in rows}),
        "resolution_counts": dict(
            sorted(pd.Series([row["proposed_resolution"] for row in rows]).value_counts().items())
        ),
        "confidence_counts": dict(
            sorted(pd.Series([row["resolution_confidence"] for row in rows]).value_counts().items())
        ),
        "cases_by_election": dict(
            sorted(pd.Series([row["election"] for row in rows]).value_counts().items())
        ),
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
