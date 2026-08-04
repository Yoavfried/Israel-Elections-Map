#!/usr/bin/env python3
"""Recover K19 polling-register attachments for large rendered-empty areas.

The official K19 polling-place PDF has a ``joined to`` column.  Rows in that
column describe planned registers whose voters were counted in another final
ballot.  This audit extracts those rows and joins them to the official CBS
ballot-to-statistical-area crosswalk and the final ballot results.
"""

from __future__ import annotations

import csv
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd
import pdfplumber
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = ROOT / "data" / "raw" / "archive_knesset19_all_stations.pdf"
AUDIT_DIR = ROOT / "data" / "processed" / "audits"
ASSIGNMENT_DIR = ROOT / "data" / "processed" / "assignments"
RESULT_PATH = (
    ROOT
    / "data"
    / "processed"
    / "normalized"
    / "ballot_votes_wide"
    / "k19_ballot_votes.csv"
)
EMPTY_AUDIT_PATH = AUDIT_DIR / "rendered_empty_statistical_area_audit.csv"
CROSSWALK_PATH = ASSIGNMENT_DIR / "historical_ballot_crosswalk.csv"
ASSIGNMENTS_PATH = ASSIGNMENT_DIR / "historical_ballot_assignments.csv"
REGISTER_OUTPUT_PATH = AUDIT_DIR / "k19_large_empty_polling_register_rows.csv"
EVIDENCE_OUTPUT_PATH = AUDIT_DIR / "k19_large_empty_attachment_evidence.csv"

ATTACHMENT_RE = re.compile(r"(?P<locality>\d{4})-(?P<ballot>\d{3}(?:\.\d+)?)")
NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")


def clean(value: Any) -> str:
    text = str(value or "").strip()
    return "" if text.lower() == "nan" else text


def integer(value: Any) -> int:
    text = clean(value).replace(",", "")
    return int(round(float(text))) if text else 0


def ballot_base(value: Any) -> str:
    text = clean(value)
    if not text:
        return ""
    try:
        return str(int(float(text)))
    except ValueError:
        return text.split(".", 1)[0]


def compact(value: Any) -> str:
    return re.sub(r"[^\w]", "", clean(value), flags=re.UNICODE)


def repair_visual_hebrew(value: Any) -> str:
    """Reverse PDF visual-order Hebrew while preserving digit order."""
    text = clean(value)[::-1]
    return NUMBER_RE.sub(lambda match: match.group(0)[::-1], text)


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


def parse_table_row(page_number: int, row: list[Any]) -> dict[str, Any] | None:
    if len(row) < 11:
        return None
    attached_to = clean(row[0])
    eligible = clean(row[1])
    ballot = clean(row[6])
    locality_code = clean(row[8]).lstrip("0") or "0"
    if not locality_code.isdigit() or not ballot or not eligible.isdigit():
        return None
    match = ATTACHMENT_RE.fullmatch(attached_to)
    return {
        "pdf_page": page_number,
        "committee_code": clean(row[10]),
        "committee_name": repair_visual_hebrew(row[9]),
        "locality_code": locality_code,
        "locality_name": repair_visual_hebrew(row[7]),
        "ballot": ballot,
        "ballot_base": ballot_base(ballot),
        "address": repair_visual_hebrew(row[5]),
        "place": repair_visual_hebrew(row[4]),
        "eligible_voters": integer(eligible),
        "attached_to": attached_to,
        "attached_host_locality_code": (
            match.group("locality").lstrip("0") if match else ""
        ),
        "attached_host_ballot": match.group("ballot") if match else "",
        "attached_host_ballot_base": (
            ballot_base(match.group("ballot")) if match else ""
        ),
    }


def target_cases() -> tuple[pd.DataFrame, dict[tuple[str, str], set[str]]]:
    empty = read_csv(EMPTY_AUDIT_PATH)
    targets = empty.loc[
        empty["election"].eq("K19")
        & empty["population_proxy"].map(integer).ge(500)
    ].copy()
    crosswalk = read_csv(CROSSWALK_PATH)
    crosswalk = crosswalk.loc[crosswalk["election"].eq("K19")].copy()
    target_ids = set(targets["stat_area_id"])
    target_lookup: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in crosswalk.loc[crosswalk["stat_area_id"].isin(target_ids)].to_dict(
        "records"
    ):
        target_lookup[
            (clean(row["locality_code"]), ballot_base(row["ballot_number"]))
        ].add(clean(row["stat_area_id"]))
    return targets, target_lookup


def select_pages(targets: pd.DataFrame) -> list[int]:
    target_needles = {
        f"{clean(row.locality_code)}{compact(row.locality_name_he.replace('*', ''))}"
        for row in targets.itertuples()
    }
    reader = PdfReader(PDF_PATH)
    selected: list[int] = []
    for index, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        compact_text = compact(text)
        if ATTACHMENT_RE.search(text) or any(
            needle in compact_text for needle in target_needles
        ):
            selected.append(index)
        if (index + 1) % 100 == 0:
            print(f"scanned {index + 1}/{len(reader.pages)} PDF pages", flush=True)
    return selected


def extract_rows(page_indexes: list[int], target_codes: set[str]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    with pdfplumber.open(PDF_PATH) as document:
        for offset, page_index in enumerate(page_indexes, start=1):
            page = document.pages[page_index]
            for table in page.extract_tables():
                for raw_row in table:
                    row = parse_table_row(page_index + 1, raw_row)
                    if not row:
                        continue
                    if not row["attached_to"] and row["locality_code"] not in target_codes:
                        continue
                    key = (
                        row["pdf_page"],
                        row["locality_code"],
                        row["ballot"],
                        row["eligible_voters"],
                        row["attached_to"],
                    )
                    if key in seen:
                        continue
                    seen.add(key)
                    output.append(row)
            if offset % 25 == 0:
                print(f"extracted {offset}/{len(page_indexes)} selected pages", flush=True)
    return output


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    targets, target_lookup = target_cases()
    target_codes = set(targets["locality_code"].map(clean))
    page_indexes = select_pages(targets)
    rows = extract_rows(page_indexes, target_codes)

    crosswalk = read_csv(CROSSWALK_PATH)
    crosswalk = crosswalk.loc[crosswalk["election"].eq("K19")].copy()
    area_by_planned_ballot: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in crosswalk.to_dict("records"):
        area_by_planned_ballot[
            (clean(row["locality_code"]), ballot_base(row["ballot_number"]))
        ].add(clean(row["stat_area_id"]))

    results = read_csv(RESULT_PATH)
    results["ballot_base"] = results["source_kalpi"].map(ballot_base)
    assignments = read_csv(ASSIGNMENTS_PATH)
    assignments = assignments.loc[assignments["election"].eq("K19")].copy()
    area_by_result_row = {
        clean(row["source_row_uid"]): clean(row["stat_area_id"])
        for row in assignments.to_dict("records")
    }

    attached_by_host: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["attached_host_locality_code"]:
            attached_by_host[
                (
                    row["attached_host_locality_code"],
                    row["attached_host_ballot_base"],
                )
            ].append(row)

    register_rows: list[dict[str, Any]] = []
    for row in rows:
        areas = area_by_planned_ballot[(row["locality_code"], row["ballot_base"])]
        register_rows.append(
            {
                **row,
                "crosswalk_area_ids": pipe(areas),
                "is_large_empty_target": str(
                    bool(target_lookup[(row["locality_code"], row["ballot_base"])])
                ).lower(),
            }
        )
    write_csv(REGISTER_OUTPUT_PATH, register_rows)

    evidence: list[dict[str, Any]] = []
    for row in rows:
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
        peer_rows = attached_by_host.get(host_key, [])
        peer_area_ids: set[str] = set()
        unknown_peer_rows: list[str] = []
        for peer in peer_rows:
            peer_areas = area_by_planned_ballot[
                (peer["locality_code"], peer["ballot_base"])
            ]
            peer_area_ids.update(peer_areas)
            if not peer_areas:
                unknown_peer_rows.append(
                    f"{peer['locality_code']}:{peer['ballot']}"
                )
        evidence.append(
            {
                "target_locality_code": row["locality_code"],
                "target_locality_name": row["locality_name"],
                "target_ballot": row["ballot"],
                "target_area_ids": pipe(target_area_ids),
                "target_planned_eligible": row["eligible_voters"],
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
                    if host_results.shape[0]
                    and host_area_ids
                    and not unknown_peer_rows
                    else "incomplete_attachment_evidence"
                ),
            }
        )
    evidence.sort(
        key=lambda item: (
            int(item["target_locality_code"]),
            float(item["target_ballot"]),
        )
    )
    write_csv(EVIDENCE_OUTPUT_PATH, evidence)
    print(
        f"extracted {len(register_rows)} register rows and "
        f"{len(evidence)} large-empty attachment rows"
    )


if __name__ == "__main__":
    main()
