from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

LOCAL_AUDIT_PYTHON = Path(__file__).resolve().parents[1] / ".local" / "python-audit"
if LOCAL_AUDIT_PYTHON.exists():
    sys.path.insert(0, str(LOCAL_AUDIT_PYTHON))

import pandas as pd

from audit_statistical_area_polling_group_evidence import (
    SOURCES,
    ballot_base,
    clean,
    integer,
    read_source,
)
from pipeline_common import PROCESSED_DIR, write_json


ROOT = Path(__file__).resolve().parents[1]
ASSIGNMENTS = (
    PROCESSED_DIR / "assignments" / "historical_ballot_assignments.csv"
)
CANDIDATES = PROCESSED_DIR / "audits" / "stable_ballot_assignment_candidates.csv"
SITE_AUDIT = PROCESSED_DIR / "audits" / "statistical_area_polling_group_sites.csv"
REVIEWS = ROOT / "data" / "manual" / "stable_ballot_assignment_reviews.csv"
OUTPUT = PROCESSED_DIR / "audits" / "stable_ballot_site_safety.csv"
MAPPING_OUTPUT = (
    PROCESSED_DIR / "audits" / "stable_ballot_site_safety_planned_mappings.csv"
)
SUMMARY_OUTPUT = (
    PROCESSED_DIR / "audits" / "stable_ballot_site_safety_summary.json"
)


def pipe(values: Any) -> str:
    return "|".join(sorted({clean(value) for value in values if clean(value)}))


def truthy(value: Any) -> bool:
    return clean(value).lower() in {"1", "true", "yes"}


def split_pipe(value: Any) -> set[str]:
    return {part for part in clean(value).split("|") if part}


def direct_reference_mappings(assignments: pd.DataFrame) -> pd.DataFrame:
    direct = assignments.loc[
        assignments["is_historical_stat_mapped"].map(truthy)
        & assignments["historical_assignment_method"].str.startswith(
            "official_cbs_ballot_crosswalk"
        )
    ].copy()
    direct["ballot_base"] = direct["ballot_base"].map(ballot_base)
    per_election = (
        direct.groupby(
            ["source_locality_code", "ballot_base", "election"], sort=True
        )["stat_area_id"]
        .agg(lambda values: sorted(set(values) - {""}))
        .reset_index(name="area_ids")
    )
    return per_election.loc[per_election["area_ids"].map(len).eq(1)].copy()


def build_mapping_audit(
    candidates: pd.DataFrame,
    reference_mappings: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (election, locality_code), scope in candidates.groupby(
        ["election", "source_locality_code"], sort=True
    ):
        config = SOURCES.get(election)
        if not config or not config.final or config.planned.filename == config.final.filename:
            continue
        planned = read_source(config.planned)
        planned = planned.loc[planned["locality_code"].eq(locality_code)].copy()
        references = reference_mappings.loc[
            reference_mappings["source_locality_code"].eq(locality_code)
            & ~reference_mappings["election"].eq(election)
        ].copy()
        for base, planned_rows in planned.groupby("ballot_base", sort=True):
            base_references = references.loc[
                references["ballot_base"].eq(base)
            ].copy()
            reference_areas = sorted(
                {areas[0] for areas in base_references["area_ids"] if areas}
            )
            reference_elections = sorted(set(base_references["election"]))
            if len(reference_areas) == 1 and len(reference_elections) >= 2:
                status = "unanimous_two_or_more_official_crosswalks"
                consensus_area = reference_areas[0]
            elif len(reference_areas) > 1:
                status = "conflicting_official_crosswalks"
                consensus_area = ""
            else:
                status = "insufficient_official_crosswalk_references"
                consensus_area = ""
            rows.append(
                {
                    "election": election,
                    "locality_code": locality_code,
                    "locality_name": pipe(
                        list(scope["source_locality_name"])
                        + list(planned_rows["locality_name"])
                    ),
                    "ballot_base": base,
                    "planned_ballots": pipe(planned_rows["source_kalpi"]),
                    "planned_eligible_voters": int(planned_rows["eligible"].sum()),
                    "consensus_stat_area_id": consensus_area,
                    "reference_elections": pipe(reference_elections),
                    "reference_stat_area_ids": pipe(reference_areas),
                    "mapping_status": status,
                }
            )
    return pd.DataFrame(rows)


def classify_candidates(candidates: pd.DataFrame) -> pd.DataFrame:
    sites = pd.read_csv(SITE_AUDIT, dtype=str, encoding="utf-8-sig").fillna("")
    planned_register_cache: dict[str, pd.DataFrame] = {}
    final_register_cache: dict[str, pd.DataFrame] = {}
    rows: list[dict[str, Any]] = []
    for candidate in candidates.to_dict("records"):
        election = clean(candidate["election"])
        locality_code = clean(candidate["source_locality_code"])
        source_ballot = clean(candidate["source_kalpi"])
        base = ballot_base(source_ballot)
        config = SOURCES.get(election)
        has_distinct_registers = bool(
            config
            and config.final
            and config.planned.filename != config.final.filename
        )
        result: dict[str, Any] = {
            **candidate,
            "has_decimal_subdivision": "." in source_ballot,
            "site_audit_id": "",
            "planned_site_ids": "",
            "final_site_ids": "",
            "site_classification": "",
            "site_planned_area_ids": "",
            "site_residual_area_ids": "",
            "site_planned_ballots": "",
            "site_residual_final_ballots": "",
            "site_preserved_ballot_bases": "",
            "safety_status": "",
        }
        if not has_distinct_registers:
            result["safety_status"] = (
                "no_decimal_batch_signal_without_distinct_pre_post_registers"
                if "." not in source_ballot
                else "unresolved_no_distinct_pre_post_registers"
            )
            rows.append(result)
            continue

        if election not in final_register_cache:
            final_register_cache[election] = read_source(config.final)
        if election not in planned_register_cache:
            planned_register_cache[election] = read_source(config.planned)
        final_register = final_register_cache[election]
        planned_register = planned_register_cache[election]
        final_rows = final_register.loc[
            final_register["locality_code"].eq(locality_code)
            & final_register["source_kalpi"].eq(source_ballot)
        ]
        if final_rows.empty:
            result["safety_status"] = "candidate_missing_from_final_register"
            rows.append(result)
            continue

        planned_same_base = planned_register.loc[
            planned_register["locality_code"].eq(locality_code)
            & planned_register["ballot_base"].eq(base)
        ]

        final_site_ids = set(final_rows["site_id"]) - {""}
        locality_sites = sites.loc[
            sites["election"].eq(election)
            & sites["locality_code"].eq(locality_code)
        ].copy()
        matching_sites = locality_sites.loc[
            locality_sites["final_site_ids"].map(
                lambda value: bool(split_pipe(value) & final_site_ids)
            )
        ]
        if len(matching_sites) != 1:
            result["final_site_ids"] = pipe(final_site_ids)
            if (
                planned_same_base.empty
                and "." not in source_ballot
                and len(final_rows) == 1
            ):
                result["safety_status"] = "safe_final_only_integer_stable_link"
            else:
                result["safety_status"] = "site_audit_missing_or_ambiguous"
            rows.append(result)
            continue

        site = matching_sites.iloc[0]
        result.update(
            {
                "site_audit_id": site["site_audit_id"],
                "planned_site_ids": site["planned_site_ids"],
                "final_site_ids": site["final_site_ids"],
                "site_classification": site["classification"],
                "site_planned_area_ids": site["all_area_ids"],
                "site_residual_area_ids": site["residual_area_ids"],
                "site_planned_ballots": site["planned_ballots"],
                "site_residual_final_ballots": site["residual_final_ballots"],
                "site_preserved_ballot_bases": site["preserved_ballot_bases"],
            }
        )
        residual_final_ballots = split_pipe(site["residual_final_ballots"])
        preserved_bases = split_pipe(site["preserved_ballot_bases"])
        residual_area_ids = split_pipe(site["residual_area_ids"])
        planned_area_ids = split_pipe(site["all_area_ids"])
        if (
            planned_same_base.empty
            and "." not in source_ballot
            and len(final_rows) == 1
        ):
            result["safety_status"] = "safe_final_only_integer_stable_link"
        elif (
            source_ballot in residual_final_ballots
            and len(planned_area_ids) == 1
            and clean(candidate["candidate_stat_area_id"]) in planned_area_ids
        ):
            result["safety_status"] = "safe_single_area_site_peer_confirmation"
        elif source_ballot in residual_final_ballots and len(residual_area_ids) > 1:
            result["safety_status"] = "unsafe_mixed_final_batch"
        elif source_ballot in residual_final_ballots and len(residual_area_ids) == 1:
            result["safety_status"] = "safe_single_residual_area"
        elif base in preserved_bases and len(planned_area_ids) >= 1:
            result["safety_status"] = "safe_preserved_ballot_base"
        else:
            result["safety_status"] = "unresolved_site_evidence"
        rows.append(result)
    return pd.DataFrame(rows)


def reviewed_rejection_keys() -> set[tuple[str, str, str]]:
    reviews = pd.read_csv(REVIEWS, dtype=str, encoding="utf-8-sig").fillna("")
    keys: set[tuple[str, str, str]] = set()
    for review in reviews.to_dict("records"):
        if clean(review.get("decision")) != "reject_exact_assignment":
            continue
        election = clean(review.get("election"))
        locality_code = clean(review.get("locality_code"))
        for source_ballot in clean(review.get("source_ballots")).split("|"):
            key = (election, locality_code, clean(source_ballot))
            if not all(key) or key in keys:
                raise ValueError(f"Invalid duplicate stable-ballot review key: {key}")
            keys.add(key)
    return keys


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    candidates = pd.read_csv(
        CANDIDATES, dtype=str, encoding="utf-8-sig"
    ).fillna("")
    assignments = pd.read_csv(
        ASSIGNMENTS, dtype=str, encoding="utf-8-sig"
    ).fillna("")
    reference_mappings = direct_reference_mappings(assignments)
    mapping_audit = build_mapping_audit(candidates, reference_mappings)
    mapping_audit.to_csv(MAPPING_OUTPUT, index=False, encoding="utf-8-sig")

    safety = classify_candidates(candidates)
    safety.to_csv(OUTPUT, index=False, encoding="utf-8-sig")
    status_counts = Counter(safety["safety_status"])
    rejection_keys = reviewed_rejection_keys()
    safety["review_key"] = safety.apply(
        lambda row: (
            clean(row["election"]),
            clean(row["source_locality_code"]),
            clean(row["source_kalpi"]),
        ),
        axis=1,
    )
    unsafe = safety.loc[
        safety["safety_status"].str.startswith("unsafe_")
    ].copy()
    unresolved = safety.loc[
        safety["safety_status"].str.startswith("unresolved_")
        | safety["safety_status"].isin(
            {
                "site_audit_missing_or_ambiguous",
                "candidate_missing_from_final_register",
            }
        )
    ].copy()
    missing_rejections = sorted(set(unsafe["review_key"]) - rejection_keys)
    summary = {
        "definition": (
            "Stable row-level assignments are checked against distinct official "
            "pre/post polling registers. A final decimal batch is unsafe when it "
            "belongs to a residual polling-site set spanning several planned areas."
        ),
        "candidate_rows": len(safety),
        "candidate_locality_election_cases": int(
            safety.groupby(["election", "source_locality_code"]).ngroups
        ),
        "decimal_candidate_rows": int(safety["has_decimal_subdivision"].sum()),
        "status_counts": dict(sorted(status_counts.items())),
        "unsafe_candidate_rows": len(unsafe),
        "unsafe_candidate_actual_voters": int(
            unsafe["actual_voters"].map(integer).sum()
        ),
        "unsafe_rows_covered_by_review": int(
            unsafe["review_key"].isin(rejection_keys).sum()
        ),
        "unresolved_safety_rows": len(unresolved),
        "missing_rejection_keys": ["/".join(key) for key in missing_rejections],
        "publication_guard": (
            "pass" if not missing_rejections and unresolved.empty else "fail"
        ),
        "planned_mapping_rows": len(mapping_audit),
        "planned_mapping_status_counts": dict(
            sorted(Counter(mapping_audit["mapping_status"]).items())
        ),
        "output": str(OUTPUT.relative_to(ROOT)),
        "mapping_output": str(MAPPING_OUTPUT.relative_to(ROOT)),
    }
    write_json(SUMMARY_OUTPUT, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if missing_rejections:
        raise ValueError(
            "Unsafe stable-ballot candidates lack reviewed rejections: "
            f"{missing_rejections[:10]}"
        )
    if not unresolved.empty:
        raise ValueError(
            "Stable-ballot site safety remains unresolved:\n"
            + unresolved[
                [
                    "source_row_uid",
                    "election",
                    "source_locality_code",
                    "source_kalpi",
                    "safety_status",
                ]
            ].to_string(index=False)
        )


if __name__ == "__main__":
    main()
