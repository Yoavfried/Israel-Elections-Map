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

from polling_group_ownership import solve_polling_group_ownership


def square(index: int, *, gap: float = 0.0):
    left = index * (0.001 + gap)
    return box(left, 0, left + 0.001, 0.001)


class PollingGroupOwnershipTest(unittest.TestCase):
    def solve(self, area_ids, groups, geometries):
        return solve_polling_group_ownership(
            area_ids,
            groups,
            geometries,
            metric_crs="EPSG:3857",
            tolerance_meters=1.0,
            max_search_nodes=100_000,
        )

    def test_forced_unique_areas_are_preserved(self):
        result = self.solve(
            ["a", "b"],
            {
                "g1": {
                    "area_ids": {"a"},
                    "weights": {"a": 10},
                    "planned": 10,
                },
                "g2": {
                    "area_ids": {"b"},
                    "weights": {"b": 20},
                    "planned": 20,
                },
            },
            {"a": square(0), "b": square(1)},
        )

        self.assertEqual(result["status"], "connected_solution")
        self.assertEqual(result["ownership"], {"g1": ("a",), "g2": ("b",)})

    def test_shared_area_maximizes_weakest_represented_share(self):
        result = self.solve(
            ["a", "b", "c"],
            {
                "g1": {
                    "area_ids": {"a", "b"},
                    "weights": {"a": 60, "b": 40},
                    "planned": 100,
                },
                "g2": {
                    "area_ids": {"b", "c"},
                    "weights": {"b": 70, "c": 30},
                    "planned": 100,
                },
            },
            {"a": square(0), "b": square(1), "c": square(2)},
        )

        self.assertEqual(result["status"], "connected_solution")
        self.assertEqual(result["ownership"]["g1"], ("a",))
        self.assertEqual(result["ownership"]["g2"], ("b", "c"))
        self.assertAlmostEqual(result["minimum_represented_share"], 0.6)

    def test_reports_when_there_are_fewer_polygons_than_groups(self):
        result = self.solve(
            ["a"],
            {
                "g1": {
                    "area_ids": {"a"},
                    "weights": {"a": 10},
                    "planned": 10,
                },
                "g2": {
                    "area_ids": {"a"},
                    "weights": {"a": 10},
                    "planned": 10,
                },
            },
            {"a": square(0)},
        )

        self.assertEqual(
            result["status"], "fewer_polygons_than_polling_groups"
        )

    def test_uses_disconnected_solution_only_when_required(self):
        result = self.solve(
            ["a", "b", "c"],
            {
                "g1": {
                    "area_ids": {"a", "c"},
                    "weights": {"a": 10, "c": 10},
                    "planned": 20,
                },
                "g2": {
                    "area_ids": {"b"},
                    "weights": {"b": 10},
                    "planned": 10,
                },
            },
            {
                "a": square(0),
                "b": square(1),
                "c": square(2),
            },
        )

        self.assertEqual(
            result["status"], "solution_requires_disconnected_geometry"
        )
        self.assertEqual(result["ownership"]["g1"], ("a", "c"))


if __name__ == "__main__":
    unittest.main()
