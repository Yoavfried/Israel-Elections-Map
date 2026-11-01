"""Materialize K26 party identities and rules from explicit election-specific inputs."""
from __future__ import annotations

import csv
import json
import sys

from pipeline_common import MANUAL_DIR, PROCESSED_DIR, RAW_DIR, write_csv


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def replace_election(path, additions):
    original = read_csv(path)
    rows = [row for row in original if row["election"] != "K26"] + additions
    write_csv(path, rows, list(original[0]))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    registry_path = MANUAL_DIR / "party_registry.csv"
    existing = read_csv(registry_path)
    identities = {(row["election"], row["source_column"]): row for row in existing}
    choices = {row["source_column"]: row for row in read_csv(MANUAL_DIR / "k26_party_metadata.csv")}
    totals = [row for row in read_csv(PROCESSED_DIR / "normalized" / "party_columns.csv") if row["election"] == "K26"]
    review_rows = read_csv(MANUAL_DIR / "k26_party_wikipedia_reviews.csv")
    reviews = {row["source_column"]: row for row in review_rows}
    valid_votes = sum(int(row["total_votes"]) for row in totals)
    below_threshold = {row["source_column"] for row in totals if 0 < int(row["total_votes"]) < valid_votes * 0.0325}
    if len(reviews) != len(review_rows) or set(reviews) != below_threshold:
        raise ValueError("K26 Wikipedia review must cover each positive-vote below-threshold list exactly once")
    published = json.loads((RAW_DIR / "k26" / "parties.json").read_text(encoding="utf-8"))["elections"]["26"]["parties"]
    if set(choices) != {row["source_column"] for row in totals}:
        raise ValueError("K26 party metadata must cover every result column exactly")
    additions = []
    mandates = []
    for total in totals:
        party = total["source_column"]
        choice = choices[party]
        reuse = identities.get((choice["reuse_election"], choice["reuse_source_column"]))
        if choice["reuse_election"] and not reuse:
            raise ValueError(f"Unknown reviewed party identity for {party}")
        name = published.get(party, {}).get("name", "")
        if not name and int(total["total_votes"]) > 0:
            raise ValueError(f"Official K26 party name missing: {party}")
        name = name.replace('\\"', '"') or "כחול לבן"
        row = dict.fromkeys(existing[0], "")
        row.update({
            "election": "K26", "election_number": "26", "source_column": party,
            "ballot_letter": party, "total_votes": total["total_votes"], "list_name_he": name,
            "display_name_he": "ישר!" if party == "דרך" else name,
            "display_name_en": choice["display_name_en"],
            "name_source": "official_govmap_election_metadata",
            "official_source_url": "https://elections.govmap.gov.il/data/votes/elections.json",
            "wikipedia_he_url": choice["wikipedia_he_url"] or (reuse or {}).get("wikipedia_he_url", ""),
            "wikipedia_en_url": choice["wikipedia_en_url"] or (reuse or {}).get("wikipedia_en_url", ""),
            "wikipedia_match_status": "explicit_identity_reuse" if reuse else "k26_initial_metadata",
            "notes": "Complete-count snapshot 2026-10-30; certification pending. "
                + (f"Identity reviewed against {choice['reuse_election']}:{choice['reuse_source_column']}." if reuse else "New K26 list; initial English display name."),
        })
        review = reviews.get(party)
        if review:
            for language in ("he", "en"):
                if bool(row[f"wikipedia_{language}_url"]) != (review[f"{language}_link_kind"] != "not_found"):
                    raise ValueError(f"K26 {party}: {language} review disagrees with the published link")
            has_link = bool(row["wikipedia_he_url"] or row["wikipedia_en_url"])
            row["wikipedia_match_status"] = "reviewed_k26_link" if has_link else "reviewed_no_verified_article"
            row["notes"] += f" Wikipedia review {review['review_date']}: HE={review['he_link_kind']}; EN={review['en_link_kind']}. {review['notes']}"
        additions.append(row)
        if int(choice["mandates"]):
            mandates.append({"election": "K26", "source_column": party, "mandates": choice["mandates"]})
    replace_election(registry_path, additions)
    replace_election(MANUAL_DIR / "election_mandates.csv", mandates)
    replace_election(MANUAL_DIR / "election_rules.csv", [{
        "election": "K26", "electoral_threshold_share": "0.0325", "total_mandates": "120",
        "official_results_url": "https://votes26.bechirot.gov.il/nationalresults",
        "threshold_source_url": "https://main.knesset.gov.il/About/Lexicon/pages/qualifying-threshold.aspx",
    }])
    print(f"K26 parties={len(additions)} mandates={sum(int(row['mandates']) for row in mandates)}")


if __name__ == "__main__":
    main()
