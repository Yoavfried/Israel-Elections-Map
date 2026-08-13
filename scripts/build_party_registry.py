#!/usr/bin/env python3
"""Build the election-specific ballot-list registry for K17 through K25.

The checked-in output is a snapshot. This script is intentionally separate from
the normal application build because refreshing it requires network access.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from collections.abc import Iterable
from pathlib import Path

import pdfplumber
from lxml import html


ROOT = Path(__file__).resolve().parents[1]
PARTY_COLUMNS_PATH = ROOT / "data" / "processed" / "normalized" / "party_columns.csv"
OUTPUT_PATH = ROOT / "data" / "manual" / "party_registry.csv"
REVIEWED_DISPLAY_NAMES_PATH = ROOT / "data" / "manual" / "party_display_names_en.csv"
AUDIT_PATH = ROOT / "data" / "processed" / "audits" / "party_registry_wikipedia_candidates.csv"
CACHE_ROOT = ROOT / "tmp" / "party_registry_sources"

USER_AGENT = "IsraelElectionMap/0.1 (party registry data builder)"
WIKIPEDIA_API = "https://he.wikipedia.org/w/api.php"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
WIKIDATA_HUMAN_ID = "Q5"

OFFICIAL_SOURCES = {
    "K17": "https://www.gov.il/BlobFolder/guide/election-committee-history/he/knesset17-results.pdf",
    "K18": "https://www.gov.il/BlobFolder/guide/election-committee-history/ar/history_election-dates_knesset18-results.pdf",
    "K19": "https://www.gov.il/BlobFolder/guide/election-committee-history/he/knesset19-results.pdf",
    "K20": "https://www.gov.il/BlobFolder/guide/election-committee-history/he/knesset20-results.pdf",
    "K21": "https://votes21.bechirot.gov.il/nationalresults",
    "K22": "https://votes22.bechirot.gov.il/nationalresults",
    "K23": "https://votes23.bechirot.gov.il/nationalresults",
    "K24": "https://votes24.bechirot.gov.il/",
    "K25": "https://votes25.bechirot.gov.il/nationalresults",
}

WIKIPEDIA_ELECTION_TITLES = {
    "K17": "הבחירות לכנסת השבע עשרה",
    "K18": "הבחירות לכנסת השמונה עשרה",
    "K19": "הבחירות לכנסת התשע עשרה",
    "K20": "הבחירות לכנסת העשרים",
    "K21": "הבחירות לכנסת העשרים ואחת",
    "K22": "הבחירות לכנסת העשרים ושתיים",
    "K23": "הבחירות לכנסת העשרים ושלוש",
    "K24": "הבחירות לכנסת העשרים וארבע",
    "K25": "הבחירות לכנסת העשרים וחמש",
}

IGNORED_SOURCE_COLUMNS = {("K18", "ת. עדכון")}
CANONICAL_BALLOT_LETTERS = {
    # The K19 source workbook misspells the official Meretz ballot code.
    ("K19", "מרץ"): "מרצ",
}
ZERO_VOTE_LIST_NAMES = {
    ("K24", "רק"): "דמוקרטית – חירות, שיוויון וערבות הדדית",
    ("K23", "זץ"): "צומת התנועה לציונות מתחדשת",
    ("K22", "זן"): "זהות - תנועה ישראלית יהודית בהנהגת משה פייגלין",
    ("K22", "כ"): "נעם - עם נורמלי בארצנו",
    ("K22", "נץ"): "כל ישראל אחים לשוויון חברתי",
    ("K21", "זנ"): "יחד בראשות אלי ישי",
    ("K21", "נך"): "מפלגת הרפורמה",
    ("K21", "ץז"): "אופק חדש בכבוד",
    ("K20", "יך"): "מגינים על ילדינו",
    ("K19", "זה"): "עתיד אחד – נלחמים בסם החדש",
    ("K19", "פך"): "נצח",
    ("K18", "פח"): "מהפך בחינוך",
}
ZERO_VOTE_SOURCE_OVERRIDES = {
    ("K18", "פח"): "https://www.gov.il/BlobFolder/guide/election-committee-history/ar/history_election-dates_knesset18-cand.pdf",
    ("K19", "זה"): "https://www.gov.il/BlobFolder/guide/election-committee-history/he/history_election-dates_knesset19-cand.pdf",
    ("K19", "פך"): "https://www.gov.il/BlobFolder/guide/election-committee-history/he/history_election-dates_knesset19-cand.pdf",
}
WIKIPEDIA_TITLE_OVERRIDES = {
    ("K23", "זץ"): "מפלגת צומת",
    ("K22", "זן"): "זהות (מפלגה)",
    ("K22", "כ"): "מפלגת נעם",
    ("K21", "זנ"): "יחד (אלי ישי)",
    ("K19", "פך"): "נצח (מפלגה)",
}
REGISTRY_FIELDS = [
    "election",
    "election_number",
    "source_column",
    "ballot_letter",
    "total_votes",
    "list_name_he",
    "name_source",
    "display_name_he",
    "display_name_en",
    "wikipedia_he_url",
    "wikipedia_en_url",
    "wikipedia_match_status",
    "official_source_url",
    "wikipedia_source_url",
    "notes",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Ignore cached source downloads.")
    parser.add_argument(
        "--apply-reviewed-names-only",
        action="store_true",
        help="Apply the checked-in English display names without refreshing source data.",
    )
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--audit-output", type=Path, default=AUDIT_PATH)
    return parser.parse_args()


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    value = value.replace("\xa0", " ").replace("\u200f", "").replace("\u200e", "")
    return " ".join(value.split())


def read_reviewed_display_names() -> dict[tuple[str, str], str]:
    with REVIEWED_DISPLAY_NAMES_PATH.open(
        "r", encoding="utf-8-sig", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))

    names: dict[tuple[str, str], str] = {}
    for row in rows:
        key = (row["election"].strip(), row["ballot_letter"].strip())
        name = row["display_name_en"].strip()
        if not all(key) or not name:
            raise ValueError("Reviewed English party names cannot contain blank keys or names.")
        if key in names:
            raise ValueError(f"Duplicate reviewed English party name for {key[0]}:{key[1]}.")
        names[key] = name
    return names


def apply_reviewed_display_names(
    rows: list[dict[str, object]],
    names: dict[tuple[str, str], str],
) -> None:
    row_keys = {
        (str(row["election"]), str(row["ballot_letter"]))
        for row in rows
    }
    unknown = sorted(set(names) - row_keys)
    if unknown:
        labels = ", ".join(f"{election}:{letter}" for election, letter in unknown)
        raise ValueError(f"Reviewed English party names contain unknown rows: {labels}")

    missing = sorted(
        (str(row["election"]), str(row["ballot_letter"]))
        for row in rows
        if int(str(row["total_votes"])) > 0
        and (str(row["election"]), str(row["ballot_letter"])) not in names
    )
    if missing:
        labels = ", ".join(f"{election}:{letter}" for election, letter in missing)
        raise ValueError(f"Positive-vote party rows lack reviewed English names: {labels}")

    for row in rows:
        key = (str(row["election"]), str(row["ballot_letter"]))
        if key in names:
            row["display_name_en"] = names[key]


def read_inventory() -> list[dict[str, str]]:
    with PARTY_COLUMNS_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [
        row
        for row in rows
        if (row["election"], row["source_column"]) not in IGNORED_SOURCE_COLUMNS
    ]


def canonical_ballot_letter(election: str, source_column: str) -> str:
    return CANONICAL_BALLOT_LETTERS.get((election, source_column), source_column)


def cached_download(url: str, cache_name: str, refresh: bool) -> bytes:
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_ROOT / cache_name
    if cache_path.exists() and not refresh:
        payload = cache_path.read_bytes()
        if not is_failed_download(payload, cache_name):
            return payload

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            payload = response.read()
    except OSError:
        payload = b""
    if is_failed_download(payload, cache_name):
        completed = subprocess.run(
            ["curl.exe", "-L", "--fail", "--max-time", "45", url],
            check=True,
            capture_output=True,
        )
        payload = completed.stdout
    cache_path.write_bytes(payload)
    return payload


def is_failed_download(payload: bytes, cache_name: str) -> bool:
    if not payload:
        return True
    if cache_name.endswith("-official.html"):
        return b"TableData" not in payload
    return b"Attention Required!" in payload or b"maintenance.gov.il/error.png" in payload


def official_cache_name(election: str, url: str) -> str:
    suffix = ".pdf" if url.lower().endswith(".pdf") else ".html"
    return f"{election.lower()}-official{suffix}"


def parse_official_html(payload: bytes) -> dict[str, dict[str, str | int]]:
    document = html.fromstring(payload)
    best_rows: dict[str, dict[str, str | int]] = {}

    for table in document.xpath("//table"):
        headers = [normalize_text(cell.text_content()) for cell in table.xpath(".//tr[1]/*[self::th or self::td]")]
        if "שם הרשימה" not in headers or "אותיות הרשימה" not in headers:
            continue
        name_index = headers.index("שם הרשימה")
        letter_index = headers.index("אותיות הרשימה")
        for row in table.xpath(".//tbody/tr"):
            cells = row.xpath("./*[self::th or self::td]")
            if len(cells) <= max(name_index, letter_index):
                continue
            letter = normalize_text(cells[letter_index].text_content())
            name_candidates = [
                normalize_text(cells[name_index].get("title")),
                normalize_text(cells[name_index].text_content()),
            ]
            name = max(name_candidates, key=len)
            if not letter or not name:
                continue
            vote_text = normalize_text(cells[-1].text_content())
            vote_match = re.search(r"[\d,]+", vote_text)
            best_rows[letter] = {
                "name": name,
                "votes": int(vote_match.group(0).replace(",", "")) if vote_match else 0,
            }
    return best_rows


def parse_official_pdf(
    payload: bytes,
    ballot_letters: set[str],
) -> dict[str, dict[str, str | int]]:
    lines: list[str] = []
    with pdfplumber.open(io.BytesIO(payload)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            lines.extend(normalize_text(line) for line in page_text.splitlines())

    reversed_letters = sorted(
        ((letter, letter[::-1]) for letter in ballot_letters),
        key=lambda pair: len(pair[1]),
        reverse=True,
    )
    rows: dict[str, dict[str, str | int]] = {}
    current_letter: str | None = None
    started = False

    for line in lines:
        compact_line = line.replace(" ", "")
        if "תולוקהרפסמהמישרהיוניכהמישרהתוא" in compact_line:
            started = True
            current_letter = None
            continue
        if not started:
            continue
        if "םירשכהתולוקהלכךס" in compact_line:
            break

        vote_match = re.match(r"^([\d,]+)\s+(.*)$", line)
        votes = int(vote_match.group(1).replace(",", "")) if vote_match else 0
        body = vote_match.group(2) if vote_match else line
        matched_letter = next(
            (
                letter
                for letter, reversed_letter in reversed_letters
                if body == reversed_letter or body.endswith(f" {reversed_letter}")
            ),
            None,
        )

        if matched_letter:
            reversed_letter = matched_letter[::-1]
            name_reversed = body[: -len(reversed_letter)].strip()
            rows[matched_letter] = {
                "name": normalize_text(name_reversed[::-1]),
                "votes": votes,
            }
            current_letter = matched_letter
        elif current_letter and line and not re.fullmatch(r"[_\d.,'\s]+", line):
            continuation = normalize_text(line[::-1])
            rows[current_letter]["name"] = normalize_text(
                f"{rows[current_letter]['name']} {continuation}"
            )

    return rows


def wikipedia_parse_payload(page_title: str, election: str, refresh: bool) -> dict:
    query = urllib.parse.urlencode(
        {
            "action": "parse",
            "page": page_title,
            "prop": "text",
            "format": "json",
            "formatversion": "2",
        }
    )
    payload = cached_download(
        f"{WIKIPEDIA_API}?{query}",
        f"{election.lower()}-wikipedia.json",
        refresh,
    )
    return json.loads(payload.decode("utf-8"))


def wiki_link_title(link) -> str:
    if "new" in (link.get("class") or "").split():
        return ""
    title = normalize_text(link.get("title"))
    href = link.get("href") or ""
    if not title and href.startswith("/wiki/"):
        title = urllib.parse.unquote(href.removeprefix("/wiki/")).replace("_", " ")
    if (
        not title
        or ":" in title
        or title.endswith("(הדף אינו קיים)")
        or title.startswith("הבחירות לכנסת")
    ):
        return ""
    return title


def cell_links(cell) -> list[str]:
    links: list[str] = []
    for link in cell.xpath(".//a[@href]"):
        title = wiki_link_title(link)
        if title and title not in links:
            links.append(title)
    return links


def parse_wikipedia_candidates(
    payload: dict,
    expected_rows: list[dict[str, str]],
) -> dict[str, dict[str, object]]:
    document = html.fromstring(payload["parse"]["text"])
    expected_letters = {row["source_column"] for row in expected_rows}
    letters_by_vote: dict[int, list[str]] = {}
    for row in expected_rows:
        votes = int(row["total_votes"])
        if votes > 0:
            letters_by_vote.setdefault(votes, []).append(row["source_column"])

    rows_by_letter: dict[str, dict[str, object]] = {}
    for table in document.xpath("//table[contains(concat(' ', normalize-space(@class), ' '), ' wikitable ')]"):
        header_cells = table.xpath("./tbody/tr[1]/th | ./tr[1]/th")
        headers = [normalize_text(cell.text_content()) for cell in header_cells]
        expanded_headers = [
            header
            for cell, header in zip(header_cells, headers, strict=True)
            for _ in range(int(cell.get("colspan") or "1"))
        ]
        if any(is_letter_header(header) for header in expanded_headers):
            merge_wikipedia_candidates(
                rows_by_letter,
                extract_wikipedia_table_rows(table, expected_letters, expanded_headers),
            )
        if any(normalize_text(cell.text_content()) == "קולות" for cell in table.xpath(".//th")):
            merge_wikipedia_candidates(
                rows_by_letter,
                extract_wikipedia_vote_rows(table, letters_by_vote),
            )
    return rows_by_letter


def is_letter_header(header: str) -> bool:
    return header in {"אות", "אותיות", "אות הרשימה", "אותיות הרשימה", "סימן"}


def merge_wikipedia_candidates(
    target: dict[str, dict[str, object]],
    candidates: dict[str, dict[str, object]],
) -> None:
    for letter, candidate in candidates.items():
        current = target.get(letter)
        if not current or wikipedia_candidate_score(candidate) > wikipedia_candidate_score(current):
            target[letter] = candidate


def wikipedia_candidate_score(candidate: dict[str, object]) -> int:
    eligible_links = 0
    for index, header in enumerate(candidate["headers"]):
        if "כינוי" in header or header in {"רשימה", "שם הרשימה", "מפלגה"}:
            eligible_links += len(candidate["links_by_cell"][index])
    basis_bonus = 5 if candidate.get("basis") == "vote_total" else 0
    return eligible_links * 10 + int(bool(fallback_wikipedia_name(candidate))) + basis_bonus


def extract_wikipedia_table_rows(
    table,
    expected_letters: set[str],
    headers: list[str],
) -> dict[str, dict[str, object]]:
    rows: dict[str, dict[str, object]] = {}
    for row in table.xpath("./tbody/tr[position() > 1] | ./tr[position() > 1]"):
        cells = row.xpath("./*[self::th or self::td]")
        if not cells:
            continue
        cell_texts = [normalize_text(cell.text_content()) for cell in cells]
        row_headers = headers[: len(cells)]
        letter_indexes = [index for index, header in enumerate(row_headers) if is_letter_header(header)]
        if not letter_indexes:
            letter_indexes = list(range(min(2, len(cells))))
        letter_matches = [
            (cell_index, letter)
            for cell_index in letter_indexes
            for text in [cell_texts[cell_index]]
            if len(text) <= 10
            for letter in expected_letters
            if text.startswith(letter)
        ]
        letter_match = max(letter_matches, key=lambda item: len(item[1]), default=None)
        if not letter_match:
            continue
        letter_index, letter = letter_match
        links_by_cell = [cell_links(cell) for cell in cells]
        rows[letter] = {
            "cell_texts": cell_texts,
            "links_by_cell": links_by_cell,
            "headers": row_headers,
            "letter_index": letter_index,
            "basis": "ballot_letter",
        }
    return rows


def extract_wikipedia_vote_rows(
    table,
    letters_by_vote: dict[int, list[str]],
) -> dict[str, dict[str, object]]:
    rows: dict[str, dict[str, object]] = {}
    for row in table.xpath("./tbody/tr[position() > 1] | ./tr[position() > 1]"):
        cells = row.xpath("./*[self::th or self::td]")
        if not cells:
            continue
        cell_texts = [normalize_text(cell.text_content()) for cell in cells]
        matched_letters: list[str] = []
        for value in cell_texts:
            vote_match = re.fullmatch(r"([\d,]+)(?:\[.*\])?", value)
            if not vote_match:
                continue
            votes = int(vote_match.group(1).replace(",", ""))
            if len(letters_by_vote.get(votes, [])) == 1:
                matched_letters = letters_by_vote[votes]
                break
        if not matched_letters:
            continue
        letter = matched_letters[0]
        list_index = next(
            (
                index
                for index, value in enumerate(cell_texts)
                if value and re.search(r"[א-ת]", value)
            ),
            0,
        )
        row_headers = [""] * len(cells)
        row_headers[list_index] = "רשימה"
        rows[letter] = {
            "cell_texts": cell_texts,
            "links_by_cell": [cell_links(cell) for cell in cells],
            "headers": row_headers,
            "letter_index": -1,
            "basis": "vote_total",
        }
    return rows


def choose_wikipedia_title(candidate: dict[str, object] | None) -> tuple[str, str]:
    if not candidate:
        return "", "no_wikipedia_table_row"

    links_by_cell = candidate["links_by_cell"]
    headers = candidate["headers"]
    nickname_links: list[str] = []
    for index, header in enumerate(headers):
        if "כינוי" not in header and header not in {"רשימה", "שם הרשימה"}:
            continue
        for title in links_by_cell[index]:
            if title not in nickname_links:
                nickname_links.append(title)
    if len(nickname_links) == 1:
        return nickname_links[0], "list_article"

    party_links: list[str] = []
    for index, header in enumerate(headers):
        if "מפלגה" not in header:
            continue
        for title in links_by_cell[index]:
            if title not in party_links:
                party_links.append(title)
    if len(party_links) == 1:
        return party_links[0], "single_party_article"
    return "", "no_standalone_article"


def chunks(values: list[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


def fetch_wikipedia_page_info(titles: set[str], refresh: bool) -> dict[str, dict[str, str]]:
    if not titles:
        return {}

    result: dict[str, dict[str, str]] = {}
    for batch_number, batch in enumerate(chunks(sorted(titles), 40), start=1):
        batch_hash = hashlib.sha256("\n".join(batch).encode("utf-8")).hexdigest()[:12]
        query = urllib.parse.urlencode(
            {
                "action": "query",
                "prop": "info|langlinks|pageprops",
                "inprop": "url",
                "lllang": "en",
                "lllimit": "max",
                "llprop": "url",
                "ppprop": "wikibase_item",
                "redirects": "1",
                "titles": "|".join(batch),
                "format": "json",
                "formatversion": "2",
            }
        )
        payload = cached_download(
            f"{WIKIPEDIA_API}?{query}",
            f"wikipedia-page-info-v3-{batch_number}-{batch_hash}.json",
            refresh,
        )
        response = json.loads(payload.decode("utf-8"))["query"]
        aliases = {item["from"]: item["to"] for item in response.get("normalized", [])}
        aliases.update({item["from"]: item["to"] for item in response.get("redirects", [])})
        pages = {page["title"]: page for page in response["pages"] if "missing" not in page}
        for original_title in batch:
            resolved_title = original_title
            while resolved_title in aliases:
                resolved_title = aliases[resolved_title]
            page = pages.get(resolved_title)
            if not page:
                continue
            english_link = next(iter(page.get("langlinks", [])), {})
            result[original_title] = {
                "he_title": page["title"],
                "he_url": page.get("fullurl", ""),
                "en_title": english_link.get("title", ""),
                "en_url": english_link.get("url", ""),
                "wikidata_id": page.get("pageprops", {}).get("wikibase_item", ""),
            }
    return result


def fetch_wikidata_instances(
    wikidata_ids: set[str],
    refresh: bool,
) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for batch_number, batch in enumerate(chunks(sorted(wikidata_ids), 50), start=1):
        batch_hash = hashlib.sha256("\n".join(batch).encode("utf-8")).hexdigest()[:12]
        query = urllib.parse.urlencode(
            {
                "action": "wbgetentities",
                "ids": "|".join(batch),
                "props": "claims",
                "format": "json",
                "formatversion": "2",
            }
        )
        payload = cached_download(
            f"{WIKIDATA_API}?{query}",
            f"wikidata-instances-{batch_number}-{batch_hash}.json",
            refresh,
        )
        entities = json.loads(payload.decode("utf-8")).get("entities", {})
        for wikidata_id in batch:
            claims = entities.get(wikidata_id, {}).get("claims", {}).get("P31", [])
            result[wikidata_id] = {
                claim.get("mainsnak", {})
                .get("datavalue", {})
                .get("value", {})
                .get("id", "")
                for claim in claims
            } - {""}
    return result


def fallback_wikipedia_name(candidate: dict[str, object] | None) -> str:
    if not candidate:
        return ""
    texts = candidate["cell_texts"]
    headers = candidate["headers"]
    for index, header in enumerate(headers):
        if "כינוי" not in header and header not in {"רשימה", "שם הרשימה"}:
            continue
        value = texts[index]
        if value and not re.fullmatch(r"[\d.%–—-]+", value):
            return value
    return ""


def has_broken_hebrew_spacing(value: str) -> bool:
    hebrew_runs = re.findall(r"[א-ת]+", value)
    return bool(hebrew_runs) and max(map(len, hebrew_runs)) >= 16


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    reviewed_display_names = read_reviewed_display_names()

    if args.apply_reviewed_names_only:
        if not args.output.exists():
            print(f"Registry does not exist: {args.output}", file=sys.stderr)
            return 1
        with args.output.open("r", encoding="utf-8-sig", newline="") as handle:
            registry_rows = list(csv.DictReader(handle))
        apply_reviewed_display_names(registry_rows, reviewed_display_names)
        write_csv(args.output, registry_rows, REGISTRY_FIELDS)
        print(
            f"Applied {len(reviewed_display_names)} reviewed English names to "
            f"{args.output.relative_to(ROOT)}"
        )
        return 0

    inventory = read_inventory()
    by_election: dict[str, list[dict[str, str]]] = {}
    for row in inventory:
        by_election.setdefault(row["election"], []).append(row)

    official_rows: dict[tuple[str, str], dict[str, str | int]] = {}
    wiki_candidates: dict[tuple[str, str], dict[str, object]] = {}
    selected_titles: dict[tuple[str, str], tuple[str, str]] = {}

    for election, rows in by_election.items():
        source_columns = {row["source_column"] for row in rows}
        official_letters = {
            canonical_ballot_letter(election, source_column)
            for source_column in source_columns
        }
        official_url = OFFICIAL_SOURCES[election]
        official_payload = cached_download(
            official_url,
            official_cache_name(election, official_url),
            args.refresh,
        )
        parsed_official = (
            parse_official_pdf(official_payload, official_letters)
            if official_url.endswith(".pdf")
            else parse_official_html(official_payload)
        )
        for source_column in source_columns:
            official = parsed_official.get(
                canonical_ballot_letter(election, source_column)
            )
            if official:
                official_rows[(election, source_column)] = official

        wiki_payload = wikipedia_parse_payload(
            WIKIPEDIA_ELECTION_TITLES[election],
            election,
            args.refresh,
        )
        parsed_wiki = parse_wikipedia_candidates(wiki_payload, rows)
        print(
            f"{election}: official {sum((election, column) in official_rows for column in source_columns)}/{len(source_columns)}, "
            f"Wikipedia table {len(parsed_wiki)}/{len(source_columns)}"
        )
        for letter, candidate in parsed_wiki.items():
            key = (election, letter)
            wiki_candidates[key] = candidate
            selected_titles[key] = choose_wikipedia_title(candidate)

    for key, title in WIKIPEDIA_TITLE_OVERRIDES.items():
        selected_titles[key] = (title, "zero_vote_article_match")

    page_info = fetch_wikipedia_page_info(
        {title for title, _ in selected_titles.values() if title},
        args.refresh,
    )
    wikidata_instances = fetch_wikidata_instances(
        {
            info["wikidata_id"]
            for info in page_info.values()
            if info.get("wikidata_id")
        },
        args.refresh,
    )

    registry_rows: list[dict[str, object]] = []
    audit_rows: list[dict[str, object]] = []
    missing_official: list[str] = []

    for source_row in inventory:
        election = source_row["election"]
        source_column = source_row["source_column"]
        ballot_letter = canonical_ballot_letter(election, source_column)
        key = (election, source_column)
        official = official_rows.get(key)
        candidate = wiki_candidates.get(key)
        title, match_status = selected_titles.get(key, ("", "no_wikipedia_table_row"))
        info = page_info.get(title, {})
        resolved_title = info.get("he_title", "")
        wikidata_id = info.get("wikidata_id", "")
        if resolved_title.startswith("הבחירות לכנסת"):
            info = {}
            match_status = "linked_name_resolves_to_election"
        elif WIKIDATA_HUMAN_ID in wikidata_instances.get(wikidata_id, set()):
            info = {}
            match_status = "linked_name_resolves_to_person"
        list_name = normalize_text(str(official["name"])) if official else ""
        name_source = "official_results" if list_name else ""
        official_source_url = OFFICIAL_SOURCES[election]
        wiki_name = fallback_wikipedia_name(candidate)
        if not list_name or has_broken_hebrew_spacing(list_name):
            if wiki_name:
                list_name = wiki_name
                name_source = "wikipedia_election_results"
            elif key in ZERO_VOTE_LIST_NAMES:
                list_name = ZERO_VOTE_LIST_NAMES[key]
                name_source = "official_candidate_list"
                official_source_url = ZERO_VOTE_SOURCE_OVERRIDES.get(
                    key,
                    official_source_url,
                )
            else:
                missing_official.append(f"{election}:{source_column}")
        elif wiki_name and len(wiki_name) > len(list_name):
            # Modern CEC result cells visually truncate some long names. The
            # same-election Wikipedia result row is exact-vote matched and
            # preserves the complete text in those cases.
            list_name = wiki_name
            name_source = "wikipedia_election_results"

        he_title = info.get("he_title", "")
        notes = ""
        if ballot_letter != source_column:
            notes = (
                f"Source result column {source_column} normalized to official ballot code "
                f"{ballot_letter}."
            )
        registry_rows.append(
            {
                "election": election,
                "election_number": source_row["election_number"],
                "source_column": source_column,
                "ballot_letter": ballot_letter,
                "total_votes": source_row["total_votes"],
                "list_name_he": list_name,
                "name_source": name_source,
                "display_name_he": he_title or list_name,
                "display_name_en": info.get("en_title", ""),
                "wikipedia_he_url": info.get("he_url", ""),
                "wikipedia_en_url": info.get("en_url", ""),
                "wikipedia_match_status": match_status,
                "official_source_url": official_source_url,
                "wikipedia_source_url": (
                    "https://he.wikipedia.org/wiki/"
                    + urllib.parse.quote(WIKIPEDIA_ELECTION_TITLES[election].replace(" ", "_"))
                ),
                "notes": notes,
            }
        )

        audit_rows.append(
            {
                "election": election,
                "source_column": source_column,
                "ballot_letter": ballot_letter,
                "selected_title": title,
                "match_status": match_status,
                "cell_texts": json.dumps(candidate["cell_texts"], ensure_ascii=False) if candidate else "",
                "links_by_cell": json.dumps(candidate["links_by_cell"], ensure_ascii=False) if candidate else "",
            }
        )

    apply_reviewed_display_names(registry_rows, reviewed_display_names)

    if missing_official:
        print("Missing official/list names: " + ", ".join(missing_official), file=sys.stderr)
        return 1

    write_csv(args.output, registry_rows, REGISTRY_FIELDS)
    write_csv(
        args.audit_output,
        audit_rows,
        ["election", "source_column", "ballot_letter", "selected_title", "match_status", "cell_texts", "links_by_cell"],
    )

    status_counts: dict[str, int] = {}
    for row in registry_rows:
        status = str(row["wikipedia_match_status"])
        status_counts[status] = status_counts.get(status, 0) + 1
    print(f"Wrote {len(registry_rows)} rows to {args.output.relative_to(ROOT)}")
    print("Wikipedia matches: " + ", ".join(f"{key}={value}" for key, value in sorted(status_counts.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
