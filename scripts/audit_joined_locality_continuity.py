#!/usr/bin/env python3
"""Audit recurring joined-locality relationships against election registers.

The reviewed statistical display builder deliberately leaves cross-election
continuity leads unapplied. This script turns those leads into reproducible
decisions. It accepts direct official evidence and tightly bounded continuity;
it never uses address geocoding and never changes ballot-level assignments.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
MANUAL_DIR = ROOT / "data" / "manual"
AUDIT_DIR = ROOT / "data" / "processed" / "audits"
PUBLIC_DIR = ROOT / "data" / "processed" / "public"
GEOGRAPHY_DIR = ROOT / "data" / "processed" / "geographies"

CANDIDATE_PATH = AUDIT_DIR / "reviewed_locality_statistical_display_audit.csv"
JOINED_PATH = MANUAL_DIR / "joined_locality_composites.csv"
K18_REGISTER_PATH = ROOT / "data" / "processed" / "k18_polling_places_extracted_prototype.csv"
K19_REGISTER_PATH = AUDIT_DIR / "k19_large_empty_polling_register_rows.csv"
OUTPUT_PATH = AUDIT_DIR / "joined_locality_continuity_evidence.csv"
SUMMARY_PATH = AUDIT_DIR / "joined_locality_continuity_evidence_summary.json"

ELECTIONS = tuple(f"K{number}" for number in range(17, 26))
MODERN_REGISTER_SOURCES = {
    "K20": "archive_knesset20_tell_the_polls_9_3.xls",
    "K21": "archive_knesset21_kalpies_full_report.xls",
    "K22": "archive_knesset22_kalpies_report_tofes_b_6th_edition_15_9.xlsx",
    "K23": "archive_knesset23_kalpies_report_19_1_20_1.xlsx",
    "K24": "archive_knesset24_kalpies_report_tofes_b_18_3_21.xlsx",
    "K25": "election-25_kalpi-places_kalpies_list_10_7_nagish.xlsx",
}
ARITHMETIC_ELECTIONS = frozenset(MODERN_REGISTER_SOURCES)
DIRECT_MANUAL_METHODS = {
    "exact_eligible_arithmetic",
    "explicit_source_location",
    "under_100_host_delta",
    "official_historical_municipal_membership",
    "mixed_reviewed_evidence",
}
AUTOMATED_METHOD_PREFIX = "automated_"
AUTOMATED_DIRECT_METHODS = {
    "automated_explicit_register_attachment",
    "automated_exact_eligible_arithmetic",
    "automated_unique_source_location",
}
ATTACHED_HOST_RE = re.compile(r"(?P<locality>\d{4})\D+(?P<ballot>\d{3}(?:\.\d+)?)")

OUTPUT_FIELDS = (
    "election",
    "relationship_id",
    "host_locality_code",
    "host_locality_name_he",
    "component_locality_codes",
    "attached_locality_codes",
    "decision_status",
    "decision_confidence",
    "decision_method",
    "decision_explanation",
    "existing_relationships",
    "existing_attached_hosts",
    "explicit_register_hosts",
    "source_location_hosts",
    "source_eligible_by_code",
    "source_component_eligible_total",
    "final_host_eligible",
    "eligible_difference",
    "continuity_evidence",
    "will_apply",
)


@dataclass(frozen=True)
class RegisterRow:
    election: str
    locality_code: str
    ballot_id: str
    eligible: int
    address: str
    place: str
    explicit_host_code: str
    locality_name: str
    source: str


def clean(value: Any) -> str:
    text = str(value or "").strip()
    return "" if text.casefold() == "nan" else text


def clean_code(value: Any) -> str:
    text = clean(value).replace(",", "")
    if not text:
        return ""
    try:
        return str(int(float(text)))
    except ValueError:
        return re.sub(r"\.0+$", "", text).lstrip("0") or "0"


def integer(value: Any) -> int:
    text = clean(value).replace(",", "")
    try:
        return int(round(float(text))) if text else 0
    except ValueError:
        return 0


def election_number(value: str) -> int:
    return int(clean(value).lstrip("Kk"))


def ballot_id(value: Any) -> str:
    text = clean(value)
    if not text:
        return ""
    try:
        number = float(text)
        return str(int(number)) if number.is_integer() else str(number)
    except ValueError:
        return text


def split_pipe(value: Any) -> list[str]:
    return [clean_code(part) for part in clean(value).split("|") if clean(part)]


def join_pipe(values: Iterable[Any]) -> str:
    cleaned = {clean(value) for value in values if clean(value)}
    return "|".join(sorted(cleaned, key=lambda value: (integer(value), value)))


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def normalized_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", clean(value)).casefold()
    return "".join(character for character in text if character.isalnum())


def name_variants(value: Any) -> set[str]:
    text = clean(value).replace("*", "")
    candidates = {text, re.split(r"[()]", text, maxsplit=1)[0].strip()}
    return {
        normalized
        for candidate in candidates
        if len(normalized := normalized_text(candidate)) >= 3
    }


def repaired_header(value: Any) -> str:
    text = str(value)
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def parse_reversed_attachment(value: Any) -> str:
    # K18's extracted attachment cell is in visual order, including its digits.
    match = ATTACHED_HOST_RE.search(clean(value)[::-1])
    return clean_code(match.group("locality")) if match else ""


def parse_modern_attachment(value: Any) -> str:
    match = re.search(r"(?<!\d)0*(\d{1,4})\s*[-\u2013]", clean(value))
    return clean_code(match.group(1)) if match else ""


def load_k18_register() -> list[RegisterRow]:
    rows: list[RegisterRow] = []
    for item in read_csv(K18_REGISTER_PATH):
        locality_code = clean_code(item.get("locality_code_clean"))
        ballot = ballot_id(item.get("kalpi_clean"))
        if not locality_code or not ballot:
            continue
        rows.append(
            RegisterRow(
                election="K18",
                locality_code=locality_code,
                ballot_id=ballot,
                eligible=integer(item.get("eligible_clean")),
                address=clean(item.get("address")),
                place=clean(item.get("place")),
                explicit_host_code=parse_reversed_attachment(item.get("place")),
                locality_name=clean(item.get("locality_name")),
                source=str(K18_REGISTER_PATH.relative_to(ROOT)),
            )
        )
    return rows


def load_k19_register() -> list[RegisterRow]:
    rows: list[RegisterRow] = []
    for item in read_csv(K19_REGISTER_PATH):
        locality_code = clean_code(item.get("locality_code"))
        ballot = ballot_id(item.get("ballot"))
        if not locality_code or not ballot:
            continue
        rows.append(
            RegisterRow(
                election="K19",
                locality_code=locality_code,
                ballot_id=ballot,
                eligible=integer(item.get("eligible_voters")),
                address=clean(item.get("address")),
                place=clean(item.get("place")),
                explicit_host_code=clean_code(item.get("attached_host_locality_code")),
                locality_name=clean(item.get("locality_name")),
                source=str(K19_REGISTER_PATH.relative_to(ROOT)),
            )
        )
    return rows


def modern_column(frame: pd.DataFrame, expected: str, *, required: bool = True) -> str:
    for column in frame.columns:
        if repaired_header(column) == expected:
            return str(column)
    if required:
        raise ValueError(f"Official polling workbook is missing column: {expected}")
    return ""


def load_modern_registers() -> list[RegisterRow]:
    rows: list[RegisterRow] = []
    locality_code_header = "\u05e1\u05de\u05dc \u05d9\u05e9\u05d5\u05d1 \u05d1\u05d7\u05d9\u05e8\u05d5\u05ea"
    locality_name_header = "\u05e9\u05dd \u05d9\u05e9\u05d5\u05d1 \u05d1\u05d7\u05d9\u05e8\u05d5\u05ea"
    ballot_header = "\u05e1\u05de\u05dc \u05e7\u05dc\u05e4\u05d9"
    address_header = "\u05db\u05ea\u05d5\u05d1\u05ea \u05e7\u05dc\u05e4\u05d9"
    place_header = "\u05de\u05e7\u05d5\u05dd \u05e7\u05dc\u05e4\u05d9"
    eligible_header = "\u05d1\u05d5\u05d7\u05e8\u05d9 \u05db\u05e0\u05e1\u05ea \u05d1\u05e4\u05d5\u05e2\u05dc"
    attachment_header = "\u05e6\u05d5\u05e8\u05e4 \u05dc-"

    for election, filename in MODERN_REGISTER_SOURCES.items():
        path = RAW_DIR / filename
        source = pd.read_excel(path, sheet_name="DataSheet", dtype=str).fillna("")
        columns = {
            "locality_code": modern_column(source, locality_code_header),
            "locality_name": modern_column(source, locality_name_header),
            "ballot": modern_column(source, ballot_header),
            "address": modern_column(source, address_header),
            "place": modern_column(source, place_header),
            "eligible": modern_column(source, eligible_header),
            "attachment": modern_column(source, attachment_header, required=False),
        }
        for item in source.to_dict("records"):
            locality_code = clean_code(item.get(columns["locality_code"]))
            ballot = ballot_id(item.get(columns["ballot"]))
            if not locality_code or not ballot:
                continue
            attachment = item.get(columns["attachment"]) if columns["attachment"] else ""
            rows.append(
                RegisterRow(
                    election=election,
                    locality_code=locality_code,
                    ballot_id=ballot,
                    eligible=integer(item.get(columns["eligible"])),
                    address=clean(item.get(columns["address"])),
                    place=clean(item.get(columns["place"])),
                    explicit_host_code=parse_modern_attachment(attachment),
                    locality_name=clean(item.get(columns["locality_name"])),
                    source=str(path.relative_to(ROOT)),
                )
            )
    return rows


def load_register_rows() -> list[RegisterRow]:
    return [*load_k18_register(), *load_k19_register(), *load_modern_registers()]


def load_candidates() -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    for row in read_csv(CANDIDATE_PATH):
        is_candidate = row.get("audit_status") == "review_candidate_cross_election_join_continuity"
        is_applied_automation = clean(row.get("evidence_method")).startswith(
            AUTOMATED_METHOD_PREFIX
        )
        if is_candidate or is_applied_automation:
            candidates.append(row)
    return candidates


def load_locality_results() -> dict[tuple[str, str], dict[str, str]]:
    output: dict[tuple[str, str], dict[str, str]] = {}
    for election in ELECTIONS:
        path = PUBLIC_DIR / "locality_results" / f"{election.lower()}.csv"
        for row in read_csv(path):
            key = (election, clean_code(row.get("locality_code")))
            if key in output:
                raise ValueError(f"Duplicate locality result: {key}")
            output[key] = row
    return output


def collect_names(
    candidates: list[dict[str, str]], register_rows: list[RegisterRow]
) -> dict[str, set[str]]:
    names: dict[str, set[str]] = defaultdict(set)
    for row in read_csv(GEOGRAPHY_DIR / "localities_2022.metadata.csv"):
        names[clean_code(row.get("locality_code"))].update(
            name_variants(row.get("locality_name_he"))
        )
    for election in ELECTIONS:
        for row in read_csv(PUBLIC_DIR / "locality_results" / f"{election.lower()}.csv"):
            names[clean_code(row.get("locality_code"))].update(
                name_variants(row.get("locality_name"))
            )
    for row in candidates:
        names[clean_code(row.get("host_locality_code"))].update(
            name_variants(row.get("host_locality_name_he"))
        )
    for row in register_rows:
        names[row.locality_code].update(name_variants(row.locality_name))
    return names


def relationship_key(row: dict[str, str]) -> tuple[str, str, tuple[str, ...]]:
    election = clean(row.get("election"))
    host = clean_code(row.get("host_locality_code"))
    components = tuple(sorted(set(split_pipe(row.get("component_locality_codes"))), key=integer))
    return election, host, components


def ordered_components(host: str, components: Iterable[str]) -> list[str]:
    return [host, *sorted({code for code in components if code != host}, key=integer)]


def accepted_relationships() -> list[dict[str, str]]:
    return [
        row
        for row in read_csv(JOINED_PATH)
        if clean(row.get("evidence_status")) in {"confirmed", "strong"}
    ]


def approved_maps(
    relationships: list[dict[str, str]],
) -> tuple[
    dict[tuple[str, str], set[str]],
    dict[tuple[str, str], list[dict[str, str]]],
    dict[tuple[str, str, tuple[str, ...]], dict[str, str]],
]:
    hosts_by_component: dict[tuple[str, str], set[str]] = defaultdict(set)
    rows_by_host: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    exact: dict[tuple[str, str, tuple[str, ...]], dict[str, str]] = {}
    for row in relationships:
        election, host, components = relationship_key(row)
        exact[(election, host, components)] = row
        rows_by_host[(election, host)].append(row)
        for code in components:
            if code != host:
                hosts_by_component[(election, code)].add(host)
    return hosts_by_component, rows_by_host, exact


def register_indexes(register_rows: list[RegisterRow]) -> tuple[
    dict[tuple[str, str], list[RegisterRow]],
    dict[tuple[str, str], int],
    dict[tuple[str, str], set[str]],
]:
    rows_by_code: dict[tuple[str, str], list[RegisterRow]] = defaultdict(list)
    eligible_by_ballot: dict[tuple[str, str, str], int] = defaultdict(int)
    explicit_hosts: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in register_rows:
        rows_by_code[(row.election, row.locality_code)].append(row)
        ballot_key = (row.election, row.locality_code, row.ballot_id)
        eligible_by_ballot[ballot_key] = max(eligible_by_ballot[ballot_key], row.eligible)
        if row.explicit_host_code:
            explicit_hosts[(row.election, row.locality_code)].add(row.explicit_host_code)
    eligible_by_code: dict[tuple[str, str], int] = defaultdict(int)
    for (election, locality_code, _), eligible in eligible_by_ballot.items():
        eligible_by_code[(election, locality_code)] += eligible
    return rows_by_code, eligible_by_code, explicit_hosts


def location_host_matches(
    *,
    locality_code: str,
    candidate_hosts: set[str],
    rows: list[RegisterRow],
    names: dict[str, set[str]],
) -> set[str]:
    if not rows:
        return set()
    common_matches: set[str] | None = None
    for row in rows:
        location = normalized_text(f"{row.address} {row.place}")
        if any(variant in location for variant in names.get(locality_code, set())):
            return set()
        matches = {
            host
            for host in candidate_hosts
            if any(variant in location for variant in names.get(host, set()))
        }
        if not matches:
            return set()
        common_matches = matches if common_matches is None else common_matches & matches
    return common_matches or set()


def decision_row(candidate: dict[str, str]) -> dict[str, Any]:
    components = split_pipe(candidate.get("component_locality_codes"))
    host = clean_code(candidate.get("host_locality_code"))
    return {
        "election": clean(candidate.get("election")),
        "relationship_id": clean(candidate.get("relationship_id")),
        "host_locality_code": host,
        "host_locality_name_he": clean(candidate.get("host_locality_name_he")),
        "component_locality_codes": join_pipe(components),
        "attached_locality_codes": join_pipe(code for code in components if code != host),
        "decision_status": "insufficient_evidence",
        "decision_confidence": "review",
        "decision_method": "insufficient_election_specific_evidence",
        "decision_explanation": "No strict automatic rule proved this election-specific join.",
        "existing_relationships": "",
        "existing_attached_hosts": "",
        "explicit_register_hosts": "",
        "source_location_hosts": "",
        "source_eligible_by_code": "",
        "source_component_eligible_total": 0,
        "final_host_eligible": 0,
        "eligible_difference": "",
        "continuity_evidence": "",
        "will_apply": "false",
    }


def set_decision(
    row: dict[str, Any],
    *,
    status: str,
    confidence: str,
    method: str,
    explanation: str,
    apply: bool = False,
) -> None:
    row.update(
        {
            "decision_status": status,
            "decision_confidence": confidence,
            "decision_method": method,
            "decision_explanation": explanation,
            "will_apply": str(apply).lower(),
        }
    )


def direct_decisions(
    candidates: list[dict[str, str]],
    relationships: list[dict[str, str]],
    register_rows: list[RegisterRow],
    locality_results: dict[tuple[str, str], dict[str, str]],
    names: dict[str, set[str]],
) -> tuple[list[dict[str, Any]], dict[tuple[str, str], set[str]]]:
    approved_hosts, rows_by_host, exact_relationships = approved_maps(relationships)
    rows_by_code, eligible_by_code, explicit_hosts = register_indexes(register_rows)
    candidate_hosts: dict[tuple[str, str], set[str]] = defaultdict(set)
    for candidate in candidates:
        election, host, components = relationship_key(candidate)
        for code in components:
            if code != host:
                candidate_hosts[(election, code)].add(host)

    output: list[dict[str, Any]] = []
    exact_arithmetic_candidates: dict[tuple[str, str], set[str]] = defaultdict(set)
    provisional_exact: set[tuple[str, str, tuple[str, ...]]] = set()
    for candidate in candidates:
        election, host, components = relationship_key(candidate)
        attached = [code for code in components if code != host]
        final_host = locality_results.get((election, host), {})
        final_eligible = integer(final_host.get("eligible_voters"))
        source_values = {code: eligible_by_code.get((election, code), 0) for code in components}
        source_total = sum(source_values.values())
        if (
            election in ARITHMETIC_ELECTIONS
            and final_eligible > 0
            and all(source_values.get(code, 0) > 0 for code in attached)
            and source_values.get(host, 0) > 0
            and source_total == final_eligible
        ):
            provisional_exact.add((election, host, components))
            for code in attached:
                exact_arithmetic_candidates[(election, code)].add(host)

    for candidate in candidates:
        election, host, components = relationship_key(candidate)
        attached = [code for code in components if code != host]
        row = decision_row(candidate)
        exact_existing = exact_relationships.get((election, host, components))
        host_rows = rows_by_host.get((election, host), [])
        existing_hosts = {code: approved_hosts.get((election, code), set()) for code in attached}
        explicit = {code: explicit_hosts.get((election, code), set()) for code in attached}
        location = {
            code: location_host_matches(
                locality_code=code,
                candidate_hosts=candidate_hosts[(election, code)],
                rows=rows_by_code.get((election, code), []),
                names=names,
            )
            for code in attached
        }
        source_values = {code: eligible_by_code.get((election, code), 0) for code in components}
        source_total = sum(source_values.values())
        final_host = locality_results.get((election, host), {})
        final_eligible = integer(final_host.get("eligible_voters"))
        standalone = [code for code in attached if (election, code) in locality_results]

        row["existing_relationships"] = ";".join(
            clean(item.get("joined_composite_id")) for item in host_rows
        )
        row["existing_attached_hosts"] = ";".join(
            f"{code}:{join_pipe(hosts)}" for code, hosts in existing_hosts.items() if hosts
        )
        row["explicit_register_hosts"] = ";".join(
            f"{code}:{join_pipe(hosts)}" for code, hosts in explicit.items() if hosts
        )
        row["source_location_hosts"] = ";".join(
            f"{code}:{join_pipe(hosts)}" for code, hosts in location.items() if hosts
        )
        row["source_eligible_by_code"] = ";".join(
            f"{code}:{source_values[code]}" for code in components
        )
        row["source_component_eligible_total"] = source_total
        row["final_host_eligible"] = final_eligible
        row["eligible_difference"] = final_eligible - source_total if final_eligible else ""

        if exact_existing:
            method = clean(exact_existing.get("evidence_method"))
            set_decision(
                row,
                status=(
                    "approved_existing_automation"
                    if method.startswith(AUTOMATED_METHOD_PREFIX)
                    else "already_approved_existing_relationship"
                ),
                confidence=clean(exact_existing.get("evidence_status")) or "confirmed",
                method=method or "existing_reviewed_relationship",
                explanation=(
                    clean(exact_existing.get("note"))
                    or "This exact election-specific relationship is already approved."
                ).split(" Evidence: ", 1)[0],
            )
        elif standalone:
            set_decision(
                row,
                status="contradicted_attached_locality_has_result",
                confidence="confirmed",
                method="standalone_final_locality_result",
                explanation="At least one attached locality has its own final locality result: " + join_pipe(standalone),
            )
        elif any(hosts - {host} for hosts in existing_hosts.values()):
            set_decision(
                row,
                status="contradicted_existing_relationship",
                confidence="confirmed",
                method="existing_reviewed_relationship",
                explanation="A reviewed relationship assigns an attached locality to a different host.",
            )
        elif all(existing_hosts.get(code) == {host} for code in attached):
            set_decision(
                row,
                status="already_approved_existing_relationship",
                confidence="confirmed",
                method="existing_reviewed_relationship",
                explanation="All attached localities are already included under this host by a broader reviewed relationship.",
            )
        elif host_rows and any(not existing_hosts.get(code) for code in attached):
            set_decision(
                row,
                status="insufficient_existing_host_requires_extension",
                confidence="review",
                method="existing_host_relationship_requires_extension",
                explanation="This host already has a different reviewed union; extending it requires a separate review.",
            )
        elif any(hosts and hosts != {host} for hosts in explicit.values()):
            set_decision(
                row,
                status="contradicted_explicit_register_attachment",
                confidence="confirmed",
                method="explicit_official_register_attachment",
                explanation="The official register explicitly attaches at least one component to another host.",
            )
        elif attached and all(explicit.get(code) == {host} for code in attached):
            set_decision(
                row,
                status="approved_explicit_register_attachment",
                confidence="confirmed",
                method="automated_explicit_register_attachment",
                explanation="Every attached locality explicitly names this host in the official election register.",
                apply=True,
            )
        elif (election, host, components) in provisional_exact and all(
            exact_arithmetic_candidates[(election, code)] == {host} for code in attached
        ):
            set_decision(
                row,
                status="approved_exact_eligible_arithmetic",
                confidence="confirmed",
                method="automated_exact_eligible_arithmetic",
                explanation="The complete official register total uniquely equals the published host eligible-voter total.",
                apply=True,
            )
        elif attached and all(location.get(code) == {host} for code in attached):
            set_decision(
                row,
                status="approved_unique_source_location",
                confidence="strong",
                method="automated_unique_source_location",
                explanation="Every attached register row uniquely names this host locality as its polling location.",
                apply=True,
            )
        output.append(row)
    return output, explicit_hosts


def direct_observations(
    relationships: list[dict[str, str]],
    decisions: list[dict[str, Any]],
    explicit_hosts: dict[tuple[str, str], set[str]],
) -> dict[str, dict[int, set[str]]]:
    observations: dict[str, dict[int, set[str]]] = defaultdict(lambda: defaultdict(set))
    for (election, component), hosts in explicit_hosts.items():
        if len(hosts) == 1:
            observations[component][election_number(election)].update(hosts)
    for row in relationships:
        method = clean(row.get("evidence_method"))
        if method not in DIRECT_MANUAL_METHODS and method not in AUTOMATED_DIRECT_METHODS:
            continue
        election, host, components = relationship_key(row)
        for component in components:
            if component != host:
                observations[component][election_number(election)].add(host)
    for row in decisions:
        if not clean(row.get("decision_status")).startswith("approved_"):
            continue
        if row.get("will_apply") != "true":
            continue
        host = clean_code(row.get("host_locality_code"))
        election = election_number(clean(row.get("election")))
        for component in split_pipe(row.get("attached_locality_codes")):
            observations[component][election].add(host)
    return observations


def continuity_for_component(
    *, component: str, host: str, election: int, observations: dict[str, dict[int, set[str]]]
) -> tuple[str, str]:
    history = observations.get(component, {})
    before = sorted(number for number in history if number < election and len(history[number]) == 1)
    after = sorted(number for number in history if number > election and len(history[number]) == 1)
    previous = before[-1] if before else None
    following = after[0] if after else None
    if previous is not None and following is not None:
        previous_host = next(iter(history[previous]))
        following_host = next(iter(history[following]))
        evidence = f"{component}:K{previous}->{previous_host},K{following}->{following_host}"
        if previous_host == following_host == host:
            return "bracketed", evidence
        if previous_host == following_host != host:
            return "contradicted", evidence
        return "transition", evidence
    if len(after) >= 2 and after[1] == after[0] + 1:
        first_host = next(iter(history[after[0]]))
        second_host = next(iter(history[after[1]]))
        evidence = f"{component}:K{after[0]}->{first_host},K{after[1]}->{second_host}"
        if first_host == second_host == host:
            return "backward", evidence
        if first_host == second_host != host:
            return "contradicted", evidence
    return "insufficient", ""


def apply_continuity(
    decisions: list[dict[str, Any]], observations: dict[str, dict[int, set[str]]]
) -> None:
    for row in decisions:
        preserve_existing = (
            row["decision_status"] == "approved_existing_automation"
            and "continuity" in row["decision_method"]
        )
        if row["decision_status"] != "insufficient_evidence" and not preserve_existing:
            continue
        election = election_number(row["election"])
        host = clean_code(row["host_locality_code"])
        outcomes = [
            continuity_for_component(
                component=component,
                host=host,
                election=election,
                observations=observations,
            )
            for component in split_pipe(row["attached_locality_codes"])
        ]
        row["continuity_evidence"] = ";".join(evidence for _, evidence in outcomes if evidence)
        kinds = {kind for kind, _ in outcomes}
        if preserve_existing:
            if not outcomes or not kinds <= {"bracketed", "backward"}:
                raise ValueError(
                    "Applied automated continuity no longer has its strict source anchors: "
                    f"{row['election']} {row['host_locality_code']} "
                    f"{row['attached_locality_codes']}"
                )
            continue
        if outcomes and kinds <= {"bracketed", "backward"}:
            if kinds == {"bracketed"}:
                method = "automated_bracketed_register_continuity"
            elif kinds == {"backward"}:
                method = "automated_backward_register_continuity"
            else:
                method = "automated_strict_register_continuity"
            set_decision(
                row,
                status="approved_strict_cross_election_continuity",
                confidence="strong",
                method=method,
                explanation="Each attached locality has the same reviewed host in strict surrounding or adjacent later register evidence.",
                apply=True,
            )
        elif "contradicted" in kinds:
            set_decision(
                row,
                status="contradicted_cross_election_evidence",
                confidence="confirmed",
                method="cross_election_register_contradiction",
                explanation="The nearest strict register evidence consistently assigns at least one component to another host.",
            )


def resolve_proposal_conflicts(decisions: list[dict[str, Any]]) -> None:
    proposed = [row for row in decisions if row["will_apply"] == "true"]
    by_host: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    by_component: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in proposed:
        by_host[(row["election"], row["host_locality_code"])].append(row)
        for component in split_pipe(row["attached_locality_codes"]):
            by_component[(row["election"], component)].append(row)

    conflicted: set[int] = set()
    for rows in by_host.values():
        component_sets = {row["component_locality_codes"] for row in rows}
        if len(component_sets) > 1:
            conflicted.update(id(row) for row in rows)
    for rows in by_component.values():
        hosts = {row["host_locality_code"] for row in rows}
        component_sets = {row["component_locality_codes"] for row in rows}
        if len(hosts) > 1 or len(component_sets) > 1:
            conflicted.update(id(row) for row in rows)
    for row in proposed:
        if id(row) not in conflicted:
            continue
        set_decision(
            row,
            status="insufficient_competing_automatic_proposals",
            confidence="review",
            method="automatic_proposal_conflict",
            explanation="More than one automatic union would claim the same host or attached polygon in this election.",
        )


def append_approvals(decisions: list[dict[str, Any]]) -> int:
    rows = read_csv(JOINED_PATH)
    fields = list(rows[0]) if rows else [
        "joined_composite_id",
        "election",
        "host_locality_code",
        "host_kalpi",
        "component_locality_codes",
        "evidence_status",
        "evidence_method",
        "note",
        "display_mode",
    ]
    existing = {relationship_key(row) for row in rows}
    decisions_by_key = {relationship_key(row): row for row in decisions}
    changed = False
    for row in rows:
        if not clean(row.get("evidence_method")).startswith(AUTOMATED_METHOD_PREFIX):
            continue
        _, host, components = relationship_key(row)
        expected_components = "|".join(ordered_components(host, components))
        if clean(row.get("component_locality_codes")) != expected_components:
            row["component_locality_codes"] = expected_components
            changed = True
        decision = decisions_by_key.get(relationship_key(row))
        if not decision:
            continue
        evidence = clean(decision.get("continuity_evidence"))
        base_note = clean(decision.get("decision_explanation")).split(" Evidence: ", 1)[0]
        expected_note = f"{base_note} Evidence: {evidence}." if evidence else base_note
        if clean(row.get("note")) != expected_note:
            row["note"] = expected_note
            changed = True
    additions: list[dict[str, Any]] = []
    for decision in decisions:
        if decision["will_apply"] != "true":
            continue
        key = relationship_key(decision)
        if key in existing:
            continue
        election, host, components = key
        attached = [code for code in components if code != host]
        additions.append(
            {
                "joined_composite_id": (
                    f"composite:auto-{election.lower()}-{host}-" + "-".join(attached)
                ),
                "election": election,
                "host_locality_code": host,
                "host_kalpi": "",
                "component_locality_codes": "|".join(ordered_components(host, components)),
                "evidence_status": decision["decision_confidence"],
                "evidence_method": decision["decision_method"],
                "note": (
                    f"{decision['decision_explanation']} Evidence: "
                    f"{decision['continuity_evidence']}."
                    if decision["continuity_evidence"]
                    else decision["decision_explanation"]
                ),
                "display_mode": "",
            }
        )
        existing.add(key)
    if not additions and not changed:
        return 0
    rows.extend(additions)
    rows.sort(
        key=lambda row: (
            election_number(clean(row.get("election"))),
            integer(row.get("host_locality_code")),
            clean(row.get("component_locality_codes")),
        )
    )
    write_csv(JOINED_PATH, rows, fields)
    return len(additions)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Append only conflict-free automatic approvals to the reviewed relationship table.",
    )
    args = parser.parse_args()

    candidates = load_candidates()
    if not candidates:
        raise SystemExit(
            "No continuity candidates found. Run build_reviewed_locality_statistical_displays.py first."
        )
    relationships = accepted_relationships()
    register_rows = load_register_rows()
    locality_results = load_locality_results()
    names = collect_names(candidates, register_rows)
    decisions, explicit_hosts = direct_decisions(
        candidates, relationships, register_rows, locality_results, names
    )
    observations = direct_observations(relationships, decisions, explicit_hosts)
    apply_continuity(decisions, observations)
    resolve_proposal_conflicts(decisions)
    decisions.sort(
        key=lambda row: (
            election_number(row["election"]),
            integer(row["host_locality_code"]),
            row["component_locality_codes"],
        )
    )
    write_csv(OUTPUT_PATH, decisions, OUTPUT_FIELDS)

    additions = append_approvals(decisions) if args.apply else 0
    summary = {
        "definition": (
            "Election-specific review of recurring joined-locality display leads. "
            "Only direct official register evidence, unique exact eligible arithmetic, "
            "or strict bounded continuity can be applied automatically."
        ),
        "candidate_cases": len(decisions),
        "decision_counts": dict(sorted(Counter(row["decision_status"] for row in decisions).items())),
        "automatic_approvals": sum(row["will_apply"] == "true" for row in decisions),
        "approved_automation_present": sum(
            row["decision_status"] == "approved_existing_automation" for row in decisions
        ),
        "applied_rows": additions,
        "output": str(OUTPUT_PATH.relative_to(ROOT)),
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
