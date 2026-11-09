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
    def test_west_bank_footprints_and_joined_register_are_k26_only(self):
        root = ROOT / "web/app/public/data/v2"
        def read(path):
            return json.loads((root / path).read_text(encoding="utf-8"))

        codes = {"3779", "3815", "3861", "3864", "3869"}
        expected = {"3779": 1819, "3815": 2784, "3861": 148, "3864": 172, "3869": 87}
        for mode, geo, marker in (
            ("statistical-areas", "statistical-areas-2022", "statistical-area-markers-2022"),
            ("localities", "localities-k26", "locality-markers-k26"),
        ):
            payload = read(f"results/k26/{mode}.json")
            visible = {r["id"]: r for r in payload["records"] if r["id"] not in payload["hiddenGeographyIds"]}
            features = {f["properties"]["localityCode"]: f for f in read(f"geographies/{geo}.geojson")["features"]
                        if f["properties"].get("localityCode") in codes}
            self.assertEqual(set(features), codes)
            for code, feature in features.items():
                self.assertEqual(feature["properties"]["displayMode"], "polygon")
                self.assertEqual(visible[feature["id"]]["totals"]["validVotes"], expected[code])
            active_markers = {f["id"] for f in read(f"geographies/{marker}.geojson")["features"]} & visible.keys()
            self.assertEqual(active_markers, {"custom:tribal_negev"})
            self.assertEqual(visible["custom:tribal_negev"]["totals"]["validVotes"], 33088)
            self.assertEqual(shape(features["3779"]["geometry"]).intersection(shape(features["3815"]["geometry"])).area, 0)
            joined, components = (
                ("display:joined-locality:K26:3555:3620", {"stat2022:35550001", "stat2022:36200001"})
                if mode == "statistical-areas" else ("composite:joined-k26-3555", {"loc:3555", "loc:3620"})
            )
            self.assertEqual(visible[joined]["totals"]["validVotes"], 188)
            self.assertTrue(components <= set(payload["hiddenGeographyIds"]))
            self.assertFalse(components & visible.keys())
        historical = read("results/k25/localities.json")
        self.assertIn("composite:joined-k25-3555", {r["id"] for r in historical["records"]})
        catalog = read("catalog.json")
        k25 = next(e for e in catalog["elections"] if e["id"] == "K25")
        self.assertEqual(k25["geographiesByMode"]["locality"]["geometryUrl"], "geographies/localities.geojson")

    def test_reviewed_city_displays_preserve_whole_final_ballots(self):
        root = ROOT / "web/app/public/data/v2"
        payload = json.loads((root / "results/k26/statistical-areas.json").read_text(encoding="utf-8"))
        display = {r["id"]: r for r in payload["records"]}
        hidden = set(payload["hiddenGeographyIds"])
        neutral = {"35700006", "36160025", "36500005", "37800035", "37800036", "37970036"}
        self.assertTrue({f"stat2022:{code}" for code in neutral} <= hidden)
        backdrop = json.loads((root / "geographies/statistical-area-backdrop-k26.geojson").read_text(encoding="utf-8"))
        self.assertTrue({f"stat2022:{code}" for code in neutral} <= {f.get("id") for f in backdrop["features"]})
        reviews = rows(ROOT / "data/manual/statistical_area_polling_group_display_reviews.csv")
        ballots = rows(ROOT / "public-data/v2/ballots/k26.csv")
        seen = set()
        for review in reviews:
            key = review["display_geography_id"]
            if not key.startswith(("display:reviewed-site-move:K26:", "display:reviewed-site-continuity:K26:")):
                continue
            record = display[key]
            scope = set(review["owned_stat_area_ids"].split("|"))
            kalpis = set(review["ambiguous_final_ballots"].split("|"))
            source = [r for r in ballots if r["source_locality_code"] == review["locality_code"]
                      and (r["source_kalpi"] in kalpis or r["stat_area_id"] in scope)]
            ballot_ids = {r["source_row_uid"] for r in source}
            self.assertFalse(seen & ballot_ids)
            self.assertTrue(scope <= hidden)
            self.assertFalse(scope & display.keys())
            self.assertEqual(record["totals"]["contributingRows"], len(source))
            self.assertEqual(record["totals"]["validVotes"], sum(int(r["valid_votes"]) for r in source))
            self.assertEqual(bool(record.get("notice")), review["review_status"] != "approved-exact-closed")
            seen.update(ballot_ids)

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
        reviews = rows(ROOT / "data/manual/statistical_area_polling_group_display_reviews.csv")
        for row in incomplete:
            self.assertNotEqual(row["review_status"], "approved-exact-closed")
            key = row["display_geography_id"]
            if key not in records:
                successors = [
                    review["display_geography_id"] for review in reviews
                    if review["election"] == row["election"]
                    and review["locality_code"] == row["locality_code"]
                    and set(row["owned_stat_area_ids"].split("|")) <= set(review["owned_stat_area_ids"].split("|"))
                    and set(row["ambiguous_final_ballots"].split("|")) <= set(review["ambiguous_final_ballots"].split("|"))
                ]
                self.assertEqual(len(successors), 1, key)
                key = successors[0]
            self.assertTrue(records[key].get("notice"))

    def test_east_jerusalem_review_displays_final_votes_once(self):
        payload = json.loads((ROOT / "web/app/public/data/v2/results/k26/statistical-areas.json").read_text(encoding="utf-8"))
        reviews = rows(ROOT / "data/manual/statistical_area_polling_group_display_reviews.csv")
        reviews = [row for row in reviews if row["ownership_policy"] == "reviewed_k26_missing_planned_area_partition"]
        self.assertEqual(len(reviews), 5)
        records = {row["id"]: row for row in payload["records"]}
        hidden = set(payload["hiddenGeographyIds"])
        ballots = [row for row in rows(ROOT / "public-data/v2/ballots/k26.csv") if row["source_locality_code"] == "3000"]
        seen_areas = set()
        seen_ballots = set()
        added_votes = 0
        for review in reviews:
            group = records[review["display_geography_id"]]
            self.assertTrue(group["notice"]["he"])
            self.assertTrue(group["notice"]["en"])
            areas = set(review["owned_stat_area_ids"].split("|"))
            final = set(review["ambiguous_final_ballots"].split("|"))
            self.assertFalse(seen_areas & areas)
            self.assertTrue(areas <= hidden)
            self.assertFalse(areas & records.keys())
            seen_areas.update(areas)
            members = [row for row in ballots if row["source_kalpi"] in final or row["stat_area_id"] in areas]
            keys = {row["source_row_uid"] for row in members}
            self.assertFalse(seen_ballots & keys)
            seen_ballots.update(keys)
            self.assertEqual(group["totals"]["contributingRows"], len(members))
            self.assertEqual(group["totals"]["validVotes"], sum(int(row["valid_votes"]) for row in members))
            for party, votes in group["partyVotes"].items():
                self.assertEqual(votes, sum(int(row[party]) for row in members))
            added_votes += sum(int(row["valid_votes"]) for row in members if row["source_kalpi"] in final)
        self.assertEqual((len(seen_areas), len(seen_ballots), added_votes), (36, 32, 9970))

    def test_reviewed_east_jerusalem_capacity_uses_verified_final_ballots(self):
        audit = rows(ROOT / "data/processed/audits/display_contributor_capacity_audit.csv")
        row = next(row for row in audit if row["display_geography_id"] == "display:polling-partition:K26:3000:reviewed-east:611")
        self.assertEqual(int(row["ambiguous_final_eligible_voters"]), 6145)
        self.assertEqual(int(row["preserved_direct_eligible_voters"]), 2437)
        self.assertEqual(int(row["election_capacity"]), 8582)
        self.assertFalse(row["flag_reason"])


if __name__ == "__main__":
    unittest.main()
