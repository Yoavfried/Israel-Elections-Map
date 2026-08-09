from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd

from pipeline_common import ELECTIONS, PROCESSED_DIR, ensure_dir, write_csv, write_json


ASSIGNMENTS = PROCESSED_DIR / "assignments" / "ballot_geography_assignments.csv"
ASSIGNMENT_PLAN = PROCESSED_DIR / "assignments" / "ballot_assignment_plan.csv"
WIDE_DIR = PROCESSED_DIR / "normalized" / "ballot_votes_wide"
OUT_DIR = PROCESSED_DIR / "public"

CORE_COLUMNS = {
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
}
NUMERIC_CORE = ["eligible_voters", "actual_voters", "valid_votes", "invalid_votes"]
K17_GUSH_KATIF_ELIGIBLE_REGISTER = 3_569
K17_ORDINARY_ELIGIBLE_REGISTER = 5_011_053
K17_NATIONAL_ELIGIBLE_REGISTER = 5_014_622
STAT_AREA_VINTAGE_BY_ELECTION = {
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


def bool_series(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().isin(["true", "1", "yes"])


def numeric(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for column in columns:
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0).astype("int64")
    return df


def party_columns(df: pd.DataFrame) -> list[str]:
    return [column for column in df.columns if column not in CORE_COLUMNS]


def add_winner_fields(df: pd.DataFrame, parties: list[str]) -> pd.DataFrame:
    if df.empty or not parties:
        df["winning_ballot_letter"] = ""
        df["winning_votes"] = 0
        df["runner_up_votes"] = 0
        df["margin_votes"] = 0
        df["winning_vote_share"] = 0.0
        return df

    winners = []
    winning_votes = []
    runner_up_votes = []
    for _, row in df.iterrows():
        ordered = sorted(((party, int(row[party])) for party in parties), key=lambda item: item[1], reverse=True)
        winner, votes = ordered[0]
        runner_up = ordered[1][1] if len(ordered) > 1 else 0
        winners.append(winner)
        winning_votes.append(votes)
        runner_up_votes.append(runner_up)
    df["winning_ballot_letter"] = winners
    df["winning_votes"] = winning_votes
    df["runner_up_votes"] = runner_up_votes
    df["margin_votes"] = df["winning_votes"] - df["runner_up_votes"]
    df["winning_vote_share"] = (df["winning_votes"] / df["valid_votes"].where(df["valid_votes"] != 0, pd.NA)).fillna(0).round(6)
    return df


def aggregate(df: pd.DataFrame, group_columns: list[str], parties: list[str]) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=group_columns + ["contributing_rows", "contributing_kalpis"] + NUMERIC_CORE + parties)

    value_columns = NUMERIC_CORE + parties
    grouped = df.groupby(group_columns, dropna=False)
    totals = grouped[value_columns].sum().reset_index()
    totals["contributing_rows"] = grouped.size().to_numpy()
    kalpi_source = df.copy()
    kalpi_source["_kalpi_identity"] = kalpi_source[["source_locality_code", "source_kalpi"]].astype(str).agg("::".join, axis=1)
    kalpis = kalpi_source.groupby(group_columns, dropna=False)["_kalpi_identity"].nunique().reset_index(name="contributing_kalpis")
    totals = totals.merge(kalpis, on=group_columns, how="left")
    totals = add_winner_fields(totals, parties)
    leading = group_columns + [
        "contributing_rows",
        "contributing_kalpis",
        "eligible_voters",
        "actual_voters",
        "valid_votes",
        "invalid_votes",
        "winning_ballot_letter",
        "winning_votes",
        "runner_up_votes",
        "margin_votes",
        "winning_vote_share",
    ]
    return totals[leading + parties]


def write_df(df: pd.DataFrame, path: Path) -> None:
    ensure_dir(path.parent)
    df.to_csv(path, index=False, encoding="utf-8-sig")


def read_wide(election: str) -> pd.DataFrame:
    path = WIDE_DIR / f"{election.lower()}_ballot_votes.csv"
    return pd.read_csv(path, dtype=str, encoding="utf-8-sig").fillna("")


def add_fallback_metadata(
    rows: pd.DataFrame,
    stat_area_vintage: int,
    id_prefix: str,
    fallback_reason: str,
    boundary_source: str | Callable[[str], str],
) -> pd.DataFrame:
    output = rows.copy()
    output.insert(
        1,
        "fallback_geography_id",
        output["locality_id"].map(
            lambda locality_id: f"{id_prefix}:{stat_area_vintage}:{locality_id}"
        ),
    )
    output.insert(2, "stat_area_vintage", stat_area_vintage)
    output.insert(3, "fallback_reason", fallback_reason)
    if callable(boundary_source):
        values = output["locality_id"].map(boundary_source)
    else:
        values = boundary_source
    output.insert(4, "boundary_source", values)
    return output


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.parse_args()

    assignments = pd.read_csv(ASSIGNMENTS, dtype=str, encoding="utf-8-sig").fillna("")
    component_plan = pd.read_csv(
        ASSIGNMENT_PLAN, dtype=str, encoding="utf-8-sig"
    ).fillna("")[
        [
            "source_row_uid",
            "target_locality_code",
            "target_locality_name",
            "assignment_source",
        ]
    ].rename(
        columns={
            "target_locality_code": "component_locality_code",
            "target_locality_name": "component_locality_name",
            "assignment_source": "plan_assignment_source",
        }
    )
    assignment_columns = [
        "source_row_uid",
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
        "unresolved_reason",
    ]

    manifest: dict[str, Any] = {"elections": [], "outputs": {}}
    summary_rows: list[dict[str, Any]] = []
    municipality_fallback_audit_rows: list[dict[str, Any]] = []

    for election_number in sorted(ELECTIONS.keys(), reverse=True):
        election = ELECTIONS[election_number]["key"]
        wide = read_wide(election)
        parties = party_columns(wide)
        merged = wide.merge(
            assignments[assignment_columns], on="source_row_uid", how="left"
        ).merge(component_plan, on="source_row_uid", how="left", validate="one_to_one")
        merged = numeric(merged, NUMERIC_CORE + parties)
        mapped = bool_series(merged["is_mapped"])
        locality_mapped = bool_series(merged["is_locality_mapped"])
        stat_rows = merged[mapped & (merged["geography_type"] == "statistical_area")].copy()
        statistical_custom_rows = merged[
            mapped & (merged["geography_type"] == "custom_geography")
        ].copy()
        geographic_rows = merged[mapped & bool_series(merged["is_geographic"])].copy()
        unmapped_rows = merged[~mapped].copy()
        geographic_scope_mask = ~merged["locality_geography_type"].isin(
            ["envelope", "non_geographic"]
        )
        geographic_scope = merged[geographic_scope_mask].copy()
        locality_rows = merged[
            locality_mapped
            & merged["locality_geography_type"].isin(["locality", "composite_locality"])
        ].copy()
        locality_rows["locality_id"] = locality_rows["locality_geography_id"]
        locality_rows["locality_code"] = locality_rows["locality_result_code"]
        locality_rows["locality_name"] = locality_rows["locality_result_name"]
        locality_custom_rows = merged[
            locality_mapped & (merged["locality_geography_type"] == "custom_geography")
        ].copy()
        locality_custom_rows["custom_geography_id"] = locality_custom_rows[
            "locality_geography_id"
        ]
        locality_custom_rows["geography_id"] = locality_custom_rows[
            "locality_geography_id"
        ]
        locality_custom_rows["locality_name"] = locality_custom_rows[
            "locality_result_name"
        ]
        locality_geographic_rows = merged[locality_mapped].copy()
        locality_unmapped_rows = merged[geographic_scope_mask & ~locality_mapped].copy()
        envelope_rows = merged[
            merged["locality_geography_type"].isin(["envelope", "non_geographic"])
        ].copy()
        envelope_rows["envelope_id"] = "envelope:official"
        envelope_rows["envelope_name_he"] = "מעטפות חיצוניות"
        envelope_rows["envelope_name_en"] = "Envelope votes"

        if not locality_unmapped_rows.empty:
            unresolved = ", ".join(
                sorted(locality_unmapped_rows["source_row_uid"].astype(str).head(10).tolist())
            )
            raise ValueError(
                f"{election} has {len(locality_unmapped_rows)} geographic rows without a locality assignment: {unresolved}"
            )

        stat_agg = aggregate(
            stat_rows,
            [
                "election",
                "stat_area_id",
                "stat_area_vintage",
                "stat_area_yishuv_stat",
                "stat_area_number",
                "locality_id",
                "locality_code",
                "locality_name",
            ],
            parties,
        )
        locality_agg = aggregate(
            locality_rows,
            ["election", "locality_id", "locality_code", "locality_name"],
            parties,
        )
        component_rows = merged[
            merged["plan_assignment_source"]
            == "reviewed_composite_component_evidence"
        ].copy()
        component_fallback_agg = locality_agg.iloc[0:0].copy()
        fully_covered_component_sources: set[str] = set()
        if not component_rows.empty:
            component_rows["_is_stat_mapped"] = bool_series(
                component_rows["is_mapped"]
            ).astype("int64")
            component_group_columns = [
                "locality_geography_id",
                "component_locality_code",
                "component_locality_name",
            ]
            component_coverage = (
                component_rows.groupby(component_group_columns, dropna=False)
                .agg(
                    component_rows=("source_row_uid", "size"),
                    mapped_rows=("_is_stat_mapped", "sum"),
                )
                .reset_index()
            )
            component_coverage["is_fully_covered"] = (
                component_coverage["mapped_rows"]
                == component_coverage["component_rows"]
            ) | (component_coverage["mapped_rows"] == 0)
            source_coverage = component_coverage.groupby(
                "locality_geography_id", dropna=False
            )["is_fully_covered"].all()
            fully_covered_component_sources = set(
                source_coverage[source_coverage].index.astype(str)
            )

            fallback_components = component_coverage[
                component_coverage["mapped_rows"] == 0
            ][component_group_columns]
            if not fallback_components.empty:
                component_fallback_rows = component_rows.merge(
                    fallback_components,
                    on=component_group_columns,
                    how="inner",
                    validate="many_to_one",
                )
                component_fallback_rows["locality_id"] = (
                    "loc:" + component_fallback_rows["component_locality_code"]
                )
                component_fallback_rows["locality_code"] = component_fallback_rows[
                    "component_locality_code"
                ]
                component_fallback_rows["locality_name"] = component_fallback_rows[
                    "component_locality_name"
                ]
                component_fallback_agg = aggregate(
                    component_fallback_rows,
                    ["election", "locality_id", "locality_code", "locality_name"],
                    parties,
                )

        mapped_locality_geography_ids = set(
            geographic_rows["locality_geography_id"].astype(str)
        ) | fully_covered_component_sources
        whole_locality_fallback_agg = locality_agg[
            ~locality_agg["locality_id"].isin(mapped_locality_geography_ids)
        ].copy()
        stat_area_vintage = STAT_AREA_VINTAGE_BY_ELECTION[election]
        whole_locality_fallback_agg = add_fallback_metadata(
            whole_locality_fallback_agg,
            stat_area_vintage,
            "municipality-fallback",
            "no_ballot_has_a_supported_statistical_area_assignment",
            lambda locality_id: (
                "reviewed_historical_composite_geometry"
                if str(locality_id).startswith("composite:")
                else "cbs_2022_locality_geometry_display_only"
            ),
        )
        component_fallback_agg = add_fallback_metadata(
            component_fallback_agg,
            stat_area_vintage,
            "municipality-component-fallback",
            "no_ballot_has_a_supported_statistical_area_assignment_for_reviewed_composite_component",
            "reviewed_historical_composite_component_display_geometry",
        )
        municipality_fallback_agg = pd.concat(
            [whole_locality_fallback_agg, component_fallback_agg],
            ignore_index=True,
        )
        if not municipality_fallback_agg.empty:
            municipality_fallback_audit_rows.extend(
                municipality_fallback_agg[
                    [
                        "election",
                        "stat_area_vintage",
                        "fallback_geography_id",
                        "locality_id",
                        "locality_code",
                        "locality_name",
                        "contributing_rows",
                        "contributing_kalpis",
                        "eligible_voters",
                        "actual_voters",
                        "valid_votes",
                        "invalid_votes",
                        "fallback_reason",
                        "boundary_source",
                    ]
                ].to_dict("records")
            )
        statistical_custom_agg = aggregate(
            statistical_custom_rows,
            ["election", "custom_geography_id", "geography_id", "locality_name"],
            parties,
        )
        statistical_custom_agg.insert(1, "geography_mode", "statistical-area")
        locality_custom_agg = aggregate(
            locality_custom_rows,
            ["election", "custom_geography_id", "geography_id", "locality_name"],
            parties,
        )
        locality_custom_agg.insert(1, "geography_mode", "locality")
        custom_agg = pd.concat(
            [statistical_custom_agg, locality_custom_agg], ignore_index=True
        )
        envelope_agg = aggregate(
            envelope_rows,
            ["election", "envelope_id", "envelope_name_he", "envelope_name_en"],
            parties,
        )
        if not envelope_agg.empty:
            source_non_geographic_eligible = int(envelope_agg["eligible_voters"].sum())
            envelope_agg["eligible_voters"] = (
                source_non_geographic_eligible + K17_GUSH_KATIF_ELIGIBLE_REGISTER
                if election == "K17"
                else 0
            )
        if election == "K17":
            ordinary_eligible = int(
                merged.loc[
                    ~bool_series(merged["is_envelope"]), "eligible_voters"
                ].sum()
            )
            if ordinary_eligible != K17_ORDINARY_ELIGIBLE_REGISTER:
                raise ValueError(
                    f"K17 ordinary eligible register is {ordinary_eligible}, "
                    f"expected {K17_ORDINARY_ELIGIBLE_REGISTER}"
                )
            envelope_eligible = int(envelope_agg["eligible_voters"].sum())
            geographic_eligible = int(geographic_scope["eligible_voters"].sum())
            if ordinary_eligible + K17_GUSH_KATIF_ELIGIBLE_REGISTER != K17_NATIONAL_ELIGIBLE_REGISTER:
                raise ValueError("K17 ordinary plus Gush Katif reconciliation failed")
            if geographic_eligible + envelope_eligible != K17_NATIONAL_ELIGIBLE_REGISTER:
                raise ValueError("K17 national eligible-register reconciliation failed")

        contribution_columns = [
            "source_row_uid",
            "election",
            "source_row_id",
            "source_locality_code",
            "source_locality_name",
            "source_kalpi",
            "geography_assignment_status",
            "geography_type",
            "geography_id",
            "stat_area_id",
            "stat_area_vintage",
            "stat_area_yishuv_stat",
            "stat_area_number",
            "locality_id",
            "locality_code",
            "locality_name",
            "custom_geography_id",
            "final_assignment_method",
            "final_assignment_source",
            "eligible_voters",
            "actual_voters",
            "valid_votes",
            "invalid_votes",
        ] + parties
        unmapped_columns = contribution_columns + ["unresolved_reason"]

        outputs = {
            "statistical_area_results": OUT_DIR / "statistical_area_results" / f"{election.lower()}.csv",
            "locality_results": OUT_DIR / "locality_results" / f"{election.lower()}.csv",
            "custom_geography_results": OUT_DIR / "custom_geography_results" / f"{election.lower()}.csv",
            "envelope_results": OUT_DIR / "envelope_results" / f"{election.lower()}.csv",
            "ballot_contributions": OUT_DIR / "ballot_contributions" / f"{election.lower()}.csv",
            "unmapped_rows": OUT_DIR / "unmapped_rows" / f"{election.lower()}.csv",
            "municipality_display_fallbacks": (
                OUT_DIR
                / "municipality_display_fallbacks"
                / f"{election.lower()}.csv"
            ),
        }
        write_df(stat_agg, outputs["statistical_area_results"])
        write_df(locality_agg, outputs["locality_results"])
        write_df(custom_agg, outputs["custom_geography_results"])
        write_df(envelope_agg, outputs["envelope_results"])
        write_df(geographic_rows[contribution_columns], outputs["ballot_contributions"])
        write_df(unmapped_rows[unmapped_columns], outputs["unmapped_rows"])
        write_df(
            municipality_fallback_agg,
            outputs["municipality_display_fallbacks"],
        )

        total_actual = int(merged["actual_voters"].sum())
        mapped_actual = int(geographic_rows["actual_voters"].sum())
        geographic_scope_actual = int(geographic_scope["actual_voters"].sum())
        locality_mapped_actual = int(locality_geographic_rows["actual_voters"].sum())
        statistical_pending = merged[geographic_scope_mask & ~mapped]
        summary_rows.append(
            {
                "election": election,
                "rows": len(merged),
                "total_actual_voters": total_actual,
                "geographic_scope_rows": len(geographic_scope),
                "geographic_scope_actual_voters": geographic_scope_actual,
                "mapped_geographic_rows": len(geographic_rows),
                "mapped_geographic_actual_voters": mapped_actual,
                "mapped_actual_voter_share": round(mapped_actual / total_actual, 6) if total_actual else 0,
                "statistical_mode_mapped_rows": len(geographic_rows),
                "statistical_mode_mapped_actual_voters": mapped_actual,
                "statistical_mode_mapped_actual_voter_share": round(
                    mapped_actual / geographic_scope_actual, 6
                )
                if geographic_scope_actual
                else 0,
                "statistical_mode_pending_rows": len(statistical_pending),
                "statistical_mode_pending_actual_voters": int(
                    statistical_pending["actual_voters"].sum()
                ),
                "locality_mode_mapped_rows": len(locality_geographic_rows),
                "locality_mode_mapped_actual_voters": locality_mapped_actual,
                "locality_mode_mapped_actual_voter_share": round(
                    locality_mapped_actual / geographic_scope_actual, 6
                )
                if geographic_scope_actual
                else 0,
                "locality_mode_pending_rows": len(locality_unmapped_rows),
                "locality_mode_pending_actual_voters": int(
                    locality_unmapped_rows["actual_voters"].sum()
                ),
                "statistical_area_rows": len(stat_rows),
                "statistical_area_actual_voters": int(stat_rows["actual_voters"].sum()),
                "custom_geography_rows": len(statistical_custom_rows),
                "custom_geography_actual_voters": int(
                    statistical_custom_rows["actual_voters"].sum()
                ),
                "unmapped_rows": len(unmapped_rows),
                "unmapped_actual_voters": int(unmapped_rows["actual_voters"].sum()),
                "envelope_rows": len(envelope_rows),
                "envelope_actual_voters": int(envelope_rows["actual_voters"].sum()),
                "special_non_geographic_rows": int(
                    (merged["locality_geography_type"] == "non_geographic").sum()
                ),
                "special_non_geographic_actual_voters": int(
                    merged.loc[
                        merged["locality_geography_type"] == "non_geographic", "actual_voters"
                    ].sum()
                ),
                "municipality_display_fallback_records": len(
                    municipality_fallback_agg
                ),
                "municipality_display_fallback_ballot_rows": int(
                    municipality_fallback_agg["contributing_rows"].sum()
                ),
                "municipality_display_fallback_actual_voters": int(
                    municipality_fallback_agg["actual_voters"].sum()
                ),
            }
        )
        manifest["elections"].append(election)
        manifest["outputs"][election] = {key: str(path.relative_to(PROCESSED_DIR.parent)).replace("\\", "/") for key, path in outputs.items()}

    write_csv(OUT_DIR / "election_summary.csv", summary_rows, list(summary_rows[0].keys()) if summary_rows else [])
    write_json(OUT_DIR / "election_summary.json", summary_rows)
    write_json(OUT_DIR / "manifest.json", manifest)
    write_csv(
        PROCESSED_DIR
        / "audits"
        / "historical_municipality_display_fallbacks.csv",
        municipality_fallback_audit_rows,
        [
            "election",
            "stat_area_vintage",
            "fallback_geography_id",
            "locality_id",
            "locality_code",
            "locality_name",
            "contributing_rows",
            "contributing_kalpis",
            "eligible_voters",
            "actual_voters",
            "valid_votes",
            "invalid_votes",
            "fallback_reason",
            "boundary_source",
        ],
    )

    print(f"public_output_elections={len(summary_rows)}")
    for row in summary_rows:
        print(
            f"{row['election']}: mapped_rows={row['mapped_geographic_rows']} "
            f"stat_pending={row['statistical_mode_pending_rows']} "
            f"stat_share={row['statistical_mode_mapped_actual_voter_share']:.2%} "
            f"locality_share={row['locality_mode_mapped_actual_voter_share']:.2%}"
        )


if __name__ == "__main__":
    main()
