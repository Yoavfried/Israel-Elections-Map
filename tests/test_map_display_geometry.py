from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from prepare_map_display_geometries import carve_overlaps, sanitize_geometry
from shapely.geometry import Polygon, box, mapping, shape


class MapDisplayGeometryTests(unittest.TestCase):
    def test_export_precision_drops_collapsed_hole_without_invalidating_polygon(self):
        outer = box(34, 32, 34.01, 32.01)
        tiny_hole = box(34.005, 32.005, 34.0050001, 32.0050001)
        source = Polygon(outer.exterior.coords, [tiny_hole.exterior.coords])
        repaired = sanitize_geometry(source)
        self.assertTrue(repaired.is_valid)
        self.assertGreater(repaired.area, source.area * 0.9999)
        exported = mapping(repaired)
        def rounded(value):
            if isinstance(value, (tuple, list)):
                return [rounded(item) for item in value]
            return round(value, 6)
        exported["coordinates"] = rounded(exported["coordinates"])
        self.assertTrue(shape(exported).is_valid)

    def test_larger_background_makes_exact_space_for_locality(self):
        locality = box(34.002, 32.002, 34.004, 32.004)
        background = box(34, 32, 34.01, 32.01)
        cleaned, changes = carve_overlaps([background, locality], ["background", "locality"])
        self.assertTrue(cleaned[1].equals(locality))
        self.assertAlmostEqual(cleaned[0].intersection(cleaned[1]).area, 0)
        self.assertAlmostEqual(cleaned[0].union(cleaned[1]).area, background.area)
        self.assertEqual([row["id"] for row in changes], ["background"])

    def test_cleanup_is_idempotent(self):
        geometries = [box(34, 32, 34.01, 32.01), box(34.002, 32.002, 34.004, 32.004)]
        first, _ = carve_overlaps(geometries, ["background", "locality"])
        second, _ = carve_overlaps(first, ["background", "locality"])
        self.assertTrue(all(left.equals(right) for left, right in zip(first, second)))


if __name__ == "__main__":
    unittest.main()
