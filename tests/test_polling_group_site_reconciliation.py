from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL_PYTHON = ROOT / ".local" / "python-geo"
if LOCAL_PYTHON.exists():
    sys.path.insert(0, str(LOCAL_PYTHON))
sys.path.insert(0, str(ROOT / "scripts"))

from build_statistical_area_polling_group_policy import (
    reconcile_planned_only_sites,
)


def site(
    site_id: str,
    labels: str,
    weights: dict[str, int],
    final_ballots: str,
    final_eligible: int,
) -> dict[str, object]:
    planned = sum(weights.values())
    return {
        "site_audit_id": site_id,
        "site_labels": labels,
        "residual_area_ids": "|".join(sorted(weights)),
        "residual_area_planned_eligible": json.dumps(weights),
        "planned_residual_eligible": planned,
        "final_residual_eligible": final_eligible,
        "eligible_difference": final_eligible - planned,
        "residual_final_ballots": final_ballots,
        "planned_site_ids": site_id.rsplit(":", 1)[-1],
        "planned_ballots": "1",
        "residual_planned_ballots": "1",
    }


class PollingGroupSiteReconciliationTests(unittest.TestCase):
    def test_unique_site_and_balance_match_recovers_planned_only_areas(self) -> None:
        active = site(
            "K25:5000:110",
            'בי"ס תל נורדאו-מבנה מערבי|מנדלי מוכר ספרים,19',
            {"336": 2722, "337": 1900, "512": 774},
            "338.1|338.2",
            10106,
        )
        omitted = site(
            "K25:5000:175",
            'בי"ס תל נורדאו-כניסה מפרישמן|פרישמן,28',
            {"334": 1489, "335": 2632, "337": 572},
            "",
            0,
        )

        reconciled, matches, unresolved = reconcile_planned_only_sites(
            [active, omitted]
        )

        self.assertEqual(unresolved, [])
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["eligible_delta"], 17)
        self.assertEqual(
            set(reconciled[0]["residual_area_ids"].split("|")),
            {"334", "335", "336", "337", "512"},
        )

    def test_arithmetic_match_without_site_identity_is_not_accepted(self) -> None:
        active = site(
            "K25:5000:110",
            "unrelated school",
            {"337": 5396},
            "338.1",
            10106,
        )
        omitted = site(
            "K25:5000:175",
            "different institution",
            {"335": 4121, "337": 572},
            "",
            0,
        )

        _reconciled, matches, unresolved = reconcile_planned_only_sites(
            [active, omitted]
        )

        self.assertEqual(matches, [])
        self.assertEqual(unresolved, ["K25:5000:175"])


if __name__ == "__main__":
    unittest.main()
