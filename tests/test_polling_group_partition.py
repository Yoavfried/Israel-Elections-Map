from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL_PYTHON = ROOT / ".local" / "python-geo"
if LOCAL_PYTHON.exists():
    sys.path.insert(0, str(LOCAL_PYTHON))
sys.path.insert(0, str(ROOT / "scripts"))

from shapely.geometry import box

from polling_group_partition import solve_polling_group_partition


class PollingGroupPartitionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.geometry = {
            "a": box(0, 0, 1, 1),
            "b": box(1, 0, 2, 1),
            "c": box(2, 0, 3, 1),
        }

    def solve(self, area_ids, groups):
        return solve_polling_group_partition(
            area_ids,
            groups,
            self.geometry,
            metric_crs="EPSG:3857",
            tolerance_meters=0.01,
        )

    def test_single_group_is_an_exact_component(self) -> None:
        result = self.solve(
            ["a", "b", "c"],
            {
                "g1": {
                    "weights": {"a": 10, "b": 20, "c": 30},
                    "actual_voters": 42,
                    "final_eligible": 60,
                }
            },
        )

        self.assertEqual(result["status"], "exact_component")
        self.assertEqual(result["units"][0].area_ids, ("a", "b", "c"))
        self.assertTrue(result["units"][0].exact)

    def test_more_groups_than_polygons_merges_groups_without_duplication(self) -> None:
        result = self.solve(
            ["a", "b"],
            {
                "g1": {
                    "weights": {"a": 80, "b": 20},
                    "actual_voters": 50,
                    "final_eligible": 100,
                },
                "g2": {
                    "weights": {"a": 70, "b": 30},
                    "actual_voters": 50,
                    "final_eligible": 100,
                },
                "g3": {
                    "weights": {"a": 10, "b": 90},
                    "actual_voters": 50,
                    "final_eligible": 100,
                },
            },
        )

        self.assertEqual(result["status"], "robust_partition")
        self.assertEqual(len(result["units"]), 2)
        self.assertEqual(
            {group for unit in result["units"] for group in unit.group_ids},
            {"g1", "g2", "g3"},
        )
        self.assertEqual(
            {area for unit in result["units"] for area in unit.area_ids},
            {"a", "b"},
        )

    def test_weak_split_merges_until_both_sides_have_a_majority(self) -> None:
        result = self.solve(
            ["a", "b", "c"],
            {
                "g1": {
                    "weights": {"a": 45, "b": 45, "c": 10},
                    "actual_voters": 100,
                    "final_eligible": 100,
                },
                "g2": {
                    "weights": {"a": 40, "b": 40, "c": 20},
                    "actual_voters": 100,
                    "final_eligible": 100,
                },
                "g3": {
                    "weights": {"a": 5, "b": 5, "c": 90},
                    "actual_voters": 100,
                    "final_eligible": 100,
                },
            },
        )

        self.assertGreaterEqual(result["minimum_score"], 0.5)
        self.assertTrue(result["merge_steps"])

    def test_disconnected_geometry_does_not_force_extra_merges(self) -> None:
        result = self.solve(
            ["a", "b", "c"],
            {
                "g1": {
                    "weights": {"a": 50, "c": 50},
                    "actual_voters": 100,
                    "final_eligible": 100,
                },
                "g2": {
                    "weights": {"b": 100},
                    "actual_voters": 100,
                    "final_eligible": 100,
                },
            },
        )

        self.assertEqual(result["status"], "robust_partition_disconnected")
        self.assertEqual(len(result["units"]), 2)
        self.assertEqual(result["merge_steps"], [])


if __name__ == "__main__":
    unittest.main()
