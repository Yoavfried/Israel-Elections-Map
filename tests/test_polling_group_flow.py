from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from polling_group_flow import analyze_exact_flow


class PollingGroupFlowTests(unittest.TestCase):
    def test_saturated_ballot_splits_one_network_into_exact_groups(self) -> None:
        analysis = analyze_exact_flow(
            {str(area): 100 for area in range(1, 6)},
            {"A": 300, "B": 150, "C": 50},
            {
                "A": {"1", "2", "3"},
                "B": {"3", "4", "5"},
                "C": {"1", "3", "5"},
            },
        )

        self.assertEqual(
            [
                (component.area_ids, component.polling_group_ids)
                for component in analysis.components
            ],
            [
                (("1", "2", "3"), ("A",)),
                (("4", "5"), ("B", "C")),
            ],
        )
        self.assertEqual(analysis.edge_bounds[("3", "B")], (0, 0))
        self.assertEqual(analysis.edge_bounds[("1", "C")], (0, 0))
        self.assertGreater(analysis.edge_bounds[("5", "C")][0], 0)

    def test_ambiguous_250_200_50_example_remains_one_component(self) -> None:
        analysis = analyze_exact_flow(
            {str(area): 100 for area in range(1, 6)},
            {"A": 250, "B": 200, "C": 50},
            {
                "A": {"1", "2", "3"},
                "B": {"3", "4", "5"},
                "C": {"1", "3", "5"},
            },
        )

        self.assertEqual(len(analysis.components), 1)
        self.assertEqual(
            analysis.components[0].area_ids,
            ("1", "2", "3", "4", "5"),
        )
        self.assertEqual(
            analysis.components[0].polling_group_ids,
            ("A", "B", "C"),
        )
        self.assertEqual(analysis.edge_bounds[("3", "B")], (0, 50))
        self.assertEqual(analysis.edge_bounds[("5", "C")], (0, 50))

    def test_rejects_unbalanced_network(self) -> None:
        with self.assertRaisesRegex(ValueError, "do not balance"):
            analyze_exact_flow(
                {"1": 100},
                {"A": 99},
                {"A": {"1"}},
            )


if __name__ == "__main__":
    unittest.main()
