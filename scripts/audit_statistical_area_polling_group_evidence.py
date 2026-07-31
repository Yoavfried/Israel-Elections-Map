from __future__ import annotations

import json
import sys
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

LOCAL_AUDIT_PYTHON = Path(__file__).resolve().parents[1] / ".local" / "python-audit"
if LOCAL_AUDIT_PYTHON.exists():
    sys.path.insert(0, str(LOCAL_AUDIT_PYTHON))

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
ASSIGNMENTS = PROCESSED / "assignments"
RESULTS = PROCESSED / "normalized" / "ballot_votes_wide"
AUDIT_DIR = PROCESSED / "audits"
OUTPUT_SITES = AUDIT_DIR / "statistical_area_polling_group_sites.csv"
OUTPUT_COMPONENTS = AUDIT_DIR / "statistical_area_polling_group_components.csv"
OUTPUT_AREAS = AUDIT_DIR / "statistical_area_polling_group_area_evidence.csv"
OUTPUT_SUMMARY = AUDIT_DIR / "statistical_area_polling_group_evidence_summary.json"


@dataclass(frozen=True)
class Layout:
    locality: int
    locality_name: int | None
    ballot: int
    site: int | None
    address: int | None
    place: int | None
    eligible: int


@dataclass(frozen=True)
class Source:
    filename: str
    layout: Layout
    kind: str = "excel"


@dataclass(frozen=True)
class ElectionSources:
    planned: Source
    final: Source | None
    evidence: str


SOURCES = {
    "K20": ElectionSources(
        planned=Source(
            "archive_knesset20_tell_the_polls_9_3.xls",
            Layout(2, 3, 4, None, 5, 6, 10),
        ),
        final=Source(
            "archive_knesset20_tell_the_polls_9_3.xls",
            Layout(2, 3, 4, None, 5, 6, 10),
        ),
        evidence="official_post_balance_register_only",
    ),
    "K21": ElectionSources(
        planned=Source(
            "archive_knesset21_ballots_table.csv",
            Layout(1, None, 2, 3, None, 4, 14),
            "csv",
        ),
        final=Source(
            "archive_knesset21_kalpies_full_report.xls",
            Layout(2, 3, 4, 5, 6, 7, 11),
        ),
        evidence="official_pre_and_post_balance_registers",
    ),
    "K22": ElectionSources(
        planned=Source(
            "archive_knesset22_kalpies_report_tofes_b_6th_edition_15_9.xlsx",
            Layout(2, 3, 4, 5, 6, 7, 11),
        ),
        final=Source(
            "archive_knesset22_kalpies_report_tofes_b_6th_edition_15_9.xlsx",
            Layout(2, 3, 4, 5, 6, 7, 11),
        ),
        evidence="official_post_balance_register_only",
    ),
    "K23": ElectionSources(
        planned=Source(
            "archive_knesset23_kalpies_report_19_1_20_1.xlsx",
            Layout(5, 6, 9, 10, 11, 12, 21),
        ),
        final=Source(
            "archive_knesset23_kalpies_report_19_1_20_1.xlsx",
            Layout(5, 6, 9, 10, 11, 12, 21),
        ),
        evidence="official_post_balance_register_with_ags",
    ),
    "K24": ElectionSources(
        planned=Source(
            "archive_knesset24_kalpies_report_tofes_a_25_12_20.xlsx",
            Layout(2, 3, 4, 5, 6, 7, 10),
        ),
        final=Source(
            "archive_knesset24_kalpies_report_tofes_b_18_3_21.xlsx",
            Layout(2, 3, 4, 5, 6, 7, 10),
        ),
        evidence="official_pre_and_post_balance_registers",
    ),
    "K25": ElectionSources(
        planned=Source(
            "election-25_kalpi-places_kalpies_list_10_7_nagish.xlsx",
            Layout(2, 3, 4, 5, 6, 7, 10),
        ),
        final=None,
        evidence="official_pre_balance_register_and_final_results",
    ),
}


def clean(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text


def integer(value: Any) -> int:
    text = clean(value).replace(",", "")
    if not text:
        return 0
    try:
        return int(Decimal(text))
    except (InvalidOperation, ValueError):
        return 0


def ballot_base(value: Any) -> str:
    return clean(value).split(".", 1)[0]


def text_key(value: Any) -> str:
    text = unicodedata.normalize("NFKC", clean(value)).lower()
    return "".join(character for character in text if character.isalnum())


def pipe(values: Any) -> str:
    return "|".join(sorted({clean(value) for value in values if clean(value)}))


def read_source(source: Source) -> pd.DataFrame:
    path = RAW / source.filename
    if source.kind == "csv":
        frame = pd.read_csv(path, dtype=str, encoding="cp1255").fillna("")
    else:
        frame = pd.read_excel(path, sheet_name="DataSheet", dtype=str).fillna("")

    layout = source.layout
    output = pd.DataFrame(
        {
            "locality_code": frame.iloc[:, layout.locality].map(clean),
            "locality_name": (
                frame.iloc[:, layout.locality_name].map(clean)
                if layout.locality_name is not None
                else ""
            ),
            "source_kalpi": frame.iloc[:, layout.ballot].map(clean),
            "site_id": (
                frame.iloc[:, layout.site].map(clean)
                if layout.site is not None
                else ""
            ),
            "address": (
                frame.iloc[:, layout.address].map(clean)
                if layout.address is not None
                else ""
            ),
            "place": (
                frame.iloc[:, layout.place].map(clean)
                if layout.place is not None
                else ""
            ),
            "eligible": frame.iloc[:, layout.eligible].map(integer),
        }
    )
    output = output.loc[
        output["locality_code"].ne("") & output["source_kalpi"].ne("")
    ].copy()
    output["ballot_base"] = output["source_kalpi"].map(ballot_base)
    output["location_key"] = (
        output["address"].map(text_key) + "|" + output["place"].map(text_key)
    )
    output["site_key"] = output["site_id"].where(
        output["site_id"].ne(""), output["location_key"]
    )
    if output["site_key"].eq("").any():
        raise ValueError(f"{source.filename} contains rows without a site identity")
    return output


class UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def add(self, value: str) -> None:
        self.parent.setdefault(value, value)

    def find(self, value: str) -> str:
        self.add(value)
        root = value
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[value] != value:
            parent = self.parent[value]
            self.parent[value] = root
            value = parent
        return root

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def unique_sets(
    frame: pd.DataFrame, key: str, value: str
) -> dict[str, list[str]]:
    return (
        frame.loc[frame[key].ne("") & frame[value].ne("")]
        .groupby(key)[value]
        .agg(lambda values: sorted(set(values)))
        .to_dict()
    )


def link_site_components(
    planned: pd.DataFrame, final: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    planned = planned.copy()
    final = final.copy()
    graph = UnionFind()
    for site in set(planned["site_key"]):
        graph.add(f"p:{site}")
    for site in set(final["site_key"]):
        graph.add(f"f:{site}")

    for site in set(planned["site_key"]) & set(final["site_key"]):
        graph.union(f"p:{site}", f"f:{site}")

    planned_sites_by_base = unique_sets(planned, "ballot_base", "site_key")
    final_sites_by_base = unique_sets(final, "ballot_base", "site_key")
    for base in set(planned_sites_by_base) & set(final_sites_by_base):
        for planned_site in planned_sites_by_base[base]:
            for final_site in final_sites_by_base[base]:
                graph.union(f"p:{planned_site}", f"f:{final_site}")

    planned_sites_by_location = unique_sets(planned, "location_key", "site_key")
    final_sites_by_location = unique_sets(final, "location_key", "site_key")
    for location in set(planned_sites_by_location) & set(final_sites_by_location):
        if location == "|":
            continue
        for planned_site in planned_sites_by_location[location]:
            for final_site in final_sites_by_location[location]:
                graph.union(f"p:{planned_site}", f"f:{final_site}")

    planned["site_component"] = planned["site_key"].map(
        lambda value: graph.find(f"p:{value}")
    )
    final["site_component"] = final["site_key"].map(
        lambda value: graph.find(f"f:{value}")
    )
    return planned, final


def result_site(
    results: pd.DataFrame, final_register: pd.DataFrame
) -> pd.DataFrame:
    results = results.copy()
    exact = unique_sets(final_register, "source_kalpi", "site_component")
    by_base = unique_sets(final_register, "ballot_base", "site_component")

    def lookup(row: pd.Series) -> str:
        exact_sites = exact.get(row["source_kalpi"], [])
        if len(exact_sites) == 1:
            return exact_sites[0]
        base_sites = by_base.get(row["ballot_base"], [])
        return base_sites[0] if len(base_sites) == 1 else ""

    results["site_component"] = results.apply(lookup, axis=1)
    return results


def balance_class(difference: int, planned: int) -> str:
    if difference == 0:
        return "exact"
    if abs(difference) <= 3:
        return "within_3"
    if planned and abs(difference) / planned <= 0.005:
        return "within_half_percent"
    return "mismatch"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    crosswalk = pd.read_csv(
        ASSIGNMENTS / "historical_ballot_crosswalk.csv",
        dtype=str,
        encoding="utf-8-sig",
    ).fillna("")
    crosswalk["locality_code"] = crosswalk["locality_code"].map(clean)
    crosswalk["ballot_base"] = crosswalk["ballot_number"].map(ballot_base)

    assignments = pd.read_csv(
        ASSIGNMENTS / "historical_ballot_assignments.csv",
        dtype=str,
        encoding="utf-8-sig",
    ).fillna("")
    assignment_lookup = assignments.set_index("source_row_uid")[
        "stat_area_id"
    ].to_dict()

    metadata = pd.read_csv(
        PROCESSED / "geographies" / "statistical_areas_2011.metadata.csv",
        dtype=str,
        encoding="utf-8-sig",
    ).fillna("")
    metadata["locality_code"] = metadata["locality_code"].map(clean)
    locality_area_counts = metadata.groupby("locality_code")[
        "stat_area_id"
    ].nunique()
    multi_area_localities = set(locality_area_counts[locality_area_counts > 1].index)
    public_area_ids: dict[str, set[str]] = {}
    for election in SOURCES:
        public = pd.read_csv(
            PROCESSED
            / "public"
            / "statistical_area_results"
            / f"{election.lower()}.csv",
            dtype=str,
            encoding="utf-8-sig",
        ).fillna("")
        public_area_ids[election] = set(public["stat_area_id"])

    site_rows: list[dict[str, Any]] = []
    area_context: dict[tuple[str, str, str], dict[str, Any]] = {}
    ambiguous_edges: list[dict[str, Any]] = []

    for election, config in SOURCES.items():
        planned_all = read_source(config.planned)
        final_all = (
            planned_all.copy()
            if config.final is None or config.final == config.planned
            else read_source(config.final)
        )
        can_test_aggregates = not config.evidence.startswith(
            "official_post_balance_register"
        )
        election_crosswalk = crosswalk.loc[crosswalk["election"].eq(election)].copy()

        result_rows = pd.read_csv(
            RESULTS / f"{election.lower()}_ballot_votes.csv",
            dtype=str,
            encoding="utf-8-sig",
        ).fillna("")
        result_rows["source_locality_code"] = result_rows[
            "source_locality_code"
        ].map(clean)
        result_rows["source_kalpi"] = result_rows["source_kalpi"].map(clean)
        result_rows["ballot_base"] = result_rows["source_kalpi"].map(ballot_base)
        result_rows["eligible_voters"] = result_rows["eligible_voters"].map(integer)
        result_rows["actual_voters"] = result_rows["actual_voters"].map(integer)
        result_rows["current_stat_area_id"] = result_rows["source_row_uid"].map(
            assignment_lookup
        ).fillna("")

        locality_codes = sorted(
            (
                set(planned_all["locality_code"])
                & set(election_crosswalk["locality_code"])
                & multi_area_localities
            )
            - {""}
        )
        for locality_code in locality_codes:
            planned = planned_all.loc[
                planned_all["locality_code"].eq(locality_code)
            ].copy()
            final_register = final_all.loc[
                final_all["locality_code"].eq(locality_code)
            ].copy()
            locality_crosswalk = election_crosswalk.loc[
                election_crosswalk["locality_code"].eq(locality_code)
            ].copy()

            area_by_base = (
                locality_crosswalk.groupby("ballot_base")["stat_area_id"]
                .agg(lambda values: sorted(set(value for value in values if value)))
                .to_dict()
            )
            planned["stat_area_id"] = planned["ballot_base"].map(
                lambda base: (
                    area_by_base.get(base, [""])[0]
                    if len(area_by_base.get(base, [])) == 1
                    else ""
                )
            )

            planned, final_register = link_site_components(planned, final_register)
            locality_results = result_rows.loc[
                result_rows["source_locality_code"].eq(locality_code)
            ].copy()
            locality_results = result_site(locality_results, final_register)
            active_result_bases = set(locality_results["ballot_base"])

            locality_name = pipe(
                list(planned["locality_name"])
                + list(final_register["locality_name"])
                + list(
                    locality_crosswalk.get(
                        "locality_name", pd.Series(dtype=str)
                    )
                )
            )
            found_planned_bases = set(planned["ballot_base"])
            missing_crosswalk = locality_crosswalk.loc[
                ~locality_crosswalk["ballot_base"].isin(found_planned_bases)
                & locality_crosswalk["ballot_base"].isin(active_result_bases)
            ]
            missing_by_area = missing_crosswalk.groupby("stat_area_id").size().to_dict()
            for area_id, missing_count in missing_by_area.items():
                if not area_id:
                    continue
                area_context.setdefault(
                    (election, locality_code, area_id),
                    {
                        "election": election,
                        "locality_code": locality_code,
                        "locality_name": locality_name,
                        "stat_area_id": area_id,
                        "site_ids": set(),
                        "ambiguous_site_ids": set(),
                        "missing_crosswalk_ballots": int(missing_count),
                    },
                )

            all_components = sorted(
                (set(planned["site_component"]) | set(locality_results["site_component"]))
                - {""}
            )
            for site_number, component in enumerate(all_components, start=1):
                planned_site = planned.loc[
                    planned["site_component"].eq(component)
                    & planned["stat_area_id"].ne("")
                ].copy()
                final_site = locality_results.loc[
                    locality_results["site_component"].eq(component)
                ].copy()
                final_register_site = final_register.loc[
                    final_register["site_component"].eq(component)
                ].copy()
                if planned_site.empty and final_site.empty:
                    continue

                planned_by_base = (
                    planned_site.groupby("ballot_base")
                    .agg(
                        planned_eligible=("eligible", "sum"),
                        planned_has_unsplit=(
                            "source_kalpi",
                            lambda values: int(
                                any(
                                    clean(value) == ballot_base(clean(value))
                                    for value in values
                                )
                            ),
                        ),
                        stat_area_count=("stat_area_id", "nunique"),
                        stat_area_id=(
                            "stat_area_id",
                            lambda values: pipe(values),
                        ),
                    )
                    .reset_index()
                )
                final_by_base = (
                    final_site.groupby("ballot_base")
                    .agg(
                        final_eligible=("eligible_voters", "sum"),
                        final_has_unsplit=(
                            "source_kalpi",
                            lambda values: int(
                                any(
                                    clean(value) == ballot_base(clean(value))
                                    for value in values
                                )
                            ),
                        ),
                    )
                    .reset_index()
                )
                base_comparison = planned_by_base.merge(
                    final_by_base,
                    on="ballot_base",
                    how="inner",
                    validate="one_to_one",
                )
                base_comparison["difference"] = (
                    base_comparison["final_eligible"]
                    - base_comparison["planned_eligible"]
                )
                preserved_bases = set(
                    base_comparison.loc[
                        base_comparison["stat_area_count"].eq(1)
                        & (
                            (
                                base_comparison["planned_has_unsplit"].astype(int).eq(1)
                                & base_comparison["final_has_unsplit"].astype(int).eq(1)
                            )
                            | base_comparison["difference"].abs().le(3)
                        ),
                        "ballot_base",
                    ]
                )

                residual_planned = planned_site.loc[
                    ~planned_site["ballot_base"].isin(preserved_bases)
                ]
                residual_final = final_site.loc[
                    ~final_site["ballot_base"].isin(preserved_bases)
                ]
                all_area_ids = sorted(set(planned_site["stat_area_id"]) - {""})
                residual_area_ids = sorted(
                    set(residual_planned["stat_area_id"]) - {""}
                )
                residual_area_planned_eligible = {
                    area_id: int(group["eligible"].sum())
                    for area_id, group in residual_planned.groupby("stat_area_id")
                    if area_id
                }
                planned_residual_eligible = int(residual_planned["eligible"].sum())
                final_residual_eligible = int(
                    residual_final["eligible_voters"].sum()
                )
                difference = final_residual_eligible - planned_residual_eligible
                residual_balance = balance_class(
                    difference, planned_residual_eligible
                )
                current_hosts = sorted(
                    set(residual_final["current_stat_area_id"]) - {""}
                )
                hosts_outside = sorted(set(current_hosts) - set(residual_area_ids))
                unmapped_planned_rows = int(
                    planned.loc[
                        planned["site_component"].eq(component)
                        & planned["stat_area_id"].eq("")
                        & planned["ballot_base"].ne("990")
                    ].shape[0]
                )
                if config.final is None:
                    final_register_balance = "not_available"
                    final_register_difference = 0
                    final_register_missing_result_rows = 0
                    final_result_rows_missing_register = 0
                else:
                    final_register_difference = int(
                        final_site["eligible_voters"].sum()
                        - final_register_site["eligible"].sum()
                    )
                    final_register_balance = balance_class(
                        final_register_difference,
                        int(final_register_site["eligible"].sum()),
                    )
                    final_register_ballots = set(
                        final_register_site["source_kalpi"]
                    )
                    final_result_ballots = set(final_site["source_kalpi"])
                    final_register_missing_result_rows = len(
                        final_register_ballots - final_result_ballots
                    )
                    final_result_rows_missing_register = len(
                        final_result_ballots - final_register_ballots
                    )

                if not can_test_aggregates and len(residual_area_ids) > 1:
                    classification = "post_balance_only_cannot_test_aggregate"
                elif len(all_area_ids) <= 1:
                    classification = "single_area_site"
                elif len(residual_area_ids) <= 1:
                    classification = "multi_area_fully_separable"
                elif residual_balance in {"exact", "within_3"}:
                    classification = "multi_area_residual_closed"
                elif residual_balance == "within_half_percent":
                    classification = "multi_area_residual_near_balance"
                else:
                    classification = "multi_area_residual_mismatch"
                if hosts_outside or unmapped_planned_rows:
                    classification += "_with_open_evidence"

                site_id = f"{election}:{locality_code}:{site_number}"
                site_rows.append(
                    {
                        "site_audit_id": site_id,
                        "election": election,
                        "locality_code": locality_code,
                        "locality_name": locality_name,
                        "source_evidence": config.evidence,
                        "classification": classification,
                        "planned_site_ids": pipe(
                            planned.loc[
                                planned["site_component"].eq(component), "site_id"
                            ]
                        ),
                        "final_site_ids": pipe(
                            final_register.loc[
                                final_register["site_component"].eq(component),
                                "site_id",
                            ]
                        ),
                        "site_labels": pipe(
                            list(
                                planned.loc[
                                    planned["site_component"].eq(component),
                                    "address",
                                ]
                            )
                            + list(
                                planned.loc[
                                    planned["site_component"].eq(component), "place"
                                ]
                            )
                            + list(
                                final_register.loc[
                                    final_register["site_component"].eq(component),
                                    "address",
                                ]
                            )
                            + list(
                                final_register.loc[
                                    final_register["site_component"].eq(component),
                                    "place",
                                ]
                            )
                        ),
                        "all_area_count": len(all_area_ids),
                        "all_area_ids": pipe(all_area_ids),
                        "residual_area_count": len(residual_area_ids),
                        "residual_area_ids": pipe(residual_area_ids),
                        "residual_area_planned_eligible": json.dumps(
                            residual_area_planned_eligible,
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                        "planned_ballots": pipe(planned_site["source_kalpi"]),
                        "preserved_ballot_bases": pipe(preserved_bases),
                        "residual_planned_ballots": pipe(
                            residual_planned["source_kalpi"]
                        ),
                        "residual_final_ballots": pipe(
                            residual_final["source_kalpi"]
                        ),
                        "planned_residual_eligible": planned_residual_eligible,
                        "final_residual_eligible": final_residual_eligible,
                        "eligible_difference": difference,
                        "eligible_difference_share": (
                            difference / planned_residual_eligible
                            if planned_residual_eligible
                            else 0
                        ),
                        "residual_actual_voters": int(
                            residual_final["actual_voters"].sum()
                        ),
                        "current_host_area_ids": pipe(current_hosts),
                        "current_hosts_outside_residual": pipe(hosts_outside),
                        "unmapped_planned_rows": unmapped_planned_rows,
                        "result_rows_without_site_in_locality": int(
                            locality_results["site_component"].eq("").sum()
                        ),
                        "final_register_balance": final_register_balance,
                        "final_register_eligible_difference": (
                            final_register_difference
                        ),
                        "final_register_rows_without_result": (
                            final_register_missing_result_rows
                        ),
                        "final_result_rows_without_register": (
                            final_result_rows_missing_register
                        ),
                    }
                )

                if can_test_aggregates and len(residual_area_ids) > 1:
                    ambiguous_edges.append(
                        {
                            "site_audit_id": site_id,
                            "election": election,
                            "locality_code": locality_code,
                            "locality_name": locality_name,
                            "area_ids": residual_area_ids,
                            "classification": classification,
                            "balance": residual_balance,
                            "hosts_outside": hosts_outside,
                            "unmapped_planned_rows": unmapped_planned_rows,
                            "actual_voters": int(
                                residual_final["actual_voters"].sum()
                            ),
                            "eligible_voters": final_residual_eligible,
                            "current_host_area_ids": current_hosts,
                            "final_register_balance": final_register_balance,
                            "final_register_rows_without_result": (
                                final_register_missing_result_rows
                            ),
                            "final_result_rows_without_register": (
                                final_result_rows_missing_register
                            ),
                        }
                    )

                for area_id in all_area_ids:
                    key = (election, locality_code, area_id)
                    context = area_context.setdefault(
                        key,
                        {
                            "election": election,
                            "locality_code": locality_code,
                            "locality_name": locality_name,
                            "stat_area_id": area_id,
                            "site_ids": set(),
                            "ambiguous_site_ids": set(),
                            "missing_crosswalk_ballots": int(
                                missing_by_area.get(area_id, 0)
                            ),
                        },
                    )
                    context["site_ids"].add(site_id)
                    if area_id in residual_area_ids and len(residual_area_ids) > 1:
                        context["ambiguous_site_ids"].add(site_id)

    site_frame = pd.DataFrame(site_rows)
    site_frame.to_csv(OUTPUT_SITES, index=False, encoding="utf-8-sig")

    component_rows: list[dict[str, Any]] = []
    component_by_area: dict[tuple[str, str, str], str] = {}
    for (election, locality_code), locality_edges in pd.DataFrame(
        ambiguous_edges
    ).groupby(["election", "locality_code"], sort=True):
        graph = UnionFind()
        edge_records = locality_edges.to_dict("records")
        for edge in edge_records:
            area_ids = edge["area_ids"]
            for area_id in area_ids:
                graph.add(area_id)
            for area_id in area_ids[1:]:
                graph.union(area_ids[0], area_id)

        grouped_edges: dict[str, list[dict[str, Any]]] = {}
        for edge in edge_records:
            root = graph.find(edge["area_ids"][0])
            grouped_edges.setdefault(root, []).append(edge)

        for component_number, edges in enumerate(
            grouped_edges.values(), start=1
        ):
            area_ids = sorted(
                set().union(*(set(edge["area_ids"]) for edge in edges))
            )
            relevant_context = [
                area_context[(election, locality_code, area_id)]
                for area_id in area_ids
                if (election, locality_code, area_id) in area_context
            ]
            open_classes = [
                edge
                for edge in edges
                if edge["balance"] not in {"exact", "within_3"}
                or edge["hosts_outside"]
                or edge["unmapped_planned_rows"]
                or edge["final_register_balance"] == "mismatch"
                or edge["final_register_rows_without_result"]
                or edge["final_result_rows_without_register"]
            ]
            missing_crosswalk_ballots = sum(
                context["missing_crosswalk_ballots"]
                for context in relevant_context
            )
            result_rows_without_site = int(
                site_frame.loc[
                    site_frame["site_audit_id"].isin(
                        [edge["site_audit_id"] for edge in edges]
                    ),
                    "result_rows_without_site_in_locality",
                ].max()
            )
            if (
                not open_classes
                and not missing_crosswalk_ballots
                and not result_rows_without_site
            ):
                component_class = (
                    "isolated_closed_aggregate"
                    if len(edges) == 1
                    else "connected_closed_aggregate"
                )
            elif (
                not missing_crosswalk_ballots
                and not result_rows_without_site
                and all(
                    edge["balance"]
                    in {"exact", "within_3", "within_half_percent"}
                    and not edge["hosts_outside"]
                    and not edge["unmapped_planned_rows"]
                    and edge["final_register_balance"]
                    in {"not_available", "exact", "within_3"}
                    and not edge["final_register_rows_without_result"]
                    and not edge["final_result_rows_without_register"]
                    for edge in edges
                )
            ):
                component_class = (
                    "isolated_near_balance_aggregate"
                    if len(edges) == 1
                    else "connected_near_balance_aggregate"
                )
            else:
                component_class = "review_open_or_unbalanced"

            component_id = (
                f"{election}:{locality_code}:aggregate:{component_number}"
            )
            current_result_areas = sorted(
                set(area_ids) & public_area_ids[election]
            )
            current_empty_areas = sorted(
                set(area_ids) - public_area_ids[election]
            )
            current_hosts = sorted(
                set().union(
                    *(
                        set(edge["current_host_area_ids"])
                        for edge in edges
                    )
                )
            )
            for area_id in area_ids:
                component_by_area[(election, locality_code, area_id)] = component_id
            component_rows.append(
                {
                    "aggregate_component_id": component_id,
                    "election": election,
                    "locality_code": locality_code,
                    "locality_name": edges[0]["locality_name"],
                    "classification": component_class,
                    "area_count": len(area_ids),
                    "stat_area_ids": pipe(area_ids),
                    "current_result_area_count": len(current_result_areas),
                    "current_result_area_ids": pipe(current_result_areas),
                    "current_empty_area_count": len(current_empty_areas),
                    "current_empty_area_ids": pipe(current_empty_areas),
                    "current_host_area_ids": pipe(current_hosts),
                    "ambiguous_site_count": len(edges),
                    "ambiguous_site_ids": pipe(
                        edge["site_audit_id"] for edge in edges
                    ),
                    "eligible_voters_in_ambiguous_sites": sum(
                        edge["eligible_voters"] for edge in edges
                    ),
                    "actual_voters_in_ambiguous_sites": sum(
                        edge["actual_voters"] for edge in edges
                    ),
                    "missing_crosswalk_ballots": missing_crosswalk_ballots,
                    "result_rows_without_site_in_locality": result_rows_without_site,
                    "open_or_unbalanced_site_count": len(open_classes),
                }
            )

    component_frame = pd.DataFrame(component_rows)
    component_frame.to_csv(
        OUTPUT_COMPONENTS, index=False, encoding="utf-8-sig"
    )

    area_rows: list[dict[str, Any]] = []
    for key, context in sorted(area_context.items()):
        election, locality_code, area_id = key
        component_id = component_by_area.get(key, "")
        if component_id:
            evidence_class = "cannot_show_separately_pending_aggregate_review"
        elif context["missing_crosswalk_ballots"]:
            evidence_class = "incomplete_source_coverage"
        else:
            evidence_class = "no_multi_area_aggregate_detected"
        area_rows.append(
            {
                "election": election,
                "locality_code": locality_code,
                "locality_name": context["locality_name"],
                "stat_area_id": area_id,
                "currently_has_result": area_id in public_area_ids[election],
                "evidence_class": evidence_class,
                "aggregate_component_id": component_id,
                "polling_site_count": len(context["site_ids"]),
                "ambiguous_polling_site_count": len(
                    context["ambiguous_site_ids"]
                ),
                "missing_crosswalk_ballots": context[
                    "missing_crosswalk_ballots"
                ],
            }
        )
    area_frame = pd.DataFrame(area_rows)
    area_frame.to_csv(OUTPUT_AREAS, index=False, encoding="utf-8-sig")

    summary = {
        "scope": sorted(SOURCES),
        "method": (
            "Official pre-balance polling registers are linked to final result "
            "rows by locality, polling-site identity, surviving ballot base, "
            "and exact site text. Bases whose eligible-voter totals remain "
            "within three voters are retained as separate. Only the residual "
            "multi-area balance is considered an aggregate candidate."
        ),
        "site_classifications": (
            site_frame.groupby(["election", "classification"])
            .size()
            .rename("count")
            .reset_index()
            .to_dict("records")
        ),
        "component_classifications": (
            component_frame.groupby(["election", "classification"])
            .size()
            .rename("count")
            .reset_index()
            .to_dict("records")
            if not component_frame.empty
            else []
        ),
    }
    OUTPUT_SUMMARY.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("Site classifications:")
    print(
        site_frame.groupby(["election", "classification"])
        .size()
        .unstack(fill_value=0)
        .to_string()
    )
    print("\nAggregate components:")
    if component_frame.empty:
        print("none")
    else:
        print(
            component_frame.groupby(["election", "classification"])
            .agg(
                components=("aggregate_component_id", "count"),
                areas=("area_count", "sum"),
                actual_voters=("actual_voters_in_ambiguous_sites", "sum"),
            )
            .to_string()
        )
        print("\nLocalities with closed candidates:")
        closed = component_frame.loc[
            component_frame["classification"].isin(
                {
                    "isolated_closed_aggregate",
                    "connected_closed_aggregate",
                    "isolated_near_balance_aggregate",
                    "connected_near_balance_aggregate",
                }
            )
        ]
        print(
            closed.groupby(["election", "locality_name"])
            .agg(
                components=("aggregate_component_id", "count"),
                areas=("area_count", "sum"),
                actual_voters=("actual_voters_in_ambiguous_sites", "sum"),
            )
            .to_string()
        )


if __name__ == "__main__":
    main()
