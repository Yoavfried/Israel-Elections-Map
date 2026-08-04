from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_statistical_area_polling_group_policy import (
    continuity_identity,
    continuity_sites_match,
    is_consolidated_subdivision_group,
)


def site(labels: str) -> dict[str, str]:
    return {
        "locality_code": "5000",
        "planned_site_ids": "60",
        "site_labels": labels,
    }


class PollingGroupContinuityTests(unittest.TestCase):
    def test_identity_uses_locality_and_official_site_id(self) -> None:
        self.assertEqual(
            continuity_identity(site("School|Main Street 8")),
            continuity_identity(site("School - south wing|Main Street 8")),
        )

    def test_site_match_requires_a_shared_normalized_label(self) -> None:
        self.assertTrue(
            continuity_sites_match(
                site("School|Main Street, 8"),
                site("School - south wing|Main Street 8"),
            )
        )
        self.assertTrue(
            continuity_sites_match(
                site("Balfour School|Main Street 11"),
                site("Balfour School - main building|Other Street 12"),
            )
        )
        self.assertFalse(
            continuity_sites_match(
                site("School|Main Street 8"),
                site("Different school|Other Street 2"),
            )
        )

    def test_detects_one_base_expanded_into_subdivisions(self) -> None:
        self.assertTrue(
            is_consolidated_subdivision_group(["495.1", "495.2", "495.3"])
        )
        self.assertFalse(is_consolidated_subdivision_group(["494", "495"]))
        self.assertFalse(
            is_consolidated_subdivision_group(["495.1", "496.1"])
        )


if __name__ == "__main__":
    unittest.main()
