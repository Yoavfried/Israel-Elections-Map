from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from pipeline_common import DATA_DIR, MANUAL_DIR, PROCESSED_DIR, int_value, normalize_code, normalize_kalpi, normalize_spaces, read_json, write_csv, write_json


MANIFEST_PATH = PROCESSED_DIR / "manifest" / "election_result_resources.json"
OUT_DIR = PROCESSED_DIR / "normalized"
K17_ELIGIBLE_OVERRIDES = MANUAL_DIR / "k17_eligible_voters.csv"
K17_ORDINARY_ELIGIBLE_TOTAL = 5_011_053

LOCALITY_CODE_FIELDS = ["סמל ישוב"]
LOCALITY_NAME_FIELDS = ["שם ישוב"]
KALPI_FIELDS = ["קלפי", "מספר קלפי", "סמל קלפי"]
ELIGIBLE_FIELDS = ["בזב", "בז''ב"]
ACTUAL_FIELDS = ["מצביעים"]
VALID_FIELDS = ["כשרים"]
INVALID_FIELDS = ["פסולים"]
NON_RESULT_FIELDS = ["\u05db\u05ea\u05d5\u05d1\u05ea"]

ADMIN_FIELDS = {
    "_id",
    "\u05ea. \u05e2\u05d3\u05db\u05d5\u05df",
    "סמל ועדה",
    "ברזל",
    "ריכוז",
    "שופט",
}
CORE_FIELD_NAMES = set(
    LOCALITY_CODE_FIELDS
    + LOCALITY_NAME_FIELDS
    + KALPI_FIELDS
    + ELIGIBLE_FIELDS
    + ACTUAL_FIELDS
    + VALID_FIELDS
    + INVALID_FIELDS
    + NON_RESULT_FIELDS
) | ADMIN_FIELDS


def first_value(row: pd.Series, fields: list[str]) -> Any:
    for field in fields:
        if field in row.index and pd.notna(row[field]) and str(row[field]).strip() != "":
            return row[field]
    return ""


def source_path(local_path: str) -> Path:
    return DATA_DIR / local_path


def is_envelope(locality_code: str, locality_name: str) -> bool:
    return locality_code in {"0", "9999"} or "מעטפ" in locality_name


def party_columns(columns: list[str]) -> list[str]:
    return [column for column in columns if column not in CORE_FIELD_NAMES]


def normalize_resource(
    resource: dict, k17_eligible_overrides: dict[str, dict[str, Any]]
) -> tuple[list[dict], list[dict], list[dict]]:
    election = resource["election"]
    election_number = int(resource["election_number"])
    path = source_path(resource["local_path"])
    df = pd.read_csv(path, dtype=str, encoding="utf-8-sig").fillna("")

    parties = party_columns(list(df.columns))
    row_index: list[dict] = []
    party_metadata: list[dict] = []
    wide_rows: list[dict] = []

    for order, (_, source_row) in enumerate(df.iterrows(), start=1):
        source_row_id = normalize_spaces(source_row.get("_id", "")) or str(order)
        locality_code = normalize_code(first_value(source_row, LOCALITY_CODE_FIELDS))
        locality_name = normalize_spaces(first_value(source_row, LOCALITY_NAME_FIELDS))
        kalpi = normalize_kalpi(first_value(source_row, KALPI_FIELDS))
        eligible = int_value(first_value(source_row, ELIGIBLE_FIELDS))
        actual = int_value(first_value(source_row, ACTUAL_FIELDS))
        valid = int_value(first_value(source_row, VALID_FIELDS))
        invalid = int_value(first_value(source_row, INVALID_FIELDS))
        if invalid == 0 and actual and actual >= valid:
            invalid = actual - valid
        if actual != valid + invalid:
            raise ValueError(
                f"{election}:{source_row_id} has {actual} actual voters but "
                f"{valid} valid plus {invalid} invalid votes"
            )
        source_row_uid = f"{election}:{source_row_id}"
        envelope = is_envelope(locality_code, locality_name)
        if election == "K17" and not envelope:
            if source_row_uid not in k17_eligible_overrides:
                raise ValueError(f"Missing K17 eligible-voter override for {source_row_uid}")
            override = k17_eligible_overrides[source_row_uid]
            eligible = override["eligible_voters"]
            expected_actual = override["actual_voters"]
            if expected_actual != actual:
                raise ValueError(
                    f"{source_row_uid} has {actual} actual voters in the result row but "
                    f"{expected_actual} in the K17 eligibility override"
                )
            if eligible < actual:
                raise ValueError(
                    f"{source_row_uid} has {eligible} eligible voters but {actual} actual voters"
                )
            if override["source_locality_name"] != locality_name or override["source_kalpi"] != kalpi:
                raise ValueError(
                    f"{source_row_uid} K17 scan identity no longer matches the result row"
                )
            locality_code = override["scan_locality_code"]

        core = {
            "source_row_uid": source_row_uid,
            "election": election,
            "election_number": election_number,
            "source_row_id": source_row_id,
            "source_order": order,
            "source_locality_code": locality_code,
            "source_locality_name": locality_name,
            "source_kalpi": kalpi,
            "eligible_voters": eligible,
            "actual_voters": actual,
            "valid_votes": valid,
            "invalid_votes": invalid,
            "is_envelope": envelope,
        }
        row_index.append(core)

        wide = dict(core)
        for party in parties:
            wide[party] = int_value(source_row.get(party, ""))
        wide_rows.append(wide)

    for party in parties:
        party_metadata.append(
            {
                "election": election,
                "election_number": election_number,
                "ballot_letter": party,
                "source_column": party,
                "total_votes": int(df[party].map(int_value).sum()),
            }
        )

    wide_path = OUT_DIR / "ballot_votes_wide" / f"{election.lower()}_ballot_votes.csv"
    write_csv(wide_path, wide_rows, list(wide_rows[0].keys()))
    return row_index, party_metadata, [
        {
            "election": election,
            "election_number": election_number,
            "source_path": str(path.relative_to(DATA_DIR.parent)).replace("\\", "/"),
            "rows": len(df),
            "party_columns": len(parties),
            "eligible_voters": sum(row["eligible_voters"] for row in row_index),
            "actual_voters": sum(row["actual_voters"] for row in row_index),
            "valid_votes": sum(row["valid_votes"] for row in row_index),
            "invalid_votes": sum(row["invalid_votes"] for row in row_index),
            "envelope_rows": sum(1 for row in row_index if row["is_envelope"]),
            "envelope_actual_voters": sum(row["actual_voters"] for row in row_index if row["is_envelope"]),
        }
    ]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.parse_args()

    manifest = read_json(MANIFEST_PATH)
    k17_eligible_overrides = load_k17_eligible_overrides()
    all_rows: list[dict] = []
    all_parties: list[dict] = []
    summaries: list[dict] = []

    for resource in sorted(manifest, key=lambda item: int(item["election_number"]), reverse=True):
        rows, parties, summary = normalize_resource(resource, k17_eligible_overrides)
        all_rows.extend(rows)
        all_parties.extend(parties)
        summaries.extend(summary)

    row_fields = [
        "source_row_uid",
        "election",
        "election_number",
        "source_row_id",
        "source_order",
        "source_locality_code",
        "source_locality_name",
        "source_kalpi",
        "eligible_voters",
        "actual_voters",
        "valid_votes",
        "invalid_votes",
        "is_envelope",
    ]
    party_fields = ["election", "election_number", "ballot_letter", "source_column", "total_votes"]
    summary_fields = [
        "election",
        "election_number",
        "source_path",
        "rows",
        "party_columns",
        "eligible_voters",
        "actual_voters",
        "valid_votes",
        "invalid_votes",
        "envelope_rows",
        "envelope_actual_voters",
    ]

    write_csv(OUT_DIR / "ballot_rows.csv", all_rows, row_fields)
    write_csv(OUT_DIR / "party_columns.csv", all_parties, party_fields)
    write_csv(OUT_DIR / "normalization_summary.csv", summaries, summary_fields)
    write_json(OUT_DIR / "normalization_summary.json", summaries)

    print(f"normalized_rows={len(all_rows)}")
    print(f"party_columns={len(all_parties)}")
    for summary in summaries:
        print(
            f"{summary['election']}: rows={summary['rows']} eligible={summary['eligible_voters']} actual={summary['actual_voters']} "
            f"envelope_rows={summary['envelope_rows']}"
        )


def load_k17_eligible_overrides() -> dict[str, dict[str, Any]]:
    df = pd.read_csv(K17_ELIGIBLE_OVERRIDES, dtype=str, encoding="utf-8-sig").fillna("")
    required = {
        "source_row_uid",
        "eligible_voters",
        "actual_voters",
        "scan_locality_code",
        "source_locality_name",
        "source_kalpi",
    }
    missing_columns = required - set(df.columns)
    if missing_columns:
        raise ValueError(
            f"{K17_ELIGIBLE_OVERRIDES} is missing columns: {sorted(missing_columns)}"
        )

    overrides: dict[str, dict[str, Any]] = {}
    for _, row in df.iterrows():
        source_row_uid = normalize_spaces(row["source_row_uid"])
        eligible = int_value(row["eligible_voters"])
        actual = int_value(row["actual_voters"])
        scan_locality_code = normalize_code(row["scan_locality_code"])
        source_locality_name = normalize_spaces(row["source_locality_name"])
        source_kalpi = normalize_kalpi(row["source_kalpi"])
        if not source_row_uid.startswith("K17:"):
            raise ValueError(f"Invalid K17 eligibility key: {source_row_uid}")
        if source_row_uid in overrides:
            raise ValueError(f"Duplicate K17 eligibility key: {source_row_uid}")
        if not scan_locality_code or not source_locality_name or not source_kalpi:
            raise ValueError(f"Incomplete K17 scan identity: {source_row_uid}")
        if eligible < actual:
            raise ValueError(
                f"{source_row_uid} has {eligible} eligible voters but {actual} actual voters"
            )
        overrides[source_row_uid] = {
            "eligible_voters": eligible,
            "actual_voters": actual,
            "scan_locality_code": scan_locality_code,
            "source_locality_name": source_locality_name,
            "source_kalpi": source_kalpi,
        }

    if len(overrides) != 8_277:
        raise ValueError(f"Expected 8,277 K17 eligibility overrides, found {len(overrides)}")
    total = sum(row["eligible_voters"] for row in overrides.values())
    if total != K17_ORDINARY_ELIGIBLE_TOTAL:
        raise ValueError(
            f"K17 ordinary eligible-voter total is {total}, expected {K17_ORDINARY_ELIGIBLE_TOTAL}"
        )
    return overrides


if __name__ == "__main__":
    main()
