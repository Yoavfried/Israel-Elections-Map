from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from functools import cache
from pathlib import Path
from typing import Any

from pipeline_common import (
    MANUAL_DIR,
    PROCESSED_DIR,
    int_value,
    normalize_spaces,
    write_csv,
    write_json,
)


ASSIGNMENT_PLAN = PROCESSED_DIR / "assignments" / "ballot_assignment_plan.csv"
HISTORICAL_ASSIGNMENTS = (
    PROCESSED_DIR / "assignments" / "historical_ballot_assignments.csv"
)
STAT_AREA_METADATA = (
    PROCESSED_DIR / "geographies" / "statistical_areas_2022.metadata.csv"
)
LOCALITIES_2022_METADATA = (
    PROCESSED_DIR / "geographies" / "localities_2022.metadata.csv"
)
HISTORICAL_STAT_AREA_METADATA = {
    vintage: (
        PROCESSED_DIR
        / "geographies"
        / f"statistical_areas_{vintage}.metadata.csv"
    )
    for vintage in (1995, 2008, 2011)
}
HISTORICAL_STAT_AREA_OVERRIDES = (
    MANUAL_DIR / "historical_stat_area_overrides.csv"
)
CROSS_ELECTION_STAT_AREA_REVIEWS = (
    MANUAL_DIR / "cross_election_stat_area_reviews.csv"
)
ARCGIS_RECONSTRUCTION_CANDIDATES = (
    PROCESSED_DIR / "audits" / "arcgis_assignment_reconstruction_candidates.csv"
)
ARCGIS_RECONSTRUCTION_LOCALITIES = (
    PROCESSED_DIR / "audits" / "arcgis_assignment_reconstruction_localities.csv"
)
ARCGIS_RECONSTRUCTION_REVIEWS = (
    MANUAL_DIR / "arcgis_assignment_reconstruction_reviews.csv"
)
STABLE_BALLOT_CANDIDATES = (
    PROCESSED_DIR / "audits" / "stable_ballot_assignment_candidates.csv"
)
STABLE_BALLOT_SUMMARY = (
    PROCESSED_DIR / "audits" / "stable_ballot_assignment_summary.json"
)
STABLE_BALLOT_REVIEWS = MANUAL_DIR / "stable_ballot_assignment_reviews.csv"
K23_CEC_AGS_CANDIDATES = (
    PROCESSED_DIR / "audits" / "k23_cec_ags_assignment_candidates.csv"
)
K23_CEC_AGS_SUMMARY = (
    PROCESSED_DIR / "audits" / "k23_cec_ags_assignment_summary.json"
)
OUT_DIR = PROCESSED_DIR / "assignments"
COMPOSITE_LOCALITIES = MANUAL_DIR / "composite_localities.csv"
HISTORICAL_PENDING_STATUSES = {
    "no_direct_historical_assignment",
    "crosswalk_area_missing_geometry",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def normalize_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def reconstruction_fingerprint(rows: list[dict[str, str]]) -> str:
    payload = "\n".join(
        f"{row['source_row_uid']}|{row['candidate_stat_area_id']}"
        for row in sorted(rows, key=lambda item: item["source_row_uid"])
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def normalize_locality_code(value: Any) -> str:
    text = str(value or "").strip()
    if not text or text.lower() == "nan":
        return ""
    try:
        number = float(text)
    except ValueError:
        digits = "".join(char for char in text if char.isdigit())
        return str(int(digits)) if digits else ""
    if number.is_integer():
        return str(int(number))
    digits = "".join(char for char in text if char.isdigit())
    return str(int(digits)) if digits else ""


def assignment_evidence_metadata(row: dict[str, Any]) -> dict[str, Any]:
    method = str(row.get("final_assignment_method", ""))
    status = str(row.get("geography_assignment_status", ""))
    if not row.get("stat_area_id") and status in {
        "no_direct_historical_assignment",
        "crosswalk_area_missing_geometry",
        "unresolved",
        "missing_stat_area_metadata",
    }:
        evidence_class = "unresolved"
        confidence = "unresolved"
        synthetic = False
    elif method.startswith("official_cbs_ballot_crosswalk"):
        evidence_class = "official_direct_crosswalk"
        confidence = "authoritative"
        synthetic = False
    elif method == "official_cec_k23_ags":
        evidence_class = "official_direct_ags"
        confidence = "authoritative"
        synthetic = False
    elif method.startswith("cbs_stable_ballot_"):
        evidence_class = "official_stability_inferred_link"
        confidence = "high"
        synthetic = True
    elif method.startswith("arcgis_residual_partition_tier_"):
        tier = method.rsplit("_", 1)[-1]
        evidence_class = "reviewed_exact_aggregate_inferred_link"
        confidence = "moderate" if tier == "c" else "high"
        synthetic = True
    elif method == "reviewed_historical_stat_area_override":
        evidence_class = "reviewed_cross_election_inferred_link"
        confidence = "high"
        synthetic = True
    elif method == "reviewed_cross_election_stat_area_assignment":
        evidence_class = "reviewed_polling_register_continuity_inferred_link"
        confidence = "high"
        synthetic = True
    elif method.startswith("validated_k26_register_"):
        evidence_class = "official_polling_register_inferred_link"
        confidence = "high"
        synthetic = True
    elif method in {"single_historical_stat_locality", "single_stat_locality"}:
        evidence_class = "deterministic_single_area_locality"
        confidence = "high"
        synthetic = False
    elif method == "custom_point_size_polygon":
        evidence_class = "reviewed_custom_geography"
        confidence = "high"
        synthetic = False
    elif status in {"official_envelope", "special_non_geographic"}:
        evidence_class = "non_geographic"
        confidence = "not_applicable"
        synthetic = False
    else:
        evidence_class = "unresolved"
        confidence = "unresolved"
        synthetic = False
    return {
        "assignment_evidence_class": evidence_class,
        "assignment_confidence": confidence,
        "assignment_is_synthetic_link": synthetic,
    }


def split_locality_codes(value: Any) -> list[str]:
    codes: list[str] = []
    for part in str(value or "").split("|"):
        code = normalize_locality_code(part)
        if code and code not in codes:
            codes.append(code)
    return codes


@cache
def load_current_locality_name_index() -> dict[str, dict[str, str]]:
    rows = read_csv(LOCALITIES_2022_METADATA)
    index: dict[str, dict[str, str]] = {}
    ambiguous: set[str] = set()
    for row in rows:
        key = normalize_spaces(row.get("locality_name_he", ""))
        locality_code = normalize_locality_code(row.get("locality_code", ""))
        if not key or not locality_code:
            continue
        if key in index and index[key]["locality_code"] != locality_code:
            ambiguous.add(key)
            continue
        index[key] = {
            "locality_code": locality_code,
            "locality_name_he": row.get("locality_name_he", ""),
        }
    for key in ambiguous:
        index.pop(key, None)
    return index


@cache
def load_composite_locality_index() -> dict[tuple[str, str], dict[str, str]]:
    rows = read_csv(COMPOSITE_LOCALITIES)
    if not rows:
        raise FileNotFoundError(
            f"Missing or empty reviewed composite-locality table: {COMPOSITE_LOCALITIES}"
        )

    index: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        composite_id = row.get("composite_locality_id", "").strip()
        source_name = normalize_spaces(row.get("source_locality_name", ""))
        elections = [
            value.strip()
            for value in row.get("elections", "").split("|")
            if value.strip()
        ]
        if not composite_id or not source_name or not elections:
            raise ValueError(f"Invalid composite-locality row: {row}")
        for election in elections:
            key = (election, source_name)
            if key in index:
                raise ValueError(
                    f"Duplicate composite-locality matcher: {election} / {source_name}"
                )
            index[key] = row
    return index


def locality_assignment(row: dict[str, str]) -> dict[str, Any]:
    method = row.get("assignment_method", "")
    if method == "official_envelope":
        return {
            "locality_assignment_status": "official_envelope",
            "locality_geography_type": "envelope",
            "locality_geography_id": "envelope:official",
            "locality_result_code": "",
            "locality_result_name": "\u05de\u05e2\u05d8\u05e4\u05d5\u05ea \u05d7\u05d9\u05e6\u05d5\u05e0\u05d9\u05d5\u05ea",
            "is_locality_mapped": False,
        }
    if method == "special_non_geographic":
        return {
            "locality_assignment_status": "special_non_geographic",
            "locality_geography_type": "non_geographic",
            "locality_geography_id": "",
            "locality_result_code": "",
            "locality_result_name": row.get("target_locality_name", ""),
            "is_locality_mapped": False,
        }
    if method == "custom_point_size_polygon":
        return {
            "locality_assignment_status": "custom_geography_assigned",
            "locality_geography_type": "custom_geography",
            "locality_geography_id": row.get("custom_geography_id", ""),
            "locality_result_code": "",
            "locality_result_name": row.get("target_locality_name", ""),
            "is_locality_mapped": True,
        }

    composite = load_composite_locality_index().get(
        (
            row.get("election", ""),
            normalize_spaces(row.get("source_locality_name", "")),
        )
    )
    if composite:
        return {
            "locality_assignment_status": "composite_locality_assigned",
            "locality_geography_type": "composite_locality",
            "locality_geography_id": composite["composite_locality_id"],
            "locality_result_code": row.get("source_locality_code", ""),
            "locality_result_name": composite["name_he"],
            "is_locality_mapped": True,
        }

    if row.get("assignment_source", "") == "reviewed_composite_component_evidence":
        current_locality = load_current_locality_name_index().get(
            normalize_spaces(row.get("source_locality_name", ""))
        )
        if current_locality:
            locality_code = current_locality["locality_code"]
            return {
                "locality_assignment_status": "source_locality_name_assigned",
                "locality_geography_type": "locality",
                "locality_geography_id": f"loc:{locality_code}",
                "locality_result_code": locality_code,
                "locality_result_name": current_locality["locality_name_he"],
                "is_locality_mapped": True,
            }

    target_codes = split_locality_codes(row.get("target_locality_code", ""))
    if len(target_codes) == 1:
        target_code = target_codes[0]
        return {
            "locality_assignment_status": "current_locality_assigned",
            "locality_geography_type": "locality",
            "locality_geography_id": f"loc:{target_code}",
            "locality_result_code": target_code,
            "locality_result_name": row.get("target_locality_name", ""),
            "is_locality_mapped": True,
        }

    return {
        "locality_assignment_status": "unresolved",
        "locality_geography_type": "unmapped",
        "locality_geography_id": "",
        "locality_result_code": "",
        "locality_result_name": row.get("target_locality_name", ""),
        "is_locality_mapped": False,
    }


def base_output(row: dict[str, str]) -> dict[str, Any]:
    return {
        "source_row_uid": row["source_row_uid"],
        "election": row["election"],
        "election_number": row["election_number"],
        "source_row_id": row["source_row_id"],
        "source_locality_code": row["source_locality_code"],
        "source_locality_name": row["source_locality_name"],
        "source_kalpi": row["source_kalpi"],
        "eligible_voters": row["eligible_voters"],
        "actual_voters": row["actual_voters"],
        "assignment_method": row["assignment_method"],
        "assignment_source": row["assignment_source"],
        **locality_assignment(row),
    }


def mapped_assignment(
    row: dict[str, str],
    stat_area_id: str,
    vintage: int,
    yishuv_stat: Any,
    stat_area_number: Any,
    locality_code: Any,
    locality_name: str,
    status: str,
    method: str,
    source: str,
) -> dict[str, Any]:
    return {
        **base_output(row),
        "geography_assignment_status": status,
        "geography_type": "statistical_area",
        "geography_id": stat_area_id,
        "stat_area_id": stat_area_id,
        "stat_area_vintage": vintage,
        "stat_area_yishuv_stat": yishuv_stat,
        "stat_area_number": stat_area_number,
        "stat_area_yishuv_stat_2022": yishuv_stat if vintage == 2022 else "",
        "stat_area_stat_2022": stat_area_number if vintage == 2022 else "",
        "locality_id": f"loc:{locality_code}",
        "locality_code": locality_code,
        "locality_name": locality_name,
        "custom_geography_id": "",
        "is_mapped": True,
        "is_geographic": True,
        "final_assignment_method": method,
        "final_assignment_source": source,
        "unresolved_reason": "",
    }


def historical_stat_assignment(
    row: dict[str, str], historical: dict[str, str]
) -> dict[str, Any]:
    return mapped_assignment(
        row=row,
        stat_area_id=historical["stat_area_id"],
        vintage=int_value(historical["stat_area_vintage"]),
        yishuv_stat=historical["yishuv_stat"],
        stat_area_number=historical["stat_area_number"],
        locality_code=historical["historical_locality_code"],
        locality_name=historical["historical_locality_name"],
        status=historical["historical_assignment_status"],
        method=historical["historical_assignment_method"],
        source=historical["historical_assignment_source"],
    )


def historical_override_assignment(
    row: dict[str, str], override: dict[str, str], stat: dict[str, str]
) -> dict[str, Any]:
    return mapped_assignment(
        row=row,
        stat_area_id=stat["stat_area_id"],
        vintage=int_value(stat["stat_area_vintage"]),
        yishuv_stat=stat["yishuv_stat"],
        stat_area_number=stat["stat_area_number"],
        locality_code=stat["locality_code"],
        locality_name=stat["locality_name_he"],
        status="reviewed_historical_override_assigned",
        method="reviewed_historical_stat_area_override",
        source=(
            "data/manual/historical_stat_area_overrides.csv;evidence="
            f"{override['evidence_sources']}"
        ),
    )


def reviewed_cross_election_assignment(
    row: dict[str, str], review: dict[str, str], stat: dict[str, str]
) -> dict[str, Any]:
    return mapped_assignment(
        row=row,
        stat_area_id=stat["stat_area_id"],
        vintage=int_value(stat["stat_area_vintage"]),
        yishuv_stat=stat["yishuv_stat"],
        stat_area_number=stat["stat_area_number"],
        locality_code=stat["locality_code"],
        locality_name=stat["locality_name_he"],
        status="reviewed_cross_election_assigned",
        method="reviewed_cross_election_stat_area_assignment",
        source=(
            "data/manual/cross_election_stat_area_reviews.csv;evidence="
            f"{review['evidence_sources']}"
        ),
    )


def arcgis_reconstructed_assignment(
    row: dict[str, str],
    candidate: dict[str, str],
    stat: dict[str, str],
) -> dict[str, Any]:
    if candidate.get("source_granularity") != "detailed_statistical_area":
        raise ValueError(
            "ArcGIS reconstruction is not a detailed statistical-area target: "
            f"{candidate.get('source_row_uid', '')}"
        )
    evidence_tier = normalize_spaces(candidate.get("evidence_tier", "")).lower()
    if evidence_tier not in {"a", "b", "c"}:
        raise ValueError(
            f"Unsupported ArcGIS reconstruction tier: {candidate.get('evidence_tier', '')}"
        )
    return mapped_assignment(
        row=row,
        stat_area_id=stat["stat_area_id"],
        vintage=int_value(stat["stat_area_vintage"]),
        yishuv_stat=stat["yishuv_stat"],
        stat_area_number=stat["stat_area_number"],
        locality_code=stat["locality_code"],
        locality_name=stat["locality_name_he"],
        status="arcgis_reconstructed_assigned",
        method=f"arcgis_residual_partition_tier_{evidence_tier}",
        source=(
            f"{candidate['source']};review="
            "data/manual/arcgis_assignment_reconstruction_reviews.csv"
        ),
    )


def stable_ballot_assignment(
    row: dict[str, str],
    candidate: dict[str, str],
    stat: dict[str, str],
) -> dict[str, Any]:
    method = normalize_spaces(candidate.get("evidence_method", ""))
    if not method.startswith("cbs_stable_ballot_"):
        raise ValueError(f"Unsupported stable-ballot method: {method}")
    sources = normalize_spaces(candidate.get("source_workbooks", ""))
    return mapped_assignment(
        row=row,
        stat_area_id=stat["stat_area_id"],
        vintage=int_value(stat["stat_area_vintage"]),
        yishuv_stat=stat["yishuv_stat"],
        stat_area_number=stat["stat_area_number"],
        locality_code=stat["locality_code"],
        locality_name=stat["locality_name_he"],
        status="cbs_stable_ballot_assigned",
        method=method,
        source=(
            f"data/raw/cbs_historical_geography/{sources};"
            "audit=data/processed/audits/stable_ballot_assignment_candidates.csv"
        ),
    )


def k23_cec_ags_assignment(
    row: dict[str, str],
    candidate: dict[str, str],
    stat: dict[str, str],
) -> dict[str, Any]:
    if candidate.get("evidence_method") != "official_cec_k23_ags":
        raise ValueError(
            f"Unsupported K23 CEC AGS method: {candidate.get('evidence_method', '')}"
        )
    return mapped_assignment(
        row=row,
        stat_area_id=stat["stat_area_id"],
        vintage=int_value(stat["stat_area_vintage"]),
        yishuv_stat=stat["yishuv_stat"],
        stat_area_number=stat["stat_area_number"],
        locality_code=stat["locality_code"],
        locality_name=stat["locality_name_he"],
        status="official_cec_ags_assigned",
        method="official_cec_k23_ags",
        source=(
            f"data/raw/{candidate['source_workbook']};"
            "audit=data/processed/audits/k23_cec_ags_assignment_candidates.csv"
        ),
    )


def current_stat_assignment(
    row: dict[str, str], stat: dict[str, str]
) -> dict[str, Any]:
    return mapped_assignment(
        row=row,
        stat_area_id=stat["stat_area_id"],
        vintage=2022,
        yishuv_stat=stat["yishuv_stat_2022"],
        stat_area_number=stat["stat_2022"],
        locality_code=stat["locality_code"],
        locality_name=stat["locality_name_he"],
        status="single_stat_assigned",
        method="single_stat_locality",
        source=row["assignment_source"],
    )


def custom_assignment(row: dict[str, str]) -> dict[str, Any]:
    return {
        **base_output(row),
        "geography_assignment_status": "custom_geography_assigned",
        "geography_type": "custom_geography",
        "geography_id": row["custom_geography_id"],
        "stat_area_id": "",
        "stat_area_vintage": "",
        "stat_area_yishuv_stat": "",
        "stat_area_number": "",
        "stat_area_yishuv_stat_2022": "",
        "stat_area_stat_2022": "",
        "locality_id": "",
        "locality_code": "",
        "locality_name": row["target_locality_name"],
        "custom_geography_id": row["custom_geography_id"],
        "is_mapped": True,
        "is_geographic": True,
        "final_assignment_method": "custom_point_size_polygon",
        "final_assignment_source": row["assignment_source"],
        "unresolved_reason": "",
    }


def unresolved(row: dict[str, str], status: str, reason: str) -> dict[str, Any]:
    return {
        **base_output(row),
        "geography_assignment_status": status,
        "geography_type": row["target_geography_type"] or "unmapped",
        "geography_id": row["custom_geography_id"],
        "stat_area_id": "",
        "stat_area_vintage": "",
        "stat_area_yishuv_stat": "",
        "stat_area_number": "",
        "stat_area_yishuv_stat_2022": "",
        "stat_area_stat_2022": "",
        "locality_id": "",
        "locality_code": row.get("target_locality_code", ""),
        "locality_name": row.get("target_locality_name", ""),
        "custom_geography_id": row["custom_geography_id"],
        "is_mapped": False,
        "is_geographic": False,
        "final_assignment_method": row["assignment_method"],
        "final_assignment_source": row["assignment_source"],
        "unresolved_reason": reason,
    }


def load_historical_assignments() -> dict[str, dict[str, str]]:
    rows = read_csv(HISTORICAL_ASSIGNMENTS)
    if not rows:
        raise FileNotFoundError(
            "Missing direct historical assignments; run "
            f"build_historical_ballot_assignments.py: {HISTORICAL_ASSIGNMENTS}"
        )
    output: dict[str, dict[str, str]] = {}
    for row in rows:
        uid = row.get("source_row_uid", "")
        if not uid or uid in output:
            raise ValueError(
                f"Missing or duplicate historical assignment UID: {uid or '(blank)'}"
            )
        output[uid] = row
    return output


def load_historical_overrides() -> dict[str, dict[str, str]]:
    rows = read_csv(HISTORICAL_STAT_AREA_OVERRIDES)
    if not rows:
        raise FileNotFoundError(
            f"Missing or empty reviewed historical override table: "
            f"{HISTORICAL_STAT_AREA_OVERRIDES}"
        )
    output: dict[str, dict[str, str]] = {}
    for row in rows:
        uid = normalize_spaces(row.get("source_row_uid", ""))
        if not uid or uid in output:
            raise ValueError(f"Missing or duplicate historical override UID: {uid}")
        if row.get("evidence_status") != "reviewed_exact_stable_conflict_resolution":
            raise ValueError(f"Unsupported historical override evidence: {uid}")
        if int_value(row.get("stat_area_vintage")) != 2011:
            raise ValueError(f"Historical override must target 2011 geography: {uid}")
        output[uid] = row
    return output


def load_cross_election_reviews() -> dict[str, dict[str, str]]:
    rows = read_csv(CROSS_ELECTION_STAT_AREA_REVIEWS)
    if not rows:
        raise FileNotFoundError(
            "Missing or empty reviewed cross-election assignment table: "
            f"{CROSS_ELECTION_STAT_AREA_REVIEWS}"
        )
    output: dict[str, dict[str, str]] = {}
    for row in rows:
        uid = normalize_spaces(row.get("source_row_uid", ""))
        if not uid or uid in output:
            raise ValueError(f"Missing or duplicate cross-election review UID: {uid}")
        if row.get("decision") != "approved" or row.get("confidence") != "high":
            raise ValueError(
                f"Only approved high-confidence cross-election rows may publish: {uid}"
            )
        if int_value(row.get("stat_area_vintage")) not in {2008, 2011}:
            raise ValueError(f"Unsupported cross-election target vintage: {uid}")
        if not normalize_spaces(row.get("evidence_class", "")):
            raise ValueError(f"Cross-election review lacks an evidence class: {uid}")
        if not normalize_spaces(row.get("evidence_sources", "")):
            raise ValueError(f"Cross-election review lacks evidence sources: {uid}")
        output[uid] = row
    return output


def load_approved_arcgis_reconstructions() -> dict[str, dict[str, str]]:
    reviews = read_csv(ARCGIS_RECONSTRUCTION_REVIEWS)
    candidates = read_csv(ARCGIS_RECONSTRUCTION_CANDIDATES)
    reports = read_csv(ARCGIS_RECONSTRUCTION_LOCALITIES)
    if not reviews or not candidates or not reports:
        raise FileNotFoundError(
            "ArcGIS reconstruction approvals require the reviewed table and "
            "fresh audit outputs"
        )

    def locality_key(row: dict[str, str]) -> tuple[str, str]:
        return (
            normalize_spaces(row.get("election", "")),
            normalize_locality_code(row.get("source_locality_code", "")),
        )

    report_index: dict[tuple[str, str], dict[str, str]] = {}
    for report in reports:
        key = locality_key(report)
        if key in report_index:
            raise ValueError(f"Duplicate ArcGIS reconstruction report: {key}")
        report_index[key] = report

    candidates_by_locality: dict[tuple[str, str], list[dict[str, str]]] = {}
    for candidate in candidates:
        candidates_by_locality.setdefault(locality_key(candidate), []).append(candidate)

    reviewed_keys: set[tuple[str, str]] = set()
    approved: dict[str, dict[str, str]] = {}
    for review in reviews:
        key = locality_key(review)
        if key in reviewed_keys:
            raise ValueError(f"Duplicate ArcGIS reconstruction review: {key}")
        reviewed_keys.add(key)
        decision = normalize_spaces(review.get("decision", "")).lower()
        if decision not in {"approved", "deferred", "rejected"}:
            raise ValueError(f"Unsupported ArcGIS reconstruction decision: {review}")
        if decision != "approved":
            continue

        report = report_index.get(key)
        locality_candidates = candidates_by_locality.get(key, [])
        if not report or not locality_candidates:
            raise ValueError(f"Approved ArcGIS reconstruction is absent from audit: {key}")
        evidence_tier = normalize_spaces(review.get("evidence_tier", "")).upper()
        if (
            evidence_tier not in {"A", "B", "C"}
            or report.get("status") != "unique_exact_partition"
            or report.get("evidence_tier") != evidence_tier
        ):
            raise ValueError(f"Approved ArcGIS reconstruction evidence changed: {key}")
        if (
            int_value(review.get("candidate_rows")) != len(locality_candidates)
            or int_value(review.get("candidate_rows"))
            != int_value(report.get("candidate_rows"))
            or int_value(review.get("candidate_actual_voters"))
            != sum(int_value(row.get("actual_voters")) for row in locality_candidates)
            or int_value(review.get("candidate_actual_voters"))
            != int_value(report.get("pending_actual_voters"))
        ):
            raise ValueError(f"Approved ArcGIS reconstruction totals changed: {key}")
        if reconstruction_fingerprint(locality_candidates) != review.get(
            "candidate_assignment_sha256"
        ):
            raise ValueError(f"Approved ArcGIS reconstruction mapping changed: {key}")

        for candidate in locality_candidates:
            if candidate.get("evidence_tier") != evidence_tier:
                raise ValueError(f"Approved ArcGIS candidate tier changed: {key}")
            uid = candidate.get("source_row_uid", "")
            if not uid or uid in approved:
                raise ValueError(f"Missing or duplicate approved ArcGIS row: {uid}")
            approved[uid] = candidate
    return approved


def load_stable_ballot_assignments() -> dict[str, dict[str, str]]:
    candidates = read_csv(STABLE_BALLOT_CANDIDATES)
    if not STABLE_BALLOT_SUMMARY.exists():
        raise FileNotFoundError(
            f"Missing stable-ballot audit summary: {STABLE_BALLOT_SUMMARY}"
        )
    summary = json.loads(STABLE_BALLOT_SUMMARY.read_text(encoding="utf-8"))
    if summary.get("status") not in {"complete", "partial_missing_sources"}:
        raise ValueError("Stable-ballot assignment audit has an invalid status")
    if summary.get("status") == "partial_missing_sources" and not summary.get(
        "missing_source_workbooks"
    ):
        raise ValueError("Partial stable-ballot audit does not identify missing sources")
    if int_value(summary.get("candidate_rows")) != len(candidates):
        raise ValueError("Stable-ballot candidate row count changed")
    if int_value(summary.get("candidate_actual_voters")) != sum(
        int_value(row.get("actual_voters")) for row in candidates
    ):
        raise ValueError("Stable-ballot candidate voter total changed")
    if reconstruction_fingerprint(candidates) != summary.get(
        "candidate_assignment_sha256"
    ):
        raise ValueError("Stable-ballot candidate mapping fingerprint changed")

    candidate_by_key: dict[tuple[str, str, str], dict[str, str]] = {}
    for candidate in candidates:
        uid = candidate.get("source_row_uid", "")
        key = (
            normalize_spaces(candidate.get("election", "")),
            normalize_locality_code(candidate.get("source_locality_code", "")),
            normalize_spaces(candidate.get("source_kalpi", "")),
        )
        if not uid or key in candidate_by_key:
            raise ValueError(f"Missing or duplicate stable-ballot row: {uid}")
        candidate_by_key[key] = candidate

    rejected_uids: set[str] = set()
    reviewed_keys: set[tuple[str, str, str]] = set()
    for review in read_csv(STABLE_BALLOT_REVIEWS):
        decision = normalize_spaces(review.get("decision", ""))
        if decision != "reject_exact_assignment":
            raise ValueError(f"Unsupported stable-ballot review decision: {decision}")
        election = normalize_spaces(review.get("election", ""))
        locality_code = normalize_locality_code(review.get("locality_code", ""))
        if not normalize_spaces(review.get("evidence_sources", "")) or not normalize_spaces(
            review.get("reason", "")
        ):
            raise ValueError("Stable-ballot rejection lacks evidence or a reason")
        for ballot in normalize_spaces(review.get("source_ballots", "")).split("|"):
            key = (election, locality_code, normalize_spaces(ballot))
            if not key[2] or key in reviewed_keys:
                raise ValueError(f"Blank or duplicate stable-ballot review key: {key}")
            candidate = candidate_by_key.get(key)
            if not candidate:
                raise ValueError(f"Stable-ballot review no longer matches a candidate: {key}")
            reviewed_keys.add(key)
            rejected_uids.add(candidate["source_row_uid"])

    output: dict[str, dict[str, str]] = {}
    for candidate in candidates:
        uid = candidate["source_row_uid"]
        if uid not in rejected_uids:
            output[uid] = candidate
    return output


def load_k23_cec_ags_assignments() -> dict[str, dict[str, str]]:
    candidates = read_csv(K23_CEC_AGS_CANDIDATES)
    if not K23_CEC_AGS_SUMMARY.exists():
        raise FileNotFoundError(
            f"Missing K23 CEC AGS audit summary: {K23_CEC_AGS_SUMMARY}"
        )
    summary = json.loads(K23_CEC_AGS_SUMMARY.read_text(encoding="utf-8"))
    if summary.get("status") != "complete":
        raise ValueError("K23 CEC AGS assignment audit is not complete")
    if int_value(summary.get("candidate_rows")) != len(candidates):
        raise ValueError("K23 CEC AGS candidate row count changed")
    if int_value(summary.get("candidate_actual_voters")) != sum(
        int_value(row.get("actual_voters")) for row in candidates
    ):
        raise ValueError("K23 CEC AGS candidate voter total changed")
    if reconstruction_fingerprint(candidates) != summary.get(
        "candidate_assignment_sha256"
    ):
        raise ValueError("K23 CEC AGS candidate mapping fingerprint changed")

    output: dict[str, dict[str, str]] = {}
    for candidate in candidates:
        uid = candidate.get("source_row_uid", "")
        if not uid or uid in output:
            raise ValueError(f"Missing or duplicate K23 CEC AGS row: {uid}")
        output[uid] = candidate
    return output


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.parse_args()

    assignment_rows = read_csv(ASSIGNMENT_PLAN)
    historical_assignments = load_historical_assignments()
    historical_overrides = load_historical_overrides()
    cross_election_reviews = load_cross_election_reviews()
    k23_cec_ags_assignments = load_k23_cec_ags_assignments()
    arcgis_reconstructions = load_approved_arcgis_reconstructions()
    stable_ballot_assignments = load_stable_ballot_assignments()
    k26_register_links = {row["source_row_uid"]: row for row in read_csv(PROCESSED_DIR / "audits" / "k26_validated_register_links.csv")}
    stat_metadata = {
        row["stat_area_id"]: row for row in read_csv(STAT_AREA_METADATA)
    }
    historical_stat_metadata = {
        row["stat_area_id"]: row
        for path in HISTORICAL_STAT_AREA_METADATA.values()
        for row in read_csv(path)
    }
    if not assignment_rows:
        raise FileNotFoundError(
            f"Missing assignment plan; run build_assignment_plan.py: {ASSIGNMENT_PLAN}"
        )

    output: list[dict[str, Any]] = []
    for row in assignment_rows:
        method = row["assignment_method"]
        historical = historical_assignments.get(row["source_row_uid"])

        k26_link = k26_register_links.get(row["source_row_uid"])
        if k26_link and method not in {"single_stat_locality", "custom_point_size_polygon", "special_non_geographic", "official_envelope"}:
            if row["election"] != "K26" or any(
                str(row[field]) != str(k26_link[field])
                for field in ("source_locality_code", "source_kalpi", "eligible_voters", "actual_voters")
            ):
                raise ValueError(f"K26 register link source identity changed: {row['source_row_uid']}")
            stat = stat_metadata[k26_link["stat_area_id"]]
            if normalize_locality_code(stat["locality_code"]) != normalize_locality_code(row["source_locality_code"]):
                raise ValueError(f"K26 register link crosses locality boundaries: {row['source_row_uid']}")
            output.append(mapped_assignment(
                row=row, stat_area_id=stat["stat_area_id"], vintage=2022,
                yishuv_stat=stat["yishuv_stat_2022"], stat_area_number=stat["stat_2022"],
                locality_code=stat["locality_code"], locality_name=stat["locality_name_he"],
                status="statistical_area_assigned",
                method=f"validated_k26_register_{k26_link['evidence_method']}",
                source="CBS K26 crosswalk; CEC planned and final registers; audit=k26_validated_register_links.csv",
            ))
            continue

        override = historical_overrides.get(row["source_row_uid"])
        if override:
            expected = {
                "election": row["election"],
                "source_locality_code": normalize_locality_code(
                    row["source_locality_code"]
                ),
                "source_kalpi": normalize_spaces(row["source_kalpi"]),
            }
            observed = {
                "election": override.get("election", ""),
                "source_locality_code": normalize_locality_code(
                    override.get("source_locality_code", "")
                ),
                "source_kalpi": normalize_spaces(override.get("source_kalpi", "")),
            }
            if observed != expected:
                raise ValueError(
                    f"Historical override source identity changed: "
                    f"{row['source_row_uid']}"
                )
            if not historical or not normalize_bool(
                historical.get("is_historical_stat_mapped", "")
            ):
                raise ValueError(
                    f"Historical override does not replace a direct assignment: "
                    f"{row['source_row_uid']}"
                )
            stat = historical_stat_metadata.get(override["target_stat_area_id"])
            if not stat:
                raise ValueError(
                    f"Historical override target lacks 2011 metadata: "
                    f"{override['target_stat_area_id']}"
                )
            if normalize_locality_code(stat.get("locality_code", "")) != expected[
                "source_locality_code"
            ]:
                raise ValueError(
                    f"Historical override crosses locality boundaries: "
                    f"{row['source_row_uid']}"
                )
            output.append(historical_override_assignment(row, override, stat))
            continue

        if historical and normalize_bool(
            historical.get("is_historical_stat_mapped", "")
        ):
            output.append(historical_stat_assignment(row, historical))
            continue
        k23_ags_candidate = k23_cec_ags_assignments.get(row["source_row_uid"])
        if k23_ags_candidate:
            if (
                not historical
                or historical.get("historical_assignment_status")
                != "no_direct_historical_assignment"
            ):
                raise ValueError(
                    "K23 CEC AGS evidence may only replace a missing direct "
                    f"historical assignment: {row['source_row_uid']}"
                )
            stat = historical_stat_metadata.get(
                k23_ags_candidate["candidate_stat_area_id"]
            )
            if not stat:
                raise ValueError(
                    "K23 CEC AGS target lacks 2011 metadata: "
                    f"{k23_ags_candidate['candidate_stat_area_id']}"
                )
            output.append(k23_cec_ags_assignment(row, k23_ags_candidate, stat))
            continue
        reconstruction = arcgis_reconstructions.get(row["source_row_uid"])
        if reconstruction:
            if (
                not historical
                or historical.get("historical_assignment_status")
                != "no_direct_historical_assignment"
            ):
                raise ValueError(
                    "ArcGIS reconstruction may only replace a missing direct "
                    f"historical assignment: {row['source_row_uid']}"
                )
            stat = historical_stat_metadata.get(
                reconstruction["candidate_stat_area_id"]
            )
            if not stat:
                raise ValueError(
                    "ArcGIS reconstruction target lacks 2011 metadata: "
                    f"{reconstruction['candidate_stat_area_id']}"
                )
            output.append(arcgis_reconstructed_assignment(row, reconstruction, stat))
            continue
        stable_candidate = stable_ballot_assignments.get(row["source_row_uid"])
        if stable_candidate:
            if (
                not historical
                or historical.get("historical_assignment_status")
                != "no_direct_historical_assignment"
            ):
                raise ValueError(
                    "Stable-ballot evidence may only replace a missing direct "
                    f"historical assignment: {row['source_row_uid']}"
                )
            stat = historical_stat_metadata.get(
                stable_candidate["candidate_stat_area_id"]
            )
            if not stat:
                raise ValueError(
                    "Stable-ballot target lacks 2011 metadata: "
                    f"{stable_candidate['candidate_stat_area_id']}"
                )
            output.append(stable_ballot_assignment(row, stable_candidate, stat))
            continue
        cross_election_review = cross_election_reviews.get(row["source_row_uid"])
        if cross_election_review:
            if (
                not historical
                or historical.get("historical_assignment_status")
                != "no_direct_historical_assignment"
            ):
                raise ValueError(
                    "Cross-election review may only replace a missing direct "
                    f"historical assignment: {row['source_row_uid']}"
                )
            expected_identity = {
                "election": row["election"],
                "locality_code": normalize_locality_code(
                    row["source_locality_code"]
                ),
                "source_kalpi": normalize_spaces(row["source_kalpi"]),
                "eligible_voters": int_value(row["eligible_voters"]),
                "actual_voters": int_value(row["actual_voters"]),
            }
            observed_identity = {
                "election": cross_election_review.get("election", ""),
                "locality_code": normalize_locality_code(
                    cross_election_review.get("locality_code", "")
                ),
                "source_kalpi": normalize_spaces(
                    cross_election_review.get("source_kalpi", "")
                ),
                "eligible_voters": int_value(
                    cross_election_review.get("eligible_voters")
                ),
                "actual_voters": int_value(
                    cross_election_review.get("actual_voters")
                ),
            }
            if observed_identity != expected_identity:
                raise ValueError(
                    "Cross-election review source identity changed: "
                    f"{row['source_row_uid']}"
                )
            target_id = cross_election_review["target_stat_area_id"]
            stat = historical_stat_metadata.get(target_id)
            if not stat:
                raise ValueError(
                    f"Cross-election review target lacks metadata: {target_id}"
                )
            if int_value(stat.get("stat_area_vintage")) != int_value(
                cross_election_review.get("stat_area_vintage")
            ):
                raise ValueError(
                    f"Cross-election review target vintage changed: {target_id}"
                )
            if normalize_locality_code(stat.get("locality_code", "")) != (
                expected_identity["locality_code"]
            ):
                raise ValueError(
                    "Cross-election review crosses locality boundaries: "
                    f"{row['source_row_uid']}"
                )
            output.append(
                reviewed_cross_election_assignment(
                    row, cross_election_review, stat
                )
            )
            continue
        if (
            historical
            and historical.get("historical_assignment_status")
            != "not_applicable_non_geographic"
        ):
            unresolved_reason = historical.get(
                "unresolved_reason",
                "No direct historical ballot assignment is available",
            )
            if historical.get("ballot_base") == "990":
                unresolved_reason = (
                    "Central ballot 990 serves locality-registered voters without "
                    "a supported area-level allocation; this multi-area locality "
                    "cannot be reduced to one statistical area"
                )
            output.append(
                unresolved(
                    row,
                    historical.get(
                        "historical_assignment_status",
                        "no_direct_historical_assignment",
                    ),
                    unresolved_reason,
                )
            )
            continue
        if method == "single_stat_locality":
            stat_id = row["target_stat_area_id"].split("|", 1)[0]
            stat = stat_metadata.get(stat_id)
            if stat:
                output.append(current_stat_assignment(row, stat))
            else:
                output.append(
                    unresolved(
                        row,
                        "missing_stat_area_metadata",
                        f"Statistical area not found: {stat_id}",
                    )
                )
            continue
        if method == "custom_point_size_polygon":
            output.append(custom_assignment(row))
            continue
        if method in {"special_non_geographic", "official_envelope"}:
            output.append(
                unresolved(
                    row,
                    method,
                    "Non-geographic row is counted but not mapped",
                )
            )
            continue
        output.append(
            unresolved(
                row,
                "unresolved",
                row.get("unresolved_reason", "Unresolved assignment"),
            )
        )

    for assignment in output:
        assignment.update(assignment_evidence_metadata(assignment))

    applied_cross_election_reviews = {
        row["source_row_uid"]
        for row in output
        if row["final_assignment_method"]
        == "reviewed_cross_election_stat_area_assignment"
    }
    if applied_cross_election_reviews != set(cross_election_reviews):
        missing_reviews = sorted(
            set(cross_election_reviews) - applied_cross_election_reviews
        )
        raise ValueError(
            "Reviewed cross-election rows were not applied: "
            f"{missing_reviews[:10]}"
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
        "geography_assignment_status",
        "geography_type",
        "geography_id",
        "stat_area_id",
        "stat_area_vintage",
        "stat_area_yishuv_stat",
        "stat_area_number",
        "stat_area_yishuv_stat_2022",
        "stat_area_stat_2022",
        "locality_id",
        "locality_code",
        "locality_name",
        "locality_assignment_status",
        "locality_geography_type",
        "locality_geography_id",
        "locality_result_code",
        "locality_result_name",
        "is_locality_mapped",
        "custom_geography_id",
        "is_mapped",
        "is_geographic",
        "final_assignment_method",
        "final_assignment_source",
        "assignment_evidence_class",
        "assignment_confidence",
        "assignment_is_synthetic_link",
        "unresolved_reason",
    ]
    write_csv(OUT_DIR / "ballot_geography_assignments.csv", output, fields)

    missing = [
        row
        for row in output
        if row["geography_assignment_status"] in HISTORICAL_PENDING_STATUSES
        or row["geography_assignment_status"] == "unresolved"
    ]
    write_csv(
        OUT_DIR / "unresolved_statistical_area_assignment_rows.csv",
        missing,
        fields,
    )

    summary: list[dict[str, Any]] = []
    for election in sorted({row["election"] for row in output}, reverse=True):
        rows = [row for row in output if row["election"] == election]
        statuses = Counter(row["geography_assignment_status"] for row in rows)
        mapped_rows = [row for row in rows if normalize_bool(row["is_mapped"])]
        locality_mapped_rows = [
            row for row in rows if normalize_bool(row["is_locality_mapped"])
        ]
        missing_rows = [
            row
            for row in rows
            if row["geography_assignment_status"] in HISTORICAL_PENDING_STATUSES
            or row["geography_assignment_status"] == "unresolved"
        ]
        summary.append(
            {
                "election": election,
                "rows": len(rows),
                "actual_voters": sum(int_value(row["actual_voters"]) for row in rows),
                "mapped_rows": len(mapped_rows),
                "mapped_actual_voters": sum(
                    int_value(row["actual_voters"]) for row in mapped_rows
                ),
                "stat_area_rows": sum(
                    row["geography_type"] == "statistical_area"
                    for row in mapped_rows
                ),
                "custom_geography_rows": sum(
                    row["geography_type"] == "custom_geography"
                    for row in mapped_rows
                ),
                "arcgis_reconstructed_rows": sum(
                    row["final_assignment_method"].startswith(
                        "arcgis_residual_partition_tier_"
                    )
                    for row in mapped_rows
                ),
                "arcgis_reconstructed_actual_voters": sum(
                    int_value(row["actual_voters"])
                    for row in mapped_rows
                    if row["final_assignment_method"].startswith(
                        "arcgis_residual_partition_tier_"
                    )
                ),
                "stable_ballot_assigned_rows": sum(
                    row["final_assignment_method"].startswith(
                        "cbs_stable_ballot_"
                    )
                    for row in mapped_rows
                ),
                "stable_ballot_assigned_actual_voters": sum(
                    int_value(row["actual_voters"])
                    for row in mapped_rows
                    if row["final_assignment_method"].startswith(
                        "cbs_stable_ballot_"
                    )
                ),
                "official_cec_ags_assigned_rows": sum(
                    row["final_assignment_method"] == "official_cec_k23_ags"
                    for row in mapped_rows
                ),
                "official_cec_ags_assigned_actual_voters": sum(
                    int_value(row["actual_voters"])
                    for row in mapped_rows
                    if row["final_assignment_method"] == "official_cec_k23_ags"
                ),
                "reviewed_historical_override_rows": sum(
                    row["final_assignment_method"]
                    == "reviewed_historical_stat_area_override"
                    for row in mapped_rows
                ),
                "reviewed_historical_override_actual_voters": sum(
                    int_value(row["actual_voters"])
                    for row in mapped_rows
                    if row["final_assignment_method"]
                    == "reviewed_historical_stat_area_override"
                ),
                "locality_mapped_rows": len(locality_mapped_rows),
                "locality_mapped_actual_voters": sum(
                    int_value(row["actual_voters"])
                    for row in locality_mapped_rows
                ),
                "statistical_area_pending_rows": len(missing_rows),
                "statistical_area_pending_actual_voters": sum(
                    int_value(row["actual_voters"]) for row in missing_rows
                ),
                "envelope_rows": statuses["official_envelope"],
                "special_non_geographic_rows": statuses[
                    "special_non_geographic"
                ],
                "unresolved_rows": statuses["unresolved"],
                "historical_unresolved_rows": sum(
                    statuses[status] for status in HISTORICAL_PENDING_STATUSES
                ),
            }
        )
    write_csv(
        OUT_DIR / "final_assignment_summary.csv",
        summary,
        list(summary[0].keys()) if summary else [],
    )
    write_json(OUT_DIR / "final_assignment_summary.json", summary)

    print(f"final_assignment_rows={len(output)}")
    print(f"statistical_area_pending_rows={len(missing)}")
    for row in summary:
        print(
            f"{row['election']}: mapped={row['mapped_rows']} "
            f"stat={row['stat_area_rows']} custom={row['custom_geography_rows']} "
            f"locality={row['locality_mapped_rows']} "
            f"stat_pending={row['statistical_area_pending_rows']}"
        )


if __name__ == "__main__":
    main()
