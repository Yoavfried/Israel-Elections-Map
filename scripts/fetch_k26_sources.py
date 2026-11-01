"""Cache the official K26 publication snapshot without changing earlier sources."""
from __future__ import annotations

import hashlib
import sys
import urllib.parse
import urllib.request
import zipfile

from pipeline_common import RAW_DIR, ensure_dir, write_json

CBS = "https://www.cbs.gov.il/he/publications/DocLib/2022/קטלוג/1. יישובים וחלוקות גאוגרפיות/"
SOURCES = {
    "ballots.csv": "https://media26.bechirot.gov.il/files/expb.csv",
    "localities.csv": "https://media26.bechirot.gov.il/files/expc.csv",
    "crosswalk.xlsx": CBS + "kalpi_October2026_stat2022.xlsx",
    "stable_ballots.xlsx": CBS + "Stable_kalpi_october_2026.xlsx",
    "crosswalk_readme.pdf": CBS + "ReadMe_Kalpi_October2026_Stat2022.pdf",
    "stable_ballots_readme.pdf": CBS + "ReadMe_Stable_Kalpi_October2026.pdf",
    "parties.json": "https://elections.govmap.gov.il/data/votes/elections.json",
    "statisticalareas_demography_2025.gdb.zip": CBS + "statisticalareas_demography_2025.gdb.zip",
}
OUT = RAW_DIR / "k26"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ensure_dir(OUT)
    rows = []
    for name, url in SOURCES.items():
        path = OUT / name
        if not path.exists():
            request = urllib.request.Request(
                urllib.parse.quote(url, safe=":/?=&%"),
                headers={"User-Agent": "Mozilla/5.0 israel-election-map"},
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                data = response.read()
            if b"<html" in data[:1000].lower() or b"<!doctype" in data[:1000].lower():
                raise ValueError(f"HTML returned instead of {name}")
            path.write_bytes(data)
        data = path.read_bytes()
        rows.append({"file": name, "url": url, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    write_json(OUT / "sources.json", rows)
    geography = OUT / "geography"
    if not list(geography.glob("*.gdb")):
        ensure_dir(geography)
        with zipfile.ZipFile(OUT / "statisticalareas_demography_2025.gdb.zip") as archive:
            for name in archive.namelist():
                if not (geography / name).resolve().is_relative_to(geography.resolve()):
                    raise ValueError("Unsafe CBS geography archive path")
            archive.extractall(geography)
    print(f"K26 source snapshot: {len(rows)} files")


if __name__ == "__main__":
    main()
