"""Reconcile the K26 snapshot and quarantine pre-balance area-key candidates."""
from __future__ import annotations

import csv
import sys
from collections import Counter, defaultdict

import openpyxl

from normalize_election_results import ADMIN_FIELDS, party_columns
from pipeline_common import PROCESSED_DIR, RAW_DIR, normalize_code, normalize_kalpi, write_csv, write_json

SOURCE = RAW_DIR / "k26"


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ballots = read_csv(SOURCE / "ballots.csv")
    localities = read_csv(SOURCE / "localities.csv")
    parties = party_columns(list(ballots[0]))
    if len(parties) != 38 or set(parties) & ADMIN_FIELDS:
        raise ValueError("K26 party/admin column separation changed")
    metrics = ["בזב", "מצביעים", "פסולים", "כשרים"] + parties
    totals = defaultdict(Counter)
    keys = set()
    for row in ballots:
        key = (row["סמל ישוב"], normalize_kalpi(row["קלפי"]))
        if key in keys:
            raise ValueError(f"Duplicate K26 ballot identity: {key}")
        keys.add(key)
        if sum(int(row[p]) for p in parties) != int(row["כשרים"]):
            raise ValueError(f"Party votes do not reconcile: {key}")
        if int(row["מצביעים"]) != int(row["כשרים"]) + int(row["פסולים"]):
            raise ValueError(f"Valid/invalid votes do not reconcile: {key}")
        totals[row["סמל ישוב"]].update({field: int(row[field]) for field in metrics})
    for row in localities:
        actual = totals.pop(row["סמל ישוב"], None)
        if actual != Counter({field: int(row[field]) for field in metrics}):
            raise ValueError(f"K26 locality totals do not reconcile: {row['סמל ישוב']}")
    if totals:
        raise ValueError("K26 ballot localities absent from the locality export")
    book = openpyxl.load_workbook(SOURCE / "crosswalk.xlsx", read_only=True, data_only=True)
    crosswalk = {}
    for values in book["kalpi_October2026_stat2022"].iter_rows(values_only=True):
        if not isinstance(values[0], (int, float)) or not isinstance(values[2], (int, float)):
            continue
        key = (normalize_code(values[0]), normalize_kalpi(values[2]))
        area = f"stat2022:{normalize_code(values[4])}"
        if key in crosswalk and crosswalk[key] != area:
            raise ValueError(f"Conflicting CBS K26 key: {key}")
        crosswalk[key] = area
    book.close()
    known = {row["stat_area_id"] for row in read_csv(PROCESSED_DIR / "geographies" / "statistical_areas_2022.metadata.csv")}
    candidates = []
    for index, row in enumerate(ballots, 1):
        if row["סמל ישוב"] == "0":
            continue
        ballot = normalize_kalpi(row["קלפי"])
        exact = crosswalk.get((row["סמל ישוב"], ballot), "")
        base = crosswalk.get((row["סמל ישוב"], ballot.split(".")[0]), "")
        candidate = exact or base
        candidates.append({
            "source_row_uid": f"K26:{index}", "source_locality_code": row["סמל ישוב"],
            "source_locality_name": row["שם ישוב"], "source_kalpi": ballot,
            "actual_voters": row["מצביעים"], "candidate_stat_area_id": candidate,
            "candidate_key_type": "exact" if exact else "base_only" if base else "none",
            "candidate_has_geometry": candidate in known,
            "accepted_as_assignment": False,
            "reason": "Pre-balance crosswalk key only; final composition has not been validated. Single-area locality assignments are independently derived, not accepted from this candidate table.",
        })
    write_csv(PROCESSED_DIR / "audits" / "k26_crosswalk_candidates.csv", candidates, list(candidates[0]))
    summary = {
        "election": "K26", "snapshot_date": "2026-10-30", "certification_status": "pending",
        "source_rows": len(ballots), "party_columns": len(parties),
        "national_totals": {field: sum(int(row[field]) for row in ballots) for field in metrics[:4]},
        "locality_reconciliation": "exact_for_every_party_and_core_count",
        "crosswalk_keys": len(crosswalk), "crosswalk_candidates_are_assignments": False,
        "candidate_key_types": dict(Counter(row["candidate_key_type"] for row in candidates)),
        "area_policy": "Independently identified single-area localities and reviewed custom buckets are retained. Additional high-confidence synthetic row links are validated against the official planned and final registers. Mixed groups use the disclosed polling-group display policy; remaining unsupported localities use municipality fallbacks. Bare pre-balance crosswalk keys are never promoted on their own.",
    }
    register_links = PROCESSED_DIR / "audits" / "k26_validated_register_links.csv"
    if register_links.exists():
        verified = read_csv(register_links)
        summary["validated_register_link_rows"] = len(verified)
        summary["validated_register_link_actual_voters"] = sum(int(row["actual_voters"]) for row in verified)
    write_json(PROCESSED_DIR / "audits" / "k26_source_audit.json", summary)
    print(summary)


if __name__ == "__main__":
    main()
