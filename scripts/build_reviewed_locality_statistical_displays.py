from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANUAL_DIR = ROOT / "data" / "manual"
PROCESSED_DIR = ROOT / "data" / "processed"
AUDIT_DIR = PROCESSED_DIR / "audits"
GEOGRAPHY_DIR = PROCESSED_DIR / "geographies"
PUBLIC_DIR = PROCESSED_DIR / "public"

JOINED_LOCALITIES_PATH = MANUAL_DIR / "joined_locality_composites.csv"
LOCALITY_CROSSWALK_PATH = MANUAL_DIR / "locality_crosswalk.csv"
LOCALITY_METADATA_PATH = GEOGRAPHY_DIR / "localities_2022.metadata.csv"
DISPLAY_REVIEW_PATH = MANUAL_DIR / "statistical_area_result_display_reviews.csv"
DISPLAY_GROUP_PATH = MANUAL_DIR / "statistical_area_display_groups.csv"
DISPLAY_OVERRIDE_PATH = MANUAL_DIR / "statistical_area_display_overrides.csv"
POLLING_FALLBACK_PATH = AUDIT_DIR / "statistical_area_polling_group_fallbacks.csv"
POLLING_DISPLAY_METADATA_PATH = (
    GEOGRAPHY_DIR / "statistical_area_polling_group_displays.metadata.csv"
)

OUTPUT_POLICY_PATH = AUDIT_DIR / "reviewed_locality_statistical_displays.csv"
OUTPUT_AUDIT_PATH = AUDIT_DIR / "reviewed_locality_statistical_display_audit.csv"
OUTPUT_SUMMARY_PATH = (
    AUDIT_DIR / "reviewed_locality_statistical_display_audit_summary.json"
)

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
    "K26": 2022,
}
CORE_TOTAL_FIELDS = (
    "contributing_rows",
    "contributing_kalpis",
    "eligible_voters",
    "actual_voters",
    "valid_votes",
    "invalid_votes",
)
POLICY_FIELDS = (
    "display_geography_id",
    "elections",
    "component_stat_area_ids",
    "aggregation_method",
    "evidence_group_id",
    "evidence_class",
    "review_status",
    "note",
    "display_locality_code",
    "display_locality_name_he",
    "display_locality_name_en",
    "display_name_he",
    "display_name_en",
    "notice_he",
    "notice_en",
)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def write_csv(
    path: Path,
    rows: list[dict[str, Any]],
    fieldnames: list[str] | tuple[str, ...] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(fieldnames or (list(rows[0]) if rows else []))
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def split_pipe(value: Any) -> list[str]:
    return [part.strip() for part in str(value or "").split("|") if part.strip()]


def clean_code(value: Any) -> str:
    text = str(value or "").strip()
    return re.sub(r"\.0+$", "", text)


def integer(value: Any) -> int:
    text = str(value or "").strip().replace(",", "")
    return int(round(float(text))) if text else 0


def numeric_key(value: Any) -> tuple[int, str]:
    text = clean_code(value)
    try:
        return int(text), text
    except ValueError:
        return 10**9, text


def normalized_name(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).replace("*", "")
    return "".join(character for character in text if character.isalnum()).casefold()


def parse_source_identity(value: str) -> tuple[str, str]:
    match = re.match(r"^(.*?)\s*\[([0-9]+)\]\s*$", str(value or "").strip())
    if not match:
        return str(value or "").strip(), ""
    return match.group(1).strip(), clean_code(match.group(2))


def claim_components(
    claims: dict[tuple[str, str], set[str]],
    *,
    owner: str,
    elections: list[str],
    component_ids: list[str],
) -> None:
    for election in elections:
        if election not in ELECTION_VINTAGES:
            continue
        for component_id in component_ids:
            claims[(election, component_id)].add(owner)


def load_existing_claims() -> tuple[
    dict[tuple[str, str], set[str]], dict[tuple[str, str], str]
]:
    claims: dict[tuple[str, str], set[str]] = defaultdict(set)
    for path in (DISPLAY_REVIEW_PATH, POLLING_FALLBACK_PATH):
        for row in read_csv(path):
            owner = str(row.get("display_geography_id") or path.name).strip()
            claim_components(
                claims,
                owner=owner,
                elections=split_pipe(row.get("elections") or row.get("election")),
                component_ids=split_pipe(row.get("component_stat_area_ids")),
            )
    for row in read_csv(POLLING_DISPLAY_METADATA_PATH):
        claim_components(
            claims,
            owner=str(row.get("display_geography_id") or "polling-display").strip(),
            elections=split_pipe(row.get("election")),
            component_ids=split_pipe(row.get("component_stat_area_ids")),
        )
    for row in read_csv(DISPLAY_GROUP_PATH):
        claim_components(
            claims,
            owner=str(row.get("display_geography_id") or "display-group").strip(),
            elections=split_pipe(row.get("elections")),
            component_ids=split_pipe(row.get("component_stat_area_id")),
        )

    hidden: dict[tuple[str, str], str] = {}
    for row in read_csv(DISPLAY_OVERRIDE_PATH):
        if str(row.get("visibility") or "").strip() != "hidden":
            continue
        stat_area_id = str(row.get("stat_area_id") or "").strip()
        for election in split_pipe(row.get("elections")):
            hidden[(election, stat_area_id)] = str(row.get("note") or "").strip()
    return claims, hidden


def load_relationships() -> list[dict[str, str]]:
    relationships: list[dict[str, str]] = []
    seen: set[tuple[str, str, tuple[str, ...]]] = set()

    for row in read_csv(JOINED_LOCALITIES_PATH):
        election = str(row.get("election") or "").strip()
        host_code = clean_code(row.get("host_locality_code"))
        component_codes = sorted(
            set(split_pipe(row.get("component_locality_codes"))), key=numeric_key
        )
        key = (election, host_code, tuple(component_codes))
        if election not in ELECTION_VINTAGES or not host_code or key in seen:
            continue
        seen.add(key)
        relationships.append(
            {
                "relationship_id": str(row.get("joined_composite_id") or "").strip(),
                "relationship_source": "reviewed_joined_locality",
                "election": election,
                "host_locality_code": host_code,
                "component_locality_codes": "|".join(component_codes),
                "evidence_status": str(row.get("evidence_status") or "").strip(),
                "evidence_method": str(row.get("evidence_method") or "").strip(),
                "relationship_note": str(row.get("note") or "").strip(),
            }
        )

    joined_templates: dict[tuple[str, tuple[str, ...]], list[dict[str, str]]] = (
        defaultdict(list)
    )
    for relationship in relationships:
        joined_templates[
            (
                relationship["host_locality_code"],
                tuple(split_pipe(relationship["component_locality_codes"])),
            )
        ].append(relationship)
    for (host_code, component_code_tuple), references in joined_templates.items():
        reference_elections = sorted(
            {row["election"] for row in references}, key=lambda value: numeric_key(value[1:])
        )
        has_confirmed_reference = any(
            row["evidence_status"] == "confirmed" for row in references
        )
        if len(reference_elections) < 2 and not has_confirmed_reference:
            continue
        for election in ELECTION_VINTAGES:
            key = (election, host_code, component_code_tuple)
            if key in seen:
                continue
            seen.add(key)
            relationships.append(
                {
                    "relationship_id": (
                        f"join-continuity-review:{election}:{host_code}:"
                        + "-".join(code for code in component_code_tuple if code != host_code)
                    ),
                    "relationship_source": "cross_election_join_continuity_candidate",
                    "election": election,
                    "host_locality_code": host_code,
                    "component_locality_codes": "|".join(component_code_tuple),
                    "evidence_status": "review",
                    "evidence_method": "reviewed_join_in_other_elections",
                    "relationship_note": (
                        "The same reviewed host-component relationship appears in "
                        + "|".join(reference_elections)
                        + "; this election requires its own approval."
                    ),
                }
            )

    current_localities = read_csv(LOCALITY_METADATA_PATH)
    current_codes_by_name: dict[str, set[str]] = defaultdict(set)
    for row in current_localities:
        current_codes_by_name[normalized_name(row.get("locality_name_he"))].add(
            clean_code(row.get("locality_code"))
        )

    accepted_mergers: list[tuple[str, str, str, str]] = []
    for row in read_csv(LOCALITY_CROSSWALK_PATH):
        if str(row.get("solution") or "").strip() != "accepted_locality_match":
            continue
        source_name, source_code = parse_source_identity(row.get("source_identity", ""))
        if not source_code:
            continue
        target_name = str(row.get("geometry_target") or "").strip()
        target_codes = current_codes_by_name.get(normalized_name(target_name), set())
        if len(target_codes) != 1:
            continue
        target_code = next(iter(target_codes))
        if target_code and target_code != source_code:
            accepted_mergers.append(
                (source_code, source_name, target_code, target_name.rstrip("*"))
            )

    for election in ELECTION_VINTAGES:
        for source_code, source_name, host_code, host_name in accepted_mergers:
            component_codes = sorted({host_code, source_code}, key=numeric_key)
            key = (election, host_code, tuple(component_codes))
            if key in seen:
                continue
            seen.add(key)
            relationships.append(
                {
                    "relationship_id": (
                        f"accepted-locality-merge:{election}:{host_code}:{source_code}"
                    ),
                    "relationship_source": "accepted_historical_locality_merge",
                    "election": election,
                    "host_locality_code": host_code,
                    "component_locality_codes": "|".join(component_codes),
                    "evidence_status": "confirmed",
                    "evidence_method": "reviewed_locality_crosswalk",
                    "relationship_note": (
                        f"The reviewed locality crosswalk treats {source_name} as part of "
                        f"{host_name}."
                    ),
                }
            )

    return relationships


def total_signature(row: dict[str, str]) -> tuple[int, ...]:
    return tuple(integer(row.get(field)) for field in CORE_TOTAL_FIELDS)


def main() -> None:
    metadata_by_vintage: dict[int, list[dict[str, str]]] = {
        vintage: read_csv(
            GEOGRAPHY_DIR / f"statistical_areas_{vintage}.metadata.csv"
        )
        for vintage in sorted(set(ELECTION_VINTAGES.values()))
    }
    claims, hidden = load_existing_claims()
    relationships = load_relationships()

    audit_rows: list[dict[str, Any]] = []
    policy_rows: list[dict[str, Any]] = []

    for election, vintage in ELECTION_VINTAGES.items():
        metadata = metadata_by_vintage[vintage]
        metadata_by_id = {row["stat_area_id"]: row for row in metadata}
        area_ids_by_locality: dict[str, list[str]] = defaultdict(list)
        for row in metadata:
            area_ids_by_locality[clean_code(row.get("locality_code"))].append(
                row["stat_area_id"]
            )
        for area_ids in area_ids_by_locality.values():
            area_ids.sort()

        stat_results = read_csv(
            PUBLIC_DIR / "statistical_area_results" / f"{election.lower()}.csv"
        )
        stat_results_by_id = {row["stat_area_id"]: row for row in stat_results}
        locality_results = read_csv(
            PUBLIC_DIR / "locality_results" / f"{election.lower()}.csv"
        )
        locality_results_by_code: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in locality_results:
            locality_results_by_code[clean_code(row.get("locality_code"))].append(row)

        election_relationships = [
            row for row in relationships if row["election"] == election
        ]
        for relationship in election_relationships:
            host_code = relationship["host_locality_code"]
            component_codes = split_pipe(relationship["component_locality_codes"])
            attached_codes = [code for code in component_codes if code != host_code]
            host_area_ids = area_ids_by_locality.get(host_code, [])
            attached_area_ids = [
                area_id
                for code in attached_codes
                for area_id in area_ids_by_locality.get(code, [])
            ]
            component_area_ids = [*host_area_ids, *attached_area_ids]
            result_area_ids = [
                area_id for area_id in component_area_ids if area_id in stat_results_by_id
            ]
            attached_result_area_ids = [
                area_id for area_id in attached_area_ids if area_id in stat_results_by_id
            ]
            existing_owners = sorted(
                {
                    owner
                    for area_id in component_area_ids
                    for owner in claims.get((election, area_id), set())
                }
            )
            hidden_area_ids = [
                area_id for area_id in component_area_ids if (election, area_id) in hidden
            ]
            locality_result_rows = locality_results_by_code.get(host_code, [])

            status = "review_required"
            explanation = "The relationship does not satisfy an automatic exact-display rule."
            if not host_area_ids:
                status = "not_applicable_host_polygon_absent"
                explanation = "The active historical geography has no polygon for the host locality."
            elif not attached_area_ids:
                status = "not_applicable_component_polygon_absent"
                explanation = "The active historical geography has no separate attached-locality polygon."
            elif existing_owners or hidden_area_ids:
                status = "already_covered_or_claimed"
                explanation = "An existing display policy already owns or hides at least one component."
            elif attached_result_area_ids:
                status = "not_needed_component_has_result"
                explanation = "At least one attached locality polygon already has an independent result."
            elif len(host_area_ids) != 1:
                status = "review_required_host_has_multiple_areas"
                explanation = (
                    "The host locality has multiple statistical areas; merging all of them would "
                    "discard supported detail."
                )
            elif host_area_ids[0] not in stat_results_by_id:
                status = "review_required_host_result_missing"
                explanation = "The sole host polygon has no statistical-area result."
            elif len(locality_result_rows) != 1:
                status = "review_required_host_locality_result_missing_or_duplicated"
                explanation = "The host locality does not have exactly one locality result row."
            elif total_signature(stat_results_by_id[host_area_ids[0]]) != total_signature(
                locality_result_rows[0]
            ):
                status = "review_required_result_total_mismatch"
                explanation = (
                    "The sole host-area result does not equal the complete host-locality result."
                )
            elif relationship["relationship_source"] == (
                "cross_election_join_continuity_candidate"
            ):
                status = "review_candidate_cross_election_join_continuity"
                explanation = (
                    "The geometry and totals satisfy the exact one-area rule, but this "
                    "election has no approved relationship row."
                )
            else:
                status = "approved_exact_display_union"
                explanation = (
                    "The sole host-area result equals the complete locality result, attached "
                    "polygons have no separate result, and no component is owned elsewhere."
                )

            host_result = locality_result_rows[0] if len(locality_result_rows) == 1 else {}
            host_metadata = metadata_by_id.get(host_area_ids[0], {}) if host_area_ids else {}
            host_name_he = str(
                host_result.get("locality_name")
                or host_metadata.get("locality_name_he")
                or host_code
            ).strip()
            host_name_en = str(
                host_metadata.get("locality_name_en") or host_name_he
            ).strip()
            host_area_number = clean_code(host_metadata.get("stat_area_number") or host_metadata.get("stat_2022"))
            component_names_he = "|".join(
                dict.fromkeys(
                    str(metadata_by_id[area_id].get("locality_name_he") or "").strip()
                    for area_id in component_area_ids
                    if area_id in metadata_by_id
                )
            )
            display_id = (
                f"display:joined-locality:{election}:{host_code}:"
                + "-".join(attached_codes)
            )

            audit_rows.append(
                {
                    **relationship,
                    "stat_area_vintage": vintage,
                    "host_locality_name_he": host_name_he,
                    "component_locality_names_he": component_names_he,
                    "host_stat_area_ids": "|".join(host_area_ids),
                    "attached_stat_area_ids": "|".join(attached_area_ids),
                    "component_stat_area_ids": "|".join(component_area_ids),
                    "result_stat_area_ids": "|".join(result_area_ids),
                    "existing_display_owners": "|".join(existing_owners),
                    "hidden_component_ids": "|".join(hidden_area_ids),
                    "host_locality_actual_voters": integer(
                        host_result.get("actual_voters")
                    ),
                    "host_stat_area_actual_voters": sum(
                        integer(stat_results_by_id[area_id].get("actual_voters"))
                        for area_id in host_area_ids
                        if area_id in stat_results_by_id
                    ),
                    "audit_status": status,
                    "audit_explanation": explanation,
                    "generated_display_geography_id": (
                        display_id if status == "approved_exact_display_union" else ""
                    ),
                }
            )

            if status != "approved_exact_display_union":
                continue
            display_name_he = (
                f"{host_name_he} · {host_area_number}" if host_area_number else host_name_he
            )
            display_name_en = (
                f"{host_name_en} · {host_area_number}" if host_area_number else host_name_en
            )
            near_balance = relationship["evidence_method"] == "combined_register_continuity"
            policy_rows.append(
                {
                    "display_geography_id": display_id,
                    "elections": election,
                    "component_stat_area_ids": "|".join(component_area_ids),
                    "aggregation_method": "sum-components",
                    "evidence_group_id": relationship["relationship_id"],
                    "evidence_class": "official_register_attachment_representative" if near_balance else "official_register_attachment_exact",
                    "review_status": "approved-high-confidence",
                    "note": relationship["relationship_note"],
                    "display_locality_code": host_code,
                    "display_locality_name_he": host_name_he,
                    "display_locality_name_en": host_name_en,
                    "display_name_he": display_name_he,
                    "display_name_en": display_name_en,
                    "notice_he": "תוצאה משותפת לפי מרשמי הקלפיות; אין תוצאות נפרדות ליישובים." if near_balance else "",
                    "notice_en": "Combined result inferred from the polling registers; separate locality results are not available." if near_balance else "",
                }
            )

    audit_rows.sort(
        key=lambda row: (
            numeric_key(str(row["election"])[1:]),
            numeric_key(row["host_locality_code"]),
            row["relationship_id"],
        )
    )
    policy_rows.sort(
        key=lambda row: (
            numeric_key(str(row["elections"])[1:]),
            numeric_key(row["display_locality_code"]),
            row["display_geography_id"],
        )
    )
    write_csv(OUTPUT_POLICY_PATH, policy_rows, POLICY_FIELDS)
    write_csv(OUTPUT_AUDIT_PATH, audit_rows)

    summary = {
        "definition": (
            "Reviewed joined localities and accepted historical locality mergers are "
            "checked against the active election geography. Automatic display unions are "
            "limited to one-area hosts whose complete locality result equals the sole area "
            "result and whose attached polygons have no independent result."
        ),
        "relationship_election_cases": len(audit_rows),
        "generated_exact_display_unions": len(policy_rows),
        "status_counts": dict(
            sorted(Counter(row["audit_status"] for row in audit_rows).items())
        ),
        "generated_by_election": dict(
            sorted(Counter(row["elections"] for row in policy_rows).items())
        ),
    }
    OUTPUT_SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
