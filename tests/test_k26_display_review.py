from __future__ import annotations

import csv
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / ".local/python-geo"))
from audit_display_contributor_capacity import ELECTIONS, demographic_capacity, load_demographics
from pyproj import Transformer
from shapely import STRtree
from shapely.geometry import shape
from shapely.ops import transform


def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


class K26DisplayReviewTests(unittest.TestCase):
    def test_meitar_union_has_no_artificial_internal_seams(self):
        geometry = json.loads((ROOT / "web/app/public/data/v2/geographies/statistical-areas-2022.geojson").read_text())
        feature = next(feature for feature in geometry["features"] if feature["properties"].get("nameHe") == "מיתר · 1, 2, 3")
        polygon = shape(feature["geometry"])
        self.assertEqual(polygon.geom_type, "Polygon")
        self.assertEqual(len(polygon.interiors), 0)

    def test_published_k26_shapes_are_valid_and_do_not_overlap(self):
        root = ROOT / "web/app/public/data/v2"
        payload = json.loads((root / "results/k26/statistical-areas.json").read_text())
        ids = {row["id"] for row in payload["records"]}
        hidden = set(payload["hiddenGeographyIds"])
        geometry = json.loads((root / "geographies/statistical-areas-2022.geojson").read_text())
        projected = []
        names = []
        project = Transformer.from_crs(4326, 2039, always_xy=True).transform
        for feature in geometry["features"]:
            p = feature["properties"]
            if p["id"] in hidden or p.get("displayMode") == "marker" or p.get("localityCode") == "9920":
                continue
            if p.get("geographyType") in {"custom", "municipality-fallback"} and p["id"] not in ids:
                continue
            polygon = shape(feature["geometry"])
            self.assertTrue(polygon.is_valid, p["id"])
            projected.append(polygon)
            names.append(p["id"])
        tree = STRtree(projected)
        for i, polygon in enumerate(projected):
            for j in tree.query(polygon, predicate="intersects"):
                if j > i:
                    overlap = polygon.intersection(projected[j])
                    self.assertLessEqual(transform(project, overlap).area, 1, f"{names[i]} / {names[j]}")

    def test_capacity_review_includes_k26_with_official_population(self):
        self.assertIn("K26", ELECTIONS)
        demographics = load_demographics()
        population, complete, capacity = demographic_capacity("K26", {"stat2022:50000223"}, demographics)
        self.assertEqual(population, 5804)
        self.assertTrue(complete)
        self.assertEqual(capacity, 7255)

    def test_unbalanced_ofakim_residual_keeps_an_uncertainty_notice(self):
        payload = json.loads((ROOT / "web/app/public/data/v2/results/k26/statistical-areas.json").read_text())
        record = next(row for row in payload["records"] if row["id"] == "stat2022:310012")
        self.assertEqual(record["totals"]["actualVoters"], 452)
        self.assertTrue(record.get("notice"))

    def test_locality_fallbacks_never_coexist_with_mixed_displays(self):
        root = ROOT / "data/processed"
        groups = rows(root / "geographies/statistical_area_polling_group_displays.metadata.csv")
        group_scopes = {(row["election"], row["locality_code"]) for row in groups}
        fallbacks = rows(root / "audits/historical_municipality_display_fallbacks.csv")
        self.assertFalse(group_scopes & {(row["election"], row["locality_code"]) for row in fallbacks})

    def test_incomplete_k26_evidence_never_loses_its_notice(self):
        policies = rows(ROOT / "data/processed/audits/statistical_area_polling_group_policy.csv")
        incomplete = [row for row in policies if row["election"] == "K26" and "incomplete_final_area_coverage" in row["evidence_warnings"]]
        self.assertTrue(incomplete)
        payload = json.loads((ROOT / "web/app/public/data/v2/results/k26/statistical-areas.json").read_text())
        records = {row["id"]: row for row in payload["records"]}
        for row in incomplete:
            self.assertNotEqual(row["review_status"], "approved-exact-closed")
            self.assertTrue(records[row["display_geography_id"]].get("notice"))


if __name__ == "__main__":
    unittest.main()
