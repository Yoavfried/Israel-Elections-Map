from __future__ import annotations

import csv
import hashlib
import io
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any

import pandas as pd

from pipeline_common import ELECTIONS, MANUAL_DIR, PROCESSED_DIR, RAW_DIR, ROOT


OUT_ROOT = ROOT / "public-data" / "v2"
WIDE_DIR = PROCESSED_DIR / "normalized" / "ballot_votes_wide"
ASSIGNMENTS = PROCESSED_DIR / "assignments" / "ballot_geography_assignments.csv"
PUBLIC_DIR = PROCESSED_DIR / "public"
GEOGRAPHY_DIR = PROCESSED_DIR / "geographies"
ASSIGNMENT_DIR = PROCESSED_DIR / "assignments"
AUDIT_DIR = PROCESSED_DIR / "audits"
PARTY_REGISTRY = MANUAL_DIR / "party_registry.csv"
ARCGIS_RECONSTRUCTION_REVIEWS = (
    MANUAL_DIR / "arcgis_assignment_reconstruction_reviews.csv"
)

ELECTION_VINTAGES = {
    "K26": 2022,
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

CORE_COLUMNS = [
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

ASSIGNMENT_COLUMNS = [
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

GEOGRAPHY_PACKAGES = [
    {
        "name": "statistical_areas_1995",
        "source": "statistical_areas_1995.geojson",
        "id_property": "stat_area_id",
        "geography_type": "statistical_area",
        "vintage": 1995,
    },
    {
        "name": "statistical_areas_2008",
        "source": "statistical_areas_2008.geojson",
        "id_property": "stat_area_id",
        "geography_type": "statistical_area",
        "vintage": 2008,
    },
    {
        "name": "statistical_areas_2011",
        "source": "statistical_areas_2011.geojson",
        "id_property": "stat_area_id",
        "geography_type": "statistical_area",
        "vintage": 2011,
    },
    {
        "name": "statistical_areas_2022",
        "source": "statistical_areas_2022.geojson",
        "id_property": "stat_area_id",
        "geography_type": "statistical_area",
        "vintage": 2022,
    },
    {
        "name": "localities_2022",
        "source": "localities_2022_dissolved.geojson",
        "id_property": "locality_id",
        "geography_type": "locality",
        "vintage": 2022,
    },
    {
        "name": "composite_localities",
        "source": "composite_localities.geojson",
        "id_property": "composite_locality_id",
        "geography_type": "composite_locality",
        "vintage": "reviewed",
    },
    {
        "name": "custom_geographies",
        "source": "custom_geographies.geojson",
        "id_property": "custom_id",
        "geography_type": "custom_geography",
        "vintage": "reviewed",
    },
]

AGGREGATE_EXPORTS = [
    ("statistical_area_results", "statistical-areas", "stat_area_id"),
    ("locality_results", "localities", "locality_id"),
    ("custom_geography_results", "custom-geographies", "geography_id"),
    ("envelope_results", "envelopes", ""),
    ("unmapped_rows", "unresolved", ""),
]

PROVENANCE_TABLES = [
    (AUDIT_DIR / "k26_crosswalk_candidates.csv", "k26_crosswalk_candidates.csv",
     "Unaccepted pre-balance K26 crosswalk-key candidates; not ballot-to-area assignments."),
    (GEOGRAPHY_DIR / "k26_geography_supplements.csv", "k26_geography_supplements.csv",
     "Exact-ID 2022-area/locality supplements from the official CBS 2025 publication."),
    (
        MANUAL_DIR / "historical_composite_ballot_components.csv",
        "historical_composite_ballot_components.csv",
        "Reviewed K17/K18 polling-register ranges that identify historical composite components.",
    ),
    (
        MANUAL_DIR / "historical_stat_area_overrides.csv",
        "historical_stat_area_overrides.csv",
        "Reviewed replacements for contradicted direct crosswalk rows.",
    ),
    (
        MANUAL_DIR / "cross_election_stat_area_reviews.csv",
        "cross_election_stat_area_reviews.csv",
        "Approved high-confidence synthetic links reconstructed from cross-election polling-register continuity.",
    ),
    (
        MANUAL_DIR / "omitted_ordinary_ballot_reviews.csv",
        "omitted_ordinary_ballot_reviews.csv",
        "Reviewed row-level, set-level, and unresolved outcomes for ordinary ballots omitted from official crosswalks.",
    ),
    (
        ARCGIS_RECONSTRUCTION_REVIEWS,
        "arcgis_reconstruction_reviews.csv",
        "Reviewed locality-election decisions for ArcGIS residual reconstruction.",
    ),
    (
        ASSIGNMENT_DIR / "historical_ballot_crosswalk.csv",
        "official_historical_ballot_crosswalk.csv",
        "Normalized official CBS ballot-to-statistical-area crosswalk rows.",
    ),
    (
        ASSIGNMENT_DIR / "final_assignment_summary.csv",
        "final_assignment_summary.csv",
        "Per-election row and voter coverage for final geography assignments.",
    ),
    (
        AUDIT_DIR / "election_source_geography_field_audit.csv",
        "election_source_geography_field_audit.csv",
        "Reproducible inventory of statistical-area and AGS fields in official sources.",
    ),
    (
        AUDIT_DIR / "arcgis_assignment_reconstruction_candidates.csv",
        "arcgis_reconstruction_candidates.csv",
        "Approved-capable exact ArcGIS residual-partition candidate rows.",
    ),
    (
        AUDIT_DIR / "arcgis_assignment_reconstruction_localities.csv",
        "arcgis_reconstruction_localities.csv",
        "All tested ArcGIS localities, including rejected dissolved aggregates.",
    ),
    (
        AUDIT_DIR / "k23_cec_ags_assignment_candidates.csv",
        "k23_cec_ags_assignment_candidates.csv",
        "Missing K23 crosswalk rows recovered from the official CEC AGS field.",
    ),
    (
        AUDIT_DIR / "k23_cec_ags_conflicts.csv",
        "k23_cec_ags_conflicts.csv",
        "K23 AGS evidence withheld because it conflicts with another source.",
    ),
    (
        AUDIT_DIR / "k23_cec_ags_coverage.csv",
        "k23_cec_ags_coverage.csv",
        "K23 AGS population coverage by locality.",
    ),
    (
        AUDIT_DIR / "k23_cec_ags_validation.csv",
        "k23_cec_ags_validation.csv",
        "Row-level comparison of K23 AGS with existing official assignments.",
    ),
    (
        AUDIT_DIR / "stable_ballot_assignment_candidates.csv",
        "stable_ballot_assignment_candidates.csv",
        "Synthetic area links inferred from official CBS stable-ballot workbooks.",
    ),
    (
        AUDIT_DIR / "stable_ballot_site_safety.csv",
        "stable_ballot_site_safety.csv",
        "Row-level preservation and mixed-site safety audit for every stable-ballot candidate.",
    ),
    (
        MANUAL_DIR / "stable_ballot_assignment_reviews.csv",
        "stable_ballot_assignment_reviews.csv",
        "Reviewed rejections where a stable base ballot became a mixed final polling-site batch.",
    ),
    (
        MANUAL_DIR / "polling_register_planned_area_reviews.csv",
        "polling_register_planned_area_reviews.csv",
        "Reviewed planned-ballot area sets used to audit final polling-site consolidations.",
    ),
    (
        AUDIT_DIR / "stable_ballot_assignment_conflicts.csv",
        "stable_ballot_assignment_conflicts.csv",
        "Stable-ballot links withheld because authoritative areas conflict.",
    ),
    (
        AUDIT_DIR / "stable_ballot_transition_audit.csv",
        "stable_ballot_transition_audit.csv",
        "K18-to-K19 stability checks against the official 2008/2011 transition keys.",
    ),
    (
        AUDIT_DIR / "historical_assignment_gap_rows.csv",
        "historical_assignment_gap_rows.csv",
        "Every unresolved ballot row with a machine-readable reason.",
    ),
    (
        AUDIT_DIR / "historical_assignment_gap_localities.csv",
        "historical_assignment_gap_localities.csv",
        "Unresolved assignment totals by election, reason, and locality.",
    ),
    (
        AUDIT_DIR / "historical_assignment_gap_summary.csv",
        "historical_assignment_gap_summary.csv",
        "Unresolved assignment totals by election and reason.",
    ),
    (
        AUDIT_DIR / "historical_crosswalk_locality_omission_recurrence.csv",
        "historical_crosswalk_locality_omission_recurrence.csv",
        "Cross-election recurrence of entire-locality omissions in official ballot crosswalks.",
    ),
    (
        AUDIT_DIR / "historical_polygon_coverage.csv",
        "historical_polygon_coverage.csv",
        "Election-by-polygon assignment, source-comparison, and population-proxy audit.",
    ),
    (
        AUDIT_DIR / "historical_polygon_assignment_persistence.csv",
        "historical_polygon_assignment_persistence.csv",
        "Cross-election assignment presence for each compatible historical polygon.",
    ),
    (
        AUDIT_DIR / "historical_polygon_coverage_summary.csv",
        "historical_polygon_coverage_summary.csv",
        "Per-election historical polygon coverage summary.",
    ),
    (
        AUDIT_DIR / "historical_municipality_display_fallbacks.csv",
        "historical_municipality_display_fallbacks.csv",
        "Display-only municipality or reviewed-component totals used when no ballot has a supported statistical-area assignment.",
    ),
]

PROVENANCE_JSON = [
    (GEOGRAPHY_DIR / "historical_geography_build_summary.json", "historical_geography_build_summary.json"),
    (AUDIT_DIR / "election_source_geography_field_audit.json", "election_source_geography_field_audit.json"),
    (AUDIT_DIR / "arcgis_assignment_reconstruction_summary.json", "arcgis_reconstruction_summary.json"),
    (AUDIT_DIR / "k23_cec_ags_assignment_summary.json", "k23_cec_ags_assignment_summary.json"),
    (AUDIT_DIR / "stable_ballot_assignment_summary.json", "stable_ballot_assignment_summary.json"),
    (AUDIT_DIR / "stable_ballot_site_safety_summary.json", "stable_ballot_site_safety_summary.json"),
    (AUDIT_DIR / "historical_assignment_gap_summary.json", "historical_assignment_gap_summary.json"),
]


def csv_bytes(frame: pd.DataFrame) -> bytes:
    text = io.StringIO(newline="")
    frame.to_csv(text, index=False, lineterminator="\n")
    return ("\ufeff" + text.getvalue()).encode("utf-8")


def write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def manifest_row(
    path: Path,
    category: str,
    description: str,
    rows: int | str = "",
    election: str = "",
    stat_area_vintage: int | str = "",
) -> dict[str, Any]:
    return {
        "path": path.relative_to(OUT_ROOT).as_posix(),
        "category": category,
        "election": election,
        "stat_area_vintage": stat_area_vintage,
        "format": path.suffix.removeprefix(".").lower(),
        "rows_or_features": rows,
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "description": description,
    }


def reset_generated_outputs() -> None:
    expected = (ROOT / "public-data" / "v2").resolve()
    if OUT_ROOT.resolve() != expected or expected.parent != (ROOT / "public-data").resolve():
        raise ValueError(f"Unsafe public-data output path: {OUT_ROOT}")
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    for name in ["ballots", "aggregates", "geographies", "metadata", "sources"]:
        target = OUT_ROOT / name
        if target.exists():
            shutil.rmtree(target)
    for name in ["manifest.csv", "manifest.json", "validation.json"]:
        target = OUT_ROOT / name
        if target.exists():
            target.unlink()


def standardized_geography(
    package: dict[str, Any],
) -> tuple[dict[str, Any], pd.DataFrame, set[str]]:
    source_path = GEOGRAPHY_DIR / package["source"]
    if not source_path.exists():
        raise FileNotFoundError(f"Missing geography input: {source_path}")
    source = json.loads(source_path.read_text(encoding="utf-8"))
    features: list[dict[str, Any]] = []
    metadata_rows: list[dict[str, Any]] = []
    ids: set[str] = set()

    for feature in source.get("features", []):
        properties = dict(feature.get("properties") or {})
        geography_id = str(properties.get(package["id_property"], "")).strip()
        if not geography_id or geography_id in ids:
            raise ValueError(
                f"{package['name']} has a blank or duplicate geography ID: {geography_id!r}"
            )
        ids.add(geography_id)
        standardized_properties = {
            "geography_id": geography_id,
            "geography_type": package["geography_type"],
            **properties,
        }
        features.append(
            {
                "type": "Feature",
                "properties": standardized_properties,
                "geometry": feature.get("geometry"),
            }
        )
        metadata_rows.append(
            {
                "geography_id": geography_id,
                "geography_type": package["geography_type"],
                "geography_package": package["name"],
                "geometry_archive": f"geographies/{package['name']}.zip",
                **properties,
            }
        )

    if not features:
        raise ValueError(f"{package['name']} contains no features")
    standardized = {
        "type": "FeatureCollection",
        "name": package["name"],
        "features": features,
    }
    metadata = pd.DataFrame(metadata_rows).fillna("")
    return standardized, metadata, ids


def write_deterministic_zip(path: Path, files: dict[str, bytes]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, files[name], compresslevel=9)


def build_geography_packages(
    manifest: list[dict[str, Any]],
) -> tuple[dict[int, set[str]], set[str], pd.DataFrame]:
    statistical_ids: dict[int, set[str]] = {}
    locality_mode_ids: set[str] = set()
    combined_metadata: list[pd.DataFrame] = []

    for package in GEOGRAPHY_PACKAGES:
        geography, metadata, ids = standardized_geography(package)
        geojson_bytes = (
            json.dumps(geography, ensure_ascii=False, separators=(",", ":")) + "\n"
        ).encode("utf-8")
        metadata_content = csv_bytes(metadata)
        metadata_path = OUT_ROOT / "geographies" / f"{package['name']}.csv"
        archive_path = OUT_ROOT / "geographies" / f"{package['name']}.zip"
        write_bytes(metadata_path, metadata_content)
        write_deterministic_zip(
            archive_path,
            {
                f"{package['name']}.csv": metadata_content,
                f"{package['name']}.geojson": geojson_bytes,
            },
        )
        manifest.append(
            manifest_row(
                metadata_path,
                "geography-metadata",
                f"Feature metadata and join IDs for {package['name']}.",
                rows=len(metadata),
                stat_area_vintage=package["vintage"],
            )
        )
        manifest.append(
            manifest_row(
                archive_path,
                "geography-package",
                f"Full-resolution GeoJSON and metadata for {package['name']}.",
                rows=len(metadata),
                stat_area_vintage=package["vintage"],
            )
        )
        combined_metadata.append(metadata)
        if package["geography_type"] == "statistical_area":
            statistical_ids[int(package["vintage"])] = ids
        else:
            locality_mode_ids.update(ids)

    all_metadata = pd.concat(combined_metadata, ignore_index=True, sort=False).fillna("")
    combined_path = OUT_ROOT / "metadata" / "geographies.csv"
    write_bytes(combined_path, csv_bytes(all_metadata))
    manifest.append(
        manifest_row(
            combined_path,
            "metadata",
            "Combined lookup for every published geography ID and package.",
            rows=len(all_metadata),
        )
    )
    return statistical_ids, locality_mode_ids, all_metadata


def build_ballot_exports(
    party_registry: pd.DataFrame,
    statistical_ids: dict[int, set[str]],
    locality_mode_ids: set[str],
    manifest: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    assignments = pd.read_csv(ASSIGNMENTS, dtype=str, encoding="utf-8-sig").fillna("")
    if assignments["source_row_uid"].duplicated().any():
        raise ValueError("Final assignments contain duplicate source_row_uid values")
    assignment_columns = ["source_row_uid", *ASSIGNMENT_COLUMNS]
    reconstruction_reviews = pd.read_csv(
        ARCGIS_RECONSTRUCTION_REVIEWS, dtype=str, encoding="utf-8-sig"
    ).fillna("")
    reconstruction_reviews = reconstruction_reviews[
        reconstruction_reviews["decision"] == "approved"
    ].copy()
    validation_rows: list[dict[str, Any]] = []
    total_rows = 0

    for number in sorted(ELECTIONS):
        election = ELECTIONS[number]["key"]
        vintage = ELECTION_VINTAGES[election]
        wide = pd.read_csv(
            WIDE_DIR / f"{election.lower()}_ballot_votes.csv",
            dtype=str,
            encoding="utf-8-sig",
        ).fillna("")
        parties = party_registry.loc[
            party_registry["election"] == election, "source_column"
        ].tolist()
        missing_parties = [column for column in parties if column not in wide.columns]
        if missing_parties:
            raise ValueError(f"{election} is missing party columns: {missing_parties}")

        selected = wide[[*CORE_COLUMNS, *parties]].merge(
            assignments[assignment_columns],
            on="source_row_uid",
            how="left",
            validate="one_to_one",
        )
        if selected["geography_assignment_status"].eq("").any():
            raise ValueError(f"{election} contains rows without final assignment metadata")
        if selected["assignment_evidence_class"].eq("").any():
            raise ValueError(f"{election} contains rows without assignment evidence metadata")

        synthetic = selected[
            selected["assignment_is_synthetic_link"].str.lower() == "true"
        ]
        if synthetic["stat_area_id"].eq("").any():
            raise ValueError(f"{election} has a synthetic link without a stat-area ID")

        reconstructed = selected[
            selected["final_assignment_method"].str.startswith(
                "arcgis_residual_partition_tier_"
            )
        ]
        election_reviews = reconstruction_reviews[
            reconstruction_reviews["election"] == election
        ]
        expected_reconstructed_rows = int(
            pd.to_numeric(
                election_reviews["candidate_rows"], errors="raise"
            ).sum()
        )
        expected_reconstructed_voters = int(
            pd.to_numeric(
                election_reviews["candidate_actual_voters"], errors="raise"
            ).sum()
        )
        reconstructed_voters = int(
            pd.to_numeric(
                reconstructed["actual_voters"], errors="raise"
            ).sum()
        )
        if (
            len(reconstructed) != expected_reconstructed_rows
            or reconstructed_voters != expected_reconstructed_voters
        ):
            raise ValueError(
                f"{election} reconstructed assignment totals do not match "
                "the reviewed ArcGIS decisions"
            )

        party_sum = (
            selected[parties]
            .apply(pd.to_numeric, errors="coerce")
            .fillna(0)
            .sum(axis=1)
        )
        valid_votes = pd.to_numeric(selected["valid_votes"], errors="coerce").fillna(0)
        if not party_sum.eq(valid_votes).all():
            bad = int((party_sum != valid_votes).sum())
            raise ValueError(f"{election} has {bad} rows whose party votes do not reconcile")

        actual_voters = pd.to_numeric(selected["actual_voters"], errors="raise")
        invalid_votes = pd.to_numeric(selected["invalid_votes"], errors="raise")
        turnout_reconciles = actual_voters.eq(valid_votes + invalid_votes)
        if not turnout_reconciles.all():
            bad = int((~turnout_reconciles).sum())
            raise ValueError(
                f"{election} has {bad} rows whose actual voters do not reconcile "
                "to valid plus invalid votes"
            )

        stat_rows = selected[selected["stat_area_id"] != ""]
        missing_stat_ids = sorted(
            set(stat_rows["stat_area_id"]) - statistical_ids[vintage]
        )
        if missing_stat_ids:
            raise ValueError(
                f"{election} has statistical-area IDs absent from {vintage} geometry: "
                f"{missing_stat_ids[:10]}"
            )

        locality_rows = selected[selected["is_locality_mapped"].str.lower() == "true"]
        missing_locality_ids = sorted(
            set(locality_rows["locality_geography_id"]) - locality_mode_ids
        )
        if missing_locality_ids:
            raise ValueError(
                f"{election} has locality IDs absent from published geometry: "
                f"{missing_locality_ids[:10]}"
            )

        custom_stat_rows = selected[
            (selected["is_mapped"].str.lower() == "true")
            & (selected["geography_type"] == "custom_geography")
        ]
        missing_custom_ids = sorted(
            set(custom_stat_rows["geography_id"]) - locality_mode_ids
        )
        if missing_custom_ids:
            raise ValueError(
                f"{election} has custom IDs absent from published geometry: "
                f"{missing_custom_ids[:10]}"
            )

        path = OUT_ROOT / "ballots" / f"{election.lower()}.csv"
        write_bytes(path, csv_bytes(selected))
        manifest.append(
            manifest_row(
                path,
                "ballot-results",
                "Complete ballot-row vote table with statistical and locality join IDs.",
                rows=len(selected),
                election=election,
                stat_area_vintage=vintage,
            )
        )
        total_rows += len(selected)
        validation_rows.append(
            {
                "election": election,
                "rows": len(selected),
                "party_columns": len(parties),
                "stat_area_vintage": vintage,
                "statistically_mapped_rows": len(stat_rows),
                "reconstructed_stat_assignment_rows": len(reconstructed),
                "reconstructed_stat_assignment_actual_voters": reconstructed_voters,
                "synthetic_assignment_rows": len(synthetic),
                "synthetic_assignment_actual_voters": int(
                    pd.to_numeric(
                        synthetic["actual_voters"], errors="raise"
                    ).sum()
                ),
                "assignment_evidence_classes": selected[
                    "assignment_evidence_class"
                ].value_counts().to_dict(),
                "locality_mapped_rows": len(locality_rows),
                "missing_stat_geometry_ids": len(missing_stat_ids),
                "missing_locality_geometry_ids": len(missing_locality_ids),
                "actual_vote_reconciliation_mismatch_rows": 0,
                "party_vote_mismatch_rows": 0,
            }
        )

    if total_rows != len(assignments):
        raise ValueError(
            f"Public ballot exports contain {total_rows} rows; assignments contain {len(assignments)}"
        )
    return validation_rows, total_rows


def copy_table(
    source: Path,
    target: Path,
    manifest: list[dict[str, Any]],
    category: str,
    description: str,
    election: str = "",
    stat_area_vintage: int | str = "",
    geography_id_source: str = "",
    valid_geography_ids: set[str] | None = None,
) -> int:
    frame = pd.read_csv(source, dtype=str, encoding="utf-8-sig").fillna("")
    if geography_id_source:
        if geography_id_source not in frame.columns:
            raise ValueError(
                f"{source} is missing geography join column {geography_id_source}"
            )
        if "geography_id" not in frame.columns:
            frame.insert(1, "geography_id", frame[geography_id_source])
        if frame["geography_id"].eq("").any():
            raise ValueError(f"{source} contains a blank geography_id")
        if valid_geography_ids is not None:
            missing_ids = sorted(set(frame["geography_id"]) - valid_geography_ids)
            if missing_ids:
                raise ValueError(
                    f"{source} has geography IDs absent from published geometry: "
                    f"{missing_ids[:10]}"
                )
        geography_types = frame["geography_id"].map(
            lambda value: (
                "statistical_area"
                if value.startswith("stat")
                else "composite_locality"
                if value.startswith("composite:")
                else "custom_geography"
                if value.startswith("custom:")
                else "locality"
            )
        )
        frame.insert(2, "geography_type", geography_types)
    write_bytes(target, csv_bytes(frame))
    manifest.append(
        manifest_row(
            target,
            category,
            description,
            rows=len(frame),
            election=election,
            stat_area_vintage=stat_area_vintage,
        )
    )
    return len(frame)


def copy_json_artifact(
    source: Path,
    target: Path,
    manifest: list[dict[str, Any]],
    description: str,
) -> None:
    if not source.exists():
        raise FileNotFoundError(source)
    payload = json.loads(source.read_text(encoding="utf-8-sig"))
    write_bytes(
        target,
        (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
    )
    manifest.append(
        manifest_row(
            target,
            "assignment-provenance",
            description,
        )
    )


def build_assignment_provenance(manifest: list[dict[str, Any]]) -> None:
    target_dir = OUT_ROOT / "metadata" / "assignment-provenance"
    for source, filename, description in PROVENANCE_TABLES:
        copy_table(
            source,
            target_dir / filename,
            manifest,
            "assignment-provenance",
            description,
        )
    for source, filename in PROVENANCE_JSON:
        copy_json_artifact(
            source,
            target_dir / filename,
            manifest,
            "Machine-readable summary for the corresponding assignment audit.",
        )
    copy_json_artifact(AUDIT_DIR / "k26_source_audit.json", target_dir / "k26_source_audit.json", manifest,
                       "K26 source reconciliation, certification status, and conservative area-assignment policy.")
    copy_table(AUDIT_DIR / "k26_validated_register_links.csv", target_dir / "k26_validated_register_links.csv", manifest,
               "assignment-provenance", "High-confidence synthetic K26 ballot links validated against official planned and final polling registers.")
    for filename in ["ballots.csv", "localities.csv", "crosswalk.xlsx", "stable_ballots.xlsx",
                     "crosswalk_readme.pdf", "stable_ballots_readme.pdf", "parties.json", "sources.json",
                     "planned_register.xlsx", "final_register.xlsx"]:
        source = RAW_DIR / "k26" / filename
        target = OUT_ROOT / "sources" / "k26" / filename
        write_bytes(target, source.read_bytes())
        manifest.append(manifest_row(target, "official-source-snapshot",
                                     "Unmodified official K26 source snapshot; source URLs and SHA-256 hashes are in sources.json.", election="K26"))


def build_metadata_and_aggregates(
    party_registry: pd.DataFrame,
    valid_geography_ids: set[str],
    manifest: list[dict[str, Any]],
) -> dict[str, int]:
    forbidden_party_fields = [
        column
        for column in party_registry.columns
        if "color" in column.lower() or "colour" in column.lower()
    ]
    if forbidden_party_fields:
        raise ValueError(
            "Public party metadata must not contain map color fields: "
            f"{forbidden_party_fields}"
        )
    parties_path = OUT_ROOT / "metadata" / "parties.csv"
    write_bytes(parties_path, csv_bytes(party_registry))
    manifest.append(
        manifest_row(
            parties_path,
            "metadata",
            "Election-specific party/list lookup keyed by election and source_column; no map colors.",
            rows=len(party_registry),
        )
    )

    reviews = pd.read_csv(MANUAL_DIR / "k26_party_wikipedia_reviews.csv", dtype=str).fillna("")
    reviews_path = OUT_ROOT / "metadata" / "party-wikipedia-reviews" / "k26.csv"
    write_bytes(reviews_path, csv_bytes(reviews))
    manifest.append(manifest_row(
        reviews_path, "metadata", "K26 below-threshold Wikipedia identity review including contextual links and deliberate blanks.",
        rows=len(reviews), election="K26",
    ))

    election_rows = []
    geographic_aggregate_rows = 0
    for number in sorted(ELECTIONS):
        election = ELECTIONS[number]["key"]
        vintage = ELECTION_VINTAGES[election]
        election_rows.append(
            {
                "election": election,
                "election_number": number,
                "year": ELECTIONS[number]["year"],
                "label": ELECTIONS[number]["label"],
                "stat_area_vintage": vintage,
                "ballot_results_path": f"ballots/{election.lower()}.csv",
                "statistical_results_path": (
                    f"aggregates/statistical-areas/{election.lower()}.csv"
                ),
                "locality_results_path": f"aggregates/localities/{election.lower()}.csv",
                "statistical_geometry_archive": (
                    f"geographies/statistical_areas_{vintage}.zip"
                ),
            }
        )
    elections = pd.DataFrame(election_rows)
    elections_path = OUT_ROOT / "metadata" / "elections.csv"
    write_bytes(elections_path, csv_bytes(elections))
    manifest.append(
        manifest_row(
            elections_path,
            "metadata",
            "Election years, active statistical-area vintages, and principal download paths.",
            rows=len(elections),
        )
    )

    copy_table(
        PUBLIC_DIR / "election_summary.csv",
        OUT_ROOT / "metadata" / "coverage.csv",
        manifest,
        "metadata",
        "Per-election statistical and locality mapping coverage.",
    )

    for number in sorted(ELECTIONS):
        election = ELECTIONS[number]["key"]
        vintage = ELECTION_VINTAGES[election]
        for source_dir, target_dir, geography_id_source in AGGREGATE_EXPORTS:
            copied_rows = copy_table(
                PUBLIC_DIR / source_dir / f"{election.lower()}.csv",
                OUT_ROOT / "aggregates" / target_dir / f"{election.lower()}.csv",
                manifest,
                f"aggregate-{target_dir}",
                f"{election} {target_dir} aggregate or review table.",
                election=election,
                stat_area_vintage=vintage,
                geography_id_source=geography_id_source,
                valid_geography_ids=(
                    valid_geography_ids if geography_id_source else None
                ),
            )
            if geography_id_source:
                geographic_aggregate_rows += copied_rows
    return {
        "geographic_aggregate_rows": geographic_aggregate_rows,
        "missing_aggregate_geometry_ids": 0,
    }


def write_manifests(
    manifest: list[dict[str, Any]],
    validation_rows: list[dict[str, Any]],
    total_rows: int,
    aggregate_validation: dict[str, int],
) -> None:
    manifest = sorted(manifest, key=lambda row: row["path"])
    fields = [
        "path",
        "category",
        "election",
        "stat_area_vintage",
        "format",
        "rows_or_features",
        "bytes",
        "sha256",
        "description",
    ]
    text = io.StringIO(newline="")
    writer = csv.DictWriter(text, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(manifest)
    write_bytes(OUT_ROOT / "manifest.csv", ("\ufeff" + text.getvalue()).encode("utf-8"))
    write_bytes(
        OUT_ROOT / "manifest.json",
        (
            json.dumps(
                {
                    "schema_version": 2,
                    "data_release": "v2.3",
                    "election_range": {"first": "K17", "last": "K26"},
                    "files": manifest,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        ).encode("utf-8"),
    )
    write_bytes(
        OUT_ROOT / "validation.json",
        (
            json.dumps(
                {
                    "schema_version": 2,
                    "total_ballot_rows": total_rows,
                    "aggregate_joins": aggregate_validation,
                    "elections": validation_rows,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        ).encode("utf-8"),
    )


def main() -> None:
    reset_generated_outputs()
    manifest: list[dict[str, Any]] = []
    party_registry = pd.read_csv(
        PARTY_REGISTRY, dtype=str, encoding="utf-8-sig"
    ).fillna("")
    statistical_ids, locality_mode_ids, geography_metadata = build_geography_packages(
        manifest
    )
    validation_rows, total_rows = build_ballot_exports(
        party_registry, statistical_ids, locality_mode_ids, manifest
    )
    aggregate_validation = build_metadata_and_aggregates(
        party_registry,
        set(geography_metadata["geography_id"].astype(str)),
        manifest,
    )
    build_assignment_provenance(manifest)
    write_manifests(manifest, validation_rows, total_rows, aggregate_validation)

    print(f"public_data_release={OUT_ROOT.relative_to(ROOT).as_posix()}")
    print(f"ballot_rows={total_rows}")
    print(f"geography_features={len(geography_metadata)}")
    print(f"files={len(manifest)}")


if __name__ == "__main__":
    main()
