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
        self.assertFalse(any(row["assignment_is_synthetic_link"].lower() == "true" for row in ballots))
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


if __name__ == "__main__":
    unittest.main()
