#!/usr/bin/env python3
"""Recover explicit K18 joins affecting large rendered-empty areas."""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
AUDIT_DIR = ROOT / "data" / "processed" / "audits"
ASSIGNMENT_DIR = ROOT / "data" / "processed" / "assignments"
SOURCE_PATH = ROOT / "data" / "processed" / "k18_polling_places_extracted_prototype.csv"
RESULT_PATH = (
    ROOT
    / "data"
    / "processed"
    / "normalized"
    / "ballot_votes_wide"
    / "k18_ballot_votes.csv"
)
EMPTY_AUDIT_PATH = AUDIT_DIR / "rendered_empty_statistical_area_audit.csv"
CROSSWALK_PATH = ASSIGNMENT_DIR / "historical_ballot_crosswalk.csv"
ASSIGNMENTS_PATH = ASSIGNMENT_DIR / "historical_ballot_assignments.csv"
OUTPUT_PATH = AUDIT_DIR / "k18_large_empty_attachment_evidence.csv"

ATTACHED_HOST_RE = re.compile(r"(?P<locality>\d{4})\D+(?P<ballot>\d{3}(?:\.\d+)?)")


def clean(value: Any) -> str:
    text = str(value or "").strip()
    return "" if text.lower() == "nan" else text


def integer(value: Any) -> int:
    text = clean(value).replace(",", "")
    try:
        return int(round(float(text))) if text else 0
    except ValueError:
        return 0


def ballot_base(value: Any) -> str:
    text = clean(value)
    try:
        return str(int(float(text))) if text else ""
    except ValueError:
        return text.split(".", 1)[0]


def pipe(values: Any) -> str:
    return "|".join(sorted({clean(value) for value in values if clean(value)}))


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, encoding="utf-8-sig").fillna("")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"Refusing to write an empty audit: {path}")
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


def parse_host(value: Any) -> tuple[str, str]:
    reversed_text = clean(value)[::-1]
    match = ATTACHED_HOST_RE.search(reversed_text)
    if not match:
        return "", ""
    return match.group("locality").lstrip("0"), match.group("ballot")


def main() -> None:
    empty = read_csv(EMPTY_AUDIT_PATH)
    targets = empty.loc[
        empty["election"].eq("K18")
        & empty["population_proxy"].map(integer).ge(500)
    ].copy()
    target_ids = set(targets["stat_area_id"])

    crosswalk = read_csv(CROSSWALK_PATH)
    crosswalk = crosswalk.loc[crosswalk["election"].eq("K18")].copy()
    area_by_planned_ballot: dict[tuple[str, str], set[str]] = defaultdict(set)
    target_lookup: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in crosswalk.to_dict("records"):
        key = (clean(row["locality_code"]), ballot_base(row["ballot_number"]))
        area_id = clean(row["stat_area_id"])
        area_by_planned_ballot[key].add(area_id)
        if area_id in target_ids:
            target_lookup[key].add(area_id)

    source = read_csv(SOURCE_PATH)
    attached_rows: list[dict[str, Any]] = []
    attached_by_host: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in source.to_dict("records"):
        locality_code = clean(item["locality_code_clean"])
        ballot = clean(item["kalpi_clean"])
        host_locality, host_ballot = parse_host(item["place"])
        if not locality_code or not ballot or not host_locality:
            continue
        row = {
            "pdf_page": clean(item["pdf_page"]),
            "locality_code": locality_code,
            "locality_name": clean(item["locality_name"]),
            "ballot": ballot,
            "ballot_base": ballot_base(ballot),
            "planned_eligible": integer(item["eligible_clean"]),
            "attached_host_locality_code": host_locality,
            "attached_host_ballot": host_ballot,
            "attached_host_ballot_base": ballot_base(host_ballot),
        }
        attached_rows.append(row)
        attached_by_host[(host_locality, ballot_base(host_ballot))].append(row)

    results = read_csv(RESULT_PATH)
    results["ballot_base"] = results["source_kalpi"].map(ballot_base)
    assignments = read_csv(ASSIGNMENTS_PATH)
    assignments = assignments.loc[assignments["election"].eq("K18")].copy()
    area_by_result_row = {
        clean(row["source_row_uid"]): clean(row["stat_area_id"])
        for row in assignments.to_dict("records")
    }

    evidence: list[dict[str, Any]] = []
    for row in attached_rows:
        target_area_ids = target_lookup[(row["locality_code"], row["ballot_base"])]
        if not target_area_ids:
            continue
        host_key = (
            row["attached_host_locality_code"],
            row["attached_host_ballot_base"],
        )
        host_results = results.loc[
            results["source_locality_code"].eq(host_key[0])
            & results["ballot_base"].eq(host_key[1])
        ]
        host_area_ids = {
            area_by_result_row.get(clean(item["source_row_uid"]), "")
            for item in host_results.to_dict("records")
        } - {""}
        peer_rows = attached_by_host[host_key]
        peer_area_ids: set[str] = set()
        unknown_peer_rows: list[str] = []
        for peer in peer_rows:
            peer_areas = area_by_planned_ballot[
                (peer["locality_code"], peer["ballot_base"])
            ]
            peer_area_ids.update(peer_areas)
            if not peer_areas:
                unknown_peer_rows.append(f"{peer['locality_code']}:{peer['ballot']}")
        evidence.append(
            {
                "target_locality_code": row["locality_code"],
                "target_locality_name": row["locality_name"],
                "target_ballot": row["ballot"],
                "target_area_ids": pipe(target_area_ids),
                "target_planned_eligible": row["planned_eligible"],
                "attached_host_locality_code": host_key[0],
                "attached_host_ballot": row["attached_host_ballot"],
                "host_final_ballots": pipe(host_results["source_kalpi"]),
                "host_final_eligible": sum(
                    integer(value) for value in host_results["eligible_voters"]
                ),
                "host_final_actual": sum(
                    integer(value) for value in host_results["actual_voters"]
                ),
                "host_result_area_ids": pipe(host_area_ids),
                "all_rows_attached_to_host": pipe(
                    f"{peer['locality_code']}:{peer['ballot']}" for peer in peer_rows
                ),
                "all_attached_area_ids": pipe(peer_area_ids),
                "unknown_attached_rows": pipe(unknown_peer_rows),
                "candidate_component_area_ids": pipe(
                    target_area_ids | host_area_ids | peer_area_ids
                ),
                "candidate_evidence_status": (
                    "closed_attachment_evidence"
                    if not host_results.empty
                    and host_area_ids
                    and not unknown_peer_rows
                    else "incomplete_attachment_evidence"
                ),
            }
        )
    evidence.sort(
        key=lambda row: (
            int(row["target_locality_code"]),
            float(row["target_ballot"]),
        )
    )
    write_csv(OUTPUT_PATH, evidence)
    print(f"audited {len(evidence)} K18 large-empty attachment rows")


if __name__ == "__main__":
    main()
