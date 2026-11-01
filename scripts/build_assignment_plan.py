from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from pipeline_common import MANUAL_DIR, PROCESSED_DIR, ROOT, int_value, normalize_code, normalize_kalpi, normalize_spaces, write_csv, write_json


BALLOT_ROWS = PROCESSED_DIR / "normalized" / "ballot_rows.csv"
LOCALITIES = PROCESSED_DIR / "geographies" / "localities_2022.metadata.csv"
CROSSWALK = MANUAL_DIR / "locality_crosswalk.csv"
ROW_OVERRIDES = MANUAL_DIR / "ballot_geography_overrides.csv"
COMPOSITE_BALLOT_COMPONENTS = MANUAL_DIR / "historical_composite_ballot_components.csv"
OUT_DIR = PROCESSED_DIR / "assignments"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def norm_name(value: Any) -> str:
    text = normalize_spaces(value)
    text = re.sub(r"\[[^\]]*\]", "", text)
    text = text.replace("׳", "").replace("״", "")
    text = text.replace("'", "").replace('"', "")
    text = re.sub(r"[\s.,:/(){}\[\]\-_*]+", "", text)
    return text


def split_source_identity(value: str) -> tuple[str, str]:
    match = re.search(r"\[(\d+)\]\s*$", value or "")
    code = normalize_code(match.group(1)) if match else ""
    name = re.sub(r"\s*\[\d+\]\s*$", "", value or "").strip()
    return name, code


def bool_value(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def row_override_lookup_keys(row: dict[str, str]) -> list[tuple[str, str, str]]:
    keys: list[tuple[str, str, str]] = []
    source_row_uid = normalize_spaces(row.get("source_row_uid", ""))
    if source_row_uid:
        keys.append(("source_row_uid", source_row_uid, ""))

    election = normalize_spaces(row.get("election", ""))
    locality_code = normalize_code(row.get("source_locality_code", ""))
    kalpi = normalize_kalpi(row.get("source_kalpi", ""))
    if election and locality_code and kalpi:
        keys.append(("locality_kalpi", f"{election}:{locality_code}", kalpi))
    return keys


def row_override_key(row: dict[str, str]) -> tuple[str, str, str]:
    keys = row_override_lookup_keys(row)
    if not keys:
        return ("", "", "")
    if normalize_spaces(row.get("source_row_uid", "")):
        return keys[0]
    return keys[-1]


def row_override_index(rows: list[dict[str, str]]) -> dict[tuple[str, str, str], dict[str, str]]:
    index: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in rows:
        key = row_override_key(row)
        if not key[0] or not key[1]:
            raise ValueError(f"Invalid ballot geography override key: {row}")
        if key in index:
            raise ValueError(f"Duplicate ballot geography override key: {key}")
        index[key] = row
    return index


def historical_ballot_base(election: str, value: Any) -> int | None:
    text = normalize_spaces(value)
    if not text:
        return None
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    return int(number) // 10 if election == "K17" else int(number)


def composite_component_index(
    rows: list[dict[str, str]],
) -> tuple[dict[tuple[str, str], list[dict[str, Any]]], dict[str, int]]:
    index: dict[tuple[str, str], list[dict[str, Any]]] = {}
    expected_matches: dict[str, int] = {}
    valid_elections = {f"K{number}" for number in range(17, 26)}
    for source in rows:
        row = dict(source)
        election = normalize_spaces(row.get("election", ""))
        source_name_key = norm_name(row.get("source_locality_name", ""))
        source_code = normalize_code(row.get("source_locality_code", ""))
        target_code = normalize_code(row.get("component_locality_code", ""))
        target_name = normalize_spaces(row.get("component_locality_name", ""))
        evidence_status = normalize_spaces(row.get("evidence_status", ""))
        try:
            ballot_min = int(row.get("ballot_base_min", ""))
            ballot_max = int(row.get("ballot_base_max", ""))
            expected = int(row.get("expected_ballot_rows", ""))
        except ValueError as error:
            raise ValueError(f"Invalid composite component range: {source}") from error
        if (
            election not in valid_elections
            or not source_name_key
            or ballot_min > ballot_max
            or not target_code
            or not target_name
            or not evidence_status.startswith("confirmed_")
            or expected <= 0
        ):
            raise ValueError(f"Incomplete composite component range: {source}")
        rule_id = f"{election}:{source_name_key}:{ballot_min}-{ballot_max}:{target_code}"
        if rule_id in expected_matches:
            raise ValueError(f"Duplicate composite component range: {rule_id}")
        row.update(
            {
                "_rule_id": rule_id,
                "_source_code": source_code,
                "_ballot_min": ballot_min,
                "_ballot_max": ballot_max,
                "_target_code": target_code,
                "_target_name": target_name,
            }
        )
        key = (election, source_name_key)
        for existing in index.get(key, []):
            if ballot_min <= existing["_ballot_max"] and ballot_max >= existing["_ballot_min"]:
                raise ValueError(f"Overlapping composite component ranges: {rule_id}")
        index.setdefault(key, []).append(row)
        expected_matches[rule_id] = expected
    return index, expected_matches


def find_composite_component(
    row: dict[str, str],
    index: dict[tuple[str, str], list[dict[str, Any]]],
) -> dict[str, Any] | None:
    election = normalize_spaces(row.get("election", ""))
    source_name_key = norm_name(row.get("source_locality_name", ""))
    source_code = normalize_code(row.get("source_locality_code", ""))
    ballot = historical_ballot_base(election, row.get("source_kalpi", ""))
    if ballot is None:
        return None
    matches = [
        rule
        for rule in index.get((election, source_name_key), [])
        if rule["_ballot_min"] <= ballot <= rule["_ballot_max"]
        and (not rule["_source_code"] or rule["_source_code"] == source_code)
    ]
    if len(matches) > 1:
        raise ValueError(f"Ballot row matches multiple composite component ranges: {row}")
    return matches[0] if matches else None


def assignment_from_composite_component(rule: dict[str, Any]) -> dict[str, Any]:
    return {
        "assignment_method": "historical_stat_area_pending",
        "assignment_source": "reviewed_composite_component_evidence",
        "target_geography_type": "statistical_area_pending",
        "target_locality_code": rule["_target_code"],
        "target_locality_name": rule["_target_name"],
        "target_stat_area_id": "",
        "custom_geography_id": "",
        "unresolved_reason": "",
    }


def assignment_from_row_override(row: dict[str, str]) -> dict[str, Any]:
    method = row["assignment_method"]
    if method == "special_non_geographic":
        return {
            "assignment_method": "special_non_geographic",
            "assignment_source": "reviewed_ballot_geography_override",
            "target_geography_type": row["target_geography_type"] or "special_non_geographic",
            "target_locality_code": "",
            "target_locality_name": row["target_locality_name"],
            "target_stat_area_id": "",
            "custom_geography_id": row["custom_geography_id"] or "special:envelope_votes",
            "unresolved_reason": "",
        }
    if method == "single_stat_locality":
        required = [
            row.get("target_locality_code", ""),
            row.get("target_locality_name", ""),
            row.get("target_stat_area_id", ""),
        ]
        if not all(normalize_spaces(value) for value in required):
            raise ValueError(f"Incomplete single-area ballot override: {row}")
        return {
            "assignment_method": "single_stat_locality",
            "assignment_source": "reviewed_ballot_stat_override",
            "target_geography_type": "statistical_area",
            "target_locality_code": normalize_code(row["target_locality_code"]),
            "target_locality_name": row["target_locality_name"],
            "target_stat_area_id": row["target_stat_area_id"],
            "custom_geography_id": "",
            "unresolved_reason": "",
        }
    if method == "historical_stat_area_pending":
        required = [
            row.get("target_locality_code", ""),
            row.get("target_locality_name", ""),
        ]
        if not all(normalize_spaces(value) for value in required):
            raise ValueError(f"Incomplete historical-area ballot override: {row}")
        return {
            "assignment_method": "historical_stat_area_pending",
            "assignment_source": "reviewed_component_locality_override",
            "target_geography_type": "statistical_area_pending",
            "target_locality_code": normalize_code(row["target_locality_code"]),
            "target_locality_name": row["target_locality_name"],
            "target_stat_area_id": "",
            "custom_geography_id": "",
            "unresolved_reason": "",
        }
    raise ValueError(f"Unsupported ballot geography override assignment method: {method}")


def locality_indexes(rows: list[dict[str, str]]) -> tuple[dict[str, dict], dict[str, list[dict]]]:
    by_code: dict[str, dict] = {}
    by_name: dict[str, list[dict]] = {}
    for row in rows:
        code = normalize_code(row["locality_code"])
        row = dict(row)
        row["locality_code"] = code
        row["single_stat_area"] = bool_value(row["single_stat_area"])
        row["has_function_code"] = bool_value(row.get("has_function_code", ""))
        by_code[code] = row
        by_name.setdefault(norm_name(row["locality_name_he"]), []).append(row)
    return by_code, by_name


def prefer_real_locality(candidates: list[dict]) -> list[dict]:
    preferred = [candidate for candidate in candidates if candidate.get("has_function_code")]
    return preferred or candidates


def crosswalk_index(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict]:
    index: dict[tuple[str, str], dict] = {}
    for row in rows:
        source_name, source_code = split_source_identity(row["source_identity"])
        source_norm = norm_name(source_name)
        if source_code:
            index[(source_code, source_norm)] = row
        index.setdefault(("", source_norm), row)
    return index


def find_crosswalk(row: dict[str, str], index: dict[tuple[str, str], dict]) -> dict | None:
    code = normalize_code(row["source_locality_code"])
    name_norm = norm_name(row["source_locality_name"])
    if code and (code, name_norm) in index:
        return index[(code, name_norm)]
    return index.get(("", name_norm))


def find_target_by_name(target_name: str, by_name: dict[str, list[dict]]) -> tuple[dict | None, str]:
    candidates = prefer_real_locality(by_name.get(norm_name(target_name), []))
    if len(candidates) == 1:
        return candidates[0], ""
    if not candidates:
        return None, f"target locality not found: {target_name}"
    return None, f"target locality name is ambiguous: {target_name}"


def assignment_from_locality(target: dict, method_source: str) -> dict[str, Any]:
    if target["single_stat_area"]:
        return {
            "assignment_method": "single_stat_locality",
            "assignment_source": method_source,
            "target_geography_type": "statistical_area",
            "target_locality_code": target["locality_code"],
            "target_locality_name": target["locality_name_he"],
            "target_stat_area_id": target["stat_area_ids"],
            "custom_geography_id": "",
            "unresolved_reason": "",
        }
    return {
        "assignment_method": "historical_stat_area_pending",
        "assignment_source": method_source,
        "target_geography_type": "statistical_area_pending",
        "target_locality_code": target["locality_code"],
        "target_locality_name": target["locality_name_he"],
        "target_stat_area_id": "",
        "custom_geography_id": "",
        "unresolved_reason": "",
    }


def assignment_from_crosswalk(
    source_row: dict[str, str],
    crosswalk_row: dict[str, str],
    by_name: dict[str, list[dict]],
) -> dict[str, Any]:
    solution = crosswalk_row["solution"]
    geometry_target = crosswalk_row["geometry_target"]
    custom_id = crosswalk_row["custom_geography_id"] or geometry_target

    if solution == "accepted_locality_match":
        target, reason = find_target_by_name(geometry_target, by_name)
        if not target:
            return unresolved("reviewed_locality_target_missing", reason)
        return assignment_from_locality(target, "reviewed_locality_crosswalk")

    if solution == "historical_stat_area_pending":
        return {
            "assignment_method": "historical_stat_area_pending",
            "assignment_source": "reviewed_historical_target_set",
            "target_geography_type": "statistical_area_pending",
            "target_locality_code": "",
            "target_locality_name": geometry_target,
            "target_stat_area_id": "",
            "custom_geography_id": "",
            "unresolved_reason": "",
        }

    if solution == "custom_point_size_polygon":
        return {
            "assignment_method": "custom_point_size_polygon",
            "assignment_source": "reviewed_custom_bucket",
            "target_geography_type": "custom_geography",
            "target_locality_code": "",
            "target_locality_name": geometry_target,
            "target_stat_area_id": "",
            "custom_geography_id": custom_id,
            "unresolved_reason": "",
        }

    if solution == "special_non_geographic":
        return {
            "assignment_method": "special_non_geographic",
            "assignment_source": "reviewed_crosswalk",
            "target_geography_type": "special_non_geographic",
            "target_locality_code": "",
            "target_locality_name": geometry_target,
            "target_stat_area_id": "",
            "custom_geography_id": custom_id,
            "unresolved_reason": "",
        }

    return unresolved("unsupported_crosswalk_solution", solution)


def unresolved(reason: str, detail: str = "") -> dict[str, Any]:
    return {
        "assignment_method": "unresolved",
        "assignment_source": "",
        "target_geography_type": "unresolved",
        "target_locality_code": "",
        "target_locality_name": "",
        "target_stat_area_id": "",
        "custom_geography_id": "",
        "unresolved_reason": f"{reason}: {detail}" if detail else reason,
    }


def assign_row(
    row: dict[str, str],
    localities_by_code: dict[str, dict],
    localities_by_name: dict[str, list[dict]],
    crosswalk: dict[tuple[str, str], dict],
    row_overrides: dict[tuple[str, str, str], dict[str, str]],
    composite_components: dict[tuple[str, str], list[dict[str, Any]]],
    component_match_counts: Counter[str],
) -> dict[str, Any]:
    if bool_value(row["is_envelope"]):
        return {
            "assignment_method": "official_envelope",
            "assignment_source": "envelope_detection",
            "target_geography_type": "official_envelope",
            "target_locality_code": "",
            "target_locality_name": "",
            "target_stat_area_id": "",
            "custom_geography_id": "special:envelope_votes",
            "unresolved_reason": "",
        }

    override = next(
        (row_overrides[key] for key in row_override_lookup_keys(row) if key in row_overrides),
        None,
    )
    if override:
        return assignment_from_row_override(override)

    component = find_composite_component(row, composite_components)
    if component:
        component_match_counts[component["_rule_id"]] += 1
        return assignment_from_composite_component(component)

    reviewed = find_crosswalk(row, crosswalk)
    code = normalize_code(row["source_locality_code"])
    if row["election"] == "K26" and code in localities_by_code and (
        not reviewed or reviewed["solution"] not in {"custom_point_size_polygon", "special_non_geographic"}
    ):
        return assignment_from_locality(localities_by_code[code], "automatic_code_match")
    if reviewed:
        return assignment_from_crosswalk(row, reviewed, localities_by_name)

    if code and code in localities_by_code:
        return assignment_from_locality(localities_by_code[code], "automatic_code_match")

    candidates = prefer_real_locality(localities_by_name.get(norm_name(row["source_locality_name"]), []))
    if len(candidates) == 1:
        return assignment_from_locality(candidates[0], "automatic_name_match")
    if len(candidates) > 1:
        return unresolved("source locality name ambiguous", row["source_locality_name"])
    return unresolved("source locality not matched", row["source_locality_name"])


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.parse_args()

    ballot_rows = read_csv(BALLOT_ROWS)
    localities_by_code, localities_by_name = locality_indexes(read_csv(LOCALITIES))
    crosswalk = crosswalk_index(read_csv(CROSSWALK))
    row_overrides = row_override_index(read_csv(ROW_OVERRIDES))
    composite_components, expected_component_matches = composite_component_index(
        read_csv(COMPOSITE_BALLOT_COMPONENTS)
    )
    component_match_counts: Counter[str] = Counter()
    ballot_override_keys = {
        key
        for row in ballot_rows
        for key in row_override_lookup_keys(row)
    }
    missing_override_keys = set(row_overrides) - ballot_override_keys
    if missing_override_keys:
        raise ValueError(f"Ballot geography overrides did not match ballot rows: {sorted(missing_override_keys)}")

    output: list[dict[str, Any]] = []
    for row in ballot_rows:
        assignment = assign_row(
            row,
            localities_by_code,
            localities_by_name,
            crosswalk,
            row_overrides,
            composite_components,
            component_match_counts,
        )
        output.append(
            {
                "source_row_uid": row["source_row_uid"],
                "election": row["election"],
                "election_number": row["election_number"],
                "source_row_id": row["source_row_id"],
                "source_locality_code": row["source_locality_code"],
                "source_locality_name": row["source_locality_name"],
                "source_kalpi": row["source_kalpi"],
                "eligible_voters": row["eligible_voters"],
                "actual_voters": row["actual_voters"],
                **assignment,
            }
        )

    mismatched_component_ranges = {
        rule_id: {"expected": expected, "actual": component_match_counts[rule_id]}
        for rule_id, expected in expected_component_matches.items()
        if component_match_counts[rule_id] != expected
    }
    if mismatched_component_ranges:
        raise ValueError(
            "Composite component ranges did not match their reviewed ballot counts: "
            f"{mismatched_component_ranges}"
        )

    fields = [
        "source_row_uid",
        "election",
        "election_number",
        "source_row_id",
        "source_locality_code",
        "source_locality_name",
        "source_kalpi",
        "eligible_voters",
        "actual_voters",
        "assignment_method",
        "assignment_source",
        "target_geography_type",
        "target_locality_code",
        "target_locality_name",
        "target_stat_area_id",
        "custom_geography_id",
        "unresolved_reason",
    ]
    write_csv(OUT_DIR / "ballot_assignment_plan.csv", output, fields)

    summary_rows: list[dict[str, Any]] = []
    for election in sorted({row["election"] for row in output}, reverse=True):
        election_rows = [row for row in output if row["election"] == election]
        by_method = Counter(row["assignment_method"] for row in election_rows)
        summary_rows.append(
            {
                "election": election,
                "rows": len(election_rows),
                "actual_voters": sum(int_value(row["actual_voters"]) for row in election_rows),
                "single_stat_rows": by_method["single_stat_locality"],
                "historical_pending_rows": by_method["historical_stat_area_pending"],
                "custom_rows": by_method["custom_point_size_polygon"],
                "special_non_geographic_rows": by_method["special_non_geographic"],
                "envelope_rows": by_method["official_envelope"],
                "unresolved_rows": by_method["unresolved"],
                "unresolved_actual_voters": sum(
                    int_value(row["actual_voters"])
                    for row in election_rows
                    if row["assignment_method"] == "unresolved"
                ),
            }
        )
    write_csv(
        OUT_DIR / "assignment_plan_summary.csv",
        summary_rows,
        [
            "election",
            "rows",
            "actual_voters",
            "single_stat_rows",
            "historical_pending_rows",
            "custom_rows",
            "special_non_geographic_rows",
            "envelope_rows",
            "unresolved_rows",
            "unresolved_actual_voters",
        ],
    )
    write_json(OUT_DIR / "assignment_plan_summary.json", summary_rows)

    historical_pending = [
        row for row in output
        if row["assignment_method"] == "historical_stat_area_pending"
    ]
    write_csv(
        OUT_DIR / "historical_stat_area_pending_rows.csv",
        historical_pending,
        fields,
    )

    unresolved_rows = [row for row in output if row["assignment_method"] == "unresolved"]
    write_csv(OUT_DIR / "unresolved_assignment_rows.csv", unresolved_rows, fields)

    print(f"assignment_rows={len(output)}")
    print(f"historical_stat_area_pending_rows={len(historical_pending)}")
    print(f"unresolved_rows={len(unresolved_rows)}")
    for row in summary_rows:
        print(
            f"{row['election']}: single={row['single_stat_rows']} pending={row['historical_pending_rows']} "
            f"custom={row['custom_rows']} special={row['special_non_geographic_rows']} "
            f"envelope={row['envelope_rows']} unresolved={row['unresolved_rows']}"
        )


if __name__ == "__main__":
    main()
