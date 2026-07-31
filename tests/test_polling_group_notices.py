from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_statistical_area_polling_group_displays import build_notice


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


if __name__ == "__main__":
    unittest.main()
