import csv
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from normalize_election_results import party_columns


def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


class K26ReleaseTests(unittest.TestCase):
    def test_administrative_and_trailing_columns_are_not_parties(self):
        self.assertEqual(party_columns(["סמל ישוב", "חיצוניות", "קלפי אחרת", "אמת", "", "Unnamed: 51"]), ["אמת"])

    def test_past_ballot_values_and_assignments_are_unchanged(self):
        for election in range(17, 26):
            with self.subTest(election=election):
                filename = f"k{election}.csv"
                before = rows(ROOT / "public-data" / "v1" / "ballots" / filename)
                after = rows(ROOT / "public-data" / "v2" / "ballots" / filename)
                self.assertEqual(before, after)

    def test_complete_count_totals_and_no_unverified_synthetic_links(self):
        ballots = rows(ROOT / "public-data" / "v2" / "ballots" / "k26.csv")
        self.assertEqual(len(ballots), 12926)
        self.assertEqual(sum(int(row["valid_votes"]) for row in ballots), 5690685)
        self.assertEqual(sum(int(row["actual_voters"]) for row in ballots), 5716673)
        links = {row["source_row_uid"]: row for row in rows(ROOT / "public-data" / "v2" / "metadata" / "assignment-provenance" / "k26_validated_register_links.csv")}
        inferred = [row for row in ballots if row["assignment_is_synthetic_link"].lower() == "true"]
        self.assertGreater(len(inferred), 3800)
        for row in inferred:
            evidence = links[row["source_row_uid"]]
            self.assertEqual(row["stat_area_id"], evidence["stat_area_id"])
            self.assertEqual(row["assignment_evidence_class"], "official_polling_register_inferred_link")
            self.assertEqual(row["source_locality_code"], evidence["source_locality_code"])
            self.assertEqual(row["source_kalpi"], evidence["source_kalpi"])
            self.assertNotEqual(row["source_kalpi"].split(".")[0], "990")
        for row in ballots:
            if row["stat_area_id"]:
                self.assertTrue(row["stat_area_id"].startswith("stat2022:"))

    def test_candidate_keys_are_not_promoted_to_assignments(self):
        candidates = rows(ROOT / "public-data" / "v2" / "metadata" / "assignment-provenance" / "k26_crosswalk_candidates.csv")
        self.assertTrue(candidates)
        self.assertTrue(all(row["accepted_as_assignment"].lower() == "false" for row in candidates))
        report = json.loads((ROOT / "public-data" / "v2" / "validation.json").read_text())
        self.assertEqual(report["total_ballot_rows"], 109455)
        for election in report["elections"]:
            self.assertEqual(election["party_vote_mismatch_rows"], 0)
            self.assertEqual(election["missing_stat_geometry_ids"], 0)
            self.assertEqual(election["missing_locality_geometry_ids"], 0)

    def test_wikipedia_review_covers_every_below_threshold_list(self):
        parties = rows(ROOT / "public-data" / "v2" / "metadata" / "parties.csv")
        eligible = {row["source_column"] for row in parties if row["election"] == "K26" and 0 < int(row["total_votes"]) < 5690685 * 0.0325}
        reviews = rows(ROOT / "public-data" / "v2" / "metadata" / "party-wikipedia-reviews" / "k26.csv")
        self.assertEqual(len(reviews), 25)
        self.assertEqual({row["source_column"] for row in reviews}, eligible)
        self.assertTrue(all(row["notes"] and row["evidence_urls"] for row in reviews))

    def test_previous_election_party_metadata_is_unchanged(self):
        before = rows(ROOT / "public-data" / "v1" / "metadata" / "parties.csv")
        after = rows(ROOT / "public-data" / "v2" / "metadata" / "parties.csv")
        self.assertEqual(before, [row for row in after if row["election"] != "K26"])

    def test_final_register_reconciles_to_every_ordinary_ballot(self):
        import openpyxl
        from decimal import Decimal
        normalize = lambda value: format(Decimal(str(value)).normalize(), "f")
        book = openpyxl.load_workbook(ROOT / "public-data" / "v2" / "sources" / "k26" / "final_register.xlsx", read_only=True, data_only=True)
        registered = {(str(int(row[3])), normalize(row[5])): int(row[12]) for row in book.worksheets[0].iter_rows(values_only=True) if isinstance(row[3], (int, float))}
        book.close()
        ballots = rows(ROOT / "public-data" / "v2" / "ballots" / "k26.csv")
        ordinary = {(row["source_locality_code"], normalize(row["source_kalpi"])): int(row["eligible_voters"]) for row in ballots if row["is_envelope"].lower() == "false"}
        self.assertEqual(registered, ordinary)


if __name__ == "__main__":
    unittest.main()
