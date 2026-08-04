from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

LOCAL_AUDIT_PYTHON = Path(__file__).resolve().parents[1] / ".local" / "python-audit"
if LOCAL_AUDIT_PYTHON.exists():
    sys.path.append(str(LOCAL_AUDIT_PYTHON))

import pandas as pd

from pipeline_common import (
    MANUAL_DIR,
    PROCESSED_DIR,
    RAW_DIR,
    int_value,
    write_csv,
    write_json,
)


SOURCE_DIR = RAW_DIR / "cbs_historical_geography"
WIDE_DIR = PROCESSED_DIR / "normalized" / "ballot_votes_wide"
ASSIGNMENT_PLAN = PROCESSED_DIR / "assignments" / "ballot_assignment_plan.csv"
SINGLE_STAT_FALLBACK_EXCLUSIONS = (
    MANUAL_DIR / "historical_single_stat_fallback_exclusions.csv"
)
OUT_DIR = PROCESSED_DIR / "assignments"

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

CROSSWALK_FILES = {
    "K17": "k17_ballot_to_stat1995.xls",
    "K18": "k18_ballot_to_stat2008.xlsx",
    "K19": "k19_ballot_to_stat2011.xlsx",
    "K20": "k20_ballot_to_stat2011.xlsx",
    "K21": "k21_ballot_to_stat2011.xlsx",
    "K22": "k22_ballot_to_stat2011.xlsx",
    "K23": "k23_ballot_to_stat2011.xlsx",
    "K24": "k24_ballot_to_stat2011.xlsx",
    "K25": "k25_ballot_to_stat2011.xlsx",
}

NON_GEOGRAPHIC_METHODS = {
    "official_envelope",
    "special_non_geographic",
    "custom_point_size_polygon",
}
HISTORICALLY_MAPPABLE_CUSTOM_GEOGRAPHIES = {
    "custom:tribal_negev",
    "custom:hebron",
}


def normalize_code(value: Any) -> str:
    text = str(value or "").strip()
    if not text or text.lower() == "nan":
        return ""
    try:
        return str(int(Decimal(text)))
    except (InvalidOperation, ValueError):
        digits = "".join(character for character in text if character.isdigit())
        return str(int(digits)) if digits else ""


def split_codes(value: Any) -> list[str]:
    output: list[str] = []
    for part in str(value or "").split("|"):
        code = normalize_code(part)
        if code and code not in output:
            output.append(code)
    return output


def normalize_name(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = "".join(
        character for character in text if unicodedata.category(character) != "Cf"
    )
    text = text.replace("־", "-").replace("–", "-").replace("—", "-")
    text = re.sub(r"\s*-\s*", "-", text)
    text = re.sub(r"[^\w\- ]", "", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def read_single_stat_fallback_exclusions() -> list[dict[str, Any]]:
    frame = pd.read_csv(
        SINGLE_STAT_FALLBACK_EXCLUSIONS,
        dtype=str,
        encoding="utf-8-sig",
    ).fillna("")
    output: list[dict[str, Any]] = []
    for index, row in frame.iterrows():
        election = str(row["election"]).strip()
        locality_code = normalize_code(row["source_locality_code"])
        locality_name_key = normalize_name(row["source_locality_name"])
        expected_rows = int_value(row["expected_rows"])
        if not election or not expected_rows or (
            not locality_code and not locality_name_key
        ):
            raise ValueError(
                "Invalid historical single-stat fallback exclusion at row "
                f"{index + 2}"
            )
        output.append(
            {
                **row.to_dict(),
                "_rule_id": f"{election}:{locality_code}:{locality_name_key}",
                "election": election,
                "source_locality_code": locality_code,
                "source_locality_name_key": locality_name_key,
                "expected_rows": expected_rows,
            }
        )
    return output


def ballot_base(election: str, value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        number = Decimal(text)
    except InvalidOperation:
        return text.split(".", 1)[0]
    if election == "K17":
        return str(int(number) // 10)
    return str(int(number))


def read_crosswalk(election: str) -> pd.DataFrame:
    path = SOURCE_DIR / CROSSWALK_FILES[election]
    if not path.exists():
        raise FileNotFoundError(f"Missing official CBS crosswalk: {path}")
    raw = pd.read_excel(path, sheet_name=-1, header=10, dtype=str).fillna("")

    if election == "K17":
        raw.columns = ["locality_code", "locality_name", "ballot_number", "stat_area_number"]
    elif election == "K18":
        raw.columns = ["stat_area_number", "ballot_number", "locality_code", "locality_name"]
    else:
        raw.columns = [
            "locality_code",
            "locality_name",
            "ballot_number",
            "stat_area_number",
            "source_yishuv_stat",
        ]

    raw["locality_code"] = raw["locality_code"].map(normalize_code)
    raw["ballot_number"] = raw["ballot_number"].map(normalize_code)
    raw["stat_area_number"] = raw["stat_area_number"].map(normalize_code)
    raw = raw[
        (raw["locality_code"] != "")
        & (raw["ballot_number"] != "")
        & (raw["stat_area_number"] != "")
    ].copy()
    raw["locality_name"] = raw["locality_name"].astype(str).str.strip()
    raw["locality_name_key"] = raw["locality_name"].map(normalize_name)
    vintage = ELECTION_VINTAGES[election]
    multiplier = 1000 if vintage == 1995 else 10000
    derived_yishuv_stat = (
        raw["locality_code"].astype(int) * multiplier
        + raw["stat_area_number"].astype(int)
    )
    if "source_yishuv_stat" in raw:
        documented = pd.to_numeric(raw["source_yishuv_stat"], errors="coerce")
        # A ballot may be assigned across a locality boundary. In that case the
        # workbook's combined statistical-area ID is the target and is authoritative.
        raw["yishuv_stat"] = documented.fillna(derived_yishuv_stat).astype("int64")
    else:
        raw["yishuv_stat"] = derived_yishuv_stat
    raw["election"] = election
    raw["stat_area_vintage"] = vintage
    raw["stat_area_id"] = raw["yishuv_stat"].map(
        lambda value: f"stat{vintage}:{value}"
    )
    raw["crosswalk_source"] = path.name

    key_columns = ["locality_code", "ballot_number"]
    conflicts = raw.groupby(key_columns)["stat_area_id"].nunique()
    if (conflicts > 1).any():
        raise ValueError(f"{election} crosswalk maps one ballot key to multiple areas")
    raw = raw.drop_duplicates(key_columns, keep="first")
    return raw[
        [
            "election",
            "stat_area_vintage",
            "locality_code",
            "locality_name",
            "locality_name_key",
            "ballot_number",
            "stat_area_number",
            "yishuv_stat",
            "stat_area_id",
            "crosswalk_source",
        ]
    ]


def read_metadata(vintage: int) -> pd.DataFrame:
    path = PROCESSED_DIR / "geographies" / f"statistical_areas_{vintage}.metadata.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"Missing historical geography metadata; run build_historical_geographies.py: {path}"
        )
    metadata = pd.read_csv(path, dtype=str, encoding="utf-8-sig").fillna("")
    metadata["locality_code"] = metadata["locality_code"].map(normalize_code)
    metadata["locality_name_key"] = metadata["locality_name_he"].map(normalize_name)
    return metadata


def unique_lookup(rows: pd.DataFrame, keys: list[str]) -> dict[tuple[str, ...], dict[str, str]]:
    output: dict[tuple[str, ...], dict[str, str]] = {}
    for key_values, group in rows.groupby(keys, dropna=False):
        key = key_values if isinstance(key_values, tuple) else (key_values,)
        if group["stat_area_id"].nunique() == 1:
            output[tuple(str(value) for value in key)] = group.iloc[0].to_dict()
    return output


def base_output(row: pd.Series, vintage: int, base: str) -> dict[str, Any]:
    return {
        "source_row_uid": row["source_row_uid"],
        "election": row["election"],
        "source_locality_code": row["source_locality_code"],
        "source_locality_name": row["source_locality_name"],
        "source_kalpi": row["source_kalpi"],
        "ballot_base": base,
        "eligible_voters": int_value(row["eligible_voters"]),
        "actual_voters": int_value(row["actual_voters"]),
        "stat_area_vintage": vintage,
    }


def assigned_output(
    row: pd.Series,
    vintage: int,
    base: str,
    stat: dict[str, Any],
    status: str,
    method: str,
    source: str,
) -> dict[str, Any]:
    return {
        **base_output(row, vintage, base),
        "stat_area_id": stat["stat_area_id"],
        "yishuv_stat": normalize_code(stat["yishuv_stat"]),
        "stat_area_number": normalize_code(stat["stat_area_number"]),
        "historical_locality_code": normalize_code(stat["locality_code"]),
        "historical_locality_name": stat.get(
            "locality_name_he", stat.get("locality_name", "")
        ),
        "historical_assignment_status": status,
        "historical_assignment_method": method,
        "historical_assignment_source": source,
        "is_historical_stat_mapped": True,
        "unresolved_reason": "",
    }


def unresolved_output(
    row: pd.Series,
    vintage: int,
    base: str,
    status: str,
    reason: str,
) -> dict[str, Any]:
    return {
        **base_output(row, vintage, base),
        "stat_area_id": "",
        "yishuv_stat": "",
        "stat_area_number": "",
        "historical_locality_code": "",
        "historical_locality_name": "",
        "historical_assignment_status": status,
        "historical_assignment_method": "",
        "historical_assignment_source": "",
        "is_historical_stat_mapped": False,
        "unresolved_reason": reason,
    }


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.parse_args()

    plan = pd.read_csv(ASSIGNMENT_PLAN, dtype=str, encoding="utf-8-sig").fillna("")
    plan = plan[
        [
            "source_row_uid",
            "target_locality_code",
            "assignment_method",
            "assignment_source",
            "target_geography_type",
            "custom_geography_id",
        ]
    ]
    single_stat_fallback_exclusions = read_single_stat_fallback_exclusions()
    exclusion_match_counts: Counter[str] = Counter()

    crosswalks = {election: read_crosswalk(election) for election in ELECTION_VINTAGES}
    for election, crosswalk in crosswalks.items():
        vintage = ELECTION_VINTAGES[election]
        alias_path = (
            PROCESSED_DIR
            / "geographies"
            / f"statistical_areas_{vintage}.aliases.csv"
        )
        aliases = pd.read_csv(
            alias_path, dtype=str, encoding="utf-8-sig"
        ).fillna("")
        aliases_by_source = aliases.set_index("source_stat_area_id").to_dict("index")
        crosswalk["source_stat_area_id"] = crosswalk["stat_area_id"]
        crosswalk["source_stat_area_number"] = crosswalk["stat_area_number"]
        crosswalk["stat_area_id"] = crosswalk["source_stat_area_id"].map(
            lambda value: aliases_by_source.get(value, {}).get(
                "canonical_stat_area_id", value
            )
        )
        crosswalk["yishuv_stat"] = crosswalk["source_stat_area_id"].map(
            lambda value: aliases_by_source.get(value, {}).get(
                "canonical_yishuv_stat", normalize_code(value.split(":", 1)[-1])
            )
        )
        crosswalk["stat_area_number"] = [
            aliases_by_source.get(source_id, {}).get(
                "canonical_stat_area_number", source_number
            )
            for source_id, source_number in zip(
                crosswalk["source_stat_area_id"],
                crosswalk["source_stat_area_number"],
            )
        ]
    all_crosswalk_rows = pd.concat(crosswalks.values(), ignore_index=True)
    write_csv(
        OUT_DIR / "historical_ballot_crosswalk.csv",
        all_crosswalk_rows.drop(columns="locality_name_key").to_dict("records"),
        [column for column in all_crosswalk_rows.columns if column != "locality_name_key"],
    )

    output: list[dict[str, Any]] = []
    summary: list[dict[str, Any]] = []
    for election, vintage in ELECTION_VINTAGES.items():
        wide = pd.read_csv(
            WIDE_DIR / f"{election.lower()}_ballot_votes.csv",
            dtype=str,
            encoding="utf-8-sig",
        ).fillna("")
        wide = wide.merge(plan, on="source_row_uid", how="left", validate="one_to_one")
        crosswalk = crosswalks[election]
        metadata = read_metadata(vintage)
        metadata_by_id = {
            row["stat_area_id"]: row for row in metadata.to_dict("records")
        }
        crosswalk_by_code = unique_lookup(
            crosswalk, ["locality_code", "ballot_number"]
        )
        crosswalk_by_name = unique_lookup(
            crosswalk, ["locality_name_key", "ballot_number"]
        )
        crosswalk_locality_codes = set(crosswalk["locality_code"])
        crosswalk_locality_names = set(crosswalk["locality_name_key"])

        stats_by_code = {
            code: group.to_dict("records")
            for code, group in metadata.groupby("locality_code")
        }
        stats_by_name: dict[str, list[dict[str, str]]] = {}
        for name, group in metadata.groupby("locality_name_key"):
            if group["locality_code"].nunique() == 1:
                stats_by_name[name] = group.to_dict("records")
        metadata_locality_names = set(metadata["locality_name_key"])

        election_output: list[dict[str, Any]] = []
        for _, row in wide.iterrows():
            base = ballot_base(election, row["source_kalpi"])
            method = row.get("assignment_method", "")
            custom_has_historical_geometry = (
                vintage == 2011
                and method == "custom_point_size_polygon"
                and row.get("custom_geography_id", "")
                in HISTORICALLY_MAPPABLE_CUSTOM_GEOGRAPHIES
            )
            if (
                method in NON_GEOGRAPHIC_METHODS
                and not custom_has_historical_geometry
            ) or str(row.get("is_envelope", "")).lower() in {
                "true",
                "1",
                "yes",
            }:
                election_output.append(
                    unresolved_output(
                        row,
                        vintage,
                        base,
                        "not_applicable_non_geographic",
                        "envelope, special, or custom-geography row",
                    )
                )
                continue

            source_codes = split_codes(row.get("source_locality_code", ""))
            target_codes = split_codes(row.get("target_locality_code", ""))
            source_name_key = normalize_name(row.get("source_locality_name", ""))

            # Composite result units use the reviewed component identity. Otherwise,
            # a historical source locality takes precedence over a modern merger or
            # rename target. This prevents identical ballot numbers in the successor
            # municipality from creating a false historical crosswalk match.
            if row.get("assignment_source", "") == "reviewed_composite_component_evidence":
                candidate_codes = target_codes
            else:
                source_identity_exists = any(
                    code in stats_by_code or code in crosswalk_locality_codes
                    for code in source_codes
                ) or source_name_key in (
                    metadata_locality_names | crosswalk_locality_names
                )
                candidate_codes = list(source_codes)
                if not source_identity_exists:
                    for code in target_codes:
                        if code not in candidate_codes:
                            candidate_codes.append(code)

            crosswalk_match: dict[str, Any] | None = None
            match_method = ""
            for code in candidate_codes:
                crosswalk_match = crosswalk_by_code.get((code, base))
                if crosswalk_match:
                    match_method = "official_cbs_ballot_crosswalk"
                    break
            if not crosswalk_match and source_name_key:
                crosswalk_match = crosswalk_by_name.get((source_name_key, base))
                if crosswalk_match:
                    match_method = "official_cbs_ballot_crosswalk_name_fallback"

            if crosswalk_match:
                stat = metadata_by_id.get(crosswalk_match["stat_area_id"])
                if stat:
                    if election == "K17":
                        match_method += "_k17_tenths_encoding"
                    elif "." in str(row["source_kalpi"]):
                        match_method += "_base_ballot_subdivision"
                    election_output.append(
                        assigned_output(
                            row,
                            vintage,
                            base,
                            stat,
                            "official_crosswalk_assigned",
                            match_method,
                            crosswalk_match["crosswalk_source"],
                        )
                    )
                else:
                    election_output.append(
                        unresolved_output(
                            row,
                            vintage,
                            base,
                            "crosswalk_area_missing_geometry",
                            f"official crosswalk area {crosswalk_match['stat_area_id']} is absent from the CBS geometry",
                        )
                    )
                continue

            fallback_exclusion = next(
                (
                    exclusion
                    for exclusion in single_stat_fallback_exclusions
                    if exclusion["election"] == election
                    and (
                        not exclusion["source_locality_code"]
                        or exclusion["source_locality_code"] in candidate_codes
                    )
                    and (
                        not exclusion["source_locality_name_key"]
                        or exclusion["source_locality_name_key"] == source_name_key
                    )
                ),
                None,
            )
            if fallback_exclusion:
                exclusion_match_counts[fallback_exclusion["_rule_id"]] += 1
                excluded = unresolved_output(
                    row,
                    vintage,
                    base,
                    "no_direct_historical_assignment",
                    fallback_exclusion["note"],
                )
                excluded["historical_assignment_method"] = (
                    "reviewed_single_stat_fallback_exclusion"
                )
                excluded["historical_assignment_source"] = (
                    "data/manual/historical_single_stat_fallback_exclusions.csv"
                )
                election_output.append(excluded)
                continue

            single_stat: dict[str, Any] | None = None
            single_method = ""
            for code in candidate_codes:
                candidates = stats_by_code.get(code, [])
                if len(candidates) == 1:
                    single_stat = candidates[0]
                    single_method = "single_historical_stat_locality"
                    break
            if not single_stat and source_name_key:
                candidates = stats_by_name.get(source_name_key, [])
                if len(candidates) == 1:
                    single_stat = candidates[0]
                    single_method = "single_historical_stat_locality_name_fallback"
            if single_stat:
                single_source = f"statistical_areas_{vintage}.metadata.csv"
                if row.get("assignment_source", "") == "reviewed_composite_component_evidence":
                    single_source += ";data/manual/historical_composite_ballot_components.csv"
                election_output.append(
                    assigned_output(
                        row,
                        vintage,
                        base,
                        single_stat,
                        "single_historical_stat_assigned",
                        single_method,
                        single_source,
                    )
                )
            else:
                election_output.append(
                    unresolved_output(
                        row,
                        vintage,
                        base,
                        "no_direct_historical_assignment",
                        "no official ballot crosswalk row and locality is not uniquely one historical statistical area",
                    )
                )

        output.extend(election_output)
        statuses = Counter(row["historical_assignment_status"] for row in election_output)
        mapped = [row for row in election_output if row["is_historical_stat_mapped"]]
        geographic = [
            row
            for row in election_output
            if row["historical_assignment_status"] != "not_applicable_non_geographic"
        ]
        summary.append(
            {
                "election": election,
                "stat_area_vintage": vintage,
                "rows": len(election_output),
                "geographic_rows": len(geographic),
                "official_crosswalk_rows": statuses["official_crosswalk_assigned"],
                "single_historical_stat_rows": statuses[
                    "single_historical_stat_assigned"
                ],
                "mapped_rows": len(mapped),
                "mapped_actual_voters": sum(row["actual_voters"] for row in mapped),
                "unresolved_rows": statuses["no_direct_historical_assignment"],
                "missing_geometry_rows": statuses["crosswalk_area_missing_geometry"],
                "non_geographic_rows": statuses["not_applicable_non_geographic"],
            }
        )

    for exclusion in single_stat_fallback_exclusions:
        observed = exclusion_match_counts[exclusion["_rule_id"]]
        expected = exclusion["expected_rows"]
        if observed != expected:
            raise ValueError(
                "Historical single-stat fallback exclusion count changed for "
                f"{exclusion['_rule_id']}: expected {expected}, observed {observed}"
            )

    fields = [
        "source_row_uid",
        "election",
        "source_locality_code",
        "source_locality_name",
        "source_kalpi",
        "ballot_base",
        "eligible_voters",
        "actual_voters",
        "stat_area_vintage",
        "stat_area_id",
        "yishuv_stat",
        "stat_area_number",
        "historical_locality_code",
        "historical_locality_name",
        "historical_assignment_status",
        "historical_assignment_method",
        "historical_assignment_source",
        "is_historical_stat_mapped",
        "unresolved_reason",
    ]
    source_uids = [row["source_row_uid"] for row in output]
    duplicate_uids = sorted(
        uid for uid, count in Counter(source_uids).items() if count > 1
    )
    if duplicate_uids:
        raise ValueError(
            f"Historical assignments contain duplicate source rows: {duplicate_uids[:10]}"
        )
    write_csv(OUT_DIR / "historical_ballot_assignments.csv", output, fields)
    write_csv(
        OUT_DIR / "historical_ballot_assignment_summary.csv",
        summary,
        list(summary[0].keys()),
    )
    write_json(OUT_DIR / "historical_ballot_assignment_summary.json", summary)
    for row in summary:
        print(
            f"{row['election']}: vintage={row['stat_area_vintage']} "
            f"crosswalk={row['official_crosswalk_rows']} single={row['single_historical_stat_rows']} "
            f"mapped={row['mapped_rows']}/{row['geographic_rows']} unresolved={row['unresolved_rows']} "
            f"missing_geometry={row['missing_geometry_rows']}"
        )


if __name__ == "__main__":
    main()
