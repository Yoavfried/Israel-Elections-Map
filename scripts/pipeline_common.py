from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
MANUAL_DIR = DATA_DIR / "manual"
PROCESSED_DIR = DATA_DIR / "processed"

ELECTIONS: dict[int, dict[str, Any]] = {
    26: {"key": "K26", "year": 2026, "label": "Knesset 26"},
    25: {"key": "K25", "year": 2022, "label": "Knesset 25"},
    24: {"key": "K24", "year": 2021, "label": "Knesset 24"},
    23: {"key": "K23", "year": 2020, "label": "Knesset 23"},
    22: {"key": "K22", "year": "2019 Sep", "label": "Knesset 22"},
    21: {"key": "K21", "year": "2019 Apr", "label": "Knesset 21"},
    20: {"key": "K20", "year": 2015, "label": "Knesset 20"},
    19: {"key": "K19", "year": 2013, "label": "Knesset 19"},
    18: {"key": "K18", "year": 2009, "label": "Knesset 18"},
    17: {"key": "K17", "year": 2006, "label": "Knesset 17"},
}


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, data: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    ensure_dir(path.parent)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def preserve_other_elections(path: Path, rows: list[dict[str, Any]], election: str | None) -> list[dict[str, Any]]:
    if not election or not path.exists():
        return rows
    with path.open(encoding="utf-8-sig", newline="") as handle:
        retained = [row for row in csv.DictReader(handle) if row.get("election", row.get("elections", "")) != election]
    return retained + rows


def normalize_spaces(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_code(value: Any) -> str:
    digits = "".join(re.findall(r"\d+", str(value or "")))
    return str(int(digits)) if digits else ""


def normalize_kalpi(value: Any) -> str:
    text = str(value or "").replace(",", ".").strip()
    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return ""
    candidate = match.group(0)
    try:
        as_float = float(candidate)
    except ValueError:
        return candidate
    if as_float.is_integer():
        return str(int(as_float))
    return candidate.rstrip("0").rstrip(".")


def int_value(value: Any) -> int:
    if value is None:
        return 0
    text = str(value).replace(",", "")
    match = re.search(r"-?\d+", text)
    return int(match.group(0)) if match else 0


def safe_filename(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9._-]+", "_", value)
    return value.strip("_")
