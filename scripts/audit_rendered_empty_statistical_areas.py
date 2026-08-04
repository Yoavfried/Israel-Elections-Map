#!/usr/bin/env python3
"""Audit visible statistical-area polygons that have no rendered result."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
COVERAGE_PATH = (
    ROOT / "data" / "processed" / "audits" / "historical_polygon_coverage.csv"
)
CROSSWALK_PATH = (
    ROOT
    / "data"
    / "processed"
    / "assignments"
    / "historical_ballot_crosswalk.csv"
)
WEB_DATA_DIR = ROOT / "web" / "app" / "public" / "data" / "v2"
OUT_DIR = ROOT / "data" / "processed" / "audits"
DETAIL_PATH = OUT_DIR / "rendered_empty_statistical_area_audit.csv"
SUMMARY_PATH = OUT_DIR / "rendered_empty_statistical_area_audit_summary.csv"
SUMMARY_JSON_PATH = OUT_DIR / "rendered_empty_statistical_area_audit_summary.json"

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


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def integer(value: Any) -> int:
    text = str(value or "").strip().replace(",", "")
    return int(round(float(text))) if text else 0


def numeric_sort(value: Any) -> tuple[int, str]:
    text = str(value or "")
    try:
        return (int(float(text)), text)
    except ValueError:
        return (10**9, text)


def load_display_polygon_ids(vintage: int) -> set[str]:
    path = (
        WEB_DATA_DIR
        / "geographies"
        / f"statistical-areas-{vintage}.geojson"
    )
    collection = json.loads(path.read_text(encoding="utf-8"))
    return {
        str((feature.get("properties") or {}).get("id") or feature.get("id") or "")
        for feature in collection.get("features", [])
        if (feature.get("properties") or {}).get("geographyType")
        == "statistical-area"
        and (feature.get("properties") or {}).get("displayMode") == "polygon"
        and (feature.get("geometry") or {}).get("type") in {"Polygon", "MultiPolygon"}
    }


def main() -> None:
    coverage = read_csv(COVERAGE_PATH)
    coverage_by_election: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in coverage:
        coverage_by_election[row["election"]].append(row)

    crosswalk_ballots: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in read_csv(CROSSWALK_PATH):
        key = (row["election"], row["stat_area_id"])
        crosswalk_ballots[key].add(row["ballot_number"])

    display_ids_by_vintage = {
        vintage: load_display_polygon_ids(vintage)
        for vintage in sorted(set(ELECTION_VINTAGES.values()))
    }

    detail_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []

    for election, vintage in ELECTION_VINTAGES.items():
        result_path = (
            WEB_DATA_DIR
            / "results"
            / election.lower()
            / "statistical-areas.json"
        )
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        records = payload.get("records", [])
        record_ids = {str(record.get("id") or "") for record in records}
        hidden_ids = {str(value) for value in payload.get("hiddenGeographyIds", [])}
        display_ids = display_ids_by_vintage[vintage]
        election_rows = [
            row
            for row in coverage_by_election[election]
            if row["stat_area_id"] in display_ids
        ]
        visible_rows = [
            row for row in election_rows if row["stat_area_id"] not in hidden_ids
        ]
        blank_rows = [
            row for row in visible_rows if row["stat_area_id"] not in record_ids
        ]
        zero_voter_record_ids = {
            str(record.get("id") or "")
            for record in records
            if str(record.get("id") or "") in display_ids
            and integer((record.get("totals") or {}).get("actualVoters")) == 0
        }

        population_available = any(
            str(row.get("population_proxy_source", "")).strip()
            or str(row.get("population_reference_year", "")).strip()
            for row in election_rows
        )
        positive_population_count = 0
        crosswalk_count = 0
        both_count = 0
        demographic_only_count = 0
        crosswalk_only_count = 0

        for row in blank_rows:
            stat_area_id = row["stat_area_id"]
            ballots = crosswalk_ballots.get((election, stat_area_id), set())
            has_crosswalk = bool(ballots)
            has_population = integer(row.get("population_proxy")) > 0
            if not has_crosswalk and not has_population:
                continue

            if has_population:
                positive_population_count += 1
            if has_crosswalk:
                crosswalk_count += 1
            if has_population and has_crosswalk:
                both_count += 1
                evidence_category = "population_and_official_crosswalk"
            elif has_population:
                demographic_only_count += 1
                evidence_category = "positive_population_only"
            else:
                crosswalk_only_count += 1
                evidence_category = "official_crosswalk_only"

            detail_rows.append(
                {
                    "election": election,
                    "stat_area_vintage": vintage,
                    "stat_area_id": stat_area_id,
                    "locality_code": row.get("locality_code", ""),
                    "locality_name_he": row.get("locality_name_he", ""),
                    "locality_name_en": row.get("locality_name_en", ""),
                    "stat_area_number": row.get("stat_area_number", ""),
                    "evidence_category": evidence_category,
                    "population_proxy": row.get("population_proxy", ""),
                    "age_20_plus_population_proxy": row.get(
                        "age_20_plus_population_proxy", ""
                    ),
                    "population_reference_year": row.get(
                        "population_reference_year", ""
                    ),
                    "population_proxy_source": row.get(
                        "population_proxy_source", ""
                    ),
                    "population_evidence_status": row.get(
                        "population_evidence_status", ""
                    ),
                    "official_crosswalk_ballot_count": len(ballots),
                    "official_crosswalk_ballots": "|".join(
                        sorted(ballots, key=numeric_sort)
                    ),
                    "polygon_assignment_status": row.get(
                        "polygon_assignment_status", ""
                    ),
                    "polygon_assignment_explanation": row.get(
                        "polygon_assignment_explanation", ""
                    ),
                }
            )

        summary_rows.append(
            {
                "election": election,
                "stat_area_vintage": vintage,
                "population_proxy_available": population_available,
                "display_polygon_count": len(election_rows),
                "visible_polygon_count": len(visible_rows),
                "visible_blank_polygon_count": len(blank_rows),
                "blank_positive_population_count": positive_population_count,
                "blank_official_crosswalk_count": crosswalk_count,
                "blank_population_and_crosswalk_count": both_count,
                "blank_positive_population_only_count": demographic_only_count,
                "blank_official_crosswalk_only_count": crosswalk_only_count,
                "blank_review_union_count": (
                    positive_population_count + crosswalk_only_count
                ),
                "visible_zero_voter_result_count": len(zero_voter_record_ids),
            }
        )

    elections_by_id: dict[str, list[str]] = defaultdict(list)
    for row in detail_rows:
        elections_by_id[str(row["stat_area_id"])].append(str(row["election"]))
    for row in detail_rows:
        elections = elections_by_id[str(row["stat_area_id"])]
        row["blank_election_count"] = len(elections)
        row["blank_elections"] = "|".join(elections)

    detail_rows.sort(
        key=lambda row: (
            numeric_sort(str(row["election"])[1:]),
            numeric_sort(row["locality_code"]),
            numeric_sort(row["stat_area_number"]),
            str(row["stat_area_id"]),
        )
    )
    detail_fields = [
        "election",
        "stat_area_vintage",
        "stat_area_id",
        "locality_code",
        "locality_name_he",
        "locality_name_en",
        "stat_area_number",
        "evidence_category",
        "population_proxy",
        "age_20_plus_population_proxy",
        "population_reference_year",
        "population_proxy_source",
        "population_evidence_status",
        "official_crosswalk_ballot_count",
        "official_crosswalk_ballots",
        "polygon_assignment_status",
        "polygon_assignment_explanation",
        "blank_election_count",
        "blank_elections",
    ]
    summary_fields = list(summary_rows[0])
    write_csv(DETAIL_PATH, detail_rows, detail_fields)
    write_csv(SUMMARY_PATH, summary_rows, summary_fields)

    unique_ids = {str(row["stat_area_id"]) for row in detail_rows}
    positive_rows = [row for row in detail_rows if integer(row["population_proxy"]) > 0]
    summary_json = {
        "definition": (
            "Visible base statistical-area polygons with no result record and "
            "either a positive CBS population proxy or an official election "
            "crosswalk reference. Hidden polygons and marker-only features are excluded."
        ),
        "totals": {
            "election_polygon_review_cases": len(detail_rows),
            "unique_statistical_area_ids": len(unique_ids),
            "unique_localities": len(
                {
                    (str(row["stat_area_vintage"]), str(row["locality_code"]))
                    for row in detail_rows
                }
            ),
            "positive_population_election_polygon_cases": len(positive_rows),
            "positive_population_unique_statistical_area_ids": len(
                {str(row["stat_area_id"]) for row in positive_rows}
            ),
        },
        "elections": summary_rows,
        "warnings": [
            "Population values are demographic proxies, not election-specific eligible-voter counts.",
            "The current pipeline has no population proxy for the 1995 vintage used by K17.",
            "A crosswalk reference proves a planned area-ballot relationship, not an exact final vote allocation.",
        ],
    }
    SUMMARY_JSON_PATH.write_text(
        json.dumps(summary_json, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {len(detail_rows)} review rows for "
        f"{len(unique_ids)} unique statistical-area IDs."
    )


if __name__ == "__main__":
    main()
