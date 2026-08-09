from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, object]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


class K24DaliyatPollingGroupTests(unittest.TestCase):
    def test_all_unsafe_stable_candidates_are_withheld(self) -> None:
        safety = read_rows(
            ROOT
            / "data"
            / "processed"
            / "audits"
            / "stable_ballot_site_safety.csv"
        )
        assignments = read_rows(
            ROOT
            / "data"
            / "processed"
            / "assignments"
            / "ballot_geography_assignments.csv"
        )
        summary = read_json(
            ROOT
            / "data"
            / "processed"
            / "audits"
            / "stable_ballot_site_safety_summary.json"
        )
        unsafe_ids = {
            row["source_row_uid"]
            for row in safety
            if row["safety_status"] == "unsafe_mixed_final_batch"
        }
        assignments_by_id = {row["source_row_uid"]: row for row in assignments}

        self.assertEqual(len(unsafe_ids), 38)
        self.assertEqual(summary["publication_guard"], "pass")
        self.assertEqual(summary["unresolved_safety_rows"], 0)
        self.assertEqual(summary["missing_rejection_keys"], [])
        self.assertTrue(unsafe_ids <= assignments_by_id.keys())
        self.assertTrue(
            all(not assignments_by_id[row_id]["stat_area_id"] for row_id in unsafe_ids)
        )

    def test_mixed_site_batches_are_not_published_as_exact_rows(self) -> None:
        assignments = read_rows(
            ROOT
            / "data"
            / "processed"
            / "assignments"
            / "ballot_geography_assignments.csv"
        )
        mixed_ballots = {
            "8.1",
            "8.2",
            "8.3",
            "8.4",
            "10.1",
            "10.2",
            "10.3",
            "12.1",
            "12.2",
            "12.3",
        }
        rows = [
            row
            for row in assignments
            if row["election"] == "K24"
            and row["source_locality_code"] == "494"
            and row["source_kalpi"] in mixed_ballots
        ]

        self.assertEqual({row["source_kalpi"] for row in rows}, mixed_ballots)
        self.assertTrue(all(not row["stat_area_id"] for row in rows))
        self.assertTrue(
            all(
                row["final_assignment_method"] == "historical_stat_area_pending"
                for row in rows
            )
        )

    def test_four_area_display_is_exact_and_reconciles(self) -> None:
        metadata = read_rows(
            ROOT
            / "data"
            / "processed"
            / "geographies"
            / "statistical_area_polling_group_displays.metadata.csv"
        )
        results = read_rows(
            ROOT
            / "data"
            / "processed"
            / "public"
            / "statistical_area_polling_group_displays.csv"
        )
        expected_areas = {
            "stat2011:4940001",
            "stat2011:4940003",
            "stat2011:4940004",
            "stat2011:4940005",
        }
        scope = [
            row
            for row in metadata
            if row["election"] == "K24" and row["locality_code"] == "494"
        ]

        self.assertEqual(len(scope), 1)
        display = scope[0]
        self.assertEqual(
            set(display["component_stat_area_ids"].split("|")), expected_areas
        )
        self.assertEqual(display["assignment_precision"], "exact")
        self.assertEqual(display["ambiguity_type"], "exact")

        result = next(
            row
            for row in results
            if row["custom_geography_id"] == display["display_geography_id"]
        )
        self.assertEqual(int(result["eligible_voters"]), 9018)
        self.assertEqual(int(result["actual_voters"]), 3679)
        self.assertEqual(int(result["contributing_kalpis"]), 18)

    def test_k24_umm_al_fahm_closed_display_is_exact(self) -> None:
        metadata = read_rows(
            ROOT
            / "data"
            / "processed"
            / "geographies"
            / "statistical_area_polling_group_displays.metadata.csv"
        )
        results = read_rows(
            ROOT
            / "data"
            / "processed"
            / "public"
            / "statistical_area_polling_group_displays.csv"
        )
        display_id = "display:reviewed-closed:K24:2710:13-14-15-21-34"
        expected_areas = {
            "stat2011:27100013",
            "stat2011:27100014",
            "stat2011:27100015",
            "stat2011:27100021",
            "stat2011:27100034",
        }
        display = next(
            row for row in metadata if row["display_geography_id"] == display_id
        )

        self.assertEqual(
            set(display["component_stat_area_ids"].split("|")), expected_areas
        )
        self.assertEqual(display["assignment_precision"], "exact")
        self.assertEqual(display["ambiguity_type"], "exact")
        self.assertEqual(int(display["source_result_rows"]), 31)

        result = next(
            row for row in results if row["custom_geography_id"] == display_id
        )
        self.assertEqual(int(result["eligible_voters"]), 17424)
        self.assertEqual(int(result["actual_voters"]), 5702)
        self.assertEqual(int(result["contributing_kalpis"]), 31)

    def test_k25_daliyat_ballot_23_is_resolved_only_at_set_level(self) -> None:
        assignments = read_rows(
            ROOT
            / "data"
            / "processed"
            / "assignments"
            / "ballot_geography_assignments.csv"
        )
        metadata = read_rows(
            ROOT
            / "data"
            / "processed"
            / "geographies"
            / "statistical_area_polling_group_displays.metadata.csv"
        )
        results = read_rows(
            ROOT
            / "data"
            / "processed"
            / "public"
            / "statistical_area_polling_group_displays.csv"
        )
        ballot = next(row for row in assignments if row["source_row_uid"] == "K25:2809")
        display_id = "display:reviewed-closed:K25:494:3-5"
        display = next(
            row for row in metadata if row["display_geography_id"] == display_id
        )

        self.assertEqual(ballot["source_kalpi"], "23")
        self.assertEqual(ballot["stat_area_id"], "")
        self.assertEqual(ballot["final_assignment_method"], "historical_stat_area_pending")
        self.assertEqual(
            set(display["component_stat_area_ids"].split("|")),
            {"stat2011:4940003", "stat2011:4940005"},
        )
        self.assertEqual(display["assignment_precision"], "exact")
        self.assertEqual(display["ambiguity_type"], "exact")
        self.assertEqual(int(display["source_result_rows"]), 9)

        result = next(
            row for row in results if row["custom_geography_id"] == display_id
        )
        self.assertEqual(int(result["eligible_voters"]), 5327)
        self.assertEqual(int(result["actual_voters"]), 2916)
        self.assertEqual(int(result["contributing_kalpis"]), 9)


if __name__ == "__main__":
    unittest.main()
