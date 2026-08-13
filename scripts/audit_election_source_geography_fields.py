from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

LOCAL_AUDIT_PYTHON = Path(__file__).resolve().parents[1] / ".local" / "python-audit"
if LOCAL_AUDIT_PYTHON.exists():
    sys.path.append(str(LOCAL_AUDIT_PYTHON))

import pandas as pd

from pipeline_common import PROCESSED_DIR, RAW_DIR, write_csv, write_json


OUT_DIR = PROCESSED_DIR / "audits"
HISTORICAL_DIR = RAW_DIR / "cbs_historical_geography"
CBS_CATALOG = RAW_DIR / "cbs_catalog_geography_files.json"

CEC_REPORTS = [
    ("K20", RAW_DIR / "archive_knesset20_tell_the_polls_9_3.xls"),
    ("K21", RAW_DIR / "archive_knesset21_kalpies_full_report.xls"),
    (
        "K22",
        RAW_DIR / "archive_knesset22_kalpies_report_tofes_b_6th_edition_15_9.xlsx",
    ),
    ("K23", RAW_DIR / "archive_knesset23_kalpies_report_19_1_20_1.xlsx"),
    ("K24", RAW_DIR / "archive_knesset24_kalpies_report_tofes_a_25_12_20.xlsx"),
    ("K24", RAW_DIR / "archive_knesset24_kalpies_report_tofes_b_18_3_21.xlsx"),
    ("K25", RAW_DIR / "election-25_kalpi-places_kalpies_list_10_7_nagish.xlsx"),
    ("K25", RAW_DIR / "archive_knesset25_kalpies_list_27_10.xlsx"),
    (
        "K25",
        RAW_DIR / "election-25_kalpi-places_statistic_report_10_7_nagish.xlsx",
    ),
]

CBS_CROSSWALKS = [
    ("K17", HISTORICAL_DIR / "k17_ballot_to_stat1995.xls"),
    ("K18", HISTORICAL_DIR / "k18_ballot_to_stat2008.xlsx"),
    ("K19", HISTORICAL_DIR / "k19_ballot_to_stat2011.xlsx"),
    ("K20", HISTORICAL_DIR / "k20_ballot_to_stat2011.xlsx"),
    ("K21", HISTORICAL_DIR / "k21_ballot_to_stat2011.xlsx"),
    ("K22", HISTORICAL_DIR / "k22_ballot_to_stat2011.xlsx"),
    ("K23", HISTORICAL_DIR / "k23_ballot_to_stat2011.xlsx"),
    ("K24", HISTORICAL_DIR / "k24_ballot_to_stat2011.xlsx"),
    ("K25", HISTORICAL_DIR / "k25_ballot_to_stat2011.xlsx"),
]


def normalized_label(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    text = unicodedata.normalize("NFKC", str(value)).lower()
    text = text.replace("\u200e", "").replace("\u200f", "")
    return re.sub(r"[^0-9a-z\u0590-\u05ff]+", "", text)


def is_ags_label(value: Any) -> bool:
    label = normalized_label(value)
    return label in {"אגס", "ags"}


def is_stat_area_label(value: Any) -> bool:
    label = normalized_label(value)
    return (
        "אזורסטטיסטי" in label
        or "איזורסטטיסטי" in label
        or label in {"stat", "statarea", "statisticalarea", "statzone"}
    )


def read_sheets(path: Path) -> dict[str, pd.DataFrame]:
    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix.lower() == ".csv":
        return {
            "csv": pd.read_csv(
                path, header=None, dtype=str, encoding="utf-8-sig", low_memory=False
            )
        }
    workbook = pd.ExcelFile(path)
    return {
        str(sheet): pd.read_excel(workbook, sheet_name=sheet, header=None, dtype=str)
        for sheet in workbook.sheet_names
    }


def field_locations(
    sheets: dict[str, pd.DataFrame], predicate: Any
) -> list[str]:
    locations: list[str] = []
    for sheet_name, frame in sheets.items():
        for row_index, row in frame.iterrows():
            for column_index, value in row.items():
                if predicate(value):
                    locations.append(
                        f"{sheet_name}!R{int(row_index) + 1}C{int(column_index) + 1}"
                    )
    return locations


def audit_source(
    election: str, path: Path, source_family: str
) -> dict[str, Any]:
    sheets = read_sheets(path)
    ags_locations = field_locations(sheets, is_ags_label)
    stat_locations = field_locations(sheets, is_stat_area_label)
    if source_family == "cbs_ballot_to_statistical_area_crosswalk":
        interpretation = "official_direct_ballot_to_statistical_area_crosswalk"
    elif ags_locations:
        interpretation = "cec_polling_place_report_contains_ags"
    else:
        interpretation = "cec_polling_place_report_has_no_ags_field"
    return {
        "election": election,
        "source_family": source_family,
        "source_file": path.relative_to(RAW_DIR.parent).as_posix(),
        "source_format": path.suffix.lower().removeprefix("."),
        "sheets": "|".join(sheets),
        "sheet_count": len(sheets),
        "max_rows": max(len(frame) for frame in sheets.values()),
        "max_columns": max(len(frame.columns) for frame in sheets.values()),
        "ags_field_detected": bool(ags_locations),
        "ags_field_locations": "|".join(ags_locations),
        "stat_area_field_detected": bool(stat_locations),
        "stat_area_field_locations": "|".join(stat_locations),
        "audit_interpretation": interpretation,
    }


def csv_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return frame.where(pd.notna(frame), "").to_dict("records")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    rows = [
        audit_source(election, path, "cec_polling_place_report")
        for election, path in CEC_REPORTS
    ]
    rows.extend(
        audit_source(election, path, "cbs_ballot_to_statistical_area_crosswalk")
        for election, path in CBS_CROSSWALKS
    )
    frame = pd.DataFrame(rows).sort_values(
        ["election", "source_family", "source_file"], kind="stable"
    )

    crosswalks = frame[
        frame["source_family"] == "cbs_ballot_to_statistical_area_crosswalk"
    ]
    if len(crosswalks) != 9 or not crosswalks["stat_area_field_detected"].all():
        raise ValueError("Every K17-K25 CBS crosswalk must expose a stat-area field")
    cec = frame[frame["source_family"] == "cec_polling_place_report"]
    cec_ags_elections = sorted(
        cec.loc[cec["ags_field_detected"], "election"].unique().tolist()
    )
    if cec_ags_elections != ["K23"]:
        raise ValueError(
            "Expected AGS in the archived CEC reports only for K23; found "
            f"{cec_ags_elections}"
        )

    catalog = json.loads(CBS_CATALOG.read_text(encoding="utf-8-sig"))
    catalog_names = [str(row.get("Name", "")) for row in catalog.get("value", [])]
    catalog_crosswalks = sorted(
        name
        for name in catalog_names
        if "kalpi" in normalized_label(name)
        and "stat" in normalized_label(name)
        and not normalized_label(name).startswith("readme")
        and Path(name).suffix.lower() in {".xls", ".xlsx"}
    )
    catalog_stable = sorted(
        name
        for name in catalog_names
        if "stablekalp" in normalized_label(name)
        and not normalized_label(name).startswith("readme")
        and Path(name).suffix.lower() in {".xls", ".xlsx"}
    )
    in_scope_crosswalks = [
        name for name in catalog_crosswalks if "2002" not in normalized_label(name)
    ]
    if len(in_scope_crosswalks) != 9 or len(catalog_stable) != 7:
        raise ValueError(
            "CBS catalog no longer has the expected one K17-K25 crosswalk per "
            "election and seven K19-K25 stability workbooks"
        )

    write_csv(
        OUT_DIR / "election_source_geography_field_audit.csv",
        csv_records(frame),
        list(frame.columns),
    )
    write_json(
        OUT_DIR / "election_source_geography_field_audit.json",
        {
            "status": "complete",
            "sources_audited": len(frame),
            "cbs_crosswalk_elections": crosswalks["election"].tolist(),
            "cec_reports_with_ags": cec_ags_elections,
            "cec_reports_without_ags": sorted(
                cec.loc[~cec["ags_field_detected"], "election"].unique().tolist()
            ),
            "cbs_catalog_in_scope_ballot_crosswalk_files": in_scope_crosswalks,
            "cbs_catalog_stable_ballot_files": catalog_stable,
            "cbs_catalog_scope_note": (
                "The downloaded CBS geography catalog contains exactly one in-scope "
                "direct crosswalk for each election K17-K25 and one stability "
                "workbook for each transition ending K19-K25; no alternate in-scope "
                "ballot geography workbook is listed."
            ),
            "interpretation": (
                "The official CBS catalog supplies one direct ballot-to-statistical-"
                "area crosswalk for every election K17-K25. Among the separately "
                "archived CEC polling-place reports audited here, only K23 exposes "
                "an AGS field."
            ),
        },
    )
    print(f"sources_audited={len(frame)}")
    print(f"cec_reports_with_ags={'|'.join(cec_ags_elections)}")


if __name__ == "__main__":
    main()
