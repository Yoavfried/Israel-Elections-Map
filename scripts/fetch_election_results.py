from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import urllib.request
from urllib.parse import urlencode
from pathlib import Path

from fetch_k26_sources import OUT as K26_SOURCE_DIR, SOURCES as K26_SOURCES, main as fetch_k26_sources
from pipeline_common import ELECTIONS, PROCESSED_DIR, RAW_DIR, ensure_dir, read_json, safe_filename, write_csv, write_json


PACKAGE_URL = "https://data.gov.il/api/3/action/package_show?id=26f9fa06-fcd7-4173-8df5-65797b63e857"
DATASTORE_URL = "https://data.gov.il/api/3/action/datastore_search"
USER_AGENT = "Mozilla/5.0 israel-election-map data pipeline"
MANIFEST_JSON = PROCESSED_DIR / "manifest" / "election_result_resources.json"


def fetch_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def election_number(name: str) -> int | None:
    match = re.search(r"ה-(\d+)", name)
    if not match:
        return None
    return int(match.group(1))


def is_ballot_resource(name: str) -> bool:
    return "קלפיות" in name


def download_datastore(resource_id: str, out_path: Path, overwrite: bool) -> tuple[str, int]:
    if out_path.exists() and not overwrite:
        with out_path.open(encoding="utf-8-sig", newline="") as handle:
            row_count = max(sum(1 for _ in handle) - 1, 0)
        return "cached", row_count

    records: list[dict] = []
    fieldnames: list[str] = []
    offset = 0
    while True:
        params = urlencode({"resource_id": resource_id, "limit": 5000, "offset": offset})
        payload = fetch_json(f"{DATASTORE_URL}?{params}")
        result = payload["result"]

        if not fieldnames:
            fieldnames = [field["id"] for field in result["fields"] if field["id"] != "_full_text"]

        batch = result["records"]
        records.extend(batch)
        if len(batch) < 5000:
            break
        offset += len(batch)

    ensure_dir(out_path.parent)
    write_csv(out_path, records, fieldnames)
    return "datastore_downloaded", len(records)


def cached_manifest_rows() -> list[dict]:
    if not MANIFEST_JSON.exists():
        return []
    rows = read_json(MANIFEST_JSON)
    for row in rows:
        local_path = RAW_DIR.parent / row["local_path"]
        if not local_path.exists():
            return []
    return rows


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--metadata-only", action="store_true")
    args = parser.parse_args()

    if not args.overwrite and not args.metadata_only:
        rows = cached_manifest_rows()
        if rows and {row["election"] for row in rows} == {e["key"] for e in ELECTIONS.values()} and all((K26_SOURCE_DIR / name).exists() for name in K26_SOURCES):
            print(f"resources={len(rows)}")
            for row in rows:
                print(f"{row['election']}: cached_manifest rows={row['row_count']} -> {row['local_path']}")
            return

    cached = cached_manifest_rows() if not args.overwrite else []
    if cached:
        rows = [row for row in cached if row["election"] != "K26"]
        resources = []
    else:
        package = fetch_json(PACKAGE_URL)
        resources = package["result"]["resources"]
        rows = []

    for resource in resources:
        name = resource.get("name") or ""
        number = election_number(name)
        if number not in ELECTIONS or not is_ballot_resource(name):
            continue

        out_name = f"k{number}_ballots_{safe_filename(resource['id'])}.csv"
        out_path = RAW_DIR / "election_results" / out_name
        row_count = ""
        if args.metadata_only:
            status = "metadata_only"
        else:
            status, row_count = download_datastore(resource["id"], out_path, args.overwrite)
        rows.append(
            {
                "election": ELECTIONS[number]["key"],
                "election_number": number,
                "year": ELECTIONS[number]["year"],
                "resource_id": resource["id"],
                "resource_name": name,
                "format": resource.get("format") or "",
                "url": resource["url"],
                "local_path": str(out_path.relative_to(RAW_DIR.parent)).replace("\\", "/"),
                "status": status,
                "row_count": row_count,
            }
        )

    count = ""
    if not args.metadata_only:
        fetch_k26_sources()
        path = K26_SOURCE_DIR / "ballots.csv"
        with path.open(encoding="utf-8-sig", newline="") as handle:
            count = sum(1 for _ in csv.DictReader(handle))
    rows.append({
        "election": "K26", "election_number": 26, "year": 2026,
        "resource_id": "cec-k26-2026-10-30", "resource_name": "K26 CEC ballot results",
        "format": "CSV", "url": "https://media26.bechirot.gov.il/files/expb.csv",
        "local_path": "raw/k26/ballots.csv", "status": "metadata_only" if args.metadata_only else "cached", "row_count": count,
    })

    rows.sort(key=lambda row: row["election_number"], reverse=True)
    write_csv(
        PROCESSED_DIR / "manifest" / "election_result_resources.csv",
        rows,
        [
            "election",
            "election_number",
            "year",
            "resource_id",
            "resource_name",
            "format",
            "url",
            "local_path",
            "status",
            "row_count",
        ],
    )
    write_json(PROCESSED_DIR / "manifest" / "election_result_resources.json", rows)

    print(f"resources={len(rows)}")
    for row in rows:
        print(f"{row['election']}: {row['status']} rows={row['row_count']} -> {row['local_path']}")


if __name__ == "__main__":
    main()
