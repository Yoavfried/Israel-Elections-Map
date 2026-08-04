from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_statistical_area_polling_group_displays import (
    apply_reviewed_display_groups,
    build_notice,
)


class PollingGroupNoticeTests(unittest.TestCase):
    def test_exact_assignment_has_no_notice(self) -> None:
        self.assertEqual(
            build_notice(
                exact_assignment=True,
                possible_inflow_numbers=["4"],
                possible_outflow_numbers=["5"],
            ),
            ("", ""),
        )

    def test_possible_inflow_names_contributing_areas(self) -> None:
        notice_he, notice_en = build_notice(
            exact_assignment=False,
            possible_inflow_numbers=["4", "5"],
            possible_outflow_numbers=[],
        )
        self.assertIn("כוללת קולות מהאזורים 4, 5", notice_he)
        self.assertIn("include votes from areas 4, 5", notice_en)

    def test_possible_outflow_names_destination_areas(self) -> None:
        notice_he, notice_en = build_notice(
            exact_assignment=False,
            possible_inflow_numbers=[],
            possible_outflow_numbers=["8"],
        )
        self.assertIn("מוצגים באזורים 8", notice_he)
        self.assertIn("displayed in areas 8", notice_en)

    def test_combined_notice_names_both_directions(self) -> None:
        notice_he, notice_en = build_notice(
            exact_assignment=False,
            possible_inflow_numbers=["4"],
            possible_outflow_numbers=["8", "9"],
        )
        self.assertIn("מוצגים באזורים 8, 9", notice_he)
        self.assertIn("כוללת קולות מהאזורים 4", notice_he)
        self.assertIn("displayed in areas 8, 9", notice_en)
        self.assertIn("include votes from areas 4", notice_en)

    def test_reviewed_group_claims_area_and_releases_generated_ballot(self) -> None:
        generated = [
            {
                "display_geography_id": "generated:1",
                "election": "K23",
                "locality_code": "5000",
                "owned_stat_area_ids": "stat2011:50000342|stat2011:50000347",
                "planned_stat_area_ids": "stat2011:50000342|stat2011:50000347",
                "ambiguous_final_ballots": "387|391",
                "planned_eligible_voters": "100",
                "represented_planned_eligible_voters": "100",
                "represented_planned_share": "1",
                "evidence_warnings": "",
            }
        ]
        reviews = [
            {
                "display_geography_id": "reviewed:347-612",
                "election": "K23",
                "locality_code": "5000",
                "owned_stat_area_ids": (
                    "stat2011:50000347|stat2011:50000612"
                ),
                "planned_stat_area_ids": (
                    "stat2011:50000347|stat2011:50000612"
                ),
                "ambiguous_final_ballots": "390.1|390.2",
                "released_final_ballots": "391",
                "ownership_status": "best_effort_detail_preserved",
                "ownership_policy": "reviewed_set_level_merge",
                "review_status": "approved-rule-generated",
            }
        ]

        adjusted = apply_reviewed_display_groups(generated, reviews)

        self.assertEqual(len(adjusted), 2)
        self.assertEqual(adjusted[0]["owned_stat_area_ids"], "stat2011:50000342")
        self.assertEqual(adjusted[0]["ambiguous_final_ballots"], "387")
        self.assertEqual(adjusted[0]["represented_planned_share"], "0")
        self.assertEqual(
            adjusted[1]["owned_stat_area_ids"],
            "stat2011:50000347|stat2011:50000612",
        )
        self.assertEqual(adjusted[1]["ambiguous_final_ballots"], "390.1|390.2")


if __name__ == "__main__":
    unittest.main()
