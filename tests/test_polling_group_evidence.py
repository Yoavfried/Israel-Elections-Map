from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCAL_PYTHON = ROOT / ".local" / "python-audit"
if LOCAL_PYTHON.exists():
    sys.path.insert(0, str(LOCAL_PYTHON))
sys.path.insert(0, str(ROOT / "scripts"))

import pandas as pd

from audit_statistical_area_polling_group_evidence import UnionFind, link_site_components


def rows(values: list[tuple[str, str, str]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "site_key": site_key,
                "ballot_base": ballot_base,
                "location_key": location_key,
            }
            for site_key, ballot_base, location_key in values
        ]
    )


class PollingGroupEvidenceTests(unittest.TestCase):
    def test_union_find_uses_an_order_independent_component_identity(self) -> None:
        forward = UnionFind()
        forward.union("p:z-site", "f:a-site")

        reverse = UnionFind()
        reverse.union("f:a-site", "p:z-site")

        self.assertEqual(forward.find("p:z-site"), "f:a-site")
        self.assertEqual(reverse.find("p:z-site"), "f:a-site")

    def test_unique_ballot_base_links_planned_and_final_sites(self) -> None:
        planned, final = link_site_components(
            rows([("planned-69", "569", "planned-location")]),
            rows([("final-69", "569", "final-location")]),
        )

        self.assertEqual(
            planned.iloc[0]["site_component"],
            final.iloc[0]["site_component"],
        )

    def test_reused_ballot_base_does_not_merge_multiple_sites(self) -> None:
        planned, final = link_site_components(
            rows(
                [
                    ("planned-a", "569", "planned-a-location"),
                    ("planned-b", "569", "planned-b-location"),
                ]
            ),
            rows([("final-a", "569", "final-a-location")]),
        )

        components = set(planned["site_component"]) | set(
            final["site_component"]
        )
        self.assertEqual(len(components), 3)

    def test_one_planned_ballot_split_across_final_sites_stays_one_component(self) -> None:
        planned, final = link_site_components(
            rows([("planned-a", "18", "planned-location")]),
            rows(
                [
                    ("final-a", "18", "final-a-location"),
                    ("final-b", "18", "final-b-location"),
                ]
            ),
        )

        components = set(planned["site_component"]) | set(
            final["site_component"]
        )
        self.assertEqual(len(components), 1)


if __name__ == "__main__":
    unittest.main()
