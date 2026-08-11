import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOUNDARIES_PATH = (
    ROOT / "data" / "manual" / "west_bank_display_boundary_replacements.geojson"
)
EXPECTED_CODES = {3782, 3785, 3786, 3825}
EXPECTED_SOURCE_ITEM = "e3848dc0a04c44cc9ad9f7db228cd3a3"


def coordinate_count(value):
    if not isinstance(value, list):
        return 0
    if value and all(isinstance(item, (int, float)) for item in value):
        return 1
    return sum(coordinate_count(item) for item in value)


class WestBankBoundaryReplacementTests(unittest.TestCase):
    def test_reviewed_display_boundaries_are_complete_and_detailed(self):
        payload = json.loads(BOUNDARIES_PATH.read_text(encoding="utf-8"))
        features = payload["features"]
        self.assertEqual(payload["type"], "FeatureCollection")
        self.assertEqual(
            {feature["properties"]["locality_code"] for feature in features},
            EXPECTED_CODES,
        )

        for feature in features:
            properties = feature["properties"]
            geometry = feature["geometry"]
            self.assertEqual(
                feature["id"], f"loc:{properties['locality_code']}"
            )
            self.assertEqual(
                properties["geometry_source"],
                "arcgis_peace_now_settlements_2024",
            )
            self.assertEqual(properties["geometry_role"], "display_only")
            self.assertEqual(
                properties["review_status"], "approved_detailed_boundary"
            )
            self.assertEqual(properties["source_item_id"], EXPECTED_SOURCE_ITEM)
            self.assertIn(geometry["type"], {"Polygon", "MultiPolygon"})
            self.assertGreater(coordinate_count(geometry["coordinates"]), 12)


if __name__ == "__main__":
    unittest.main()
